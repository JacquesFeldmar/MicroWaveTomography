"""Conserve les cinq grilles09 existantes et l'echec Vfin, sans reconstruire."""
from datetime import datetime,timezone
import hashlib,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
os.environ['OMP_NUM_THREADS']=os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import verifie_propositions as V
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[2]
DOSSIER=ICI/'proposition_09_base_protegee_dans_pcb'
ANCRE=SIM/'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lit(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    sortie=DOSSIER/'rapport_partiel_et_echec.json'
    if sortie.exists():raise FileExistsError(sortie)
    a=lit(ANCRE)['sources_controle_sha256'];avant={n:sha(SIM/n) for n in a}
    assert avant==a and len(a)==17
    original=lit(ICI/'proposition_07_plancher_cellules_libres/rapport_prototype.json')
    modeles={(e['antenne'],e['niveau']):e for e in original['resultats']}
    disponibles=[('diamant_uwb','base'),('diamant_uwb','fin'),
        ('diamant_uwb_x18','base'),('diamant_uwb_x18','fin'),('vivaldi_tomographie','base')]
    resultats=[];groupes={}
    for nom,niveau in disponibles:
        e=modeles[nom,niveau]
        f=DOSSIER/(nom+'_'+niveau+'_GRILLE_SEULE.npz')
        with np.load(f) as z:g={a:z[a].copy() for a in 'xyz'}
        groupes.setdefault(nom,{})[niveau]=g
        mi=V.minima(g)
        cfl=float(1/(299792458*np.sqrt(sum(1/(v['minimum_mm']*1e-3)**2 for v in mi.values()))))
        points=int(np.prod([len(g[a]) for a in 'xyz']))
        cellules=int(np.prod([len(g[a])-1 for a in 'xyz']))
        eps=max(d.get('epsilon_statique',d.get('epsilon',1)) for d in e['definitions_materiaux'])
        lam=299792458/6.3e9*1e3/(np.sqrt(eps)*e['politique']['lambda_substrat'])
        n,p=e['normal'],e['propagation'];h,u=e['h_mm'],e['u0_mm']
        caps={};ratio={}
        for i,axe in enumerate('xyz'):
            gg=g[axe];d=np.diff(gg);mil=(gg[:-1]+gg[1:])/2
            cap=np.full(len(d),e['air_mm'])
            boite=e['boite_physique_mm']
            masque=(mil>=boite[0][i])&(mil<=boite[1][i]);cap[masque]=np.minimum(cap[masque],lam)
            if axe=='x':masque=(mil>=-5.588)&(mil<=5.588)
            elif axe==n:masque=(mil>=-h/3)&(mil<=4*h/3)
            else:masque=(mil>=u-h)&(mil<=u+6.4516)
            cible=min(e['politique']['sma_max_mm'],h/e['politique']['normal']) if axe==n else e['politique']['sma_max_mm']
            cap[masque]=np.minimum(cap[masque],cible)
            caps[axe]=dict(maximum_ratio_pas_sur_cap=float(np.max(d/cap)),respecte=bool(np.all(d<=cap*(1+1e-8))))
            ratio[axe]=float(np.max(np.maximum(d[1:]/d[:-1],d[:-1]/d[1:])))
        assert all(v['respecte'] for v in caps.values()) and max(ratio.values())<=1.5*(1+1e-8)
        dnorm=g[n][(g[n]>=0)&(g[n]<=h)]
        diag=dict(U_x0_primaire=bool(np.any(g['x']==0)),normal_cellules=len(dnorm)-1,
            I_dual_hsur2_ecart_mm=float(np.min(abs((dnorm[:-1]+dnorm[1:])/2-h/2))),
            vias=[dict(transversal=int(sum((g['x'][:-1]>=v['x_mm']-v['diametre_mm']/2-1e-8)&(g['x'][1:]<=v['x_mm']+v['diametre_mm']/2+1e-8))),
                longitudinal=int(sum((g[p][:-1]>=v['u_mm']-v['diametre_mm']/2-1e-8)&(g[p][1:]<=v['u_mm']+v['diametre_mm']/2+1e-8))))
                for v in e['diagnostics']['cellules_via']])
        assert diag['U_x0_primaire'] and diag['normal_cellules']==e['politique']['normal'] and diag['I_dual_hsur2_ecart_mm']<1e-14
        assert all(v['transversal']==v['longitudinal']==e['politique']['via'] for v in diag['vias'])
        resultats.append(dict(antenne=nom,niveau=niveau,npz=f.name,npz_sha256=sha(f),
            cellules=cellules,points=points,minima=mi,CFLvide_s=cfl,
            dt_projete_s=.8*cfl,caps=caps,rapport_voisin_max=ratio,diagnostics=diag,
            couts_heures={str(t)+'ns':dict(debit25M=points*(int(np.ceil(t*1e-9/(.8*cfl)))+1)/25e6/3600,
                debit35M=points*(int(np.ceil(t*1e-9/(.8*cfl)))+1)/35e6/3600) for t in (12,16)}))
    comparaisons=[]
    for nom in ('diamant_uwb','diamant_uwb_x18'):
        e=modeles[nom,'base'];a,b=groupes[nom]['base'],groupes[nom]['fin']
        corps={axe:V.scan(a[axe],b[axe],e['boite_physique_mm'][0][i],e['boite_physique_mm'][1][i]) for i,axe in enumerate('xyz')}
        n,p=e['normal'],e['propagation'];h,u=e['h_mm'],e['u0_mm']
        blocs=dict(x=V.scan(a['x'],b['x'],-5.588,5.588),
            normale=V.scan(a[n],b[n],-h/3,4*h/3),propagation=V.scan(a[p],b[p],u-h,u+6.4516))
        assert all(v['nombre_grossissements']==0 for v in list(corps.values())+list(blocs.values()))
        pml={axe:bool(np.array_equal(a[axe][:9],b[axe][:9]) and np.array_equal(a[axe][-9:],b[axe][-9:])) for axe in 'xyz'}
        assert all(pml.values())
        comparaisons.append(dict(antenne=nom,projection_PCB=corps,blocs=blocs,pml_identiques_bits=pml))
    apres={n:sha(SIM/n) for n in avant};assert avant==apres
    r=dict(etat='echec_construction_vivaldi_fin_z',utc=datetime.now(timezone.utc).isoformat(),
        aucun_Run=True,aucune_qualification=True,script_sha256=sha(__file__),
        constructeur_sha256=sha(DOSSIER/'construit_prototype_exact.py'),
        preuve_source07=sha(ICI/'proposition_07_plancher_cellules_libres/rapport_prototype.json'),
        sources17_avant=avant,sources17_apres=apres,resultats_cinq_grilles=resultats,
        comparaisons_losanges=comparaisons,manquante='vivaldi_tomographie/fin',
        echec=dict(axe='z',apres_20_essais=True,
            intervalle_base_obligatoire_mm=[6.4516,6.582649999954057],
            largeur_mm=.1310499999540573,derniere_cellule_fine_SMA_mm=.08466666666666622,
            rapport_minimal_sans_subdivision=.1310499999540573/.08466666666666622,
            rapport_max_autorise=1.5,plancher_mm=.0762,
            largeur_si_deux_cellules_au_plancher_mm=2*.0762,
            conclusion='Intervalle trop grand non subdivise, trop court pour deux cellules au plancher. Conflit local ancres/plancher/gradation ; aucune relaxation.'))
    with sortie.open('x',encoding='utf-8',newline='\n') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print('Rapport',sortie,'SHA256',sha(sortie))
    print('Losanges : non-grossissement PCB/blocs et PML bits verifies ; Vfin non construit.')


if __name__=='__main__':main()
