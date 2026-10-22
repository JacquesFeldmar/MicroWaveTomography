"""Ecarts numeriques des13profils Grand clos ; aucun calcul FDTD."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
os.environ['OMP_NUM_THREADS']=os.environ['OPENBLAS_NUM_THREADS']='1'
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[1]
BASE=SIM/'resultats/pcbway_r1/diamant_uwb_x18'


def charge(nom,p):
    spec=importlib.util.spec_from_file_location(nom,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    sortie=ICI/'rapport_ecarts_fermes.json'
    if sortie.exists():raise FileExistsError(sortie)
    C=charge('couts_grand_diagnostic',ICI/'grilles_couts_sans_run.py')
    U=charge('numerique_independant_grand',SIM/'chatGPT_critical_review/controle_extreme_fin/analyse_extreme_fin.py')
    np=U.np;avant_sources=C.sources();avant_fichiers=C.fichiers()
    hpath=SIM/'chatGPT_critical_review/controle_extreme_fin/controle_final_n34/rapport.json'
    h=json.loads(hpath.read_text(encoding='utf-8'));d={}
    for nom in C.PROFILS:
        m=json.loads((BASE/nom/'simulation_manifest.json').read_text(encoding='utf-8'))
        if m['etat']!='termine':raise ValueError('Profil non clos :'+nom)
        for fichier,digest in h['preuves'][nom].items():
            if sha(BASE/nom/fichier)!=digest:raise ValueError('Preuve helper modifiee :'+nom+'/'+fichier)
        data=np.loadtxt(BASE/nom/'s11.s1p',comments=('!','#'))
        d[nom]=(data[:,0],data[:,1]+1j*data[:,2])
    spaciales=[('base_8ns','fin_8ns'),('fin_12ns','tres_fin_12ns'),('tres_fin_12ns','ultra_fin_12ns'),
        ('ultra_fin_12ns','extreme_fin_12ns'),('extreme_fin_12ns','n30_12ns'),('n30_12ns','n34_12ns')]
    temporelles=[(n+'_8ns',n+'_12ns') for n in ('fin','tres_fin','ultra_fin','extreme_fin','n30','n34')]
    def mesure(paire,type_):return dict(profils=list(paire),**U.ecarts_independants(d[paire[0]],d[paire[1]],type_))
    sp=[mesure(p,'spatial') for p in spaciales];te=[mesure(p,'temporel') for p in temporelles]
    for type_,e in [('spatial',sp[-1]),('temporel',te[-1])]:
        if any(e[k]!=h[type_][k] for k in ('valeurs','seuils_acceptation','reussi','points_masque_db')):
            raise ValueError('Difference des valeurs reproduites :'+type_)
    f,s=d['n30_12ns'];t=d['n34_12ns'][1];delta=abs(s-t)
    garde=(abs(s)>=.1)&(abs(t)>=.1);db=abs(20*np.log10(abs(s)/abs(t)))
    pics=[]
    for i in np.argsort(delta)[-12:][::-1]:
        pics.append(dict(frequence_hz=float(f[i]),ecart_complexe=float(delta[i]),
            module_n30=float(abs(s[i])),module_n34=float(abs(t[i])),
            ecart_modules=float(abs(abs(s[i])-abs(t[i]))),ecart_db=float(db[i]),dans_masque_db=bool(garde[i])))
    bandes=[]
    for lo,hi in [(1,2),(2,3),(3,4),(4,4.15),(4.15,4.3),(4.3,5),(5,6.31)]:
        ids=(f>=int(round(lo*1e9)))&(f<int(round(hi*1e9)))
        bandes.append(dict(bande_ghz=[lo,hi],points=int(ids.sum()),
            rms_complexe=float(np.sqrt(np.mean(delta[ids]**2))),
            fraction_energie_ecart=float(np.sum(delta[ids]**2)/np.sum(delta**2))))
    ancien12=[mesure((n+'_12ns','n34_12ns'),'spatial') for n in ('fin','tres_fin','ultra_fin','extreme_fin','n30')]
    apres_sources=C.sources();apres_fichiers=C.fichiers()
    if avant_sources!=apres_sources or avant_fichiers!=apres_fichiers:raise ValueError('Source/preuve modifiee')
    rapport=dict(schema='diagnostic_ecarts_grand_n34_fermes_v1',utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__),helper_sha256=sha(hpath),aucun_fdtd=True,qualification_officielle=False,
        profils=list(C.PROFILS),nombre_profils=13,comparaisons_spatiales_successives=sp,
        comparaisons_temporelles=te,pics_ecart_complexe_n30_n34=pics,
        frequences_ecart_complexe_superieur_0p05_hz=f[delta>.05].tolist(),
        frequences_ecart_db_superieur_1_dans_masque_hz=f[garde&(db>1)].tolist(),
        energie_ecart_par_bande=bandes,anciens12ns_contre_n34=ancien12,
        source17_identiques=avant_sources==apres_sources,profils360_identiques=avant_fichiers==apres_fichiers,
        sources_17_sha256=apres_sources,fichiers_13_profils_sha256=apres_fichiers,
        interpretation='Metriques existantes reproduites ; aucune nouvelle selection ni modification des criteres.')
    with sortie.open('x',encoding='utf-8',newline='\n') as out:json.dump(rapport,out,ensure_ascii=False,indent=2,allow_nan=False);out.write('\n')
    print(json.dumps(dict(rapport=str(sortie),spatial=sp[-1],temporel=te[-1],
        pics=pics[:4],aucun_ancien12ns_passe=not any(p['reussi'] for p in ancien12)),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
