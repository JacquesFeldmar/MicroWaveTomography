"""Contrelecture Q des13profils Grand clos, apres l'observateur N34 seulement.

Ne pas executer pendant la file77627. Apres sa fin complete et celle du helper :
  python -B -X utf8 simulation/chatGPT_critical_review/controle_extreme_fin/revue_croisee_n34/controle_croise.py
Codes :0accord/PASS ;2accord/echec numerique ;3prerequis absents ;1integrite.
Un rapport neuf uniquement ; aucun FDTD, CalcPort, bilan global ou selection.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode=True
for nom in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[nom]='1'
os.environ['MPLBACKEND']='Agg'
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[2]
BASE=SIM/'resultats/pcbway_r1/diamant_uwb_x18'
JOURNAUX=SIM/'resultats/pcbway_r1/journaux'
ANCRAGE=SIM/'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'
HELPER=ICI.parent/'analyse_extreme_fin.py'
RAPPORT_HELPER=ICI.parent/'controle_final_n34/rapport.json'
ATTESTATION=JOURNAUX/'fin_queue_n34_observee_automatiquement.json'
FIN_ANALYSE=JOURNAUX/'fin_analyse_n34_automatique.json'
SHA_ANCRAGE='47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383'
SHA_HELPER='2d5215a9e388d2c8cfd6f075eafde1776246d9de3bfe84461a9eda06d94e3b9b'
SHA_QUEUE='a882257a59d5d856fe950e724deab93e5039084ef51542152c5dad86ba035e62'
SHA_OBSERVATEUR='a76122a10a5b705f2bf13f320481afe30745e194a6b2a22829743c25c1ffceda'
PROFILS=('base_8ns','fin_8ns','fin_12ns','tres_fin_8ns','tres_fin_12ns',
    'ultra_fin_8ns','ultra_fin_12ns','extreme_fin_8ns','extreme_fin_12ns',
    'n30_8ns','n30_12ns','n34_8ns','n34_12ns')
PAIRES={'spatial':['n30_12ns','n34_12ns'],'temporel':['n34_8ns','n34_12ns']}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lit(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def exige(condition,message):
    if not condition:raise ValueError(message)
def entier(valeur):return type(valeur) is int


def prerequis():
    """Aucun acces a BASE ni import projet avant validation de ces preuves."""
    manquants=[str(p) for p in (ATTESTATION,FIN_ANALYSE,RAPPORT_HELPER) if not p.is_file()]
    if manquants:return None,manquants
    a,f,h=(lit(p) for p in (ATTESTATION,FIN_ANALYSE,RAPPORT_HELPER))
    exige(a.get('schema')=='fin_queue_n34_code_terminal_v1','Schema attestation file inconnu')
    exige(entier(a.get('code_terminal')) and a['code_terminal']==0,'File N34 non terminee avec code0')
    exige(a.get('session_associee')==77627 and a.get('pid_parent')==22904,'Identite file N34 differente')
    exige(a.get('queue_sha256')==SHA_QUEUE and a.get('observateur_sha256')==SHA_OBSERVATEUR,
        'Queue/observateur differents dans attestation')
    exige(f.get('schema')=='fin_analyse_n34_automatique_v1','Schema fin analyse inconnu')
    exige(entier(f.get('code_terminal_file')) and f['code_terminal_file']==0,'Code file different dans fin analyse')
    exige(entier(f.get('code_terminal_analyse')) and f['code_terminal_analyse'] in (0,2),
        'Analyse non close avec code0ou2')
    exige(f.get('attestation_file_sha256')==sha(ATTESTATION),'Lien SHA de l attestation incorrect')
    exige(f.get('helper_sha256')==SHA_HELPER and f.get('observateur_sha256')==SHA_OBSERVATEUR,
        'Helper/observateur differents dans fin analyse')
    exige(f.get('sources_17_inchangees') is True,'Gel17non confirme par observateur')
    exige(f.get('qualification_globale_effectuee') is False,'La preuve ne doit pas qualifier globalement')
    exige(h.get('etat')=='analyse_terminee' and h.get('mode')=='n34','Helper N34 incomplet/inattendu')
    exige(h.get('qualification_officielle') is False,'Qualification officielle inattendue')
    exige(h.get('sortie_zero_queue_confirmee_par_coordinateur') is True,'Sortie file non attestee dans helper')
    exige(h.get('profils_attendus')==list(PROFILS),'Whitelist helper differente des13profils')
    exige(type(h.get('controles_numeriques_reussis')) is bool and
        (0 if h['controles_numeriques_reussis'] else 2)==f['code_terminal_analyse'],
        'Code analyse et verdict helper incoherents')
    exige(sha(HELPER)==SHA_HELPER,'Helper courant different de la version observee')
    entrees={str(p.relative_to(SIM)):sha(p) for p in (ATTESTATION,FIN_ANALYSE,RAPPORT_HELPER)}
    return (a,f,h,entrees),[]


def sources():
    exige(sha(ANCRAGE)==SHA_ANCRAGE,'Ancrage17sources modifie')
    attendu=lit(ANCRAGE)['sources_controle_sha256']
    actuel={n:sha(SIM/n) for n in attendu}
    exige(len(actuel)==17 and actuel==attendu,'Sources17differentes du gel N34')
    return actuel


def fichiers():
    # Whitelist stricte ; aucun parcours de BASE ou de ses autres enfants.
    return {str(p.relative_to(BASE)):sha(p) for nom in PROFILS
        for p in sorted((BASE/nom).rglob('*')) if p.is_file()}


def interdit(*args,**kwargs):
    raise RuntimeError('Tout nouveau calcul et toute comparaison globale sont interdits')


def main():
    sortie=ICI/'rapport_croise.json'
    if sortie.exists():raise FileExistsError(sortie)
    preconditions,manque=prerequis()
    if manque:
        print(json.dumps(dict(etat='preconditions_absentes',manquants=manque,
            aucun_profil_lu=True,aucun_import_projet=True),ensure_ascii=False))
        return 3
    attestation,fin_analyse,helper,entrees=preconditions
    avant_sources=sources()
    # Les attestations precedentes sont indispensables avant ces premieres
    # lectures de manifestes/profils, notamment n34_8 et n34_12.
    for nom in PROFILS:
        exige(lit(BASE/nom/'simulation_manifest.json').get('etat')=='termine','Profil non clos :'+nom)
    avant_fichiers=fichiers()
    sys.path.insert(0,str(SIM))
    import numpy as np
    import qualifie_pcbway as Q
    import raffine_qualification_plus_pcbway as PLUS
    Q.calcule=Q.comparer=Q.F.lance=Q.F.serie=Q.F.construit=interdit
    PLUS.enregistre(Q)  # R533+n34, copies en memoire uniquement.
    donnees,controles={},{}
    for nom in PROFILS:
        niveau,duree=nom.rsplit('_',1)
        d=Q.charge_calcul(BASE/nom,exiger_courant=True)
        Q.valide_campagne(*d[2:],'diamant_uwb_x18',niveau,float(duree[:-2]))
        donnees[nom]=d
        controles[nom]=dict(lecture_courante_et_configuration_validees=True,
            n_pas=d[2]['execution']['n_pas'],dt_s=d[2]['execution']['dt_s'],
            geometrie_sha256=d[3]['geometrie_sha256'],indicateurs=Q.indicateurs(*d[:2]),
            manifeste_sha256=sha(BASE/nom/'simulation_manifest.json'),
            entree_sha256=sha(BASE/nom/'qualification_entree.json'))
    initial=donnees[PROFILS[0]]
    communs=dict(
        geometrie=all(Q.G.json_octets(d[3]['geometrie'])==Q.G.json_octets(initial[3]['geometrie']) for d in donnees.values()),
        contrat=all(Q.G.json_octets(d[3]['simulation_contract'])==Q.G.json_octets(initial[3]['simulation_contract']) for d in donnees.values()),
        sources=all(d[2]['sources_sha256']==initial[2]['sources_sha256'] for d in donnees.values()),
        environnement=all(d[2]['environnement']==initial[2]['environnement'] for d in donnees.values()),
        frequences=all(np.array_equal(d[0],initial[0]) for d in donnees.values()))
    exige(all(communs.values()),'Geometrie/contrat/sources/environnement/frequences differents')
    grossier,court,long=(donnees[n] for n in ('n30_12ns','n34_8ns','n34_12ns'))
    spatial=Q.ecarts(grossier[0],grossier[1],long[0],long[1])
    temporel=Q.ecarts(court[0],court[1],long[0],long[1],temporel=True)
    coherence=dict(maillage_manifeste_identique=court[2]['maillage']==long[2]['maillage'],
        dt_binaire_identique=float(court[2]['execution']['dt_s']).hex()==float(long[2]['execution']['dt_s']).hex(),
        dt_hex=float(long[2]['execution']['dt_s']).hex(),axes={})
    with np.load(BASE/'n34_8ns/maillage.npz',allow_pickle=False) as g8, \
         np.load(BASE/'n34_12ns/maillage.npz',allow_pickle=False) as g12:
        exige(set(g8.files)==set(g12.files)==set('xyz'),'Axes NPZ inattendus')
        for axe in 'xyz':
            x,y=g8[axe],g12[axe]
            identique=(x.ndim==1 and x.dtype.str=='<f8' and y.dtype.str=='<f8' and
                x.shape==y.shape and x.tobytes()==y.tobytes())
            digest=hashlib.sha256(x.tobytes()).hexdigest()
            coherence['axes'][axe]=dict(forme=list(x.shape),dtype=str(x.dtype),
                identique_binaire=identique,sha256=digest)
            exige(identique and digest==long[2]['maillage']['axes'][axe]['sha256'],
                'Coordonnees temporelles differentes/incoherentes sur '+axe)
    exige(coherence['maillage_manifeste_identique'] and coherence['dt_binaire_identique'],
        'Maillage/dt temporels differents')
    masques=dict(spatial=int(((abs(grossier[1])>=.1)&(abs(long[1])>=.1)).sum()),
        temporel=int(((abs(court[1])>=.1)&(abs(long[1])>=.1)).sum()))
    final=Q.indicateurs(*long[:2])
    passivite={n:{k:c['indicateurs'][k] for k in ('maximum_module','passivite_numerique')}
               for n,c in controles.items()}
    resultat=bool(spatial['reussi'] and temporel['reussi'] and final['passivite_numerique'])
    comparaisons={}
    for type_,courant in (('spatial',spatial),('temporel',temporel)):
        h=helper[type_]
        comparaisons[type_]=bool(h['profils']==PAIRES[type_] and
            all(courant[k]==h[k] for k in ('valeurs','seuils_acceptation','reussi')) and
            h['points_masque_db']==masques[type_])
    comparaisons['indicateurs_reference']=Q.G.json_octets(final)==Q.G.json_octets(helper['indicateurs_reference'])
    comparaisons['passivite_par_profil']=passivite==helper['passivite_par_profil']
    comparaisons['verdict']=resultat==helper['controles_numeriques_reussis']
    hg=helper['grille_temporelle']
    comparaisons['grille_temporelle']=bool(hg['coordonnees_bit_a_bit_identiques'] is True and
        hg['dt_bit_a_bit_identique'] is True and float(hg['dt_s']).hex()==coherence['dt_hex'])
    hc=helper['verifications_communes']
    comparaisons['communs']=bool(hc['nombre_profils']==13 and
        hc['geometrie_sha256']==initial[3]['geometrie_sha256'] and
        hc['sources_physiques_sha256']==initial[2]['sources_sha256'] and
        hc['environnement_archive']==initial[2]['environnement'] and
        Q.G.json_octets(hc['contrat'])==Q.G.json_octets(initial[3]['simulation_contract']))
    comparaisons['preuves_helper']=helper['preuves']=={
        n:{f:sha(BASE/n/f) for f in ('simulation_manifest.json','qualification_entree.json','s11.s1p','maillage.npz')}
        for n in PROFILS}
    scripts=helper['provenance']['scripts_sha256']
    comparaisons['scripts_helper']=bool(scripts.get('analyse_extreme_fin.py')==SHA_HELPER and
        all(scripts.get(n)==avant_sources[n] for n in ('qualifie_pcbway.py',
            'raffine_qualification_pcbway.py','raffine_qualification_plus_pcbway.py')))
    exige(all(comparaisons.values()),'Desaccord Q/helper sur les structures pertinentes :'+str(comparaisons))
    apres_sources,apres_fichiers=sources(),fichiers()
    exige(avant_sources==apres_sources and avant_fichiers==apres_fichiers,'Source/preuve modifiee pendant lecture')
    exige(all(sha(SIM/n)==h for n,h in entrees.items()),'Attestation/rapport helper modifie pendant lecture')
    rapport=dict(schema='revue_croisee_n34_v1',date_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__),qualification_officielle=False,qualification_globale_effectuee=False,
        nombre_profils=13,profils=controles,communs=communs,paires=PAIRES,
        spatial=spatial,temporel=temporel,coherence_temporelle=coherence,
        points_masque_module_ge_0p1=masques,indicateurs_reference_n34_12=final,
        passivite_par_profil=passivite,passivite_tous_profils=all(x['passivite_numerique'] for x in passivite.values()),
        reussi=resultat,code_sortie_controle=0 if resultat else 2,
        egalite_exacte_helper_structures_pertinentes=comparaisons,
        comparaisons_exclues='Descriptions textuelles, commandes, heures et chemins locaux ; tuples/listes normalises via JSON pour les indicateurs.',
        prerequis_sha256=entrees,code_terminal_file=attestation['code_terminal'],
        code_terminal_analyse=fin_analyse['code_terminal_analyse'],
        sources_17_sha256_avant=avant_sources,sources_17_sha256_apres=apres_sources,
        fichiers_13_profils_sha256_avant=avant_fichiers,fichiers_13_profils_sha256_apres=apres_fichiers,
        nombre_fichiers_fermes=len(apres_fichiers),aucun_calcul_ni_resultat_modifie=True,
        portee='Contrelecture Q stricte des13profils clos ; PLUS.enregistre(Q) en memoire ; aucun FDTD/CalcPort/globalQ/selection.')
    with sortie.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(rapport,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(spatial=spatial,temporel=temporel,points_masque=masques,
        maximum_module=final['maximum_module'],passivite=final['passivite_numerique'],
        reussi=resultat,code_sortie=0 if resultat else 2,rapport=str(sortie)),ensure_ascii=False,indent=2))
    return 0 if resultat else 2


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
