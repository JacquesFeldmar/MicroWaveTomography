"""Construit/teste Q sur copie temporaire ; aucune source de simulation ecrite.

Tous les sous-processus heritent d'un thread OMP/BLAS. Aucun Run FDTD.
"""
import os

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]
ATTENDU = "2e6b6f7f07b8903acfa6a51eb40bab6f3961dd1af1a95e7b76d9661f0af70ac4"
INTEGRE_ATTENDU = "5fd159116157bef7191c3b86225cf0524fffd3e700295469fa12604c59482217"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def correction(texte):
    def remplace_unique(a, b):
        nonlocal texte
        if texte.count(a) != 1:
            raise ValueError("ancre du correctif absente/non unique : " + a[:70])
        texte = texte.replace(a, b, 1)
    remplace_unique("import sys\n\nsys.dont_write_bytecode = True", '''import sys

sys.dont_write_bytecode = True
# L'entree CLI delegue au controleur canonique : AP et L importent ainsi
# exactement le meme module et le meme catalogue, sans alias sys.modules.
if __name__ == "__main__":
    from qualifie_pcbway import main
    raise SystemExit(main())''')
    remplace_unique('}\nBASE = RACINE / "resultats" / "pcbway_r1"', '''}
import raffine_qualification_pcbway as R
R.enregistre(sys.modules[__name__])
BASE = RACINE / "resultats" / "pcbway_r1"''')
    remplace_unique('def comparer(base=BASE, ecrire=True):\n', '''def comparer(base=BASE, ecrire=True):
    if (Path(base)/"selection_qualification.json").is_file():
        import qualification_adaptative as A
        return A.comparer(base, ecrire=ecrire)
''')
    remplace_unique('if __name__ == "__main__":\n    p=argparse.ArgumentParser(description=__doc__)',
                    'def main(argv=None):\n    p=argparse.ArgumentParser(description=__doc__)')
    remplace_unique('    args=p.parse_args()\n', '    args=p.parse_args(argv)\n')
    remplace_unique('        sys.exit(0 if comparer(args.base)["tous_reussis"] else 2)',
                    '        return 0 if comparer(args.base)["tous_reussis"] else 2')
    remplace_unique('    calcule(args.antenne,args.niveau,args.duree_ns,args.fils,args.cout,args.base)\n',
                    '    calcule(args.antenne,args.niveau,args.duree_ns,args.fils,args.cout,args.base)\n    return 0\n')
    return texte


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--python-openems", default=r"C:\Users\jfeld\anaconda3\envs\openems\python.exe")
    p.add_argument("--python-traitement", default=r"C:\Users\jfeld\anaconda3\envs\ph\python.exe")
    p.add_argument("--ciblee", action="store_true", help="uniquement integration CLI/import, apres correction sans effet numerique")
    p.add_argument("--source-integree", nargs="?", const=SIM, type=Path,
                   help="copie Q deja integre (SHA final strict), sans patch ni ecriture dans le depot ; chemin optionnel pour preuve isolee")
    args = p.parse_args()
    # Le moteur copie n'a pas ../outils : l'installation native reste une
    # dependance en lecture seule, explicite pour les DLL CSXCAD/openEMS.
    installation = SIM.parent/"outils/openEMS"
    if installation.is_dir():
        os.environ.setdefault("CSXCAD_INSTALL_PATH", str(installation))
    integre = args.source_integree is not None
    origine = (args.source_integree if integre else SIM).resolve()
    source = origine / "qualifie_pcbway.py"
    attendu = INTEGRE_ATTENDU if integre else ATTENDU
    if not source.is_file() or sha(source) != attendu:
        raise SystemExit("SHA Q inconnu : attendu "+attendu+" ; aucune copie, application ou verification executee.")
    original = source.read_bytes()
    chemin_patch = HERE/"integration_qualification.patch"
    if integre:
        octets_copie = original  # Ni regeneration, ni reapplication du patch.
    else:
        texte = original.decode("utf-8").replace("\r\n", "\n")
        modifie = correction(texte)
        patch = "".join(difflib.unified_diff(texte.splitlines(True), modifie.splitlines(True),
                                            fromfile="a/simulation/qualifie_pcbway.py", tofile="b/simulation/qualifie_pcbway.py"))
        if chemin_patch.exists() and chemin_patch.read_text(encoding="utf-8") != patch:
            historique = HERE/"integration_qualification_avant_controle_cache.patch"
            if not historique.exists():
                shutil.copy2(chemin_patch, historique)
        chemin_patch.write_text(patch, encoding="utf-8", newline="\n")
        fin = "\r\n" if b"\r\n" in original else "\n"
        octets_copie = modifie.replace("\n", fin).encode("utf-8")
        if hashlib.sha256(octets_copie).hexdigest() != INTEGRE_ATTENDU:
            raise SystemExit("Le patch ne produit pas le SHA final attendu.")
    proteges = sorted([*origine.glob("*.py"), *(origine/"antennes").glob("*/geometrie.py")])
    avant = {p.relative_to(origine).as_posix(): sha(p) for p in proteges}
    selection = origine/"resultats/pcbway_r1/selection_qualification.json"
    selection_avant = sha(selection) if selection.exists() else None
    executions = []
    with tempfile.TemporaryDirectory(prefix="mwt_integration_q_isolee_") as temp:
        copie = Path(temp)/"simulation"
        copie.mkdir()
        for chemin in [*origine.glob("*.py"), *origine.glob("*.md"), *origine.glob("requirements*.txt"),
                       *(origine/"antennes").rglob("*.py"), *(origine/"tests").glob("*.py")]:
            destination = copie/chemin.relative_to(origine)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(chemin, destination)
        (copie/"qualifie_pcbway.py").write_bytes(octets_copie)
        shutil.copy2(HERE/"checks_integration_qualification.py", copie/"tests/test_integration_qualification.py")
        commandes = [
            ("Q_AP_R_et_integration", [args.python_openems,"-B","-X","utf8","-m","unittest","-v",
                "test_qualification_pcbway","test_qualification_adaptative",
                "test_raffine_qualification_pcbway","test_integration_qualification"], copie/"tests"),
            ("L_livraison", [args.python_traitement,"-B","-X","utf8","-m","pytest","-q",
                "-p","no:cacheprovider","test_livre_pcbway.py"], copie),
        ]
        if args.ciblee or integre:
            commandes = [("integration_ciblee", [args.python_openems,"-B","-X","utf8","-m","unittest","-v",
                           "test_integration_qualification"], copie/"tests")]
        for nom, commande, cwd in commandes:
            print("DEBUT "+nom+" (copie temporaire uniquement)", flush=True)
            r = subprocess.run(commande, cwd=cwd, env=os.environ.copy(), capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            journaux = Path(temp)/"journaux" if integre else HERE
            journaux.mkdir(exist_ok=True)
            (journaux/(nom+".stdout.txt")).write_text(r.stdout, encoding="utf-8")
            (journaux/(nom+".stderr.txt")).write_text(r.stderr, encoding="utf-8")
            executions.append(dict(nom=nom, commande=commande, retour=r.returncode,
                                   stdout_sha256=sha(journaux/(nom+".stdout.txt")),
                                   stderr_sha256=sha(journaux/(nom+".stderr.txt"))))
            if integre:
                print(r.stdout, end="", flush=True)
                import sys
                print(r.stderr, end="", file=sys.stderr, flush=True)
            print("FIN "+nom+" retour="+str(r.returncode), flush=True)
        sha_copie = sha(copie/"qualifie_pcbway.py")
    apres = {p.relative_to(origine).as_posix(): sha(p) for p in proteges}
    intact = avant == apres and selection_avant == (sha(selection) if selection.exists() else None)
    bilan = dict(schema="staging_integration_qualification_v1",
        mode="source_integree_copie_isolee" if integre else "patch_sur_copie_isolee",
        q_original_sha256=attendu,
        q_original_apres_sha256=sha(source), q_copie_testee_sha256=sha_copie,
        patch_sha256=sha(HERE/"integration_qualification.patch"), sources_intactes=intact,
        selection_reelle_sha256_avant=selection_avant,
        sources_sha256=avant, executions=executions,
        aucun_calcul_fdtd=True, reussi=intact and all(x["retour"] == 0 for x in executions))
    if not integre:
        nom_bilan = "verification_ciblee.json" if args.ciblee else "verification.json"
        (HERE/nom_bilan).write_text(json.dumps(bilan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    else:
        print("RAPPORT_INTEGRATION_JSON", flush=True)
    print(json.dumps({k:v for k,v in bilan.items() if k != "sources_sha256"},ensure_ascii=False,indent=2))
    return 0 if bilan["reussi"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
