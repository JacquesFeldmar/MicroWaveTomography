"""Lecture des cinq profils PETIT F2 clos ; aucun FDTD ni profil actif lu."""
from datetime import datetime,timezone
import hashlib,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[n]='1'
os.environ['MPLBACKEND']='Agg'
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[1]
sys.path.insert(0,str(SIM))
import numpy as np
import qualifie_pcbway as Q

BASE=SIM/'resultats/pcbway_maille_controlee_v2/diamant_uwb'
PROFILS=(('base_8ns','base',8),('base_12ns','base',12),
    ('fin_8ns','fin',8),('fin_12ns','fin',12),('fin_16ns','fin',16))
F1=SIM/'resultats/pcbway_r1/diamant_uwb/fin_16ns'
GEL=SIM/'chatGPT_critical_review/integration_finale_f2/gel_campagne_F2.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lit(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def exige(x,m):
    if not x:raise ValueError(m)
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def ecarts_numpy(fa,sa,fb,sb,temporel=False):
    exige(np.array_equal(fa,fb),'Frequences differentes')
    delta=np.abs(sa-sb)
    garde=(np.abs(sa)>=.1)&(np.abs(sb)>=.1)
    db=np.abs(20*np.log10(np.maximum(np.abs(sa),1e-15)/np.maximum(np.abs(sb),1e-15)))
    phase=np.abs(np.angle(sa*np.conj(sb),deg=True))
    valeurs=dict(maximum_complexe=float(np.max(delta)),
        rms_complexe=float(np.sqrt(np.mean(delta**2))),
        percentile95_db=float(np.percentile(db[garde],95)) if garde.any() else None,
        percentile95_phase_deg=float(np.percentile(phase[garde],95)) if garde.any() else None)
    seuils=dict(maximum_complexe=.015 if temporel else .05,
        rms_complexe=.005 if temporel else .02,percentile95_db=.5 if temporel else 1.)
    reussi=all(valeurs[k] is not None and valeurs[k]<=v for k,v in seuils.items())
    j=int(np.argmax(delta))
    return dict(valeurs=valeurs,seuils_acceptation=seuils,reussi=reussi,
        masque_db_indices=np.flatnonzero(garde).tolist(),nombre_masque_db=int(garde.sum()),
        maximum_complexe_frequence_hz=float(fa[j]),
        points_ecart_complexe_principaux=[dict(frequence_hz=float(fa[k]),
            delta_complexe=float(delta[k]),module_a=float(abs(sa[k])),module_b=float(abs(sb[k])),
            delta_db=float(db[k]),dans_masque_db=bool(garde[k]),phase_ecart_deg=float(phase[k]))
            for k in np.argsort(delta)[-10:][::-1]])


