"""Cloture documentaire en stdlib, sans import du projet ni calcul scientifique."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


DOSSIER = Path(__file__).resolve().parent
SIMULATION = DOSSIER.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def charge(rel):
    return json.loads((DOSSIER / rel).read_text(encoding="utf-8"))


def ecrit_neuf(rel, contenu):
    with (DOSSIER / rel).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(contenu, f, ensure_ascii=True, indent=2)
        f.write("\n")


def main():
    for nom in ("bilan_final_staging.json", "index_final_sha256.json"):
        if (DOSSIER / nom).exists():
            raise FileExistsError(nom)
    avant = charge("avant.json")
    for rel, attendu in avant["sources_17_sha256"].items():
        assert sha(SIMULATION / rel) == attendu, rel
    for nom, attendu in avant["originaux_sha256"].items():
        assert sha(SIMULATION / nom) == attendu, nom
        assert sha(DOSSIER / "originaux" / nom) == attendu, nom
    assert sha(DOSSIER / "Q5fd_avant.py") == avant["q5fd_sha256"]

    complet = charge("execution_regressions_finales_03/verification.json")
    cible = charge("execution_collision_montage_04/verification.json")
    for execution in (complet, cible):
        for champ in ("reussi", "sources_17_inchangees", "originaux_Q_W_AP_intacts",
                      "staging_inchange_pendant_tests", "aucun_Run",
                      "aucun_resultat_reel_lu", "aucun_patch_applique"):
            assert execution[champ] is True, champ
        assert execution["sources_17_sha256"] == avant["sources_17_sha256"]
        for nom, attendu in execution["modifies_sha256"].items():
            assert sha(DOSSIER / "modifies" / nom) == attendu, nom
        for detail in execution["executions"]:
            assert detail["retour"] == 0
    assert complet["modifies_sha256"] == cible["modifies_sha256"]
    test_sha = sha(DOSSIER / "tests/test_moteurs_qualification.py")
    assert test_sha == cible["tests_sha256"]["test_moteurs_qualification.py"]
    preuves = {}
    for sous, verification in (
        ("execution_regressions_finales_03", complet),
        ("execution_collision_montage_04", cible),
    ):
        for detail in verification["executions"]:
            for flux in ("stdout", "stderr"):
                rel = f"{sous}/{detail['nom']}.{flux}.txt"
                assert sha(DOSSIER / rel) == detail[f"{flux}_sha256"]
                preuves[rel] = sha(DOSSIER / rel)
        rel = f"{sous}/verification.json"
        preuves[rel] = sha(DOSSIER / rel)
    journal = (DOSSIER / "execution_regressions_finales_03/Q_AP_W_moteurs.stderr.txt").read_text(encoding="utf-8")
    assert re.search(r"Ran 77 tests in [\d.]+s\s+OK", journal)
    journal = (DOSSIER / "execution_regressions_finales_03/L_livraison.stdout.txt").read_text(encoding="utf-8")
    assert "34 passed" in journal
    journal = (DOSSIER / "execution_collision_montage_04/Q_AP_W_moteurs.stderr.txt").read_text(encoding="utf-8")
    assert re.search(r"Ran 25 tests in [\d.]+s\s+OK", journal)
    ecrit_neuf("bilan_final_staging.json", {
        "schema": "bilan_final_staging_moteurs_f1_f2_v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "modifies_sha256": cible["modifies_sha256"],
        "test_courant_sha256": test_sha,
        "sources_17_sha256": avant["sources_17_sha256"],
        "originaux_Q_W_AP_sha256": avant["originaux_sha256"],
        "sources_17_et_originaux_inchanges": True,
        "regression_complete": {
            "dossier": "execution_regressions_finales_03",
            "unittest": 77, "pytest_livraison": 34, "tests_distincts": 111,
            "test_sha256": complet["tests_sha256"]["test_moteurs_qualification.py"],
        },
        "supplement_test_cache": {
            "dossier": "execution_collision_montage_04", "tests": 25,
            "description": "Meme fonction renforcee : signatures CAD/contrat/Montage identiques dans les deux sens F1/F2, refus moteur et aucun appel lance.",
            "trois_sources_inchangees_depuis_regression_complete": True,
            "recouvrement_des_111_tests": True,
        },
        "preuves_sha256": preuves,
        "revue_independante": {
            "fichier": "revue_independante_03.json",
            "sha256": sha(DOSSIER / "revue_independante_03.json"),
            "portee": "Relecture des trois sources finales ; test avant le renforcement de la collision.",
        },
        "aucun_Run": True, "aucun_resultat_reel_lu": True,
        "aucun_patch_applique": True,
        "limite": "Validation logicielle avec stub F2 controle dans TEMP ; aucune validation physique du futur moteur F2 ni de ses presets.",
        "statut": "Proposition de staging ; integration et moteur physique soumis a validation separee du responsable.",
    })
    fichiers = {p.relative_to(DOSSIER).as_posix(): sha(p)
                for p in sorted(DOSSIER.rglob("*")) if p.is_file()
                and p.name != "index_final_sha256.json"}
    ecrit_neuf("index_final_sha256.json", {
        "schema": "index_final_staging_moteurs_f1_f2_v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "portee": "Photographie des fichiers presents a la cloture ; index exclu de lui-meme.",
        "nombre_fichiers": len(fichiers), "sha256": fichiers,
    })
    relu = charge("index_final_sha256.json")
    for rel, attendu in relu["sha256"].items():
        assert sha(DOSSIER / rel) == attendu, rel
    print(json.dumps({"reussi": True, "fichiers_indexes": len(fichiers),
                      "bilan_sha256": sha(DOSSIER / "bilan_final_staging.json"),
                      "index_sha256": sha(DOSSIER / "index_final_sha256.json")}, indent=2))


if __name__ == "__main__":
    main()
