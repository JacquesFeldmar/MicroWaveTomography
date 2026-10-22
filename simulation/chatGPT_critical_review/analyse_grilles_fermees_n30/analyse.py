"""Diagnostic des seuls onze profils grand losange clos jusqu'a N30.

Lecture seule par defaut ; --rapport cree seulement un JSON neuf dans ce
repertoire. Aucun solveur, test, selection ou qualification n'est execute.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
os.environ['OMP_NUM_THREADS'] = os.environ['OPENBLAS_NUM_THREADS'] = '1'
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[1]
BASE = SIM/'resultats/pcbway_r1'
RACINE = BASE/'diamant_uwb_x18'
# Copie byte-exact fermee ; le point operateur original peut recevoir des
# metadonnees sans invalider ce diagnostic. Aucun acces a cet original au rejeu.
CHECKPOINT = ICI/'checkpoint_n34_fige.json'
CHECKPOINT_SHA = '47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383'
sys.path.insert(0, str(SIM))
import numpy as np
import qualifie_pcbway as Q
import raffine_qualification_pcbway as R

PROFILS = [('base_8ns','base',8),('fin_8ns','fin',8),('fin_12ns','fin',12),
    ('tres_fin_8ns','tres_fin',8),('tres_fin_12ns','tres_fin',12),
    ('ultra_fin_8ns','ultra_fin',8),('ultra_fin_12ns','ultra_fin',12),
    ('extreme_fin_8ns','extreme_fin',8),('extreme_fin_12ns','extreme_fin',12),
    ('n30_8ns','n30',8),('n30_12ns','n30',12)]
PAIRES = [('base_8ns','fin_8ns'),('fin_12ns','tres_fin_12ns'),
    ('tres_fin_12ns','ultra_fin_12ns'),('ultra_fin_12ns','extreme_fin_12ns'),
    ('extreme_fin_12ns','n30_12ns')]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sources():
    if sha(CHECKPOINT) != CHECKPOINT_SHA:
        raise ValueError('Checkpoint N34 modifie')
    attendues = json.loads(CHECKPOINT.read_text(encoding='utf-8-sig'))['sources_controle_sha256']
    actuelles = {n: sha(SIM/n) for n in attendues}
    if len(actuelles) != 17 or actuelles != attendues:
        raise ValueError('Les17sources gelees ne correspondent pas au checkpoint N34')
    return actuelles


def empreintes_profils():
    return {str(p.relative_to(BASE)): sha(p) for nom, _, _ in PROFILS
        for p in sorted((RACINE/nom).rglob('*')) if p.is_file()}


def cellule(lignes, position):
    i = int(np.searchsorted(lignes, position, side='right')-1)
    return dict(bornes_mm=[float(lignes[i]),float(lignes[i+1])],
                largeur_mm=float(lignes[i+1]-lignes[i]))


def port_xml(nom):
    xml = ET.parse(RACINE/nom/'entree_openems.xml')
    prop = next(p for p in xml.iter() if p.attrib.get('Name') == 'port_resist_1')
    points = [prop.find('Primitives/Box/'+n) for n in ('P1','P2')]
    return np.array([[float(p.attrib[a]) for a in 'XYZ'] for p in points])


def analyse():
    avant_sources = sources()
    # Liste fermee explicite : aucun parcours des profils actifs ni de BASE.
    for nom, _, _ in PROFILS:
        m = json.loads((RACINE/nom/'simulation_manifest.json').read_text(encoding='utf-8'))
        if m['etat'] != 'termine':
            raise ValueError('Profil attendu clos : '+nom)
    avant_profils = empreintes_profils()
    R.enregistre(Q)  # Catalogue seulement en memoire, sans appel a calcule.
    donnees, grilles = {}, {}
    for nom, niveau, duree in PROFILS:
        d = Q.charge_calcul(RACINE/nom, exiger_courant=True)
        Q.valide_campagne(*d[2:], 'diamant_uwb_x18', niveau, duree)
        donnees[nom] = d
        with np.load(RACINE/nom/'maillage.npz', allow_pickle=False) as g:
            grilles[nom] = {a:g[a].copy() for a in 'xyz'}
    premier = donnees[PROFILS[0][0]]
    for nom, d in donnees.items():
        if (not np.array_equal(d[0],premier[0]) or
            any(d[2][k] != premier[2][k] for k in ('sources_sha256','environnement')) or
            any(d[3][k] != premier[3][k] for k in ('geometrie_sha256','simulation_contract'))):
            raise ValueError('Frequences/sources/environnement/geometrie/contrat differents : '+nom)
    paires = []
    for a,b in PAIRES:
        f,s = donnees[a][:2];t = donnees[b][1]
        delta = abs(s-t);garde = (abs(s)>=.1)&(abs(t)>=.1)
        db = abs(20*np.log10(abs(s)/abs(t)))
        paires.append(dict(profils=[a,b], maximum_complexe=float(delta.max()),
            rms_complexe=float(np.sqrt(np.mean(delta**2))),
            percentile95_db=float(np.percentile(db[garde],95)),
            points_masque_db=int(garde.sum()), points_db_superieur_1=int((garde&(db>1)).sum()),
            anciennes_lignes_absentes_grille_suivante={axe:int(sum(
                np.min(abs(grilles[b][axe]-x))>1e-8 for x in grilles[a][axe])) for axe in 'xyz'}))
    locaux = []
    for axe,position in [('y',-35.975),('x',-5.23367)]:
        cellules = {n:cellule(grilles[n][axe],position)
                    for n in ('extreme_fin_12ns','n30_12ns')}
        locaux.append(dict(axe=axe, position_mm=position, cellules=cellules,
            rapport_largeurs_n30_sur_extreme=cellules['n30_12ns']['largeur_mm']/
                                          cellules['extreme_fin_12ns']['largeur_mm']))
    trois = {}
    objet = np.array([[-28.8,-36,0],[28.8,36,1.6]])
    for niveau in ('ultra_fin','extreme_fin','n30'):
        nom = niveau+'_12ns';g=grilles[nom];m=donnees[nom][2]
        p=port_xml(nom);h=Q.NIVEAUX[niveau]['maille_min'];zones=p+np.array([[-2*h],[2*h]])
        mini=[]
        for lo,hi in ((2.7,3.5),(5.4,6.2)):
            f,s=donnees[nom][:2];ids=np.flatnonzero((f>=lo*1e9)&(f<=hi*1e9))
            i=ids[abs(s[ids]).argmin()]
            mini.append(dict(fenetre_ghz=[lo,hi], frequence_ghz=float(f[i]/1e9),
                             s11_db=float(20*np.log10(abs(s[i])))))
        trois[niveau]=dict(cellules=m['maillage']['cellules'],dt_s=m['execution']['dt_s'],
            parametres=Q.NIVEAUX[niveau],port_boite_mm=p.tolist(),
            intervalles_fins_par_axe_mm={a:zones[:,i].tolist() for i,a in enumerate('xyz')},
            etendues_intervalles_fins_mm=dict(zip('xyz',(zones[1]-zones[0]).tolist())),
            bornes_domaine_mm={a:[float(g[a][0]),float(g[a][-1])] for a in 'xyz'},
            entrees_pml_8_mm={a:[float(g[a][8]),float(g[a][-9])] for a in 'xyz'},
            distance_pcb_entrees_pml_mm={a:[float(objet[0,i]-g[a][8]),
                float(g[a][-9]-objet[1,i])] for i,a in enumerate('xyz')},
            lignes_z_substrat_mm=g['z'][(g['z']>=0)&(g['z']<=1.6)].tolist(),
            minima_echantillonnes=mini)
    apres_sources=sources();apres_profils=empreintes_profils()
    if avant_sources != apres_sources or avant_profils != apres_profils:
        raise ValueError('Une preuve fermee ou une source a change pendant la lecture')
    return dict(schema='diagnostic_grilles_fermees_n30_v1',
        diagnostic_uniquement=True,nouvelle_qualification_effectuee=False,
        aucun_solveur_ni_test=True,aucune_lecture_profils_actifs=True,
        utc=datetime.now(timezone.utc).isoformat(),
        provenance=dict(script_sha256=sha(Path(__file__)),python=platform.python_version(),
            numpy=np.__version__,threads={n:os.environ[n] for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS')},
            checkpoint_fige=str(CHECKPOINT.relative_to(SIM)),checkpoint_sha256=CHECKPOINT_SHA,
            checkpoint_operateur_origine='resultats/pcbway_r1/journaux/reprise_grand_n34_vivaldi_ultra_fin_lancement.json',
            checkpoint_operateur_relu=False),
        sources_17_sha256_avant=avant_sources,sources_17_sha256_apres=apres_sources,
        profils_fermes=[n for n,_,_ in PROFILS],fichiers_fermes_sha256_avant=avant_profils,
        fichiers_fermes_sha256_apres=apres_profils,nombre_fichiers_fermes=len(avant_profils),
        coherences_communes_validees=['frequences','sources','environnement','geometrie','contrat'],
        observations_paires_deja_evaluees=paires,grossissements_locaux_mesures=locaux,
        trois_niveaux=trois,
        code_a_lire=dict(generation_grille='fdtd.py:290-317',zone_port='fdtd.py:294-305',
            bornes_domaine='fdtd.py:282-287',comparaison='qualifie_pcbway.py:116-131'),
        limites=['Une grille non emboitee ne constitue pas en soi une erreur.',
            'Les grossissements locaux cites sont des mesures effectives, distinctes de ce constat general.',
            'La responsabilite de chaque changement de grille, domaine ou port dans S11 n est pas identifiee.',
            'Les intervalles fins sont imposes par projection sur chaque axe cartesien, pas par une boite locale 3D.',
            'Les minima sont echantillonnes a25MHz ; aucune interpolation ni position exacte de resonance revendiquee.',
            'Aucun nouveau jugement de qualification, aucun changement des seuils ni selection de profils.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rapport',type=Path)
    args=p.parse_args();sortie=None
    if args.rapport is not None:
        sortie=(ICI/args.rapport).resolve()
        if not sortie.is_relative_to(ICI) or sortie.parent != ICI or sortie.exists():
            p.error('--rapport doit viser un fichier neuf dans ce seul repertoire')
    rapport=analyse();texte=json.dumps(rapport,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if sortie is not None:
        with sortie.open('x',encoding='utf-8',newline='\n') as f:f.write(texte)
        print(json.dumps(dict(rapport=str(sortie),script_sha256=rapport['provenance']['script_sha256'],
            sources_gelee_verifiees=17,fichiers_fermes_inchanges=rapport['nombre_fichiers_fermes']),ensure_ascii=False))
    else:
        print(texte,end='')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
