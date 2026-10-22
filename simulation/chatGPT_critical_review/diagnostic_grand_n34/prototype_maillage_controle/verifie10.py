"""Controle NumPy des six grilles10, sans reconstruction ni solveur."""
from datetime import datetime,timezone
import hashlib,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
os.environ['OMP_NUM_THREADS']=os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import verifie_propositions as V
ICI=Path(__file__).resolve().parent
DOSSIER=ICI/'proposition_10_interpolations_sma_libres'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lit(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    # Reutilisation byte-exact de l'analyse des intervalles07, avec entree10.
    # Ce helper commun ecrit sa propre provenance ; aucune source07 modifiee.
    V.DOSSIER=DOSSIER
    V.main()
    commun=lit(DOSSIER/'verification_geometrique_et_cfl.json')
    assert all(v['nombre_grossissements']==0 for e in commun['controles']
               for v in e['projection_tout_objet'].values())
    rapport=lit(DOSSIER/'rapport_prototype.json')
    caps=[]
    for e in rapport['resultats']:
        with np.load(DOSSIER/e['npz']) as z:g={a:z[a].copy() for a in 'xyz'}
        eps=max(d.get('epsilon_statique',d.get('epsilon',1)) for d in e['definitions_materiaux'])
        cap_sub=299792458/6.3e9*1e3/(np.sqrt(eps)*e['politique']['lambda_substrat'])
        n,p=e['normal'],e['propagation'];h,u=e['h_mm'],e['u0_mm'];phys=e['boite_physique_mm']
        axes={}
        for i,axe in enumerate('xyz'):
            gg=g[axe];dd=np.diff(gg);mil=(gg[:-1]+gg[1:])/2
            limites=np.full(len(dd),e['air_mm'])
            sub=(mil>=phys[0][i])&(mil<=phys[1][i]);limites[sub]=np.minimum(limites[sub],cap_sub)
            if axe=='x':bloc=(mil>=-5.588)&(mil<=5.588)
            elif axe==n:bloc=(mil>=-h/3)&(mil<=4*h/3)
            else:bloc=(mil>=u-h)&(mil<=u+6.4516)
            limite=min(e['politique']['sma_max_mm'],h/e['politique']['normal']) if axe==n else e['politique']['sma_max_mm']
            limites[bloc]=np.minimum(limites[bloc],limite)
            ratio=float(np.max(dd/limites));assert ratio<=1+1e-8
            axes[axe]=dict(maximum_ratio_pas_sur_plafond=ratio,
                plus_petite_cellule_mm=float(dd.min()),plancher=e['details'][axe]['plancher_points_libres_mm'])
            assert dd.min()>=axes[axe]['plancher']*(1-1e-8)
        caps.append(dict(antenne=e['antenne'],niveau=e['niveau'],epsilon_statique=eps,
            plafond_substrat_mm=float(cap_sub),axes=axes))
        assert e['diagnostics']['U_x0_primaire_exact'] and e['diagnostics']['I_hsur2_dual_ecart_mm']<1e-14
        assert e['diagnostics']['normal_cellules']==e['politique']['normal']
        assert all(v['transversales']==v['longitudinales']==e['politique']['via'] for v in e['diagnostics']['cellules_via'])
    sortie=DOSSIER/'verification10_integrale.json'
    if sortie.exists():raise FileExistsError(sortie)
    resultat=dict(schema='controle_integral_grilles10_sans_run_v1',utc=datetime.now(timezone.utc).isoformat(),
        aucun_Run=True,aucune_qualification=True,monotonie_sur_projection_PCB_et_SMA=True,
        air_hors_PCB_non_exige_monotone=True,caps=caps,
        source_analyse_sha256=sha(__file__),helper_commun_sha256=sha(ICI/'verifie_propositions.py'),
        rapport_constructeur_sha256=sha(DOSSIER/'rapport_prototype.json'),
        rapport_commun_sha256=sha(DOSSIER/'verification_geometrique_et_cfl.json'),
        sources17=commun['sources17_apres'])
    with sortie.open('x',encoding='utf-8',newline='\n') as f:json.dump(resultat,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print('Verification10 complete : SHA256',sha(sortie))


if __name__=='__main__':main()
