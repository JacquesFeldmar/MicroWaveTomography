"""Verification native F2 dans une copie TEMP des dix sources, aucun Run."""
import ast
import copy
from datetime import datetime,timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode=True
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[n]='1'
os.environ['MPLBACKEND']='Agg'
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[1]
ANCRE=SIM/'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'
PROTO=SIM/'chatGPT_critical_review/diagnostic_grand_n34/prototype_maillage_controle/proposition_10_interpolations_sma_libres'
F2=ICI/'modifies/fdtd_maille_controlee.py'
SORTIE=ICI/'preuve_native_f2_grilles.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lit(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def exige(x,m):
    if not x:raise ValueError(m)


def fonctions(p):
    return {n.name:n for n in ast.parse(Path(p).read_text(encoding='utf-8')).body
            if isinstance(n,ast.FunctionDef)}


def main():
    exige(not SORTIE.exists(),'Preuve deja presente')
    attendu=lit(ANCRE)['sources_controle_sha256'];avant={n:sha(SIM/n) for n in attendu}
    exige(avant==attendu and len(avant)==17,'17sources historiques modifiees')
    sourceF2=sha(F2)
    f1,f2=fonctions(SIM/'fdtd.py'),fonctions(F2)
    exceptions={'construit','_sources','_sauve_manifeste','lance'}
    identiques=[]
    for nom in f1:
        if nom not in exceptions:
            exige(ast.dump(f1[nom],include_attributes=False)==ast.dump(f2[nom],include_attributes=False),'Fonction physique modifiee :'+nom)
            identiques.append(nom)
    a,b=copy.deepcopy(f1['lance']),copy.deepcopy(f2['lance'])
    ajout=0
    for n in ast.walk(b):
        if isinstance(n,ast.Call):
            anciens=len(n.keywords)
            n.keywords=[k for k in n.keywords if k.arg!='politique_maillage']
            ajout+=anciens-len(n.keywords)
    exige(ajout==1 and ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False),
        'lance differe au-dela de la metadonnee politique')
    # Le dossier Temp est volontairement conserve, jamais un profil reel.
    temp=Path(tempfile.mkdtemp(prefix='controle_f2_sans_run_')).resolve()
    phys={n:d for n,d in attendu.items() if n.startswith('antennes/') or n in ('fdtd.py','banc.py','materiaux.py','connectique.py')}
    exige(len(phys)==9,'Inventaire physiqueF1 inattendu')
    for nom in phys:
        dest=temp/nom;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SIM/nom,dest)
    shutil.copy2(F2,temp/F2.name)
    # La copie TEMP n'a pas le dossier outils voisin de la racine reelle.
    # Utiliser explicitement les DLL deja installees, sans rien installer.
    os.environ.setdefault('CSXCAD_INSTALL_PATH',str(SIM.parent/'outils/openEMS'))
    sys.path.insert(0,str(temp))
    import numpy as np
    M=importlib.import_module('fdtd_maille_controlee')
    B=importlib.import_module('banc')
    exige(Path(M.ICI)==temp and Path(B.__file__).parent==temp,'Import hors copieTemp')
    inventaire=M._sources();exige(inventaire==dict(phys,**{'fdtd_maille_controlee.py':sourceF2}),'Sources10 incoherentes')
    exige(M.NOM_MOTEUR=='maillage_controle_v2','Tag moteur')
    exige(M.NIVEAUX=={'base':dict(mailles_par_lambda=16,mailles_par_lambda_air=16,maille_min=.15),
        'fin':dict(mailles_par_lambda=24,mailles_par_lambda_air=16,maille_min=.10)},'Presets')
    def interdit(*a,**k):raise RuntimeError('Run/calibration interdit dans ce controle')
    M.lance=M.serie=M._calibre_dt=interdit
    resultats=[]
    for nom in ('diamant_uwb','diamant_uwb_x18','vivaldi_tomographie'):
        mod=M.charge_antenne(nom)
        for niveau in ('base','fin'):
            grids={};politiques={}
            with np.load(PROTO/(nom+'_'+niveau+'_GRILLE_SEULE.npz')) as z:
                reference={a:z[a].copy() for a in 'xyz'}
            for duree in (12,16):
                montage=B.Montage(acquisition=B.Acquisition(f_min=1e9,f_max=6.3e9,points=213),
                    maillage=B.Maillage(**M.NIVEAUX[niveau],n_pas_max=500000,duree_ns=duree))
                dossier=temp/(nom+'_'+niveau+'_'+str(duree)+'ns_AUCUN_RUN')
                fdtd,csx,port,dest=M.construit(montage,mod,dossier=str(dossier),n_pas=2,duree_ns=duree)
                g={a:np.asarray(csx.GetGrid().GetLines(a),dtype='<f8') for a in 'xyz'}
                for axe in 'xyz':
                    exige(g[axe].tobytes()==reference[axe].astype('<f8').tobytes(),
                        'Axes differents du prototype10 :'+nom+'/'+niveau+'/'+axe+'/'+str(duree))
                exige(not dossier.exists(),'Dossier solveur cree')
                politique=M.politique_maillage(montage,mod,csx)
                exige(politique['U_x0_primaire_exact'] and politique['I_dual_hsur2_ecart_mm']<1e-14,'Sondes')
                exige(politique['cellules_normales']==(11 if niveau=='base' else 17),'Normales')
                exige(all(v['cellules_transversales']==v['cellules_longitudinales']==(4 if niveau=='base' else 6) for v in politique['vias']),'Vias')
                grids[duree]={a:hashlib.sha256(g[a].tobytes()).hexdigest() for a in 'xyz'}
                politiques[duree]=politique
                resume=M.resume_maillage(csx)
                del fdtd,csx,port
            exige(grids[12]==grids[16] and politiques[12]==politiques[16],'Duree affecte grille/politique')
            resultats.append(dict(antenne=nom,niveau=niveau,axes_sha256_12ns=grids[12],
                axes_sha256_16ns=grids[16],prototype10_identique_bytes=True,grille=resume,politique=politiques[12]))
            print(nom,niveau,resume['cellules'],'cellules : axes exacts10 et12/16 identiques',flush=True)
    probe=temp/'preuve_tag_hors_simulation';probe.mkdir()
    test_tag={}
    for etat in ('prepare','termine','echec'):
        m={'etat':etat};M._sauve_manifeste(probe,m)
        test_tag[etat]=lit(probe/'simulation_manifest.json')['moteur']
    exige(set(test_tag.values())=={M.NOM_MOTEUR},'Tag perdu dans manifeste')
    cas_extra=B.Montage(maillage=B.Maillage(mailles_par_lambda=32,mailles_par_lambda_air=16,maille_min=.08))
    extra=M._reglages_controles(cas_extra,M.charge_antenne('diamant_uwb'))
    exige(extra['normal']==21 and extra['via']==8,'Formules de raffinement')
    try:
        M._reglages_controles(B.Montage(),M.charge_antenne('diamant_uwb'))
    except ValueError:refus_inconnu=True
    else:refus_inconnu=False
    exige(refus_inconnu,'Configuration plus grossiere acceptee')
    apres={n:sha(SIM/n) for n in attendu}
    exige(avant==apres and sha(F2)==sourceF2 and M._sources()==inventaire,'Sources modifiees')
    import openEMS,CSXCAD,scipy
    r=dict(schema='preuve_native_f2_grilles_sans_run_v1',utc=datetime.now(timezone.utc).isoformat(),
        aucun_Run=True,aucune_calibration=True,aucune_qualification=True,
        script_sha256=sha(__file__),F2_sha256=sourceF2,copie_TEMP_conservee=str(temp),
        sources10=inventaire,sources17_avant=avant,sources17_apres=apres,
        python=sys.version,numpy=np.__version__,scipy=scipy.__version__,
        openEMS=getattr(openEMS,'__version__','inconnu'),CSXCAD=getattr(CSXCAD,'__version__','inconnu'),
        fonctionsF1_AST_inchangees=identiques,lance_seule_addition_politique=True,
        tags_manifeste=test_tag,reglages_plus_fins_sans_grille=extra,
        configuration_inconnue_refusee=refus_inconnu,resultats=resultats)
    with SORTIE.open('x',encoding='utf-8',newline='\n') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print('Preuve',SORTIE,'SHA256',sha(SORTIE),flush=True)


if __name__=='__main__':main()
