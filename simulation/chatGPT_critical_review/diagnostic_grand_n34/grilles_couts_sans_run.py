"""Diagnostic Grand clos et constructions38/42 : AUCUN Run/calibrage FDTD.

Seuls13profils fermes sont lus. Les nouvelles grilles restent des objets de
diagnostic, dans ce dossier, jamais des profils ou preuves de qualification.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[n]='1'
os.environ['MPLBACKEND']='Agg'
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[1]
BASE=SIM/'resultats/pcbway_r1/diamant_uwb_x18'
JOURNAUX=SIM/'resultats/pcbway_r1/journaux'
ANCRE=SIM/'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'
PROFILS=('base_8ns','fin_8ns','fin_12ns','tres_fin_8ns','tres_fin_12ns',
    'ultra_fin_8ns','ultra_fin_12ns','extreme_fin_8ns','extreme_fin_12ns',
    'n30_8ns','n30_12ns','n34_8ns','n34_12ns')
sys.path.insert(0,str(SIM))
import numpy as np
import qualifie_pcbway as Q
import raffine_qualification_plus_pcbway as PLUS


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lit(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def exige(c,m):
    if not c:raise ValueError(m)
def sources():
    exige(sha(ANCRE)=='47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383','Ancrage modifie')
    attendu=lit(ANCRE)['sources_controle_sha256'];actuel={n:sha(SIM/n) for n in attendu}
    exige(len(actuel)==17 and actuel==attendu,'Sources17modifiees');return actuel
def fichiers():
    return {str(p.relative_to(BASE)):sha(p) for nom in PROFILS
        for p in sorted((BASE/nom).rglob('*')) if p.is_file()}
def interdit(*a,**kw):raise RuntimeError('Tout Run/calibrage/calcul global est interdit')
def cellule(g,p):
    distance=float(np.min(abs(g-p)));i=int(np.clip(np.searchsorted(g,p,side='right')-1,0,len(g)-2))
    return dict(position_mm=float(p),distance_ligne_plus_proche_mm=distance,
        point_sur_ligne=distance<1e-8,bornes_mm=[float(g[i]),float(g[i+1])],
        largeur_mm=float(g[i+1]-g[i]),fraction=float((p-g[i])/(g[i+1]-g[i])))
def caract(g):
    axes={a:dict(lignes=len(g[a]),minimum_mm=float(np.diff(g[a]).min()),
        maximum_mm=float(np.diff(g[a]).max()),bornes_mm=[float(g[a][0]),float(g[a][-1])],
        entree_pml8_mm=[float(g[a][8]),float(g[a][-9])],sha256=hashlib.sha256(g[a].astype('<f8').tobytes()).hexdigest()) for a in 'xyz'}
    cfl=1/(299792458*np.sqrt(sum(1/(axes[a]['minimum_mm']*1e-3)**2 for a in 'xyz')))
    return dict(axes=axes,cellules=int(np.prod([len(g[a])-1 for a in 'xyz'])),
        points=int(np.prod([len(g[a]) for a in 'xyz'])),dt_cfl_vide_s=float(cfl),
        x_flanc_port=cellule(g['x'],1.2275619047618136),
        y_apres_port=cellule(g['y'],-35.73702380952378),
        z_au_dessus_cuivre=cellule(g['z'],1.6277777777777778),
        bord_microstrip_x=cellule(g['x'],1.55),raccord_y=cellule(g['y'],-18),
        position_ligne_U_la_plus_proche_x0_mm=float(g['x'][np.argmin(abs(g['x']))]),
        lignes_diametre_via_x_mm=g['x'][(g['x']>=4.0894-1e-8)&(g['x']<=4.5466+1e-8)].tolist(),
        lignes_diametre_via_y_mm=g['y'][(g['y']>=-30.2596-1e-8)&(g['y']<=-29.8024+1e-8)].tolist())


def main():
    sortie=ICI/'rapport_grilles_couts.json'
    exige(not sortie.exists(),'Rapport deja present')
    a=lit(JOURNAUX/'fin_queue_n34_observee_automatiquement.json')
    f=lit(JOURNAUX/'fin_analyse_n34_automatique.json')
    exige(a['code_terminal']==0 and f['code_terminal_file']==0 and f['code_terminal_analyse'] in (0,2),'Cloture N34 non attestee')
    avant_sources=sources()
    for nom in PROFILS:exige(lit(BASE/nom/'simulation_manifest.json')['etat']=='termine','Profil non clos :'+nom)
    avant_fichiers=fichiers();grilles={};evolution=[]
    for nom in PROFILS:
        with np.load(BASE/nom/'maillage.npz',allow_pickle=False) as z:g={a:z[a].copy() for a in 'xyz'}
        grilles[nom]=g;m=lit(BASE/nom/'simulation_manifest.json')
        evolution.append(dict(profil=nom,grille=caract(g),execution=m['execution'],
            montage_maillage=m['montage']['maillage'],geometrie_sha256=m['geometrie_sha256']))
    stats=np.loadtxt(BASE/'n34_12ns/openEMS_stats.txt',comments='%')
    run=np.loadtxt(BASE/'n34_12ns/openEMS_run_stats.txt',comments='%')
    fin=run[run[:,0]>=.8*run[-1,0],2]
    debit_fin=float(np.median(fin));debit_global=float(stats[5])
    n34=caract(grilles['n34_12ns']);dt_actual=float(stats[1])
    PLUS.enregistre(Q)
    Q.calcule=Q.comparer=Q.F.lance=Q.F.serie=Q.F._calibre_dt=interdit
    original=Q.montage_campagne('n34',12)
    exige(Q.G.json_octets(asdict(original))==Q.G.json_octets(lit(BASE/'n34_12ns/qualification_entree.json')['montage']),
        'Montage N34 different de sa source fermee')
    module=Q.F.charge_antenne('diamant_uwb_x18');propositions=[]
    for nombre in (38,42):
        nom='GRILLE_SEULE_substrat'+str(nombre)+'_air22_port1sur14'
        npz=ICI/(nom+'.npz');exige(not npz.exists(),'Grille diagnostic deja presente')
        montage=replace(original,maillage=replace(original.maillage,mailles_par_lambda=nombre))
        fdtd,csx,port,dossier=Q.F.construit(montage,module,dossier=str(ICI/(nom+'_AUCUN_RUN')),n_pas=2,duree_ns=12)
        g={a:np.asarray(csx.GetGrid().GetLines(a),dtype='<f8') for a in 'xyz'}
        resume=caract(g)
        np.savez_compressed(npz,**g)
        # Projection depuis le vrai dt N34 et son CFL ; ce n'est PAS un dt
        # calibre sur le nouvel operateur. Aucun lancement de deux pas.
        dt_proj=dt_actual*resume['dt_cfl_vide_s']/n34['dt_cfl_vide_s']
        pas=int(np.ceil(12e-9/dt_proj))+1
        propositions.append(dict(nom=nom,montage=asdict(montage),grille=resume,
            fichier_npz=npz.name,fichier_npz_sha256=sha(npz),aucun_Run=True,
            dossier_calcul_non_cree=not Path(dossier).exists(),aucune_calibration_operateur=True,
            dt_projete_s=float(dt_proj),pas_12ns_projetes=pas,
            heures_projection_debit_fin_N34=resume['points']*pas/debit_fin/3600,
            heures_projection_debit_global_N34=resume['points']*pas/debit_global/3600,
            anciennes_lignes_N34_absentes={a:int(sum(np.min(abs(g[a]-x))>1e-8 for x in grilles['n34_12ns'][a])) for a in 'xyz'},
            note_cout='Projection indicative : ratio des CFL vides, pas impose reel inconnu ; debit observe peut changer.'))
        del fdtd,csx,port
    # Union naive : diagnostic algebrique, aucune construction FDTD.
    union={a:Q.F._uniques(np.r_[grilles['n30_12ns'][a],grilles['n34_12ns'][a]]) for a in 'xyz'}
    uni=caract(union)
    travail_union=uni['cellules']/n34['cellules']*n34['dt_cfl_vide_s']/uni['dt_cfl_vide_s']
    apres_sources=sources();apres_fichiers=fichiers()
    exige(avant_sources==apres_sources and avant_fichiers==apres_fichiers,'Source/preuve changee')
    rapport=dict(schema='diagnostic_grand_n34_grilles_couts_v1',utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__),python=sys.version,numpy=np.__version__,fils=1,
        versions_constructeur={n:getattr(sys.modules.get(n),'__version__',None) for n in ('openEMS','CSXCAD','scipy')},
        aucun_Run=True,aucun_nouveau_profil=True,qualification_officielle=False,
        nombre_fichiers_fermes=len(apres_fichiers),sources_17_sha256_avant=avant_sources,sources_17_sha256_apres=apres_sources,
        fichiers_13_profils_sha256_avant=avant_fichiers,fichiers_13_profils_sha256_apres=apres_fichiers,
        attestations=dict(file=a,analyse=f,code_hote_observateur_signale_par_root=1,
            distinction='File physique0 ; helper2 echec numerique ; hote observateur1 distinct, jamais assimile au codefile.'),
        evolution13profils=evolution,n34_reel=dict(points_operateur=int(stats[0]),dt_s=dt_actual,
            pas=int(stats[2]),temps_solveur_s=float(stats[4]),debit_global_cellules_s=debit_global,
            debit_median_dernier_cinquieme_cellules_s=debit_fin),
        grilles_proposees_sans_run=propositions,union_naive=dict(grille=uni,
            facteur_cellules_pas_sur_CFL_vides=float(travail_union),recommandee=False),
        limites=['Pas de duree ou stabilite operateur validee pour les propositions ; aucunFDTD.',
            'Meme air/port nominaux ne garantissent pas des lignes libres ou des sondes identiques.',
            'Les couts sont des projections, pas des engagements ni des simulations qualifiees.'])
    with sortie.open('x',encoding='utf-8',newline='\n') as out:json.dump(rapport,out,ensure_ascii=False,indent=2,allow_nan=False);out.write('\n')
    print(json.dumps({'rapport':str(sortie),'sources_inchangees':17,'fichiers_inchanges':len(apres_fichiers),
        'propositions':[{'N':p['montage']['maillage']['mailles_par_lambda'],'cellules':p['grille']['cellules'],
            'dt_projete_s':p['dt_projete_s'],'heures':[p['heures_projection_debit_fin_N34'],p['heures_projection_debit_global_N34']]} for p in propositions]},ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
