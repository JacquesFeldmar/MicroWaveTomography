"""Teste les copies Q/W/AP dans TEMP ; aucune source de production appliquee.

Le moteur F2 est un stub logiciel marque, pas un prototype electromagnetique.
Les regressions F1 utilisent CSXCAD/CalcPort et des sondes synthetiques, sans Run.
"""
import os
for nom in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[nom]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['MPLBACKEND']='Agg'

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ICI=Path(__file__).resolve().parent
SIM=ICI.parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sortie',type=Path,required=True,help='dossier neuf de journaux dans le staging')
    p.add_argument('--ciblee',action='store_true')
    args=p.parse_args()
    sortie=(ICI/args.sortie).resolve()
    if not sortie.is_relative_to(ICI) or sortie==ICI or sortie.exists():
        p.error('sortie doit designer un sous-dossier NEUF du staging')
    avant=json.loads((ICI/'avant.json').read_text(encoding='utf8'))
    sources={n:sha(SIM/n) for n in avant['sources_17_sha256']}
    if sources!=avant['sources_17_sha256']:
        raise ValueError('sources17 differentes de la capture, aucune execution')
    for n,h in avant['originaux_sha256'].items():
        if sha(SIM/n)!=h:
            raise ValueError('original modifie : '+n)
    os.environ['CSXCAD_INSTALL_PATH']=str(SIM.parent/'outils/openEMS')
    sortie.mkdir(parents=True,exist_ok=False)
    executions=[]
    with tempfile.TemporaryDirectory(prefix='mwt_staging_moteurs_') as temp:
        racine=Path(temp).resolve()
        if racine.parent!=Path(tempfile.gettempdir()).resolve() or not racine.name.startswith('mwt_staging_moteurs_'):
            raise ValueError('racine TEMP inattendue')
        copie=racine/'simulation';copie.mkdir()
        fichiers=[*SIM.glob('*.py'),*SIM.glob('*.md'),*SIM.glob('requirements*.txt'),
                  *(SIM/'antennes').rglob('*.py'),*(SIM/'tests').glob('*.py')]
        for f in fichiers:
            if f.name=='fdtd_maille_controlee.py' or '__pycache__' in f.parts:
                continue
            dst=copie/f.relative_to(SIM);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
        for f in (ICI/'modifies').glob('*.py'):
            shutil.copy2(f,copie/f.name)
        for f in (ICI/'tests').glob('*.py'):
            shutil.copy2(f,copie/'tests'/f.name)
        shutil.copy2(SIM/'chatGPT_critical_review/staging_integration_qualification/checks_integration_qualification.py',
                     copie/'tests/test_integration_qualification.py')
        (copie/'_staging_moteurs_f1_f2.txt').write_text('COPIE TEMP SYNTHETIQUE ; aucun Run\n',encoding='utf8')
        modifies_testes={f.name:sha(copie/f.name) for f in sorted((ICI/'modifies').glob('*.py'))}
        tests_testes={f.name:sha(copie/'tests'/f.name) for f in sorted((ICI/'tests').glob('*.py'))}
        py_openems=r'C:\Users\jfeld\anaconda3\envs\openems\python.exe'
        py_ph=r'C:\Users\jfeld\anaconda3\envs\ph\python.exe'
        modules=['test_moteurs_qualification'] if args.ciblee else [
            'test_qualification_pcbway','test_qualification_adaptative','test_fenetre_sondes',
            'test_integration_qualification','test_moteurs_qualification']
        commandes=[('Q_AP_W_moteurs',[py_openems,'-B','-X','utf8','-m','unittest','-v',*modules],copie/'tests')]
        if not args.ciblee:
            commandes.append(('L_livraison',[py_ph,'-B','-X','utf8','-m','pytest','-q','-p','no:cacheprovider','test_livre_pcbway.py'],copie))
        for nom,commande,cwd in commandes:
            print('DEBUT '+nom,flush=True)
            r=subprocess.run(commande,cwd=cwd,env=os.environ.copy(),capture_output=True,text=True,encoding='utf8',errors='replace')
            (sortie/(nom+'.stdout.txt')).write_text(r.stdout,encoding='utf8',newline='\n')
            (sortie/(nom+'.stderr.txt')).write_text(r.stderr,encoding='utf8',newline='\n')
            executions.append(dict(nom=nom,commande=commande,retour=r.returncode,
                stdout_sha256=sha(sortie/(nom+'.stdout.txt')),stderr_sha256=sha(sortie/(nom+'.stderr.txt'))))
            print('FIN '+nom+' retour='+str(r.returncode),flush=True)
        originales_apres={n:sha(SIM/n) for n in avant['sources_17_sha256']}
        originaux_intacts=all(sha(SIM/n)==h for n,h in avant['originaux_sha256'].items())
        staging_intact=(modifies_testes=={f.name:sha(f) for f in sorted((ICI/'modifies').glob('*.py'))} and
                        tests_testes=={f.name:sha(f) for f in sorted((ICI/'tests').glob('*.py'))})
        bilan=dict(schema='staging_moteurs_f1_f2_v1',utc=datetime.now(timezone.utc).isoformat(),
            sources_17_inchangees=originales_apres==sources,originaux_Q_W_AP_intacts=originaux_intacts,
            sources_17_sha256=originales_apres,modifies_sha256=modifies_testes,
            tests_sha256=tests_testes,staging_inchange_pendant_tests=staging_intact,executions=executions,
            moteur_F2='STUB logiciel controle dans TEMP, pas le moteur physique',aucun_Run=True,
            aucun_resultat_reel_lu=True,aucun_patch_applique=True,
            reussi=originales_apres==sources and originaux_intacts and staging_intact and all(r['retour']==0 for r in executions))
    (sortie/'verification.json').write_text(json.dumps(bilan,indent=2)+'\n',encoding='utf8')
    for f in (ICI/'modifies').glob('*.py'):
        old=(ICI/'Q5fd_avant.py' if f.name=='qualifie_pcbway.py' else ICI/'originaux'/f.name).read_text(encoding='utf8')
        new=f.read_text(encoding='utf8')
        diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/simulation/'+f.name,tofile='b/simulation/'+f.name))
        (sortie/(f.stem+'.patch')).write_text(diff,encoding='utf8',newline='\n')
    print(json.dumps(bilan,indent=2),flush=True)
    return 0 if bilan['reussi'] else 1


if __name__=='__main__':
    raise SystemExit(main())
