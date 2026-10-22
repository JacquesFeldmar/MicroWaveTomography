"""Prouve les deux voies du runner, sans integrer Q dans le projet.

Seules les preuves de ce staging sont ecrites. La source integree de preuve,
sa campagne existante et son cache existent exclusivement dans TEMP.
"""
import os
for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("runner_integration_preuve", HERE/"verifie_integration_isolee.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def inventaire(base):
    return {p.relative_to(base).as_posix():R.sha(p) for p in base.rglob("*") if p.is_file()}


def execute(nom, arguments):
    r = subprocess.run([sys.executable,"-B","-X","utf8",str(HERE/"verifie_integration_isolee.py"),*arguments],
                       cwd=R.SIM.parent,env=os.environ.copy(),capture_output=True,text=True,encoding="utf-8")
    (HERE/(nom+".stdout.txt")).write_text(r.stdout,encoding="utf-8")
    (HERE/(nom+".stderr.txt")).write_text(r.stderr,encoding="utf-8")
    return r


def main():
    original = (R.SIM/"qualifie_pcbway.py").read_bytes()
    assert hashlib.sha256(original).hexdigest() == R.ATTENDU
    with tempfile.TemporaryDirectory(prefix="mwt_preuve_q_deja_integre_") as temp:
        source = Path(temp)/"simulation"
        source.mkdir()
        for p in [*R.SIM.glob("*.py"),*R.SIM.glob("*.md"),*R.SIM.glob("requirements*.txt"),
                  *(R.SIM/"antennes").rglob("*.py"),*(R.SIM/"tests").glob("*.py")]:
            destination=source/p.relative_to(R.SIM)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,destination)
        texte=original.decode("utf-8").replace("\r\n","\n")
        fin="\r\n" if b"\r\n" in original else "\n"
        (source/"qualifie_pcbway.py").write_bytes(R.correction(texte).replace("\n",fin).encode("utf-8"))
        assert R.sha(source/"qualifie_pcbway.py") == R.INTEGRE_ATTENDU
        campagne=source/"resultats/pcbway_r1"
        campagne.mkdir(parents=True)
        (campagne/"selection_qualification.json").write_text('{"temoin_campagne_existante":true}\n',encoding="utf-8")
        cache=source/"__pycache__"
        cache.mkdir()
        (cache/"temoin_existant.pyc").write_bytes(b"CACHE EXISTANT A PRESERVER")
        avant=inventaire(source)
        staging_avant=inventaire(HERE)
        # Capturer d'abord sans ecrire les journaux : le mode integre doit
        # laisser le staging lui-meme totalement intact.
        r=subprocess.run([sys.executable,"-B","-X","utf8",str(HERE/"verifie_integration_isolee.py"),
                          "--source-integree",str(source)],cwd=R.SIM.parent,env=os.environ.copy(),
                         capture_output=True,text=True,encoding="utf-8")
        staging_intact=inventaire(HERE)==staging_avant
        source_intacte=inventaire(source)==avant
        (HERE/"preuve_source_integree.stdout.txt").write_text(r.stdout,encoding="utf-8")
        (HERE/"preuve_source_integree.stderr.txt").write_text(r.stderr,encoding="utf-8")
        if r.returncode != 0:
            raise AssertionError(r.stderr)
        rapport=json.loads(r.stdout.split("RAPPORT_INTEGRATION_JSON\n",1)[1])
        assert rapport["mode"] == "source_integree_copie_isolee" and rapport["reussi"]
        assert rapport["q_original_sha256"] == rapport["q_copie_testee_sha256"] == R.INTEGRE_ATTENDU
        assert staging_intact and source_intacte
        inconnu=Path(temp)/"source_inconnue"
        inconnu.mkdir()
        (inconnu/"qualifie_pcbway.py").write_bytes(original+b"\n# SHA inconnu pour test de refus\n")
        rejet=execute("preuve_rejet_sha_inconnu",["--source-integree",str(inconnu)])
        assert rejet.returncode != 0 and "SHA Q inconnu" in rejet.stderr
        assert "DEBUT" not in rejet.stdout
    # La voie originale reste utilisable sur Q reel gele, mais n'applique le
    # patch qu'a sa copie temporaire ; seulement sept tests, aucune reprise L.
    print("Preuve source integree : 7 tests reussis ; lancement voie originale ciblee",flush=True)
    initial=execute("preuve_voie_originale_ciblee",["--ciblee"])
    assert initial.returncode == 0,initial.stderr
    assert (R.SIM/"qualifie_pcbway.py").read_bytes() == original
    bilan=dict(schema="preuve_deux_voies_integration_q_v1",reussi=True,
               source_reelle_gelee_sha256=R.ATTENDU,source_integree_attendue_sha256=R.INTEGRE_ATTENDU,
               patch_final_sha256=R.sha(HERE/"integration_qualification.patch"),
               runner_sha256=R.sha(HERE/"verifie_integration_isolee.py"),
               checks_sha256=R.sha(HERE/"checks_integration_qualification.py"),
               integre_source_et_campagne_cache_intacts=source_intacte,
               integre_aucune_ecriture_staging=staging_intact,
               sha_inconnu_refuse_avant_execution=True,
               voie_integree=rapport,
               voie_originale_ciblee=json.loads((HERE/"verification_ciblee.json").read_text(encoding="utf-8")),
               aucune_integration_reelle=True,aucun_calcul_fdtd=True)
    (HERE/"preuve_deux_voies.json").write_text(json.dumps(bilan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in bilan.items() if not k.startswith("voie_")},ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
