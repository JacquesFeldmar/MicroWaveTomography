"""EXPORT GERBER -- des geometries simulees aux fichiers que PCBWay attend.

    python export_gerber.py --antenne vivaldi_tomographie
    python export_gerber.py --panneau losanges
    python export_gerber.py --tout

Regle du projet : les cotes n'existent qu'a UN endroit, le `geometrie.py` de
l'antenne. Cet outil leur demande leurs contours a plat et ecrit directement
le jeu Gerber RS-274X plus le fichier de percage, zippe, sans passer par
KiCad. L'etape manuelle qu'imposait `export_dxf.py` etait le seul endroit du
projet ou les cotes pouvaient diverger de celles qui ont ete simulees.

CE QUI EST PRODUIT, et pourquoi ce jeu-la
-----------------------------------------
    .GTL .GBL   les deux cuivres
    .GTS .GBS   ouvertures de vernis sur TOUTE la carte (commande None)
    .GKO        contour de decoupe, fraisages interieurs compris
    -NPTH.DRL   percages mecaniques non metallises
    -PTH.DRL    vias de l'empreinte SMA, metallises
    lisez_moi   les options a cocher sur le formulaire PCBWay

Les ouvertures de vernis recouvrent toute l'enveloppe de carte. La commande
doit demander explicitement Solder mask: None, sans resine sur le cuivre ni
dans les fentes. Aucun effet RF du vernis ou de la finition n'est suppose nul.

GERBER, en deux lignes. Un fichier par couche. `G36*`/`G37*` encadre un
polygone PLEIN ; en dehors, les coordonnees tracent un trait de la largeur de
l'ouverture courante. Les coordonnees sont en micrometres de millimetre
(format 4.6), ce que declarent les entetes `%FSLAX46Y46*%` et `%MOMM*%`.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile

import numpy as np

import fdtd as F

# ---------------------------------------------------------------- Gerber
ENTETE = """G04 {titre}*
%TF.GenerationSoftware,MicroWaveTomography,export_gerber.py,1.0*%
%TF.FileFunction,{fonction}*%
%TF.Part,{part}*%
%FSLAX46Y46*%
%MOMM*%
%LPD*%
%ADD10C,{diametre:.6f}*%
D10*
G01*"""


def _xy(x, y):
    return f"X{int(round(x * 1e6))}Y{int(round(y * 1e6))}"


def ecrit_gerber(chemin, titre, fonction, pleins=(), traits=(),
                 diametre=0.100, part="Single"):
    """Un fichier RS-274X : des polygones pleins, puis des traits.

    `part` est l'attribut X2 qui dit au fabricant si le fichier decrit UNE
    carte ou un PANNEAU de plusieurs. Un panneau annonce comme une carte
    simple, c'est un contour interieur qu'il prendra pour une erreur.
    """
    mor = [ENTETE.format(titre=titre, fonction=fonction, diametre=diametre,
                         part=part)]
    for poly in pleins:
        pts = [tuple(p) for p in poly]
        mor.append("G36*")
        mor.append(_xy(*pts[0]) + "D02*")
        for p in pts[1:]:
            mor.append(_xy(*p) + "D01*")
        mor.append(_xy(*pts[0]) + "D01*")
        mor.append("G37*")
    for poly in traits:
        pts = [tuple(p) for p in poly]
        mor.append(_xy(*pts[0]) + "D02*")
        for p in pts[1:]:
            mor.append(_xy(*p) + "D01*")
    mor.append("M02*")
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(mor) + "\n")
    return chemin


def ecrit_excellon(chemin, trous, titre="", metallise=False):
    """Percages, en millimetres a point decimal explicite.

    Le point decimal evite toute discussion sur la suppression des zeros,
    qui est la faute classique de ce format -- et elle se paie en trous au
    centieme de millimetre de leur place.
    """
    diametres = sorted({round(d, 3) for _, _, d in trous})
    mor = ["M48", f";{titre}", ";TYPE=" + ("PLATED" if metallise else "NON_PLATED"),
           ";FORMAT={3:3 / absolute / metric / decimal}",
           "FMAT,2", "METRIC,TZ", "G90", "G05"]
    for i, d in enumerate(diametres, start=1):
        mor.append(f"T{i}C{d:.3f}")
    mor += ["%"]
    for i, d in enumerate(diametres, start=1):
        mor.append(f"T{i}")
        for x, y, dd in trous:
            if abs(round(dd, 3) - d) < 1e-9:
                mor.append(f"X{x:.3f}Y{y:.3f}")
    mor += ["T0", "M30"]
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(mor) + "\n")
    return chemin


# ---------------------------------------------------------------- notice
# These are procurement values, not measured broadband FR4 properties.
FABRICATION_DEFAUT = dict(
    material="FR-4 Shengyi S1000H, TG150 (pas de substitution sans accord)",
    material_datasheet="https://www.pcbway.com/img/images/product/TDS-S1000H-S1000HB.pdf",
    material_reference_epsilon_r=4.6,
    material_reference_tan_delta=0.011,
    material_reference_frequency_hz=1.0e9,
    surface_finish="ENIG",
    copper_weight="1 oz (35 um nominal)",
    solder_mask="None",
    silkscreen="None",
    quantity=5,
)


def options_fabrication(carte, options=None):
    """Merge explicit card/command metadata; no hidden RF claim in the notice."""
    choix = dict(FABRICATION_DEFAUT)
    choix.update(carte.get("fabrication", {}))
    choix.update(options or {})
    if choix["solder_mask"] != "None":
        raise ValueError("Ce contrat export exige Solder mask: None.")
    return choix


def notice_fabrication(carte, fichiers, options=None):
    o = options_fabrication(carte, options)
    largeur, hauteur = etendue(carte)
    panneau = carte.get("nombre_designs", 2 if carte.get("panneau") else 1)
    trous = carte["trous"]
    vias = carte.get("vias", [])
    return f"""Commande PCBWay -- {carte['nom']}

