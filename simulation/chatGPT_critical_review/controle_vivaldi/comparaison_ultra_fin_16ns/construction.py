"""Produits individuels Vivaldi UF ; aucun FDTD ni qualification globale."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode=True
for nom in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[nom]='1'
os.environ['MPLBACKEND']='Agg'
ICI=Path(__file__).resolve().parent
CONTROLE=ICI.parent
SIM=ICI.parents[2]
BASE=SIM/'resultats/pcbway_r1/vivaldi_tomographie'
sys.path.insert(0,str(SIM))
import numpy as np
import qualifie_pcbway as Q
import raffine_qualification_pcbway as R
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROFILS=[('base_8ns','base',8),('fin_8ns','fin',8),('fin_12ns','fin',12),
    ('tres_fin_12ns','tres_fin',12),('tres_fin_16ns','tres_fin',16),
    ('ultra_fin_12ns','ultra_fin',12),('ultra_fin_16ns','ultra_fin',16)]
HISTORIQUES=[('spatial',['base_8ns','fin_8ns'],'Échec spatial initial conservé.'),
    ('temporel',['fin_8ns','fin_12ns'],'Échec temporel initial conservé.'),
    ('spatial',['fin_12ns','tres_fin_12ns'],'Échec spatial au niveau très fin conservé.'),
    ('temporel',['tres_fin_12ns','tres_fin_16ns'],'Contrôle temporel précédent réussi et conservé.')]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lit(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def ecrit(nom,obj):
    with (ICI/nom).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def sources():
    p=SIM/'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'
    if sha(p)!='47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383':
        raise ValueError('Ancrage fermé17sources modifié')
    attendu=lit(p)['sources_controle_sha256'];actuel={n:sha(SIM/n) for n in attendu}
    if len(actuel)!=17 or attendu!=actuel:raise ValueError('Sources17 différentes du gel')
    return actuel
def preuves():
    return {str(p.relative_to(BASE)):sha(p) for nom,_,_ in PROFILS
        for p in sorted((BASE/nom).rglob('*')) if p.is_file()}


def courbe(type_,paire,donnees,ecart):
    a,b=(donnees[n] for n in paire);f=a[0]/1e9;s,t=a[1],b[1]
    dbs=20*np.log10(np.maximum(abs(s),1e-15));dbt=20*np.log10(np.maximum(abs(t),1e-15))
    delta=abs(s-t);garde=(abs(s)>=.1)&(abs(t)>=.1);db=abs(dbs-dbt)
    limite=ecart['seuils_acceptation'];val=ecart['valeurs']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
        'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold'})
    fig,axes=plt.subplots(3,1,figsize=(11.8,10.5),sharex=True,
        gridspec_kw={'height_ratios':[1.3,1,1]},layout='constrained')
    couleur='#196887';autre='#bc5b22';rouge='#b33c38';vert='#25764f'
    titre='spatial à 16 ns' if type_=='spatial' else 'temporel, 12 → 16 ns'
    fig.suptitle('Vivaldi — contrôle '+titre+'\nContrôles individuels satisfaits ; aucune qualification globale',fontsize=15)
    axes[0].plot(f,dbs,label=paire[0],color=autre,lw=1.6)
    axes[0].plot(f,dbt,label=paire[1],color=couleur,lw=1.6)
    axes[0].axhline(-20,color='#737d85',ls=':',lw=1,label='−20 dB : frontière du masque de comparaison')
    axes[0].set_ylabel('S11 (dB)');axes[0].legend(loc='lower left',fontsize=9)
    axes[0].set_title('Courbes sur les 213 fréquences archivées (pas de 25 MHz)',fontsize=11)
    axes[1].plot(f,delta,color=couleur,lw=1.6,label='|S11 a − S11 b|, tous les points')
    axes[1].axhline(limite['maximum_complexe'],color=rouge,ls='--',lw=1.3,
        label=f"Seuil du maximum : {limite['maximum_complexe']:g}")
    axes[1].set_ylim(0,1.2*max(float(delta.max()),limite['maximum_complexe']))
    axes[1].set_ylabel('Écart complexe (module)')
    axes[1].set_title(f"Maximum {val['maximum_complexe']:.8f} ≤ {limite['maximum_complexe']:g} ; "
        f"RMS {val['rms_complexe']:.8f} ≤ {limite['rms_complexe']:g}",fontsize=11)
    axes[1].legend(loc='upper right',fontsize=9)
    axes[2].plot(f,db,color='#b7bfc5',lw=1,label='Écart dB complet (hors masque en gris)')
    axes[2].plot(f,np.where(garde,db,np.nan),color=vert,lw=1.8,
        label=f"Masque retenu : {int(garde.sum())}/213 points, deux |S11| ≥ 0,1")
    axes[2].axhline(limite['percentile95_db'],color=rouge,ls='--',lw=1.3,
        label=f"Seuil du p95 : {limite['percentile95_db']:g} dB")
    axes[2].set_ylabel('|Écart de S11 en dB|');axes[2].set_xlabel('Fréquence (GHz)')
    axes[2].set_title(f"p95 masqué = {val['percentile95_db']:.8f} dB ; le seuil porte sur le percentile, pas chaque point",fontsize=10.5)
    axes[2].legend(loc='upper right',fontsize=9)
    for ax in axes:
        ax.grid(alpha=.2);ax.set_xlim(1,6.3);ax.set_xticks(np.arange(1,6.1,.5))
    nom='comparaison_'+type_+'_ultra_fin.png'
    fig.savefig(ICI/nom,dpi=190,facecolor='white');plt.close(fig)
    return nom


def main():
    journal=[]
    try:
        if any(p.name not in ('construction.py','construction_erreur.log') for p in ICI.iterdir()):
            raise FileExistsError('Le dossier de produits doit être neuf, hors script')
        debut=datetime.now(timezone.utc).isoformat();avant_sources=sources()
        for nom,_,_ in PROFILS:
            if lit(BASE/nom/'simulation_manifest.json')['etat']!='termine':raise ValueError('Profil non clos :'+nom)
        avant_preuves=preuves();R.enregistre(Q);donnees={}
        for nom,niveau,duree in PROFILS:
            donnees[nom]=Q.charge_calcul(BASE/nom,exiger_courant=True)
            Q.valide_campagne(*donnees[nom][2:],'vivaldi_tomographie',niveau,duree)
        u=SIM/'chatGPT_critical_review/controle_extreme_fin/analyse_extreme_fin.py'
        if sha(u)!='2d5215a9e388d2c8cfd6f075eafde1776246d9de3bfe84461a9eda06d94e3b9b':raise ValueError('Helper numérique U modifié')
        spec=importlib.util.spec_from_file_location('utils_produits_vuf',u);U=importlib.util.module_from_spec(spec);spec.loader.exec_module(U)
        init=CONTROLE/'preuve_initiale_vivaldi.json';precedent=CONTROLE/'controle_final_vivaldi/rapport.json'
        final=CONTROLE/'controle_final_vivaldi_ultra/rapport.json'
        cross=CONTROLE/'revue_croisee_ultra_fin/rapport_croise.json'
        execution_root=CONTROLE/'revue_croisee_ultra_fin/execution_verification_root.json'
        fin_root=SIM/'resultats/pcbway_r1/journaux/fin_vivaldi_ultra_fin_resultats_2026-10-19.json'
        if sha(cross)!='986fbe36217714dd7369c7f7a5b68d574956684e630c470182226be77d2884aa':raise ValueError('Preuve croisée root différente')
        entrees={str(p.relative_to(SIM)):sha(p) for p in (init,precedent,final,cross,execution_root,fin_root)}
        baselines=[lit(init),lit(precedent)];dernier=lit(final)
        def mesure(type_,noms,attendu):
            a,b=(donnees[n] for n in noms)
            e=Q.ecarts(a[0],a[1],b[0],b[1],temporel=type_=='temporel')
            if any(e[k]!=attendu[k] for k in ('valeurs','seuils_acceptation','reussi')):
                raise ValueError('Valeurs historiques/finales différentes :'+str(noms))
            return dict(**e,calculs=noms,points_masque_db=int(((abs(a[1])>=.1)&(abs(b[1])>=.1)).sum()),
                masque_definition='deux modules ≥0,1 ; max/RMS sur tous les points ; p95 sur les points masqués')
        historiques=[]
        for i,(type_,noms,motif) in enumerate(HISTORIQUES):
            historiques.append(dict(type=type_,calculs=noms,motif=motif,
                ecarts=mesure(type_,noms,baselines[i//2][type_])))
        spatial=mesure('spatial',['tres_fin_16ns','ultra_fin_16ns'],dernier['spatial'])
        temporel=mesure('temporel',['ultra_fin_12ns','ultra_fin_16ns'],dernier['temporel'])
        grille=U.grille_identique(BASE,temporel['calculs'],donnees)
        indicateurs=Q.indicateurs(*donnees['ultra_fin_16ns'][:2])
        if Q.G.json_octets(indicateurs)!=Q.G.json_octets(dernier['indicateurs_reference']):
            raise ValueError('Indicateurs de référence différents')
        figures=[courbe(t,e['calculs'],donnees,e) for t,e in [('spatial',spatial),('temporel',temporel)]]
        bilan=dict(schema='bilan_intermediaire_vivaldi_ultra_fin_16ns_v1',
            antenne='vivaldi_tomographie',qualification_globale=False,qualification_officielle=False,
            statut='Contrôle individuel clos ; campagne globale non qualifiée.',reference='ultra_fin_16ns',
            calculs_utilises=[n for n,_,_ in PROFILS],nombre_profils=7,nombre_preliminaires=4,
            spatial=spatial,temporel=temporel,essais_preliminaires=historiques,
            controles_individuels_reussis=bool(spatial['reussi'] and temporel['reussi'] and indicateurs['passivite_numerique']),
            indicateurs=indicateurs,grille_temporelle=grille,passivite_par_profil=dernier['passivite_par_profil'],
            figures=figures,preuves_historiques_et_root_sha256=entrees,
            limites=['Stabilité S11 selon les critères déclarés, sans borne absolue de l erreur.',
                'Port idéal au bord PCB ; connecteur coaxial et soudure hors modèle3D.',
                'Les échecs antérieurs sont conservés ; aucune sélection globale créée.'])
        apres_sources=sources();apres_preuves=preuves()
        if avant_sources!=apres_sources or avant_preuves!=apres_preuves:raise ValueError('Source/preuve modifiée')
        if any(sha(SIM/p)!=h for p,h in entrees.items()):raise ValueError('Rapport source modifié')
        ecrit('bilan_intermediaire_ultra_fin_16ns.json',bilan)
        ecrit('preuve_integrite.json',dict(debut_utc=debut,fin_utc=datetime.now(timezone.utc).isoformat(),
            script_sha256=sha(Path(__file__)),commande=sys.argv,python=sys.version,numpy=np.__version__,
            matplotlib=matplotlib.__version__,fils=1,backend='Agg',aucun_fdtd=True,aucun_profil_grand_lu=True,
            sources_17_sha256_avant=avant_sources,sources_17_sha256_apres=apres_sources,
            nombre_fichiers_fermes=len(avant_preuves),preuves_sha256_avant=avant_preuves,
            preuves_sha256_apres=apres_preuves,rapports_sources_sha256=entrees))
        journal.append('Sept profils Vivaldi clos revalidés ; aucun FDTD ou comparaison globale.')
        journal.append('Quatre comparaisons historiques conservées avec métriques/seuils/verdicts exacts.')
        journal.append('Valeurs finales identiques au contrôle indépendant et rapport root croisé lié par SHA.')
        journal.append('Dix-sept sources et '+str(len(avant_preuves))+' fichiers fermés SHA avant/après identiques.')
        journal.append('Code sortie :0 ; inspection visuelle des deux PNG encore requise.')
        with (ICI/'construction.log').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(journal)+'\n')
        print(json.dumps(dict(etat='produits_crees',figures=figures,
            bilan_sha256=sha(ICI/'bilan_intermediaire_ultra_fin_16ns.json'),fichiers_inchanges=len(avant_preuves)),ensure_ascii=False))
        return 0
    except Exception:
        with (ICI/'construction_erreur.log').open('x',encoding='utf-8',newline='\n') as f:f.write(traceback.format_exc())
        raise


if __name__=='__main__':raise SystemExit(main())
