"""Extrait une fenetre initiale de sondes FDTD, puis relit avec CalcPort.

Aucune execution FDTD : la derivee est explicitement rattachee au calcul long.
Les originaux et les temps U/I decales d'un demi-pas restent inchanges.

  python fenetre_sondes.py --source resultats/.../fin_12ns \
      --sortie resultats/.../fin_8ns --duree-ns 8
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np

import fdtd as F


# Execute avec les modules COPIES de la simulation mere, pas ceux du projet
# susceptible d'evoluer. CalcPort utilise les temps propres de U et de I dans
# sa DTFT; ne pas appliquer une deuxieme correction de phase au demi-pas.
EXTRACTION = r'''
import json
from pathlib import Path
import sys
import numpy as np
source, sortie = map(Path, sys.argv[1:3])
sys.path.insert(0, str(source/'sources'))
import fdtd as F
from banc import Acquisition, Antenne, Plaque, Maillage, Montage
entrees = json.loads((sortie/'parametres_extraction.json').read_text(encoding='utf-8'))
d = entrees['montage']
montage = Montage(acquisition=Acquisition(**d['acquisition']),
    antenne=Antenne(**d['antenne']), plaque=Plaque(**d['plaque']),
    maillage=Maillage(**d['maillage']))
module = F.charge_antenne(entrees['antenne'])
fdtd, csx, port, _ = F.construit(montage, module,
    x_cm=entrees.get('cible_cm'), dossier=str(sortie),
    x_domaine=entrees.get('x_domaine_cm'),
    distances_communes_cm=entrees.get('distances_communes_cm') or None,
    n_pas=entrees['n_pas'], duree_ns=entrees['duree_ns'],
    dt_impose_s=entrees['dt_s'])
archive = np.load(source/'maillage.npz')
for axe in 'xyz':
    if not np.array_equal(np.asarray(csx.GetGrid().GetLines(axe)), archive[axe]):
        raise ValueError('reconstruction du maillage archive differente sur '+axe)
if F._proprietes_matiere(csx)[3] != entrees['materiaux']:
    raise ValueError('reconstruction des materiaux archivee differente')
data = np.loadtxt(source/'s11.s1p', comments=('!', '#'))
frequences, sauve = data[:,0], data[:,1]+1j*data[:,2]
port.CalcPort(str(source), frequences, ref_impedance=montage.acquisition.z_ref)
complet = np.array(port.uf_ref/port.uf_inc, copy=True)
erreur = float(np.max(np.abs(complet-sauve)))
if erreur > 2e-10:
    raise ValueError('CalcPort complet ne reproduit pas S11 mere : '+str(erreur))
port.CalcPort(str(sortie), frequences, ref_impedance=montage.acquisition.z_ref)
derive = port.uf_ref/port.uf_inc
incident = np.abs(port.uf_inc)
if not np.all(np.isfinite(derive)):
    raise ValueError('S11 derive non fini')
np.savez_compressed(sortie/'extraction_calcport.npz',
                    frequences=frequences, s11=derive, s11_parent_relu=complet)
(sortie/'relecture_calcport.json').write_text(json.dumps(dict(
    difference_max_complete_vs_s11_parent=erreur,
    minimum_module_uf_inc=float(incident.min()),
    maximum_module_uf_inc=float(incident.max()),
    minimum_sur_maximum_uf_inc=float(incident.min()/max(incident.max(), 1e-300)),
    extracteur='openEMS.ports.LumpedPort.CalcPort des sources et packages installes',
    phase='DTFT aux temps originaux U et I; demi-pas Yee conserve sans correction ajoutee',
    maillage_archive_identique=True, materiaux_archives_identiques=True), indent=2),
    encoding='utf-8')
'''


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for bloc in iter(lambda: f.read(1024*1024), b''):
            h.update(bloc)
    return h.hexdigest()


def ecrit_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                    indent=2, allow_nan=False), encoding='utf-8')


def montage_depuis_dict(d):
    from banc import Acquisition, Antenne, Plaque, Maillage, Montage
    return Montage(acquisition=Acquisition(**d['acquisition']),
        antenne=Antenne(**d['antenne']), plaque=Plaque(**d['plaque']),
        maillage=Maillage(**d['maillage']))


def prefixe_sonde(source, sortie, nombre, dt_s, decalage_attendu, nombre_source):
    """Copie les octets des N premieres lignes de donnees et leurs en-tetes."""
    data = np.loadtxt(source, comments='%')
    if data.ndim != 2 or data.shape[1] != 2 or len(data) < nombre:
        raise ValueError('sonde absente, non scalaire ou trop courte : '+str(source))
    if len(data) != nombre_source:
        raise ValueError('nombre reel de lignes different de la source annoncee : '+str(source))
    if not np.all(np.isfinite(data)):
        raise ValueError('sonde non finie : '+str(source))
    temps = data[:,0]
    if abs(temps[0]/dt_s-decalage_attendu) > 1e-6:
        raise ValueError('origine temporelle U/I inattendue : '+str(source))
    ticks = (temps-temps[0])/dt_s
    if np.max(abs(ticks-np.arange(len(temps)))) > 2e-6:
        raise ValueError('sonde non echantillonnee a chaque pas : '+str(source))
    compte = 0
    with Path(source).open('rb') as entree, Path(sortie).open('xb') as out:
        for ligne in entree:
            if ligne.startswith(b'%') or not ligne.strip():
                out.write(ligne)
                continue
            if compte >= nombre:
                break
            out.write(ligne)
            compte += 1
    if compte != nombre:
        raise ValueError('prefixe incomplet : '+str(source))
    return dict(echantillons=nombre, dt_effectif_s=float(np.median(np.diff(temps[:nombre]))),
        debut_s=float(temps[0]), fin_s=float(temps[nombre-1]),
        decalage_initial_en_pas=decalage_attendu, sha256=sha256(sortie),
        sha256_original=sha256(source), prefixe_octets_originaux=True)


def derive(source, sortie, duree_ns):
    """Cree un dossier neuf compatible avec les lecteurs de qualification."""
    source, sortie = Path(source).resolve(), Path(sortie).resolve()
    if source == sortie or sortie.is_relative_to(source) or source.is_relative_to(sortie):
        raise ValueError('source et sortie doivent etre deux dossiers disjoints')
    if sortie.exists() and any(sortie.iterdir()):
        raise FileExistsError('dossier de derivee non vide : '+str(sortie))
    if not np.isfinite(duree_ns) or duree_ns <= 0:
        raise ValueError('duree-ns doit etre positive et finie')
    manifeste_path = source/'simulation_manifest.json'
    manifeste = json.loads(manifeste_path.read_text(encoding='utf-8'))
    q_path = source/'qualification_entree.json'
    qualification = json.loads(q_path.read_text(encoding='utf-8'))
    if manifeste.get('etat') != 'termine' or manifeste.get('derive_sondes'):
        raise ValueError('source attendue : simulation FDTD directe terminee')
    if manifeste['execution'].get('fin_energie_active', True):
        raise ValueError('une execution a arret anticipe ne satisfait pas ce protocole')
    for nom, empreinte in manifeste['fichiers_sha256'].items():
        p = (source/nom).resolve()
        if not p.is_relative_to(source) or not p.is_file() or sha256(p) != empreinte:
            raise ValueError('archive source alteree ou manquante : '+nom)
    for nom, empreinte in manifeste['sources_sha256'].items():
        p = (source/'sources'/nom).resolve()
        if not p.is_relative_to(source/'sources') or not p.is_file() or sha256(p) != empreinte:
            raise ValueError('source Python archivee alteree : '+nom)
    dt_s = float(manifeste['execution']['dt_s'])
    t_s = float(duree_ns)*1e-9
    limite = float(manifeste['execution']['duree_demandee_s'])
    if t_s > limite*(1+1e-12):
        raise ValueError('fenetre demandee plus longue que la source')
    plein = math.isclose(t_s, limite, rel_tol=1e-12, abs_tol=1e-21)
    n_pas = (int(manifeste['execution']['n_pas']) if plein else
             int(np.ceil(t_s/dt_s))+1)
    # openEMS 0.37 ecrit les indices 0..NrTS INCLUS : NrTS+1 lignes,
    # tant pour U(k*dt) que pour I((k+.5)*dt). Verifie sur le mini reel.
    nombre = n_pas+1
    if n_pas < 2:
        raise ValueError('fenetre trop courte pour CalcPort')
    if any(manifeste['sondes'][nom]['echantillons'] !=
           int(manifeste['execution']['n_pas'])+1 for nom in ('port_ut_1','port_it_1')):
        raise ValueError('convention NrTS+1 du solveur differente; protocole a adapter')
    stats = np.loadtxt(source/'openEMS_stats.txt', comments='%')
    if int(stats[2]) != int(manifeste['execution']['n_pas']):
        raise ValueError('iterations effectives differentes du manifeste source')
    if not np.isclose(stats[1], dt_s, rtol=2e-7, atol=1e-18):
        raise ValueError('dt effectif du solveur different du manifeste source')
    xml = ET.parse(source/'entree_openems.xml').getroot()
    excitation = xml.find('./FDTD/Excitation')
    if excitation is None or excitation.get('Type') != '0':
        raise ValueError('le protocole exige une excitation gaussienne Type=0')
    fc = float(excitation.get('fc', 'nan'))
    if not np.isfinite(fc) or fc <= 0:
        raise ValueError('fc gaussien non valide')
    # openEMS v0.37.0 : Lpulse=ceil(9/(pi*fc*dt)), tronque a NrTS.
    # Le pulse doit etre integral dans le calcul parent ET le court equivalent.
    longueur_pulse = int(np.ceil(9/(np.pi*fc*dt_s)))
    if min(n_pas, int(manifeste['execution']['n_pas'])) < longueur_pulse:
        raise ValueError('le nombre de pas tronquerait le pulse gaussien nominal')
    # Verifier les conditions d'une excitation identique a un calcul court.
    # Les campagnes a 8 ns sont largement au-dela du pulse gaussien (~1 ns).
    # et/ht ne sont PAS l'energie residuelle : ce sont les signaux d'excitation.
    for nom in ('et', 'ht'):
        data = np.loadtxt(source/nom, comments='%')
        signal = data[:,1]
        pic = float(np.max(np.abs(signal)))
        if pic and np.any(np.abs(signal[data[:,0] > t_s]) > pic*1e-8):
            raise ValueError('la fenetre tronquerait le pulse excitation : '+nom)
    nouveau_montage = deepcopy(manifeste['montage'])
    nouveau_montage['maillage']['duree_ns'] = float(duree_ns)
    # Le runner doit retrouver exactement la signature du calcul court.
    import qualifie_pcbway as Q
    carte = Q.G.carte_antenne(manifeste['antenne'])
    if (Q.G.json_octets(Q.G.geometrie_canonique(carte)) != Q.G.json_octets(qualification['geometrie']) or
            Q.G.json_octets(carte['simulation_contract']) != Q.G.json_octets(qualification['simulation_contract'])):
        raise ValueError('la geometrie/contrat courants different de la qualification source')
    if (Q.G.json_octets(qualification['montage']) != Q.G.json_octets(manifeste['montage']) or
            Q.signature(carte, montage_depuis_dict(manifeste['montage'])) != qualification['signature_physique']):
        raise ValueError('montage/signature de qualification source incoherents')
    signature = Q.signature(carte, montage_depuis_dict(nouveau_montage))
    sortie.mkdir(parents=True, exist_ok=True)
    derivee = deepcopy(manifeste)
    derivee.update(etat='derivation_en_cours', derive_sondes=True,
        protocole='prefixe_causal_U_I_puis_vrai_CalcPort_v1',
        montage=nouveau_montage, calcul_fdtd_execute=False,
        debut_utc=datetime.now(timezone.utc).isoformat(),
        derivation=dict(source=str(source), source_relatif=os.path.relpath(source, sortie),
            manifeste_parent_sha256=sha256(manifeste_path),
            qualification_parent_sha256=sha256(q_path),
            duree_parent_demandee_s=limite, n_pas_parent=manifeste['execution']['n_pas'],
            n_pas_retenus=n_pas, echantillons_retenus_par_sonde=nombre,
            longueur_pulse_gaussien_pas=longueur_pulse,
            interpretation='meme evolution discrete tronquee; pas une simulation independante',
            convention='NrTS=ceil(T/dt)+1; NrTS+1 lignes par sonde, indices 0..NrTS; I a +dt/2'))
    derivee.pop('entree_xml_sha256', None)
    derivee.pop('fichiers_sha256', None)
    derivee.pop('calibration_dt', None)
    derivee.pop('sondes', None)
    derivee['execution'].update(n_pas=n_pas, duree_demandee_s=t_s,
        duree_prevue_s=(n_pas-1)*dt_s,
        duree_reelle_U_s=n_pas*dt_s,
        duree_reelle_I_depuis_zero_s=(n_pas+.5)*dt_s,
        convention_duree='duree_prevue conserve la formule du moteur; fins reelles NrTS*dt et (NrTS+.5)*dt',
        couvre_inverse_df=bool(n_pas*dt_s >= 1/montage_depuis_dict(nouveau_montage).acquisition.df),
        methode='derivee de sondes du calcul parent; aucun Run FDTD')
    try:
        shutil.copytree(source/'sources', sortie/'sources')
        for nom in ('maillage.npz', 'geometrie.json'):
            shutil.copy2(source/nom, sortie/nom)
        shutil.copy2(manifeste_path, sortie/'origine_simulation_manifest.json')
        shutil.copy2(q_path, sortie/'origine_qualification_entree.json')
        shutil.copy2(source/'entree_openems.xml', sortie/'origine_entree_openems.xml')
        derivee['entree_xml_origine'] = dict(fichier='origine_entree_openems.xml',
            sha256=sha256(source/'entree_openems.xml'), duree_demandee_s=limite,
            avertissement='XML du calcul parent complet, pas entree FDTD de la fenetre derivee')
        derivee['sondes'] = {
            nom: prefixe_sonde(source/nom, sortie/nom, nombre, dt_s, decalage,
                               int(manifeste['execution']['n_pas'])+1)
            for nom, decalage in (('port_ut_1',0.),('port_it_1',.5))}
        parametres = dict(antenne=manifeste['antenne'], montage=nouveau_montage,
            cible_cm=manifeste.get('cible_cm'), x_domaine_cm=manifeste.get('x_domaine_cm'),
            distances_communes_cm=manifeste.get('distances_communes_cm'),
            dt_s=dt_s, n_pas=n_pas, duree_ns=duree_ns, materiaux=manifeste['materiaux'])
        ecrit_json(sortie/'parametres_extraction.json', parametres)
        (sortie/'extraction_calcport.py').write_text(EXTRACTION, encoding='utf-8')
        commande = [sys.executable, '-B', '-X', 'utf8', str(sortie/'extraction_calcport.py'),
                    str(source), str(sortie)]
        resultat = subprocess.run(commande, capture_output=True, text=True, encoding='utf-8')
        (sortie/'extraction_journal.txt').write_text(resultat.stdout+resultat.stderr, encoding='utf-8')
        if resultat.returncode:
            raise RuntimeError('echec de CalcPort archive; voir extraction_journal.txt')
        calcul = np.load(sortie/'extraction_calcport.npz')
        f, s = calcul['frequences'], calcul['s11']
        F.ecrit_s1p(str(sortie/'s11.s1p'), f, s,
            z_ref=nouveau_montage['acquisition']['z_ref'],
            commentaire='DERIVE DE SONDES, sans nouveau FDTD; voir simulation_manifest.json')
        q = deepcopy(qualification)
        q.update(montage=nouveau_montage, signature_physique=signature,
                 derive_sondes=True, provenance=derivee['derivation'],
                 debut_utc=derivee['debut_utc'])
        ecrit_json(sortie/'qualification_entree.json', q)
        ecrit_json(sortie/'s11_indicateurs.json', Q.indicateurs(f, s))
        derivee.update(etat='termine', relecture_calcport=json.loads(
            (sortie/'relecture_calcport.json').read_text(encoding='utf-8')))
    except Exception as exc:
        derivee.update(etat='echec', erreur=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        derivee['fin_utc'] = datetime.now(timezone.utc).isoformat()
        derivee['fichiers_sha256'] = {str(p.relative_to(sortie)).replace('\\','/'): sha256(p)
            for p in sortie.rglob('*') if p.is_file() and p.name != 'simulation_manifest.json'}
        ecrit_json(sortie/'simulation_manifest.json', derivee)
    return derivee


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--sortie', required=True, type=Path)
    p.add_argument('--duree-ns', required=True, type=float)
    args = p.parse_args()
    m = derive(args.source, args.sortie, args.duree_ns)
    print(json.dumps(dict(etat=m['etat'], derive_sondes=True,
        dossier=str(args.sortie.resolve()), n_pas=m['execution']['n_pas']), ensure_ascii=False))
