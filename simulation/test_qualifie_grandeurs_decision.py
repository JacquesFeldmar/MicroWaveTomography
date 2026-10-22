"""Tests de la qualification sur les grandeurs de decision.

Campagnes synthetiques uniquement : aucun profil reel n'est lu, pour que ces
tests ne dependent d'aucun resultat de solveur et ne puissent pas etre
confondus avec une qualification.
"""
import json
from pathlib import Path

import numpy as np
import pytest

import qualifie_grandeurs_decision as Q

FREQS = np.arange(1.0e9, 6.3e9 + 1.0, 25e6)      # la grille de la campagne


def ecrit_s1p(chemin, modules):
    """Un Touchstone dont |S11| vaut exactement `modules`, phase nulle."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    m = np.broadcast_to(np.asarray(modules, dtype=float), FREQS.shape)
    lignes = ["# Hz S RI R 50"]
    lignes += [f"{f:.0f} {v:.9e} 0.000000000e+00" for f, v in zip(FREQS, m)]
    chemin.write_text("\n".join(lignes) + "\n", encoding="ascii")


def campagne(tmp_path, niveaux_par_antenne, reference="fin_16ns",
             tous_reussis=False):
    """Fabrique une campagne : {antenne: {niveau: modules}}."""
    racine = tmp_path / "campagne"
    antennes = {}
    for antenne, niveaux in niveaux_par_antenne.items():
        for niveau, modules in niveaux.items():
            ecrit_s1p(racine / antenne / niveau / "s11.s1p", modules)
        antennes[antenne] = {
            "reference": str(racine / antenne / reference),
            "calculs_utilises": sorted(niveaux),
            "geometrie_sha256": "0" * 64,
            "spatial": {"ecarts": {"reussi": False}},
            "temporel": {"ecarts": {"reussi": True}},
        }
    racine.mkdir(parents=True, exist_ok=True)
    (racine / "qualification_globale.json").write_text(
        json.dumps({"antennes": antennes, "moteur": "moteur_temoin",
                    "tous_reussis": tous_reussis}, ensure_ascii=False),
        encoding="utf-8")
    return racine


def db(valeur_db):
    """Le module dont la puissance vaut `valeur_db`."""
    return 10 ** (valeur_db / 20.0)


# ----------------------------------------------------------------- reussite
def test_niveaux_qui_s_accordent_passent(tmp_path):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.00), "fin_16ns": db(-12.10)}})
    bilan = Q.qualifie(str(r))
    assert bilan["tous_reussis"]
    a = bilan["antennes"]["temoin"]
    assert a["reussi"]
    assert a["etendues"]["etendue_puissance_moyenne_db"] == pytest.approx(
        0.10, abs=1e-6)
    assert a["etendues"]["etendue_part_sous_6db_pts"] == 0.0


def test_reference_identifiee_et_ses_grandeurs_presentes(tmp_path):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.00), "fin_16ns": db(-12.10)}})
    a = Q.qualifie(str(r))["antennes"]["temoin"]
    assert a["reference_niveau"] == "fin_16ns"
    assert a["grandeurs_reference"]["puissance_reflechie_moyenne_db"] == \
        pytest.approx(-12.10, abs=1e-6)
    assert a["grandeurs_reference"]["part_sous_6db_pct"] == 100.0


# ------------------------------------------------------------------- echecs
def test_etendue_de_puissance_trop_grande_echoue(tmp_path):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.0), "fin_16ns": db(-12.8)}})
    bilan = Q.qualifie(str(r))
    assert not bilan["tous_reussis"]
    c = bilan["antennes"]["temoin"]["controles"]
    assert not c["etendue_puissance_moyenne_db"]["reussi"]
    assert c["etendue_part_sous_6db_pts"]["reussi"]


def test_etendue_de_part_sous_6db_trop_grande_echoue(tmp_path):
    """Meme puissance moyenne, mais la part de bande adaptee bouge."""
    n = FREQS.size
    bas, haut = db(-20.0), db(-0.5)
    a = np.where(np.arange(n) < n // 2, bas, haut)
    b = np.where(np.arange(n) < n // 2 + 10, bas, haut)
    r = campagne(tmp_path, {"temoin": {"base_12ns": a, "fin_16ns": b}})
    c = Q.qualifie(str(r))["antennes"]["temoin"]["controles"]
    assert not c["etendue_part_sous_6db_pts"]["reussi"]


# ------------------------------------------------- la part sous -10 dB ne juge pas
def test_part_sous_10db_rapportee_mais_non_qualifiante(tmp_path):
    """Un |S11| qui longe -10 dB fait basculer beaucoup de points pour un
    deplacement minime. C'est le cas du petit losange : on le rapporte, on
    n'en fait pas un critere."""
    n = FREQS.size
    juste_sous, juste_au_dessus = db(-10.01), db(-9.99)
    a = np.full(n, juste_sous)
    b = np.full(n, juste_au_dessus)
    r = campagne(tmp_path, {"temoin": {"base_12ns": a, "fin_16ns": b}})
    bilan = Q.qualifie(str(r))
    a_bilan = bilan["antennes"]["temoin"]
    assert a_bilan["etendues"]["etendue_part_sous_10db_pts"] == 100.0
    assert a_bilan["etendues"]["etendue_puissance_moyenne_db"] < 0.05
    assert a_bilan["reussi"], "la part sous -10 dB ne doit pas faire echouer"
    assert "etendue_part_sous_10db_pts" in bilan["indicatif_non_qualifiant"]


