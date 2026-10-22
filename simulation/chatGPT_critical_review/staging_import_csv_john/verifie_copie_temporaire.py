"""Teste le correctif sur une copie temporaire sans toucher donnees.py.

Execution depuis la racine du projet, avec Python -B -X utf8. Le rapport JSON
est exclusivement ecrit dans le present dossier de staging.
"""
import os

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"

import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]
ROOT = SIM.parent
EXPECTED = "4164aa6d4c0cba4f88592c776592dff79ec5bceeac65f6b65d1a9043a3114237"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


def main():
    source = SIM / "donnees.py"
    if sha(source) != EXPECTED:
        raise SystemExit("Le SHA original differe : ne pas appliquer ni tester ce correctif sans relecture.")
    original = source.read_text(encoding="utf-8")
    ancre = '                entete = [re.sub(r"[^a-z]", "", x.lower()) for x in colonnes]\n'
    ajout = ('                if [x.strip().lower() for x in colonnes[1:]] == ["s11_real", "s11_imag"]:\n'
             '                    entete[1:] = ["real", "imag"]\n')
    if original.count(ancre) != 1:
        raise SystemExit("Ancre du correctif absente ou non unique.")
    modifie = original.replace(ancre, ancre + ajout, 1)
    patch = "".join(difflib.unified_diff(original.splitlines(keepends=True), modifie.splitlines(keepends=True),
                                        fromfile="a/simulation/donnees.py", tofile="b/simulation/donnees.py"))
    if patch != (HERE / "lecteur_csv_john.patch").read_text(encoding="utf-8"):
        raise SystemExit("Le patch unifie ne correspond pas a la copie testee.")
    data = ROOT / "from Maurice/plexiglas/textes/texte3_john/data"
    entrees = {str(p.relative_to(ROOT)): sha(p) for p in sorted(data.glob("*")) if p.is_file()}
    with tempfile.TemporaryDirectory(prefix="mwt_donnees_john_isole_") as dossier:
        copie = Path(dossier) / "donnees.py"
        copie.write_text(modifie, encoding="utf-8", newline="\n")
        charger("donnees", copie)
        modules = [charger("test_donnees_existants", SIM / "test_donnees.py"),
                   charger("test_csv_john_staging", HERE / "test_csv_john.py")]
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in modules)
        resultat = unittest.TextTestRunner(verbosity=2).run(suite)
    intact = sha(source) == EXPECTED and entrees == {
        str(p.relative_to(ROOT)): sha(p) for p in sorted(data.glob("*")) if p.is_file()}
    bilan = dict(source_originale=str(source.relative_to(ROOT)), sha256_original_attendu=EXPECTED,
                 sha256_original_apres=sha(source), sha256_copie_testee=hashlib.sha256(modifie.encode()).hexdigest(),
                 sha256_patch=sha(HERE / "lecteur_csv_john.patch"),
                 tests=resultat.testsRun, echecs=len(resultat.failures), erreurs=len(resultat.errors),
                 sources_et_exports_intacts=intact, entrees_sha256=entrees,
                 threads={k: os.environ[k] for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
                 reussi=resultat.wasSuccessful() and intact)
    (HERE / "verification.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in bilan.items() if k != "entrees_sha256"}, ensure_ascii=False, indent=2))
    return 0 if bilan["reussi"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
