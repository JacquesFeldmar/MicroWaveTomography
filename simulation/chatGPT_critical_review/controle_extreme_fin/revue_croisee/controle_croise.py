"""Read-only cross-check of nine completed large-rhombus calculations."""
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
SIM = ROOT / "simulation"
sys.path.insert(0, str(SIM))
ATTENDU_Q = "2e6b6f7f07b8903acfa6a51eb40bab6f3961dd1af1a95e7b76d9661f0af70ac4"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    destination = Path(__file__).with_name("rapport_croise.json")
    if destination.exists():
        raise FileExistsError(destination)
    assert sha(SIM / "qualifie_pcbway.py") == ATTENDU_Q
    import numpy as np
    import qualifie_pcbway as Q
    import raffine_qualification_pcbway as R
    R.enregistre(Q)  # Process-local registry; the Q source stays unchanged.
    base = SIM / "resultats/pcbway_r1/diamant_uwb_x18"
    profils = ("base_8ns", "fin_8ns", "fin_12ns", "tres_fin_8ns", "tres_fin_12ns",
               "ultra_fin_8ns", "ultra_fin_12ns", "extreme_fin_8ns", "extreme_fin_12ns")
    donnees, controles = {}, {}
    for nom in profils:
        niveau, fenetre = nom.rsplit("_", 1)
        f, s, m, q = Q.charge_calcul(base / nom, exiger_courant=True)
        Q.valide_campagne(m, q, "diamant_uwb_x18", niveau, float(fenetre[:-2]))
        donnees[nom] = (f, s, m, q)
        controles[nom] = dict(lecture_courante_et_configuration_validees=True,
            n_pas=m["execution"]["n_pas"], dt_s=m["execution"]["dt_s"],
            geometrie_sha256=q["geometrie_sha256"],
            manifeste_sha256=sha(base / nom / "simulation_manifest.json"),
            entree_sha256=sha(base / nom / "qualification_entree.json"),
            indicateurs=Q.indicateurs(f, s))
    premier = donnees[profils[0]]
    communs = dict(
        geometrie=all(Q.G.json_octets(d[3]["geometrie"]) == Q.G.json_octets(premier[3]["geometrie"]) for d in donnees.values()),
        contrat=all(Q.G.json_octets(d[3]["simulation_contract"]) == Q.G.json_octets(premier[3]["simulation_contract"]) for d in donnees.values()),
        sources=all(d[2]["sources_sha256"] == premier[2]["sources_sha256"] for d in donnees.values()),
        environnement=all(d[2]["environnement"] == premier[2]["environnement"] for d in donnees.values()),
        grille_frequence=all(np.array_equal(d[0], premier[0]) for d in donnees.values()))
    assert all(communs.values()), communs
    a, b = donnees["ultra_fin_12ns"], donnees["extreme_fin_12ns"]
    t = donnees["extreme_fin_8ns"]
    spatial = Q.ecarts(a[0], a[1], b[0], b[1])
    temporel = Q.ecarts(t[0], t[1], b[0], b[1], temporel=True)
    maillage = {}
    with np.load(base / "extreme_fin_8ns/maillage.npz") as g8, np.load(base / "extreme_fin_12ns/maillage.npz") as g12:
        assert set(g8.files) == set(g12.files)
        for cle in g8.files:
            x, y = g8[cle], g12[cle]
            maillage[cle] = dict(forme=list(x.shape), dtype=str(x.dtype),
                identique_binaire=x.shape == y.shape and x.dtype == y.dtype and x.tobytes() == y.tobytes())
    coherence_temporelle = dict(
        maillage_manifeste_identique=t[2]["maillage"] == b[2]["maillage"],
        dt_binaire_identique=np.float64(t[2]["execution"]["dt_s"]).tobytes() == np.float64(b[2]["execution"]["dt_s"]).tobytes(),
        dt_hex=float(b[2]["execution"]["dt_s"]).hex(), axes=maillage,
        fichier_npz_identique=sha(base / "extreme_fin_8ns/maillage.npz") == sha(base / "extreme_fin_12ns/maillage.npz"))
    assert coherence_temporelle["maillage_manifeste_identique"] and coherence_temporelle["dt_binaire_identique"]
    assert all(x["identique_binaire"] for x in maillage.values())
    masques = {"spatial": int(np.count_nonzero((np.abs(a[1]) >= .1) & (np.abs(b[1]) >= .1))),
               "temporel": int(np.count_nonzero((np.abs(t[1]) >= .1) & (np.abs(b[1]) >= .1)))}
    final = Q.indicateurs(b[0], b[1])
    verdict = bool(spatial["reussi"] and temporel["reussi"] and final["passivite_numerique"])
    assert sha(SIM / "qualifie_pcbway.py") == ATTENDU_Q
    rapport = dict(schema="revue_croisee_extreme_fin_v1", date_utc=datetime.now(timezone.utc).isoformat(),
        q_sha256=ATTENDU_Q, r_sha256=sha(SIM / "raffine_qualification_pcbway.py"),
        script_sha256=sha(__file__), profils=controles, nombre_profils=len(profils), communs=communs,
        sources_physiques_sha256=premier[2]["sources_sha256"], environnement=premier[2]["environnement"],
        coherence_temporelle=coherence_temporelle, points_masque_module_ge_0p1=masques,
        spatial=spatial, temporel=temporel, indicateurs_reference_extreme12=final,
        reussi=verdict, aucun_calcul_ni_resultat_modifie=True,
        portee="Lecture stricte des preuves de neuf profils et criteres Q existants, aucun FDTD, aucune selection, registre R en memoire seulement.")
    with destination.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(dict(spatial=spatial, temporel=temporel, points_masque=masques,
        passivite=final["passivite_numerique"], maximum_module=final["maximum_module"],
        reussi=verdict, rapport=str(destination)), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
