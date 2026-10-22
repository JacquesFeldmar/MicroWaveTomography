"""Analyse des NPZ prototypes deja construits, sans import de projet ni Run."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode=True
os.environ['OMP_NUM_THREADS']=os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[2]
DOSSIER=ICI/'proposition_07_plancher_cellules_libres'
ANCRE=SIM/'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lit(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def exige(x,m):
    if not x:raise ValueError(m)


def scan(a,b,lo,hi):
    """Toutes les zones du pas piecewise constant, pas un echantillonnage."""
    t=np.unique(np.r_[lo,hi,a[(a>lo)&(a<hi)],b[(b>lo)&(b<hi)]])
    p=(t[:-1]+t[1:])/2
    da=np.diff(a)[np.clip(np.searchsorted(a,p,side='right')-1,0,len(a)-2)]
    db=np.diff(b)[np.clip(np.searchsorted(b,p,side='right')-1,0,len(b)-2)]
    ratio=db/da;j=int(np.argmax(ratio))
    mauvais=db>da*(1+1e-8)
    return dict(bornes_mm=[lo,hi],intervalles_communs=len(p),
        nombre_grossissements=int(mauvais.sum()),
        fraction_longueur_grossie=float(np.diff(t)[mauvais].sum()/(hi-lo)),
        maximum_ratio_fin_sur_base=float(ratio[j]),point_pire_mm=float(p[j]),
        pas_base_pire_mm=float(da[j]),pas_fin_pire_mm=float(db[j]),
        maille_max_base_mm=float(da.max()),maille_max_fin_mm=float(db.max()))


def minima(g):
    r={}
    for a,v in g.items():
        d=np.diff(v);mn=d.min()
        jj=np.flatnonzero(np.isclose(d,mn,rtol=1e-8,atol=1e-10))
        r[a]=dict(minimum_mm=float(mn),nombre_occurrences=len(jj),
            cellules_mm=[[float(v[j]),float(v[j+1])] for j in jj])
    return r


def main():
    sortie=DOSSIER/'verification_geometrique_et_cfl.json'
    exige(not sortie.exists(),'Sortie deja presente')
    exige(sha(ANCRE)=='47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383','Ancrage change')
    attendu=lit(ANCRE)['sources_controle_sha256']
    avant={n:sha(SIM/n) for n in attendu}
    exige(avant==attendu,'17sources changees')
    rapport=lit(DOSSIER/'rapport_prototype.json')
    exige(sha(DOSSIER/'construit_prototype_exact.py')==rapport['script_sha256'],'Sourceprototype non conforme')
    groupes={}
    for e in rapport['resultats']:
        exige(sha(DOSSIER/e['npz'])==e['npz_sha256'],'NPZ modifie')
        with np.load(DOSSIER/e['npz']) as z:g={a:z[a].copy() for a in 'xyz'}
        groupes.setdefault(e['antenne'],{})[e['niveau']]=(e,g)
    controles=[]
    for nom,niveaux in groupes.items():
        e,a=niveaux['base'];f,b=niveaux['fin']
        n,p=e['normal'],e['propagation'];h,u=e['h_mm'],e['u0_mm']
        via=e['diagnostics']['cellules_via'][0]
        zones={'x_sma':('x',-5.588,5.588),
               'normale_bloc':(n,-h/3,4*h/3),
               'propagation_sma':(p,u-h,via['u_mm']+.4826)}
        sc={k:scan(a[axe],b[axe],lo,hi) for k,(axe,lo,hi) in zones.items()}
        exige(all(v['nombre_grossissements']==0 for v in sc.values()),'Grossissement dans bloc critique :'+nom)
        pml={axe:bool(np.array_equal(a[axe][:9],b[axe][:9]) and
            np.array_equal(a[axe][-9:],b[axe][-9:])) for axe in 'xyz'}
        exige(all(pml.values()),'PML modifiees')
        corps={axe:scan(a[axe],b[axe],e['boite_physique_mm'][0][i],
              e['boite_physique_mm'][1][i]) for i,axe in enumerate('xyz')}
        controles.append(dict(antenne=nom,blocs_critiques=sc,projection_tout_objet=corps,
            pml8_identiques_bits=pml,minima_base=minima(a),minima_fin=minima(b),
            limitation='Les points libres du corps hors blocs restent non emboites ; leurs eventuels grossissements locaux sont mesures explicitement.'))
    # Seul profil historique lu, ferme depuis09:06:36Z : comparaison du
    # cout CFL, pas comparaison de S11 ni qualification inter-moteurs.
    historique=SIM/'resultats/pcbway_r1/vivaldi_tomographie/ultra_fin_16ns'
    fichiers={n:sha(historique/n) for n in ('simulation_manifest.json','maillage.npz')}
    m=lit(historique/'simulation_manifest.json')
    exige(m['etat']=='termine','Historique V non clos')
    with np.load(historique/'maillage.npz') as z:old={a:z[a].copy() for a in 'xyz'}
    reference=dict(profil=str(historique.relative_to(SIM)),fichiers_sha256=fichiers,
        minima=minima(old),CFL_s=m['maillage']['dt_cfl_vide_s'],
        dt_operateur_s=m['execution']['dt_s'],
        ratio_dt_CFL=m['execution']['dt_s']/m['maillage']['dt_cfl_vide_s'])
    apres={n:sha(SIM/n) for n in attendu}
    exige(avant==apres,'Sources changees pendant lecture')
    exige(fichiers=={n:sha(historique/n) for n in fichiers},'Preuve historique modifiee')
    resultat=dict(schema='verification_geometrique_prototype_sans_run_v1',
        utc=datetime.now(timezone.utc).isoformat(),analyseur_sha256=sha(__file__),
        rapport_prototype_sha256=sha(DOSSIER/'rapport_prototype.json'),
        sources17_avant=avant,sources17_apres=apres,controles=controles,
        comparaison_CFL_VUF_herite=reference,
        aucun_Run=True,aucun_test_solveur=True,aucune_qualification=True)
    with sortie.open('x',encoding='utf-8',newline='\n') as out:
        json.dump(resultat,out,ensure_ascii=False,indent=2,allow_nan=False)
        out.write('\n')
    print(json.dumps({v['antenne']:{k:x['maximum_ratio_fin_sur_base'] for k,x in v['blocs_critiques'].items()} for v in controles},ensure_ascii=False))
    print('Rapport',sortie,'SHA256',sha(sortie))


if __name__=='__main__':main()
