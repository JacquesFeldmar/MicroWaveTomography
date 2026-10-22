"""Regression tests for fabrication transfer, including deliberately bad ZIPs."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

import pytest

import apercu
import export_gerber as G
import verifie_gerber as V


@pytest.fixture
def specimen():
    return dict(nom="specimen", description="specimen de controle", epaisseur=1.6,
                F_Cu=[[(1, 1), (9, 1), (9, 9), (1, 9)]],
                B_Cu=[[(0, 0), (10, 0), (10, 10), (0, 10)]],
                Edge_Cuts=[[(0, 0), (10, 0), (10, 10), (0, 10)]],
                trous=[(0.5, 5, 0.3)], vias=[(5, 5, 0.4572)],
                detail=0.3, controles="10 x 10 mm", panneau="", feed="")


def modifie_zip(source, destination, transforme):
    """Recompute payload hashes so a geometry failure is not a CRC/hash failure."""
    with zipfile.ZipFile(source) as z:
        fichiers = {n: z.read(n) for n in z.namelist()}
    transforme(fichiers)
    nom = next(n for n in fichiers if n.endswith("_manifest.json"))
    m = json.loads(fichiers[nom])
    m["payload_sha256"] = {n: hashlib.sha256(b).hexdigest()
                           for n, b in fichiers.items() if n != nom}
    fichiers[nom] = G.json_octets(m)
    with zipfile.ZipFile(destination, "w") as z:
        for n, b in fichiers.items():
            z.writestr(n, b)
    return destination


def controle(zip_path, tmp_path, specimen):
    _, ok = V.verifie(zip_path, tmp_path / "controle", attendu=specimen, rendus=False)
    rapport = json.loads((tmp_path / "controle" /
                          (Path(zip_path).stem + "_verification.json")).read_text(encoding="utf-8"))
    return ok, {c["controle"]: c for c in rapport["controles"]}


def test_export_deterministe_et_percages_trois_etats(tmp_path, specimen):
    a = G.exporte(specimen, tmp_path / "a")
    b = G.exporte(specimen, tmp_path / "b")
    assert Path(a).read_bytes() == Path(b).read_bytes()
    ok, controles = controle(a, tmp_path, specimen)
    assert ok
    assert controles["percages_NPTH"]["relus"][0]["metallisation"] == "NPTH"
    assert controles["percages_PTH"]["relus"][0]["metallisation"] == "PTH"


@pytest.mark.parametrize("ext", list(V.COUCHES))
def test_couche_absente_refusee(tmp_path, specimen, ext):
    source = G.exporte(specimen, tmp_path / "source")
    z = modifie_zip(source, tmp_path / "absente.zip",
                   lambda fs: fs.pop("specimen." + ext))
    ok, controles = controle(z, tmp_path, specimen)
    assert not ok
    assert not controles["membres_exacts"]["ok"]
    assert not controles["couche_" + ext]["ok"]


def test_cuivre_differe_malgre_meme_bbox(tmp_path, specimen):
    source = G.exporte(specimen, tmp_path / "source")
    def change(fs):
        # Cut an internal corner; the 1..9 x/y bounding box is unchanged.
        fs["specimen.GTL"] = fs["specimen.GTL"].replace(
            b"X9000000Y9000000D01*", b"X9000000Y8000000D01*\nX8000000Y9000000D01*")
    z = modifie_zip(source, tmp_path / "cuivre.zip", change)
    ok, controles = controle(z, tmp_path, specimen)
    assert not ok
    assert controles["sha256_specimen.GTL"]["ok"]
    assert not controles["geometrie_GTL"]["ok"]


def test_contour_ouvert_refuse(tmp_path, specimen):
    source = G.exporte(specimen, tmp_path / "source")
    def change(fs):
        fs["specimen.GKO"] = fs["specimen.GKO"].replace(b"X0Y0D01*\nM02*", b"M02*")
    z = modifie_zip(source, tmp_path / "ouvert.zip", change)
    ok, controles = controle(z, tmp_path, specimen)
    assert not ok
    assert not controles["geometrie_GKO"]["ok"]


def test_contour_mesure_ligne_mediane(tmp_path, specimen):
    z = G.exporte(specimen, tmp_path)
    pile, ok = V.verifie(z, tmp_path / "controle", attendu=specimen, rendus=False)
    assert ok
    bbox = pile.outline.bounding_box(unit="mm")
    assert bbox[1][0] - bbox[0][0] == pytest.approx(10.1)
    assert G.etendue(specimen) == (10, 10)


@pytest.mark.parametrize("type_trou", ["NPTH", "PTH"])
def test_metallisation_inconnue_refusee(tmp_path, specimen, type_trou):
    source = G.exporte(specimen, tmp_path / "source")
    def change(fs):
        nom = f"specimen-{type_trou}.DRL"
        fs[nom] = re.sub(rb";TYPE=[^\n]+\n", b"", fs[nom])
    z = modifie_zip(source, tmp_path / "inconnu.zip", change)
    ok, controles = controle(z, tmp_path, specimen)
    assert not ok
    assert not controles["declaration_" + type_trou]["ok"]
    assert controles["percages_" + type_trou]["relus"][0]["metallisation"] == "INCONNUE"


def test_position_percage_refusee(tmp_path, specimen):
    source = G.exporte(specimen, tmp_path / "source")
    def change(fs):
        fs["specimen-NPTH.DRL"] = fs["specimen-NPTH.DRL"].replace(b"X0.500", b"X0.550")
    z = modifie_zip(source, tmp_path / "trou.zip", change)
    ok, controles = controle(z, tmp_path, specimen)
    assert not ok
    assert not controles["percages_NPTH"]["ok"]


def test_fonction_couche_refusee(tmp_path, specimen):
    source = G.exporte(specimen, tmp_path / "source")
    def change(fs):
        fs["specimen.GTL"] = fs["specimen.GTL"].replace(b"Copper,L1,Top", b"Copper,L2,Bot")
    z = modifie_zip(source, tmp_path / "fonction.zip", change)
    ok, controles = controle(z, tmp_path, specimen)
    assert not ok
    assert not controles["couche_GTL"]["ok"]


@pytest.mark.parametrize("nom", ["../hors.txt", "C:/hors.txt", "dossier/hors.txt", "..\\hors.txt"])
def test_archive_traversal_refusee(tmp_path, specimen, nom):
    z = tmp_path / "dangereux.zip"
    with zipfile.ZipFile(z, "w") as archive:
        archive.writestr(nom, "interdit")
    ok, controles = controle(z, tmp_path, specimen)
    assert not ok
    assert "membre ZIP interdit" in controles["lecture_verification"]["erreur"]


def test_drc_percage_disque_entier(tmp_path, specimen):
    rapport = apercu.controle_exact(specimen, [(0.1, 5, 0.6)])
    assert any(not ok and "hors substrat" in texte for ok, texte in rapport)


@pytest.mark.parametrize("produit", ["panneau_losanges", "vivaldi_tomographie"])
def test_deux_produits_reels(tmp_path, produit):
    carte = (G.carte_panneau_losanges() if produit == "panneau_losanges"
             else G.carte_antenne(produit))
    z = G.exporte(carte, tmp_path)
    assert V.verifie(z, attendu=carte, rendus=False)[1]


def test_rendus_reels_non_vides(tmp_path, specimen):
    z = G.exporte(specimen, tmp_path)
    assert V.verifie(z, attendu=specimen)[1]
    from PIL import Image
    for ext in V.COUCHES:
        im = Image.open(tmp_path / "verification" / f"specimen_{ext}.png")
        assert im.width == 1400
        assert im.height > 0
