"""Execution explicite de la campagne deja preparee, sans ecraser les journaux."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]
BASE = SIM / 'resultats/pcbway_maille_controlee_v2'


def neuf(path, objet):
    with path.open('x', encoding='utf-8') as f:
        json.dump(objet, f, ensure_ascii=False, indent=2)


def main():
    paths = [HERE / n for n in ('execution_campagne.stdout.txt',
        'execution_campagne.stderr.txt', 'lancement_campagne.json', 'fin_processus_campagne.json')]
    if any(p.exists() for p in paths):
        raise FileExistsError('Journaux de campagne deja presents')
    etat = json.loads((BASE / 'etat_orchestration.json').read_text(encoding='utf-8'))
    if etat['etat'] != 'prepare':
        raise ValueError('La campagne doit etre preparee et non commencee')
    orchestre = SIM / 'orchestre_f2.py'
    commande = [sys.executable, '-B', '-X', 'utf8', '-u', str(orchestre),
        '--executer', '--base', str(BASE)]
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    with paths[0].open('xb') as out, paths[1].open('xb') as err:
        p = subprocess.Popen(commande, cwd=SIM, env=env, stdout=out, stderr=err)
        debut = dict(schema='lancement_campagne_F2_v1',
            utc=datetime.now(timezone.utc).isoformat(), pid=p.pid, commande=commande,
            orchestrateur_sha256=hashlib.sha256(orchestre.read_bytes()).hexdigest(),
            lanceur_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            qualification_globale_effectuee=False)
        neuf(paths[2], debut)
        print(json.dumps(debut, ensure_ascii=False), flush=True)
        code = p.wait()
    fin = dict(schema='fin_processus_campagne_F2_v1',
        utc=datetime.now(timezone.utc).isoformat(), pid=p.pid, code_natif=code,
        preuve_fin_orchestration=(BASE / 'fin_orchestration.json').is_file())
    neuf(paths[3], fin)
    print(json.dumps(fin, ensure_ascii=False), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
