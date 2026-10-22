"""Lance une fois le diagnostic pilote, avec sorties binaires UTF-8 conservees."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]


def neuf(path, objet):
    with path.open('x', encoding='utf-8') as f:
        json.dump(objet, f, ensure_ascii=False, indent=2)


def main():
    fichiers = [HERE / n for n in ('execution_pilote.stdout.txt',
        'execution_pilote.stderr.txt', 'lancement_pilote.json', 'fin_processus_pilote.json')]
    if any(p.exists() for p in fichiers) or (SIM / 'resultats/validation_maille_controle_v2').exists():
        raise FileExistsError('Pilote ou journaux deja presents')
    env = dict(os.environ)
    env.update({n: '1' for n in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
        'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})
    env['PYTHONUTF8'] = '1'
    driver = HERE / 'procedure_pilote_f2.py'
    commande = [sys.executable, '-B', '-X', 'utf8', '-u', str(driver)]
    with fichiers[0].open('xb') as out, fichiers[1].open('xb') as err:
        p = subprocess.Popen(commande, cwd=SIM, env=env, stdout=out, stderr=err)
        debut = dict(schema='lancement_pilote_F2_v1',
            utc=datetime.now(timezone.utc).isoformat(), pid=p.pid, commande=commande,
            pilote_sha256=hashlib.sha256(driver.read_bytes()).hexdigest(),
            lanceur_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        neuf(fichiers[2], debut)
        print(json.dumps(debut, ensure_ascii=False), flush=True)
        code = p.wait()
    fin = dict(schema='fin_processus_pilote_F2_v1',
        utc=datetime.now(timezone.utc).isoformat(), pid=p.pid, code_natif=code,
        preuve_complete=(SIM / 'resultats/validation_maille_controle_v2/journaux/fin_pilote.json').is_file())
    neuf(fichiers[3], fin)
    print(json.dumps(fin, ensure_ascii=False), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