{carte['description']}

A COCHER SUR LE FORMULAIRE
--------------------------
Board Type .................. {'Panel by customer' if panneau > 1 else 'Single pieces'}
Different Design ............ {panneau}
Size ........................ {largeur:.3f} x {hauteur:.3f} mm
Quantity .................... {o['quantity']}
Layers ...................... 2
Material .................... {o['material']}
Thickness ................... {carte['epaisseur']:.3f} mm
Copper weight ............... {o['copper_weight']}
Surface finish .............. {o['surface_finish']}
Solder mask ................. None, aucune resine sur aucune face
Silkscreen .................. {o['silkscreen']}
Min track/spacing ........... 6/6 mil (detail source: {carte['detail']:.3f} mm)
Min hole size ............... {min((d for _, _, d in trous + vias), default=0):.3f} mm
Edge connector / gold fingers / castellated holes ... No
Remove product No. .......... Yes, aucune marque ajoutee sur les antennes

CONTRAT DE FABRICATION ET DE COMPARAISON
---------------------------------------
Les dimensions de carte sont celles de la LIGNE MEDIANE du contour GKO.
La largeur du trait de contour (0,100 mm) ne s'ajoute pas a ces dimensions.
Les GTS/GBS ouvrent le vernis sur toute la carte; demander aussi explicitement
None au fabricant. Aucun vernis ne doit rester dans les fentes ou sur le FR4.
NPTH : {len(trous)} trous mecaniques, TYPE=NON_PLATED, fichier -NPTH.DRL.
PTH : {len(vias)} vias metallises, TYPE=PLATED, fichier -PTH.DRL.
Le panneau comporte {panneau} conception(s), a declarer comme telles.
La quantite de l'article panneau se compte en PANNEAUX complets.
Les diametres PTH sont FINIS apres metallisation; les vias restent ouverts.
Pas de remplissage, bouchage, tenting ou resine dans les vias.
Le cuivre rejoint volontairement le bord UNIQUEMENT a l'alimentation SMA.
Ne pas reculer ce cuivre ni ajouter chanfrein, dorure dure ou metallisation
de tranche sous pretexte de l'option "Edge connector" : elle est No.

