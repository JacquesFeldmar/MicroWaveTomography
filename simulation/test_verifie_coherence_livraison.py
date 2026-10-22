"""Tests de la verification de coherence : chaque maillon doit pouvoir casser.

Arborescences synthetiques uniquement. Un controle qui ne sait pas echouer ne
controle rien, donc chaque test casse exactement un maillon et verifie que
c'est celui-la, et lui seul, qui tombe.
"""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

import verifie_coherence_livraison as C

SOURCE = "antennes/temoin/geometrie.py"
CONTENU = b"# temoin\nNOM = 'temoin'\n"
GEOMETRIE = "a" * 64


def sha(donnees):
    return hashlib.sha256(donnees).hexdigest()


def batit(racine, campagne, geometrie_manifeste=GEOMETRIE,
          source_contenu=CONTENU, gele_contenu=CONTENU,
          geometrie_qualif="z" * 64, zip_sha_inventaire=None):
    """Une livraison complete et coherente, sauf ce qu'on lui demande de rater."""
    (racine / "antennes" / "temoin").mkdir(parents=True, exist_ok=True)
    (racine / SOURCE).write_bytes(source_contenu)

    manifeste = {"produit": "temoin", "geometrie_sha256": geometrie_manifeste,
                 "sources_sha256": {SOURCE: sha(CONTENU)}}
    base = racine / "fabrication" / "temoin"
    base.mkdir(parents=True, exist_ok=True)
    chemin_zip = base / "temoin_pcbway.zip"
    with zipfile.ZipFile(chemin_zip, "w") as z:
        z.writestr("temoin_manifest.json",
                   json.dumps(manifeste, ensure_ascii=False))
        z.writestr("temoin.GTL", "G04 temoin*\nM02*\n")
    empreinte = sha(chemin_zip.read_bytes())
    (base / "temoin_pcbway.zip.sha256").write_text(
        f"{empreinte}  temoin_pcbway.zip\n", encoding="ascii")

    (racine / "fabrication" / "inventaire_livraison_courante.json").write_text(
        json.dumps({"articles": [{
            "produit": "temoin",
            "geometrie_sha256": GEOMETRIE,
            "zip_sha256": zip_sha_inventaire or empreinte}]},
            ensure_ascii=False), encoding="utf-8")

    gelees = campagne / "controle_orchestration" / "sources" / "antennes" / "temoin"
    gelees.mkdir(parents=True, exist_ok=True)
    (gelees / "geometrie.py").write_bytes(gele_contenu)

    ponctuelle = campagne / "qualification_globale.json"
    ponctuelle.write_text(json.dumps({
        "antennes": {"temoin": {"geometrie_sha256": "z" * 64}},
        "tous_reussis": False}, ensure_ascii=False), encoding="utf-8")
    (campagne / "qualification_grandeurs_decision.json").write_text(
        json.dumps({
            "antennes": {"temoin": {"geometrie_sha256": geometrie_qualif}},
            "qualification_ponctuelle_conservee": {
                "sha256": sha(ponctuelle.read_bytes())},
            "tous_reussis": True}, ensure_ascii=False), encoding="utf-8")
    return racine, campagne


@pytest.fixture
def livraison(tmp_path):
    return batit(tmp_path / "arbre", tmp_path / "campagne")


def maillons_tombes(constats):
    return [m for ok, m, _ in constats if not ok]


def test_livraison_coherente_ferme_la_chaine(livraison):
    racine, campagne = livraison
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert tout_bon, maillons_tombes(constats)
    assert len(constats) == 6          # 1, 2, 3, 4, 5, 5b


def test_empreinte_de_zip_falsifiee_dans_l_inventaire(tmp_path):
    racine, campagne = batit(tmp_path / "a", tmp_path / "c",
                             zip_sha_inventaire="b" * 64)
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert not tout_bon
    assert maillons_tombes(constats) == ["1. empreinte du ZIP temoin"]


def test_geometrie_du_manifeste_differente_de_l_inventaire(tmp_path):
    racine, campagne = batit(tmp_path / "a", tmp_path / "c",
                             geometrie_manifeste="c" * 64)
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert not tout_bon
    assert maillons_tombes(constats) == ["2. geometrie du manifeste temoin"]


def test_source_retouchee_apres_export(tmp_path):
    """Le cas qui motive l'outil : la geometrie a bouge apres le ZIP."""
    racine, campagne = batit(tmp_path / "a", tmp_path / "c",
                             source_contenu=CONTENU + b"# retouche\n",
                             gele_contenu=CONTENU + b"# retouche\n")
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert not tout_bon
    assert maillons_tombes(constats) == ["3. sources du manifeste temoin"]


def test_source_gelee_differente_de_l_arbre(tmp_path):
    """La campagne a simule autre chose que ce que l'arbre contient."""
    racine, campagne = batit(tmp_path / "a", tmp_path / "c",
                             gele_contenu=b"# une autre antenne\n")
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert not tout_bon
    assert maillons_tombes(constats) == ["4. sources gelees de la campagne"]


def test_source_absente_de_l_arbre(tmp_path):
    racine, campagne = batit(tmp_path / "a", tmp_path / "c")
    (racine / SOURCE).unlink()
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert not tout_bon
    assert set(maillons_tombes(constats)) == {
        "3. sources du manifeste temoin", "4. sources gelees de la campagne"}


def test_qualifications_en_desaccord_sur_la_geometrie(tmp_path):
    racine, campagne = batit(tmp_path / "a", tmp_path / "c",
                             geometrie_qualif="d" * 64)
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert not tout_bon
    assert maillons_tombes(constats) == ["5. accord des deux qualifications"]


def test_verdict_ponctuel_altere_apres_citation(livraison):
    racine, campagne = livraison
    (campagne / "qualification_globale.json").write_text(
        json.dumps({"antennes": {"temoin": {"geometrie_sha256": "z" * 64}},
                    "tous_reussis": True}, ensure_ascii=False),
        encoding="utf-8")
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert not tout_bon
    assert maillons_tombes(constats) == [
        "5b. verdict ponctuel cite sans alteration"]


def test_qualification_manquante_est_refusee(livraison):
    racine, campagne = livraison
    (campagne / "qualification_grandeurs_decision.json").unlink()
    constats, tout_bon = C.controle(str(campagne), racine=str(racine))
    assert not tout_bon
    assert "5. accord des deux qualifications" in maillons_tombes(constats)


def test_zip_sans_manifeste_est_refuse(livraison):
    racine, campagne = livraison
    chemin = racine / "fabrication" / "temoin" / "temoin_pcbway.zip"
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("temoin.GTL", "G04 temoin*\nM02*\n")
    (chemin.parent / "temoin_pcbway.zip.sha256").write_text(
        f"{sha(chemin.read_bytes())}  temoin_pcbway.zip\n", encoding="ascii")
    with pytest.raises(ValueError, match="manifeste"):
        C.controle(str(campagne), racine=str(racine))


def test_rapport_json_ecrit_les_constats(livraison, tmp_path, monkeypatch):
    racine, campagne = livraison
    rapport = tmp_path / "rapport.json"
    monkeypatch.setattr("sys.argv", ["v", "--campagne", str(campagne),
                                     "--racine", str(racine),
                                     "--rapport", str(rapport)])
    assert C.principal() == 0
    d = json.loads(rapport.read_text("utf-8"))
    assert d["tout_bon"] is True
    assert len(d["constats"]) == 6
