"""Relecture de compatibilite ph des21profils fermes explicitement listes.

Python ph, -B, un fil, Agg. Aucun calcul, CalcPort, comparaison globale,
selection ni livraison. Un seul JSON plat neuf est cree a cote du script.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import traceback

sys.dont_write_bytecode = True
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[n]='1'
os.environ['MPLBACKEND']='Agg'
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[1]
BASE=SIM/'resultats/pcbway_r1'
SORTIE=Path(__file__).with_suffix('.json')
ANCRAGE=SIM/'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'
ANCRAGE_SHA='47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383'
PROFILS={
    'diamant_uwb':[('base_8ns','base',8),('fin_8ns','fin',8),('fin_12ns','fin',12),
        ('base_16ns','base',16),('fin_16ns','fin',16)],
    'diamant_uwb_x18':[('base_8ns','base',8),('fin_8ns','fin',8),('fin_12ns','fin',12),
        ('tres_fin_8ns','tres_fin',8),('tres_fin_12ns','tres_fin',12),
        ('ultra_fin_8ns','ultra_fin',8),('ultra_fin_12ns','ultra_fin',12),
        ('extreme_fin_8ns','extreme_fin',8),('extreme_fin_12ns','extreme_fin',12),
        ('n30_8ns','n30',8),('n30_12ns','n30',12)],
    'vivaldi_tomographie':[('base_8ns','base',8),('fin_8ns','fin',8),('fin_12ns','fin',12),
        ('tres_fin_12ns','tres_fin',12),('tres_fin_16ns','tres_fin',16)],
}
PAIRES={
    'diamant_uwb':{'spatial':['base_16ns','fin_16ns'],'temporel':['fin_12ns','fin_16ns']},
    'diamant_uwb_x18':{'spatial':['extreme_fin_12ns','n30_12ns'],'temporel':['n30_8ns','n30_12ns']},
    'vivaldi_tomographie':{'spatial':['fin_12ns','tres_fin_12ns'],'temporel':['tres_fin_12ns','tres_fin_16ns']},
}
RAPPORTS={
    'diamant_uwb':BASE/'diamant_uwb/bilan_intermediaire_16ns.json',
    'diamant_uwb_x18':SIM/'chatGPT_critical_review/controle_extreme_fin/controle_final_n30/rapport.json',
    'vivaldi_tomographie':SIM/'chatGPT_critical_review/controle_vivaldi/controle_final_vivaldi/rapport.json',
}
PAIRES_PETIT=BASE/'journaux/reprise_qualification_adaptee.json'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def lit(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def sources():
    if sha(ANCRAGE)!=ANCRAGE_SHA:
        raise ValueError('Ancrage17sources altere')
    attendu=lit(ANCRAGE)['sources_controle_sha256']
    actuel={n:sha(SIM/n) for n in attendu}
    if len(actuel)!=17 or actuel!=attendu:
        raise ValueError('Sourcesgelees differentes de l ancrageN34')
    return actuel


def fichiers():
    # Aucun glob/rglob de BASE ou des parents des profils :21sous-arbres clos.
    return {str(p.relative_to(BASE)):sha(p)
        for antenne,profils in PROFILS.items() for nom,_,_ in profils
        for p in sorted((BASE/antenne/nom).rglob('*')) if p.is_file()}


def aplatit(prefixe,objet,resultat):
    if isinstance(objet,dict):
        for k,v in objet.items():aplatit(prefixe+'.'+k,v,resultat)
    else:
        if not isinstance(objet,(str,int,float,bool,type(None))):
            raise TypeError('Valeur non plate inattendue :'+prefixe)
        resultat[prefixe]=objet


def main():
    if SORTIE.exists():
        raise FileExistsError('Rapport deja present ; aucun ecrasement :'+str(SORTIE))
    resultat=dict(schema='compatibilite_lecture_ph_profils_fermes_v1',
        utc=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),
        executable=sys.executable,script_sha256=sha(Path(__file__)),
        objectif='compatibilite du lectorat PDF ; aucun nouveau verdict physique',
        aucun_solveur=True,aucun_CalcPort=True,aucun_Q_calcule=True,
        aucun_Q_comparer_global=True,aucune_selection_livraison=True,
        aucun_profil_actif_lu=True,OMP_NUM_THREADS=os.environ['OMP_NUM_THREADS'],
        OPENBLAS_NUM_THREADS=os.environ['OPENBLAS_NUM_THREADS'],MPLBACKEND=os.environ['MPLBACKEND'],
        ancrage=str(ANCRAGE.relative_to(SIM)),ancrage_sha256=ANCRAGE_SHA)
    avant_sources={};avant_fichiers={};entrees={};code=1
    try:
        avant_sources=sources()
        for antenne,profils in PROFILS.items():
            for nom,_,_ in profils:
                m=lit(BASE/antenne/nom/'simulation_manifest.json')
                if m['etat']!='termine':raise ValueError('Profil non clos :'+antenne+'/'+nom)
        avant_fichiers=fichiers()
        references={n:lit(p) for n,p in RAPPORTS.items()}
        contexte_petit=lit(PAIRES_PETIT)['petit']
        for nom in ('diamant_uwb_x18','vivaldi_tomographie'):
            for type_,paire in PAIRES[nom].items():
                if references[nom][type_]['profils']!=paire:
                    raise ValueError('Paire native de reference differente :'+nom+'/'+type_)
        for type_,paire in PAIRES['diamant_uwb'].items():
            if contexte_petit[type_]!=paire:raise ValueError('Paire petit contexte differente')
        resultat['petit_bilan_nomme_les_paires']=False
        resultat['petit_paires_proviennent_du_contexte_operateur_explicitement_lie']=True
        resultat['petit_limite_provenance']='Le bilan16ns ne nomme pas ses paires ; noms verifies dans reprise_qualification_adaptee.json.'
        entrees={str(p.relative_to(SIM)):sha(p) for p in [*RAPPORTS.values(),PAIRES_PETIT]}
        sys.path.insert(0,str(SIM))
        import numpy as np
        import qualifie_pcbway as Q
        import raffine_qualification_pcbway as R
        resultat['numpy']=np.__version__
        R.enregistre(Q)  # Seule extension du catalogue, en memoire.
        donnees={};nombre=0;refuses=0
        for antenne,profils in PROFILS.items():
            donnees[antenne]={}
            for nom,niveau,duree in profils:
                cle=antenne+'/'+nom
                try:
                    d=Q.charge_calcul(BASE/antenne/nom,exiger_courant=True)
                    Q.valide_campagne(*d[2:],antenne,niveau,duree)
                    donnees[antenne][nom]=d;nombre+=1
                    resultat['lecture_acceptee.'+cle]=True
                except ImportError:
                    raise  # Aucun contournement d'un import bloque.
                except Exception as erreur:
                    refuses+=1;resultat['lecture_acceptee.'+cle]=False
                    resultat['lecture_erreur.'+cle]=type(erreur).__name__+': '+str(erreur)
            if len(donnees[antenne])!=len(profils):
                continue
            initial=donnees[antenne][profils[0][0]]
            for d in donnees[antenne].values():
                if (not np.array_equal(d[0],initial[0]) or
                    any(d[2][k]!=initial[2][k] for k in ('sources_sha256','environnement')) or
                    any(d[3][k]!=initial[3][k] for k in ('geometrie_sha256','simulation_contract'))):
                    raise ValueError('Incoherence entre profils fermes :'+antenne)
        resultat['nombre_profils_acceptes']=nombre
        resultat['nombre_profils_refuses']=refuses
        if nombre!=21:raise ValueError(str(refuses)+'profils refuses par le lecteur courant ;21attendus')
        tous_identiques=True
        for antenne,paires in PAIRES.items():
            for type_,(a,b) in paires.items():
                da,db=donnees[antenne][a],donnees[antenne][b]
                courant=Q.ecarts(da[0],da[1],db[0],db[1],temporel=type_=='temporel')
                natif=references[antenne][type_]
                prefixe='metriques.'+antenne+'.'+type_
                resultat[prefixe+'.paire']=a+' -> '+b
                for champ in ('valeurs','seuils_acceptation','reussi'):
                    identique=courant[champ]==natif[champ]
                    tous_identiques=bool(tous_identiques and identique)
                    resultat[prefixe+'.'+champ+'.identique_exactement']=identique
                    aplatit(prefixe+'.'+champ+'.ph',courant[champ],resultat)
                    aplatit(prefixe+'.'+champ+'.natif',natif[champ],resultat)
        resultat['metriques_six_paires_identiques_exactement']=tous_identiques
        if not tous_identiques:raise ValueError('Difference numerique exacte ph/natif :voir champs plats')
        resultat['etat']='lecture_compatible';code=0
    except Exception as erreur:
        resultat['etat']='lecture_refusee'
        resultat['erreur_type']=type(erreur).__name__
        resultat['erreur']=str(erreur)
        resultat['trace']=traceback.format_exc()
    finally:
        try:
            apres_sources=sources();apres_fichiers=fichiers()
            resultat['sources_17_inchangees']=avant_sources==apres_sources
            resultat['fichiers_21_profils_inchanges']=avant_fichiers==apres_fichiers
            resultat['nombre_fichiers_fermes']=len(apres_fichiers)
            for phase,table in [('avant',avant_sources),('apres',apres_sources)]:
                for n,h in table.items():resultat['sources.'+phase+'.'+n]=h
            for phase,table in [('avant',avant_fichiers),('apres',apres_fichiers)]:
                for n,h in table.items():resultat['profils.'+phase+'.'+n]=h
            for n,h in entrees.items():
                resultat['references_native_sha256.'+n]=h
                if sha(SIM/n)!=h:raise ValueError('Reference native changee :'+n)
            if not resultat['sources_17_inchangees'] or not resultat['fichiers_21_profils_inchanges']:
                raise ValueError('Source ou preuve fermee changee pendant lecture')
        except Exception as erreur:
            code=1;resultat['etat']='erreur_integrite'
            resultat['erreur_integrite']=str(erreur)
        resultat['code_sortie']=code
        with SORTIE.open('x',encoding='utf-8',newline='\n') as f:
            json.dump(resultat,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in resultat.items() if k in ('etat','code_sortie','python','numpy',
        'nombre_profils_acceptes','nombre_fichiers_fermes','sources_17_inchangees',
        'fichiers_21_profils_inchanges','metriques_six_paires_identiques_exactement','erreur')},ensure_ascii=False))
    return code


if __name__=='__main__':
    raise SystemExit(main())