Fiche matiere : {o['material_datasheet']}
Valeurs de reference du choix de matiere : epsilon_r = {o['material_reference_epsilon_r']},
tan(delta) = {o['material_reference_tan_delta']} a {o['material_reference_frequency_hz']/1e9:g} GHz.
Ces valeurs ne sont pas des mesures du lot livre ni une caracterisation
large bande. Conserver reference et lot, epaisseur livree, tolerance de gravure,
epaisseur de cuivre et empilage ENIG pour confronter mesures et simulation.
Le modele utilise h={carte['epaisseur']:.3f} mm de DIELECTRIQUE. Faire preciser
l'epaisseur dielectrique et l'epaisseur finie cuivre/finition inclus separement.
La valeur nominale du formulaire ne remplace pas ces dimensions du lot.
Le port ideal de simulation ne caracterise pas le connecteur SMA ni sa soudure.
La calibration VNA doit avoir son plan de reference et ses fichiers conserves.

CONNECTEUR ET SEPARATION
------------------------
SMA femelle bord de carte : Cinch/Johnson 142-0701-851, non RP-SMA.
L'empreinte est DEJA dans les Gerbers : signal dessus, deux pattes de masse
dessus reliees au plan de masse dessous par deux vias PTH par antenne.
Le pad signal mesure 2,286 x 5,080 mm avant adaptation vers la ligne.
{carte.get('feed', '')}
Le connecteur, sa reference et la position de soudure font partie du montage
experimental. Aucune equivalence exacte avec un port ideal n'est supposee.
Les connecteurs ne sont pas inclus dans cette commande de PCB nus.
Les anciennes courbes de la revision sans cette implantation ne qualifient
pas la revision presente. Se reporter au bilan de campagne qui accompagne
la livraison pour le statut et les limites de qualification numerique.

CONTROLE AVANT COMMANDE
-----------------------
{carte['controles']}
Verifier le contour et les deux faces dans le visualiseur du fabricant.
Ne pas ajouter ni modifier de cuivre, trou ou contour lors de la revue CAM.