# --------------------------------------------- le verdict ponctuel est conserve
def test_verdict_ponctuel_conserve_et_non_remplace(tmp_path):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.0), "fin_16ns": db(-12.1)}}, tous_reussis=False)
    bilan = Q.qualifie(str(r))
    conserve = bilan["qualification_ponctuelle_conservee"]
    assert conserve["tous_reussis"] is False
    assert conserve["fichier"] == "qualification_globale.json"
    assert len(conserve["sha256"]) == 64
    assert bilan["tous_reussis"] is True
    assert bilan["antennes"]["temoin"]["spatial_ponctuel_reussi"] is False
    assert bilan["antennes"]["temoin"]["temporel_ponctuel_reussi"] is True


def test_qualification_globale_n_est_pas_modifiee(tmp_path, capsys):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.0), "fin_16ns": db(-12.1)}})
    avant = (r / "qualification_globale.json").read_bytes()
    Q.qualifie(str(r))
    assert (r / "qualification_globale.json").read_bytes() == avant


def test_limites_declarees_presentes(tmp_path):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.0), "fin_16ns": db(-12.1)}})
    limites = " ".join(Q.qualifie(str(r))["limites_declarees"]).lower()
    assert "point par point" in limites
    assert "connecteur" in limites


# ------------------------------------------------------------------- refus
def test_un_seul_niveau_lisible_est_refuse(tmp_path):
    r = campagne(tmp_path, {"temoin": {"fin_16ns": db(-12.0)}})
    with pytest.raises(ValueError, match="moins de deux niveaux"):
        Q.qualifie(str(r))


def test_profil_hors_bande_est_refuse(tmp_path):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.0), "fin_16ns": db(-12.1)}})
    hors = r / "temoin" / "base_12ns" / "s11.s1p"
    hors.write_text("# Hz S RI R 50\n100000000 0.5 0.0\n200000000 0.5 0.0\n",
                    encoding="ascii")
    with pytest.raises(ValueError, match="aucun point dans la bande"):
        Q.qualifie(str(r))


def test_ecriture_du_fichier_et_code_de_sortie(tmp_path, monkeypatch):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.0), "fin_16ns": db(-12.1)}})
    monkeypatch.setattr("sys.argv", ["q", "--campagne", str(r)])
    assert Q.principal() == 0
    ecrit = json.loads(
        (r / "qualification_grandeurs_decision.json").read_text("utf-8"))
    assert ecrit["schema"] == "qualification_grandeurs_decision/1"
    assert ecrit["seuils"] == Q.SEUILS


def test_echec_rend_le_code_deux(tmp_path, monkeypatch):
    r = campagne(tmp_path, {"temoin": {
        "base_12ns": db(-12.0), "fin_16ns": db(-13.0)}})
    monkeypatch.setattr("sys.argv", ["q", "--campagne", str(r)])
    assert Q.principal() == 2