def main():
    sortie=ICI/'lecture_independante.json'
    exige(not sortie.exists(),'Rapport deja present')
    gel=lit(GEL);attendus={**gel['sources_physiques_sha256'],**gel['controles_sha256']}
    exige(len(attendus)==18,'Inventaire gele attendu18')
    avant={n:sha(SIM/n) for n in attendus};exige(avant==attendus,'Source gelee changee')
    manifests_avant={nom:sha(BASE/nom/'simulation_manifest.json') for nom,_,_ in PROFILS}
    f1manif_avant=sha(F1/'simulation_manifest.json')
    fermes={};refcommun=None
    for nom,niveau,duree in PROFILS:
        chemin=BASE/nom
        f,s,m,q=Q.charge_calcul(chemin,exiger_courant=True)
        Q.valide_campagne(m,q,'diamant_uwb',niveau,duree)
        exige(Q.identite_moteur(m,q)==Q.MOTEUR_F2,'Tag moteur nonF2')
        commun=dict(sources=m['sources_sha256'],environnement=m['environnement'],
            materiaux=m['materiaux'],geometrie=q['geometrie'],contrat=q['simulation_contract'],
            frequences=f.tolist())
        if refcommun is None:refcommun=canon(commun)
        exige(canon(commun)==refcommun,'Contrat/physique/env/frequences differents entreF2')
        fermes[nom]=(f,s,m,q)
    comparaison={}
    for nom,a,b,temps in (('spatial','base_12ns','fin_12ns',False),
                          ('temporel','fin_12ns','fin_16ns',True)):
        fa,sa,*_=fermes[a];fb,sb,*_=fermes[b]
        independant=ecarts_numpy(fa,sa,fb,sb,temps)
        natif=Q.ecarts(fa,sa,fb,sb,temporel=temps)
        for k in ('valeurs','seuils_acceptation','reussi'):
            exige(independant[k]==natif[k],'Desaccord NumPy/Q :'+nom+'/'+k)
        comparaison[nom]=dict(profils=[a,b],numpy=independant,Q=natif,accord_exact=True)
    Q.verifie_grilles_temporelles([BASE/'fin_12ns',BASE/'fin_16ns'])
    dt12=fermes['fin_12ns'][2]['execution']['dt_s'];dt16=fermes['fin_16ns'][2]['execution']['dt_s']
    exige(np.asarray(dt12,dtype='<f8').tobytes()==np.asarray(dt16,dtype='<f8').tobytes(),'dt temporel nonidentique')
    diagnostics=[]
    for nom,_,_ in PROFILS:
        f,s,m,q=fermes[nom];db=20*np.log10(np.maximum(abs(s),1e-15));j=int(np.argmin(db))
        diagnostics.append(dict(profil=nom,manifeste_sha256=manifests_avant[nom],
            maximum_module=float(abs(s).max()),passivite=bool(abs(s).max()<=1.005),
            minimum_S11_db=float(db[j]),frequence_minimum_hz=float(f[j]),
            maillage=m['maillage'],dt_s=m['execution']['dt_s'],
            FDTD_direct=not m.get('derive_sondes',False),indicateurs=Q.indicateurs(f,s)))
    # Lecture d'une reference F1 fermee, exclusivement diagnostique.
    f,s,m,q=Q.charge_calcul(F1,exiger_courant=False)
    exige(Q.identite_moteur(m,q)==Q.MOTEUR_F1,'Reference historique nonF1')
    rf,rs,*_=fermes['fin_16ns']
    inter=ecarts_numpy(f,s,rf,rs)
    diagnosticF1=dict(profil=str(F1.relative_to(SIM)),manifeste_sha256=f1manif_avant,
        source_physique_sha256=m['sources_sha256'],environnement=m['environnement'],
        maximum_module=float(abs(s).max()),indicateurs=Q.indicateurs(f,s),
        comparaison_valeurs_F1fin16_F2fin16=inter,
        usage='DIAGNOSTIC SEULEMENT : aucune paire inter-moteurs ne qualifie la convergenceF2',
        seuils_inter_moteurs_non_utilises_pour_qualification=True)
    apres={n:sha(SIM/n) for n in attendus}
    manifests_apres={nom:sha(BASE/nom/'simulation_manifest.json') for nom,_,_ in PROFILS}
    exige(avant==apres==attendus and manifests_avant==manifests_apres and
           f1manif_avant==sha(F1/'simulation_manifest.json'),'Preuve/source changee pendant lecture')
    r=dict(schema='lecture_independante_petit_losange_F2_v1',utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__),python=sys.version,numpy=np.__version__,threads_analyse=1,
        aucun_solveur=True,aucune_construction_maillage=True,aucune_selection_ecrite=True,
        gel_sha256=sha(GEL),sources18_avant=avant,sources18_apres=apres,
        cinq_manifestes_sha256_avant=manifests_avant,cinq_manifestes_sha256_apres=manifests_apres,
        cinq_profils_Q_valides=True,communs_physique_contrat_geometrie_env_frequences=True,
        diagnostics_profils=diagnostics,comparaisons_F2=comparaison,
        temps_axes_NPZ_et_dt_octets_identiques=True,reference='fin_16ns',
        reference_passive=bool(abs(rs).max()<=1.005),reference_maximum_module=float(abs(rs).max()),
        diagnostic_historique_F1=diagnosticF1,
        convergence_F2_petit_acquise=bool(comparaison['spatial']['numpy']['reussi'] and comparaison['temporel']['numpy']['reussi']),
        qualification_globale_effectuee=False,
        conclusion='Les cinq calculs sont integres et lisibles ; echec spatialF2, controle temporel reussi. Antenne non qualifiee par cette campagne.',
        limites=['Aucune cause scientifique du desaccord spatial n\'est demontree par ces seules valeurs.',
                 'Le debit CPU ou stdout silencieux ne prouvent ni avancement ni validite physique ; aucune observation de profil actif ici.',
                 'La comparaison F1/F2 est conservee pour diagnostic et ne remplace pas les criteres F2 fixes.'])
    with sortie.open('x',encoding='utf-8',newline='\n') as out:json.dump(r,out,ensure_ascii=False,indent=2,allow_nan=False);out.write('\n')
    print(json.dumps(dict(rapport=str(sortie),sha256=sha(sortie),
        spatial=comparaison['spatial']['numpy']['valeurs'],
        temporel=comparaison['temporel']['numpy']['valeurs'],
        frequence_ecart_spatial_max_hz=comparaison['spatial']['numpy']['maximum_complexe_frequence_hz'],
        reference_maximum_module=r['reference_maximum_module'],sources18_inchangees=True),ensure_ascii=False))


if __name__=='__main__':main()