FICHIERS
--------
""" + "\n".join("  " + Path(f).name for f in fichiers) + "\n"


# ---------------------------------------------------------------- cartes
def contrat_antenne(ant):
    """Physical assumptions recorded from the same module used by the solver."""
    contrat = dict(antenne=ant.NOM, epaisseur_substrat_mm=float(ant.cotes().get("h", 1.6)),
                   cuivre="PEC ideal; finition et rugosite non modelisees")
    if hasattr(ant, "EPS_R"):
        contrat["materiau"] = dict(
            modele=getattr(ant, "MODELE_MATERIAU", "constant"),
            epsilon_reference=float(ant.EPS_R),
            tan_delta_reference=float(ant.TAN_DELTA),
            frequence_reference_hz=float(getattr(ant, "F_REFERENCE_HZ", 1e9)))
        if contrat["materiau"]["modele"] == "debye":
            from materiaux import modele_debye
            contrat["materiau"]["definition"] = modele_debye(
                ant.EPS_R, ant.TAN_DELTA, getattr(ant, "F_REFERENCE_HZ", 1e9)).dictionnaire()
    if getattr(ant, "AVEC_SMA", False):
        from connectique import manifeste
        contrat["connecteur"] = manifeste()
    return contrat


def _translate(polys, dx, dy):
    return [[(float(x) + dx, float(y) + dy) for x, y in poly] for poly in polys]


def carte_antenne(nom):
    """Une antenne seule, telle que son `geometrie.py` la decrit."""
    ant = F.charge_antenne(nom)
    if not hasattr(ant, "contours_mm"):
        raise SystemExit(f"{nom} n'expose pas contours_mm().")
    c = ant.contours_mm()
    d = ant.cotes()
    controles = getattr(ant, "controles_fabrication", lambda: "")()
    detail = getattr(ant, "detail_mini_mm", lambda: float("nan"))()
    if getattr(ant, "AVEC_SMA", False):
        from connectique import VIA_DIAMETRE_MM
        detail = min(detail, VIA_DIAMETRE_MM)  # neck to the ground via
    return dict(
        nom=ant.NOM, description=ant.DESCRIPTION,
        epaisseur=d.get("h", 1.6),
        F_Cu=c["F_Cu"], B_Cu=c["B_Cu"], Edge_Cuts=c["Edge_Cuts"],
        trous=list(getattr(ant, "percages_mm", lambda: [])()),
        vias=list(getattr(ant, "vias_mm", lambda: [])()),
        simulation_contract=contrat_antenne(ant),
        controles=controles, panneau="", feed="",
        detail=detail)


# --------------------------------------------------- le panneau des losanges
GAP = 3.0               # mm, largeur du fraisage entre les deux cartes
PONTETS = ((10.0, 13.0), (27.0, 30.0))      # en y, le long du fraisage
TROU_PONTET = 0.6       # mm, amorces de rupture
PAS_PONTET = 0.9        # mm


def carte_panneau_losanges():
    """Les deux losanges sur un panneau, relies par deux pontets secables.

    Le panneau porte DEUX conceptions, declarees comme telles a PCBWay.
    Pourquoi des pontets et pas un trait de scie : la rupture doit
    tomber loin du cuivre, et sur une tranche franche -- scier du FR4 a cote
    d'un bord rayonnant abime justement ce que la simulation suppose net.

    Pourquoi pas de rainurage en V : les deux cartes n'ont pas la meme
    hauteur, et une rainure doit traverser le panneau de bord a bord.

    Les deux bords d'alimentation sont tous deux sur le bord EXTERIEUR du
    panneau, en y = 0 : ce sont eux qui recoivent le SMA, ils doivent sortir
    fraises net et non casses.
    """
    petit = F.charge_antenne("diamant_uwb")
    grand = F.charge_antenne("diamant_uwb_x18")
    cp, cg = petit.contours_mm(), grand.contours_mm()
    dp, dg = petit.cotes(), grand.cotes()
    if not np.isclose(dp["h"], dg["h"], rtol=0, atol=1e-9):
        raise ValueError("Les deux antennes d'un panneau doivent partager la meme epaisseur.")
    for attribut in ("EPS_R", "TAN_DELTA", "F_REFERENCE_HZ", "MODELE_MATERIAU"):
        if getattr(petit, attribut, None) != getattr(grand, attribut, None):
            raise ValueError("Materiaux incompatibles sur un meme panneau : " + attribut)

    lp, hp = dp["carte_l"], dp["carte_w"]           # 32 x 40
    lg, hg = dg["carte_l"], dg["carte_w"]           # 57,6 x 72
    x_gauche = lp + GAP                              # bord gauche du grand
    larg = x_gauche + lg

    # Les contours des antennes sont centres ; on les pose sur le panneau.
    tp = (lp / 2, hp / 2)
    tg = (x_gauche + lg / 2, hg / 2)
    f_cu = _translate(cp["F_Cu"], *tp) + _translate(cg["F_Cu"], *tg)
    b_cu = _translate(cp["B_Cu"], *tp) + _translate(cg["B_Cu"], *tg)

    # Contour exterieur : le L des deux cartes, entaille aux deux bouts du
    # fraisage. Entre les deux entailles, la matiere reste : c'est elle que
    # le fraisage interieur viendra reduire aux deux pontets.
    y0, y1 = PONTETS[0][0], PONTETS[-1][1]
    exterieur = [(0.0, 0.0), (lp, 0.0), (lp, y0), (x_gauche, y0),
                 (x_gauche, 0.0), (larg, 0.0), (larg, hg),
                 (x_gauche, hg), (x_gauche, y1), (lp, y1),
                 (lp, hp), (0.0, hp)]
    # Fraisage interieur : la fente entre les deux pontets.
    interieur = [(lp, PONTETS[0][1]), (x_gauche, PONTETS[0][1]),
                 (x_gauche, PONTETS[1][0]), (lp, PONTETS[1][0])]

    trous = []
    vias = []
    for ant, (dx, dy) in ((petit, tp), (grand, tg)):
        vias.extend((x + dx, y + dy, diam) for x, y, diam in
                    getattr(ant, "vias_mm", lambda: [])())
    for a, b in PONTETS:
        n = max(2, int(round((b - a) / PAS_PONTET)) + 1)
        for y in np.linspace(a, b, n):
            trous.append((lp, float(y), TROU_PONTET))
            trous.append((x_gauche, float(y), TROU_PONTET))

    return dict(
        nom="panneau_losanges",
        description=("panneau de deux monopoles en losange derives de la conception "
                     "publiee (32 x 40 mm et echelle 1,8 : 57,6 x 72 mm), "
                     "avec interface SMA commune, relies par deux pontets secables"),
        epaisseur=dp["h"],
        F_Cu=f_cu, B_Cu=b_cu,
        Edge_Cuts=[exterieur, interieur], trous=trous, vias=vias,
        simulation_contract=dict(
            antennes=[contrat_antenne(petit), contrat_antenne(grand)],
            transformations_mm={petit.NOM: list(tp), grand.NOM: list(tg)},
            comparaison="antennes separees, pontets arases au contour nominal avant mesure"),
        detail=min(carte_antenne(petit.NOM)["detail"], carte_antenne(grand.NOM)["detail"]),
        panneau="Panel by customer", nombre_designs=2,
        feed=("\nLes DEUX bords d'alimentation sont en bas du panneau, sur le "
              "bord\nexterieur : ils sortent fraises, pas casses. Les deux "
              "pontets sont sur\nle cote, perces d'amorces de rupture. Avant "
              "mesure, araser les pontets au contour nominal de chaque antenne."),
        controles=(f"   - encombrement du panneau : {larg:.2f} x {hg:.2f} mm\n"
                   f"   - petit losange : {lp:.2f} x {hp:.2f} mm\n"
                   f"   - grand losange : {lg:.2f} x {hg:.2f} mm\n"
                   f"   - fraisage de separation : {GAP:.2f} mm de large\n"
                   f"   - deux pontets de {PONTETS[0][1]-PONTETS[0][0]:.1f} mm"
                   f", perces a {TROU_PONTET:.1f} mm"))


# ---------------------------------------------------------------- jeu complet
COUCHES = (
    ("GTL", "F_Cu", "Copper,L1,Top", "cuivre superieur", 0.100),
    ("GBL", "B_Cu", "Copper,L2,Bot", "cuivre inferieur", 0.100),
    ("GTS", "Mask_Open", "Soldermask,Top", "ouverture integrale vernis dessus", 0.100),
    ("GBS", "Mask_Open", "Soldermask,Bot", "ouverture integrale vernis dessous", 0.100),
)


def ecrit_jeu(carte, dossier):
    base = os.path.join(dossier, carte["nom"])
    os.makedirs(dossier, exist_ok=True)
    ecrits = []
    part = "Array" if carte.get("panneau") else "Single"
    carte = dict(carte)
    # Positive soldermask artwork denotes openings. The entire rectangular
    # envelope is open, including all gaps and slots of a customer panel.
    pts = np.asarray([p for poly in carte["Edge_Cuts"] for p in poly], dtype=float)
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    carte["Mask_Open"] = [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
    for ext, cle, fonction, titre, diam in COUCHES:
        ecrits.append(ecrit_gerber(f"{base}.{ext}", titre, fonction,
                                   pleins=carte[cle], diametre=diam,
                                   part=part))
    ecrits.append(ecrit_gerber(
        f"{base}.GKO", "contour de decoupe", "Profile,NP",
        traits=[list(p) + [p[0]] for p in carte["Edge_Cuts"]],
        diametre=0.100, part=part))
    if carte["trous"]:
        # File name AND explicit TYPE metadata identify the plating state.
        ecrits.append(ecrit_excellon(f"{base}-NPTH.DRL", carte["trous"],
                                     f"{carte['nom']} -- tous non metallises"))
    if carte.get("vias"):
        ecrits.append(ecrit_excellon(f"{base}-PTH.DRL", carte["vias"],
                                     f"{carte['nom']} -- vias metallises", metallise=True))
    return ecrits


def etendue(carte):
    pts = np.array([p for cle in ("F_Cu", "B_Cu", "Edge_Cuts")
                    for poly in carte[cle] for p in poly], dtype=float)
    return (pts[:, 0].max() - pts[:, 0].min(),
            pts[:, 1].max() - pts[:, 1].min())


def geometrie_canonique(carte):
    """Coordinates actually exported, in mm; independent of labels and paths."""
    return dict(nom=carte["nom"], epaisseur_mm=float(carte["epaisseur"]),
                **{k: [[[float(x), float(y)] for x, y in poly]
                       for poly in carte[k]] for k in ("F_Cu", "B_Cu", "Edge_Cuts")},
                trous_npth_mm=[[float(v) for v in trou] for trou in carte["trous"]],
                vias_pth_mm=[[float(v) for v in trou] for trou in carte.get("vias", [])])


def json_octets(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256_fichier(chemin):
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def sources_carte(carte):
    noms = (["diamant_uwb", "diamant_uwb_x18"]
            if carte["nom"] == "panneau_losanges" else [carte["nom"]])
    racine = Path(__file__).resolve().parent
    chemins = [Path("export_gerber.py"), Path("connectique.py"), Path("materiaux.py")]
    if "diamant_uwb_x18" in noms and "diamant_uwb" not in noms:
        noms.append("diamant_uwb")
    for nom in noms:
        chemins.append(Path("antennes") / nom / "geometrie.py")
    return {p.as_posix(): sha256_fichier(racine / p) for p in chemins
            if (racine / p).is_file()}


def exporte(carte, dossier, options=None):
    """Reproducible ZIP, payload hashes inside; ZIP hash in a sidecar file."""
    dossier = Path(dossier)
    ecrits = ecrit_jeu(carte, str(dossier))
    notice = dossier / (carte["nom"] + "_lisez_moi.txt")
    notice.write_bytes(notice_fabrication(carte, ecrits, options).encode("utf-8"))
    ecrits.append(str(notice))
    geom = geometrie_canonique(carte)
    manifeste = dict(
        schema="MicroWaveTomography-fabrication-v2", produit=carte["nom"],
        convention_contour="ligne_mediane_GKO_mm",
        geometrie=geom,
        geometrie_sha256=hashlib.sha256(json_octets(geom)).hexdigest(),
        sources_sha256=sources_carte(carte),
        fabrication=options_fabrication(carte, options),
        simulation_contract=carte.get("simulation_contract", {}),
        payload_sha256={Path(f).name: sha256_fichier(f) for f in ecrits})
    chemin_manifeste = dossier / (carte["nom"] + "_manifest.json")
    chemin_manifeste.write_bytes(json_octets(manifeste))
    ecrits.append(str(chemin_manifeste))
    zip_chemin = dossier / (carte["nom"] + "_pcbway.zip")
    with zipfile.ZipFile(zip_chemin, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for chemin in sorted(ecrits, key=lambda f: Path(f).name):
            info = zipfile.ZipInfo(Path(chemin).name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, Path(chemin).read_bytes(), compresslevel=9)
    zip_chemin.with_suffix(".zip.sha256").write_bytes(
        f"{sha256_fichier(zip_chemin)}  {zip_chemin.name}\n".encode("ascii"))
    larg, haut = etendue(carte)
    print(f"  {carte['nom']} : {larg:.3f} x {haut:.3f} mm; "
          f"{len(carte['trous'])} NPTH + {len(carte.get('vias', []))} PTH -> {zip_chemin}")
    return str(zip_chemin)


def principal():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--antenne", default=None)
    p.add_argument("--panneau", default=None, choices=["losanges"])
    p.add_argument("--tout", action="store_true")
    p.add_argument("--sortie", default=None)
    p.add_argument("--contrat-json", default=None,
                   help="JSON optionnel : fabrication et simulation_contract")
    args = p.parse_args()

    travaux = []
    if args.tout or args.panneau == "losanges":
        travaux.append((carte_panneau_losanges(),
                        args.sortie or os.path.join("fabrication",
                                                    "panneau_losanges")))
    if args.tout:
        travaux.append((carte_antenne("vivaldi_tomographie"),
                        args.sortie or os.path.join("fabrication",
                                                    "vivaldi_tomographie")))
    elif args.antenne:
        travaux.append((carte_antenne(args.antenne),
                        args.sortie or os.path.join("fabrication",
                                                    args.antenne)))
    if not travaux:
        p.error("choisir --antenne, --panneau losanges, ou --tout")
    for carte, dossier in travaux:
        if args.contrat_json:
            contrat = json.loads(Path(args.contrat_json).read_text(encoding="utf-8"))
            carte["fabrication"] = contrat.get("fabrication", carte.get("fabrication", {}))
            carte["simulation_contract"] = contrat.get("simulation_contract", carte.get("simulation_contract", {}))
        exporte(carte, dossier)


if __name__ == "__main__":
    principal()
