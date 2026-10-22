"""Relire les ZIP PCBWay avec gerbonara et comparer les GEOMETRIES completes.

    python verifie_gerber.py fabrication/.../..._pcbway.zip

La source Python courante est la reference independante du contenu du ZIP.
Le contour est compare sur sa ligne mediane (la largeur du trait est ignoree).
La metallisation a trois etats : True, False, None; None est un echec.
Un JSON de controles et de vrais SVG/PNG issus du lecteur tiers sont produits.
Ce controle de transfert ne demontre aucune performance electromagnetique.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile

import numpy as np

import export_gerber as G

COUCHES = {
    "GTL": (("top", "copper"), ("Copper", "L1", "Top"), "F_Cu"),
    "GBL": (("bottom", "copper"), ("Copper", "L2", "Bot"), "B_Cu"),
    "GTS": (("top", "mask"), ("Soldermask", "Top"), "Mask_Open"),
    "GBS": (("bottom", "mask"), ("Soldermask", "Bot"), "Mask_Open"),
    "GKO": (("mechanical", "outline"), ("Profile", "NP"), "Edge_Cuts"),
}
TOL_COORD_MM = 0.002


def _archive_sure(chemin, dossier):
    """Flat regular files only; no traversal, drive name, alias, or symlink."""
    with zipfile.ZipFile(chemin) as z:
        infos = z.infolist()
        if len(infos) > 30 or sum(i.file_size for i in infos) > 100_000_000:
            raise ValueError("archive excessive")
        vus = set()
        for i in infos:
            nom = i.filename
            mode = i.external_attr >> 16
            if (not nom or "\\" in nom or ":" in nom or
                    PurePosixPath(nom).name != nom or nom in (".", "..") or
                    not re.fullmatch(r"[A-Za-z0-9_.-]+", nom) or nom.endswith(".") or
                    nom.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(
                        f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10))} or
                    nom.casefold() in vus or i.is_dir() or
                    stat.S_ISLNK(mode) or i.file_size > 20_000_000):
                raise ValueError(f"membre ZIP interdit : {nom!r}")
            vus.add(nom.casefold())
        if z.testzip() is not None:
            raise ValueError("CRC ZIP invalide")
        for i in infos:
            (Path(dossier) / i.filename).write_bytes(z.read(i))
    return [i.filename for i in infos]


def _polygones(polys):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    objets = []
    for p in polys:
        forme = Polygon(p)
        if not forme.is_valid or forme.area <= 0:
            raise ValueError("polygone source ou Gerber invalide")
        objets.append(forme)
    return unary_union(objets)


def _regions_lues(couche):
    from gerbonara.graphic_objects import Region
    from gerbonara.utils import MM
    from shapely.geometry import GeometryCollection
    resultat = GeometryCollection()
    for objet in couche.objects:
        if not isinstance(objet, Region) or any(objet.arc_centers):
            raise ValueError("primitive inattendue : seules les regions lineaires sont exportees")
        # Region is not a dataclass in gerbonara 1.6.3; its inherited
        # converted() fails. Convert coordinates through the unit API.
        points = [(objet.unit.convert_to(MM, x), objet.unit.convert_to(MM, y))
                  for x, y in objet.outline]
        forme = _polygones([points])
        resultat = (resultat.union(forme) if objet.polarity_dark else
                    resultat.difference(forme))
    return resultat


def _centre_contour(couche):
    from gerbonara.graphic_objects import Line
    from gerbonara.utils import MM
    from shapely.geometry import LineString
    from shapely.ops import polygonize_full, unary_union
    lignes = []
    for objet in couche.objects:
        if not isinstance(objet, Line) or not objet.polarity_dark:
            raise ValueError("contour : primitive autre qu'un segment positif")
        o = objet.converted(MM)
        lignes.append(LineString([(o.x1, o.y1), (o.x2, o.y2)]))
    centre = unary_union(lignes)
    polygones, coupures, pendantes, invalides = polygonize_full(centre)
    if (centre.is_empty or not coupures.is_empty or not pendantes.is_empty or
            not invalides.is_empty or polygones.is_empty):
        raise ValueError("contour ouvert, pendant, vide ou invalide")
    return centre


def _compare_surface(lue, attendue):
    if lue.is_empty or attendue.is_empty:
        return False, dict(erreur="surface vide")
    ecart = lue.symmetric_difference(attendue).area
    limite = max(0.002, attendue.length * 0.000002)
    hausdorff = lue.boundary.hausdorff_distance(attendue.boundary)
    return (ecart <= limite and hausdorff <= TOL_COORD_MM), dict(
        surface_relue_mm2=lue.area, surface_attendue_mm2=attendue.area,
        difference_symetrique_mm2=ecart, tolerance_surface_mm2=limite,
        distance_contours_mm=hausdorff)


def _controle_geometrie(couches, forages, attendu, ajoute):
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    pts = np.asarray([p for poly in attendu["Edge_Cuts"] for p in poly], dtype=float)
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    reference = dict(attendu, Mask_Open=[[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]])
    for ext, (_, _, cle) in COUCHES.items():
        try:
            if ext == "GKO":
                lu = _centre_contour(couches[ext])
                ref = unary_union([LineString(list(p) + [p[0]]) for p in reference[cle]])
                ecart = lu.hausdorff_distance(ref)
                longueur = abs(lu.length - ref.length)
                ajoute("geometrie_GKO", ecart <= TOL_COORD_MM and longueur <= 0.01,
                       distance_ligne_mediane_mm=ecart, difference_longueur_mm=longueur,
                       dimensions_ligne_mediane_mm=[x1-x0, y1-y0])
            else:
                ok, detail = _compare_surface(_regions_lues(couches[ext]),
                                               _polygones(reference[cle]))
                ajoute("geometrie_" + ext, ok, **detail)
        except (KeyError, ValueError) as e:
            ajoute("geometrie_" + ext, False, erreur=str(e))
    for type_trou, cle in (("NPTH", "trous"), ("PTH", "vias")):
        lus = []
        forage = forages.get(type_trou)
        for objet in (forage.objects if forage is not None else []):
            from gerbonara.graphic_objects import Flash
            from gerbonara.utils import MM
            if not isinstance(objet, Flash):
                ajoute("percages_primitives_" + type_trou, False, erreur="fraisage Excellon inattendu")
                continue
            o = objet.converted(MM)
            lus.append((o.x, o.y, o.tool.diameter, o.plated))
        refs = sorted(tuple(t) for t in attendu.get(cle, []))
        lus.sort(key=lambda t: t[:3])
        concorde = len(lus) == len(refs)
        if concorde:
            concorde = all(np.allclose(lu[:3], ref, atol=TOL_COORD_MM, rtol=0)
                           and lu[3] is (type_trou == "PTH") for lu, ref in zip(lus, refs))
        ajoute("percages_" + type_trou, concorde, attendus=len(refs), relus=[dict(
            x_mm=x, y_mm=y, diametre_mm=d,
            metallisation=("PTH" if p is True else "NPTH" if p is False else "INCONNUE"))
            for x, y, d, p in lus])


def _rendus(pile, couches, dossier, nom, ajoute):
    """SVG from gerbonara -> actual resvg rasterization -> nonblank PNG check."""
    import resvg_py
    from PIL import Image
    couleurs = {f"{s} {u}": "#222222" for s, u in pile.graphic_layers}
    couleurs.update({"top copper": "#bd3a27", "bottom copper": "#2069b2",
                     "top mask": None, "bottom mask": None,
                     "drill pth": "#111111", "drill npth": "#111111",
                     "outline": "#000000"})
    vues = {ext: str(c.to_svg(fg="#202020", bg="white", margin=1))
            for ext, c in couches.items()}
    vues["superposition"] = str(pile.to_svg(colors=couleurs, margin=1))
    vues["dessus"] = str(pile.to_pretty_svg(side="top", margin=1))
    vues["dessous"] = str(pile.to_pretty_svg(side="bottom", margin=1))
    for vue, svg in vues.items():
        chemin = Path(dossier) / f"{nom}_{vue}"
        chemin.with_suffix(".svg").write_text(svg, encoding="utf-8")
        png = resvg_py.svg_to_bytes(svg_string=svg, width=1400, dpi=96)
        im = Image.open(io.BytesIO(png)).convert("RGBA")
        pixels = np.asarray(im)
        visibles = pixels[..., 3] > 0
        non_blancs = visibles & (pixels[..., :3].min(axis=2) < 240)
        bon = int(non_blancs.sum()) > 50 and bool(
            np.any(pixels != pixels[0, 0]))
        chemin.with_suffix(".png").write_bytes(png)
        ajoute("rendu_" + vue, bon, pixels_non_blancs=int(non_blancs.sum()),
               png=chemin.with_suffix(".png").name)


def verifie(chemin_zip, sortie=None, attendu=None, rendus=True, contrat=None):
    """Return (third-party LayerStack, bool), and persist a detailed JSON report."""
    from gerbonara import ExcellonFile, GerberFile, LayerStack
    chemin_zip = Path(chemin_zip)
    dossier = Path(sortie) if sortie else chemin_zip.parent / "verification"
    dossier.mkdir(parents=True, exist_ok=True)
    rapport = dict(archive=chemin_zip.name, sha256=G.sha256_fichier(chemin_zip),
                   convention_contour="ligne_mediane_GKO_mm", controles=[])

    def ajoute(nom, ok, **detail):
        rapport["controles"].append(dict(controle=nom, ok=bool(ok), **detail))
        print(f"    {'OK' if ok else 'ECHEC'} {nom}")

    pile = None
    try:
        with tempfile.TemporaryDirectory(prefix="mwt_gerber_") as temp:
            fichiers = _archive_sure(chemin_zip, temp)
            racine = Path(temp)
            manifests = [f for f in fichiers if f.endswith("_manifest.json")]
            if len(manifests) != 1:
                raise ValueError("un manifeste unique est obligatoire")
            manifeste = json.loads((racine / manifests[0]).read_text(encoding="utf-8"))
            nom = manifeste["produit"]
            if not re.fullmatch(r"[a-z0-9_]+", nom):
                raise ValueError("nom produit invalide")
            if attendu is None:
                if nom == "panneau_losanges":
                    attendu = G.carte_panneau_losanges()
                elif nom in ("vivaldi_tomographie", "diamant_uwb", "diamant_uwb_x18"):
                    attendu = G.carte_antenne(nom)
                else:
                    raise ValueError("produit non pris en charge")
            ajoute("produit", nom == attendu["nom"])
            if contrat:
                attendu = dict(attendu)
                attendu["fabrication"] = contrat.get("fabrication", attendu.get("fabrication", {}))
                attendu["simulation_contract"] = contrat.get("simulation_contract", attendu.get("simulation_contract", {}))
            ajoute("schema_convention", manifeste.get("schema") == "MicroWaveTomography-fabrication-v2"
                   and manifeste.get("convention_contour") == "ligne_mediane_GKO_mm")
            geo = G.geometrie_canonique(attendu)
            sha = hashlib.sha256(G.json_octets(geo)).hexdigest()
            ajoute("geometrie_source_manifeste", manifeste.get("geometrie") == geo
                   and manifeste.get("geometrie_sha256") == sha)
            ajoute("sources_sha256", manifeste.get("sources_sha256") == G.sources_carte(attendu))
            ajoute("contrat_simulation", G.json_octets(manifeste.get("simulation_contract", {})) ==
                   G.json_octets(attendu.get("simulation_contract", {})))
            ajoute("options_fabrication", manifeste.get("fabrication") == G.options_fabrication(attendu))
            payload = manifeste["payload_sha256"]
            requis = {f"{nom}.{ext}" for ext in COUCHES}
            requis.add(nom + "_lisez_moi.txt")
            if attendu["trous"]:
                requis.add(nom + "-NPTH.DRL")
            if attendu.get("vias"):
                requis.add(nom + "-PTH.DRL")
            ajoute("membres_exacts", set(fichiers) == requis | {manifests[0]}
                   and set(payload) == requis)
            for f in sorted(requis):
                ajoute("sha256_" + f, f in fichiers and
                       payload.get(f) == G.sha256_fichier(racine / f))
            ajoute("options_sans_vernis", manifeste.get("fabrication", {}).get("solder_mask") == "None")
            if chemin_zip.with_suffix(".zip.sha256").exists():
                ajoute("sha256_zip", chemin_zip.with_suffix(".zip.sha256").read_text(
                    encoding="ascii").split()[0] == rapport["sha256"])
            couches = {}
            for ext, (cle, fonction, _) in COUCHES.items():
                f = racine / f"{nom}.{ext}"
                if not f.is_file():
                    ajoute("couche_" + ext, False, erreur="absente")
                    continue
                couche = couches[ext] = GerberFile.open(f)
                ajoute("couche_" + ext, tuple(couche.file_attrs.get(".FileFunction", ())) == fonction
                       and tuple(couche.file_attrs.get(".Part", ())) ==
                       (("Array",) if attendu.get("panneau") else ("Single",)))
            forages = {}
            for type_trou, cle in (("NPTH", "trous"), ("PTH", "vias")):
                fichier_forage = racine / f"{nom}-{type_trou}.DRL"
                if attendu.get(cle) and fichier_forage.is_file():
                    forages[type_trou] = ExcellonFile.open(fichier_forage)
                    declaration = ";TYPE=" + ("PLATED" if type_trou == "PTH" else "NON_PLATED")
                    ajoute("declaration_" + type_trou, declaration in fichier_forage.read_text(encoding="ascii"))
            pile = LayerStack(graphic_layers={COUCHES[e][0]: c for e, c in couches.items()},
                              drill_npth=forages.get("NPTH"), drill_pth=forages.get("PTH"), board_name=nom)
            _controle_geometrie(couches, forages, attendu, ajoute)
            if rendus and len(couches) == len(COUCHES):
                _rendus(pile, couches, dossier, nom, ajoute)
    except Exception as e:
        ajoute("lecture_verification", False, erreur=f"{type(e).__name__}: {e}")
    bon = bool(rapport["controles"]) and all(c["ok"] for c in rapport["controles"])
    rapport["ok"] = bon
    chemin_rapport = dossier / (chemin_zip.stem + "_verification.json")
    chemin_rapport.write_bytes(G.json_octets(rapport))
    print(f"  {'VALIDE' if bon else 'INVALIDE'} : {chemin_zip}\n  Rapport : {chemin_rapport}")
    return pile, bon


def compare(pile, attendu):
    """Legacy API rejects insufficient width/height-only references."""
    raise ValueError("Utiliser verifie(zip, attendu=carte) : une boite englobante ne qualifie pas les polygones.")


def principal():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archives", nargs="+")
    p.add_argument("--sortie")
    p.add_argument("--sans-rendus", action="store_true")
    p.add_argument("--contrat-json")
    args = p.parse_args()
    contrat = json.loads(Path(args.contrat_json).read_text(encoding="utf-8")) if args.contrat_json else None
    bons = [verifie(z, args.sortie, rendus=not args.sans_rendus, contrat=contrat)[1] for z in args.archives]
    raise SystemExit(0 if all(bons) else 1)


if __name__ == "__main__":
    principal()
