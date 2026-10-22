"""Deux setups diagnostiques au plus, uniquement apres relecture du mode --executer.

Le mode par defaut prepare des copies et un plan sans importer openEMS.
Le mode --executer consomme ce plan ferme et appelle seulement
Run(setup_only=True), qui retourne avant RunFDTD dans le wrapper epingle.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
for nom in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[nom] = '1'
os.environ['MPLBACKEND'] = 'Agg'
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[1]
GEL = SIM / 'chatGPT_critical_review/integration_finale_f2/gel_campagne_F2.json'
BASE = SIM / 'resultats/pcbway_maille_controlee_v2/diamant_uwb'
PROFILS = ('base_12ns', 'fin_16ns')
ENTREES = ('entree_openems.xml', 'maillage.npz', 'simulation_manifest.json')
API = Path(sys.executable).parent / 'Lib/site-packages/openEMS/openEMS.pyx'
BIN = SIM.parent / 'outils/openEMS'
GIB = 1024 ** 3
# Limites de surveillance ; les donnees partielles sont conservees en cas d'arret.
MAX_DISQUE = 4 * GIB
MIN_LIBRE_DISQUE = 20 * GIB
MAX_RSS = 3 * GIB
MIN_RAM_AVANT = 4 * GIB
MIN_RAM_PENDANT = int(1.5 * GIB)
MAX_SECONDES = 1200
INTERVALLE_S = .25


def exige(condition, texte):
    if not condition:
        raise ValueError(texte)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def lit(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def sauve(p, objet):
    with Path(p).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(objet, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')


def ressources():
    class Memoire(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in ('total_phys', 'avail_phys', 'total_page',
                                            'avail_page', 'total_virtual', 'avail_virtual', 'extended')]
    m = Memoire()
    m.length = ctypes.sizeof(m)
    exige(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)), 'GlobalMemoryStatusEx echoue')
    return dict(ram_disponible_octets=int(m.avail_phys),
                disque_libre_octets=shutil.disk_usage(ICI).free)


def rss_processus(processus):
    class Compteurs(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [
            (n, ctypes.c_size_t) for n in ('peak_working_set', 'working_set', 'quota_peak_paged',
                                          'quota_paged', 'quota_peak_nonpaged', 'quota_nonpaged',
                                          'pagefile', 'peak_pagefile')]
    c = Compteurs()
    c.cb = ctypes.sizeof(c)
    fonction = ctypes.windll.psapi.GetProcessMemoryInfo
    fonction.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    fonction.restype = ctypes.c_int
    exige(fonction(ctypes.c_void_p(int(processus._handle)), ctypes.byref(c), c.cb),
          'GetProcessMemoryInfo echoue')
    return int(c.working_set)


def inventaire(dossier):
    return {p.relative_to(dossier).as_posix(): dict(octets=p.stat().st_size, sha256=sha(p))
            for p in sorted(dossier.rglob('*')) if p.is_file()}


def controle_originaux(plan):
    exige({n: sha(SIM / n) for n in plan['sources18_sha256']} == plan['sources18_sha256'],
          'Une des dix-huit sources gelees a change')
    exige(all(sha(SIM / n) == h for n, h in plan['entrees_originales_sha256'].items()),
          'Une entree de profil ferme a change')
    exige(all(sha(Path(n)) == h for n, h in plan['outils_sha256'].items()),
          'Un outil natif/wrapper a change')
    exige(sha(__file__) == plan['script_sha256'], 'Script different du plan relu')


def prepare(sortie):
    import numpy as np
    exige(not sortie.exists(), 'Le dossier de preparation doit etre neuf')
    exige(sortie.parent.resolve() == ICI.resolve(), 'Preparation seulement sous ce dossier de revue')
    gel = lit(GEL)
    attendus = {**gel['sources_physiques_sha256'], **gel['controles_sha256']}
    exige(len(attendus) == 18 and {n: sha(SIM / n) for n in attendus} == attendus,
          'Sources gelees differentes')
    extensions = list(API.parent.glob('openEMS*.pyd'))
    csx = API.parent.parent / 'CSXCAD'
    extensions += list(csx.glob('CSXCAD*.pyd')) + list(csx.glob('CSRectGrid*.pyd'))
    exige(len(extensions) == 3, 'Inventaire des extensions natives inattendu')
    outils = [API, API.with_suffix('.pxd'), BIN / 'openEMS.exe', BIN / 'openEMS.dll', BIN / 'CSXCAD.dll'] + extensions
    outils_sha = {str(p): sha(p) for p in outils}
    source_api = API.read_text(encoding='utf-8')
    exige('if setup_only or EC!=0:' in source_api and
          source_api.index('if setup_only or EC!=0:') < source_api.index('self.thisptr.RunFDTD()'),
          'Chemin setup_only du wrapper non reconnu')
    entree_sha = {}
    cas = []
    for profil in PROFILS:
        dossier = BASE / profil
        manifeste = lit(dossier / 'simulation_manifest.json')
        exige(manifeste['etat'] == 'termine' and manifeste['moteur'] == 'maillage_controle_v2',
              'Profil non termine ou moteur different')
        arbre = ET.parse(dossier / 'entree_openems.xml')
        xml_grid = arbre.find('ContinuousStructure/RectilinearGrid')
        axes = {}
        with np.load(dossier / 'maillage.npz', allow_pickle=False) as z:
            for a in 'xyz':
                v = z[a]
                exige(v.dtype == np.dtype('<f8') and np.isfinite(v).all() and (np.diff(v) > 0).all(),
                      'Axe archive invalide')
                vx = np.fromstring(xml_grid.find(a.upper() + 'Lines').text, sep=',')
                exige(v.shape == vx.shape, 'Comptes XML/NPZ differents')
                axes[a] = dict(nombre=len(v), octets_sha256=hashlib.sha256(v.tobytes()).hexdigest(),
                    ecart_max_XML_NPZ_mm=float(abs(v-vx).max()))
        points = int(np.prod([axes[a]['nombre'] for a in 'xyz']))
        for nom in ENTREES:
            p = dossier / nom
            entree_sha[p.relative_to(SIM).as_posix()] = sha(p)
        cas.append(dict(profil=profil, axes=axes, points_grille=points,
            dt_restitue_s=manifeste['execution']['dt_s'],
            NrTS_XML=int(arbre.find('FDTD').get('NumberOfTimesteps')),
            echelle_un_tableau_float32_octets=4*points,
            echelle_douze_tableaux_float32_octets=48*points))
    sortie.mkdir()
    (sortie / 'contexte').mkdir()
    shutil.copyfile(GEL, sortie / 'contexte/gel_campagne_F2.json')
    for n in attendus:
        p = sortie / 'contexte/sources' / n
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SIM / n, p)
    shutil.copyfile(__file__, sortie / 'contexte' / Path(__file__).name)
    shutil.copyfile(API, sortie / 'contexte/openEMS.pyx')
    shutil.copyfile(API.with_suffix('.pxd'), sortie / 'contexte/openEMS.pxd')
    for cas_courant in cas:
        p = sortie / 'entrees' / cas_courant['profil']
        p.mkdir(parents=True)
        for n in ENTREES:
            shutil.copyfile(BASE / cas_courant['profil'] / n, p / n)
        for n in ENTREES:
            exige(sha(p / n) == sha(BASE / cas_courant['profil'] / n), 'Copie non exacte')
    aide = subprocess.run([str(BIN / 'openEMS.exe'), '--help'], capture_output=True, check=True)
    (sortie / 'contexte/openEMS_help.stdout.txt').write_bytes(aide.stdout)
    (sortie / 'contexte/openEMS_help.stderr.txt').write_bytes(aide.stderr)
    plan = dict(schema='plan_setup_operateur_archive_F2_v1', utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=sha(__file__), sources18_sha256=attendus, outils_sha256=outils_sha,
        entrees_originales_sha256=entree_sha, cas=cas, python=sys.executable, numpy=np.__version__,
        mode='CAD_XML_archive__axes_NPZ_et_dt_manifeste_restitues_sans_recalcul',
        options_API=dict(setup_only=True, cleanup=False, engine='multithreaded', numThreads=1,
            debug_PEC=True, debug_operator=True, debug_boxes=True, showProbeDiscretization=True, verbose=1),
        timestepping_interdit=True, aucun_Setup_effectue=True, aide_CLI_code=0,
        limites_surveillees=dict(disque_sortie_octets=MAX_DISQUE, disque_libre_min_octets=MIN_LIBRE_DISQUE,
            rss_enfant_octets=MAX_RSS, ram_libre_avant_octets=MIN_RAM_AVANT,
            ram_libre_pendant_octets=MIN_RAM_PENDANT, secondes_par_setup=MAX_SECONDES,
            intervalle_s=INTERVALLE_S, quota_dur_NTFS=False),
        ressources_lors_preparation=ressources(),
        limites_scientifiques=['CAD/materiaux lus dans le XML deja arrondi : pas operateur ancien bitidentique garanti.',
            'Axes NPZ et dt du manifeste exacts restitues en memoire ; aucune interpolation/construction de grille.',
            'et/ht peuvent etre generes pendant Setup : ce sont des impulsions precalculees, pas du timestepping.',
            'Les sorties effectives, formats et tableaux VTK seront inventories apres les deux setups.',
            'Plafonds surveilles, pas quota NTFS dur : depassement possible entre deux controles de0,25s.'])
    controle_originaux(plan)
    sauve(sortie / 'plan.json', plan)
    sauve(sortie / 'index_preparation.json', inventaire(sortie))
    print(json.dumps(dict(preparation=str(sortie), plan_sha256=sha(sortie/'plan.json'),
        aucun_Setup_effectue=True, cas=cas), ensure_ascii=False))


def worker(racine, profil):
    import numpy as np
    exige(profil in PROFILS, 'Profil non autorise')
    plan = lit(racine / 'plan.json')
    controle_originaux(plan)
    entree = racine / 'entrees' / profil
    for n in ENTREES:
        original = (BASE / profil / n).relative_to(SIM).as_posix()
        exige(sha(entree / n) == plan['entrees_originales_sha256'][original], 'Copie entree changee')
    os.environ['CSXCAD_INSTALL_PATH'] = str(BIN)
    from openEMS import openEMS
    fdtd = openEMS()
    exige(fdtd.ReadFromXML(str(entree / 'entree_openems.xml')) is True, 'ReadFromXML a echoue')
    grid = fdtd.GetCSX().GetGrid()
    with np.load(entree / 'maillage.npz', allow_pickle=False) as z:
        for a in 'xyz':
            # Restitution litterale d'axes existants ; aucun SmoothMeshLines/AddEdges/constructor.
            grid.SetLines(a, z[a])
            exige(grid.GetLines(a).tobytes() == z[a].tobytes(), 'Axe restitue different')
    dt = lit(entree / 'simulation_manifest.json')['execution']['dt_s']
    fdtd.SetTimeStep(dt)
    travail = racine / 'sorties' / profil
    exige(not travail.exists(), 'Sortie Setup deja presente')
    travail.mkdir(parents=True)
    cwd = Path.cwd()
    debut = time.monotonic()
    try:
        # IMPORTANT : setup_only est un argument FORMEL consomme par le wrapper.
        # Ne pas ajouter no_simulation : le C++ sortirait avant le setup des boites.
        code = fdtd.Run(str(travail), setup_only=True, cleanup=False,
            engine='multithreaded', numThreads=1, debug_PEC=True,
            debug_operator=True, debug_boxes=True, showProbeDiscretization=True, verbose=1)
    finally:
        os.chdir(cwd)
    exige(type(code) is int and code == 0, 'SetupFDTD code=' + repr(code))
    controle_originaux(plan)
    sauve(travail / 'preuve_retour_setup.json', dict(code_setup=code,
        secondes=time.monotonic()-debut, timestepping_appele=False, setup_only_literal=True,
        dt_restitue_s=dt, axes_restitues_octets_identiques=True))


def execute(racine):
    plan = lit(racine / 'plan.json')
    controle_originaux(plan)
    exige(not (racine / 'execution_demarre.json').exists() and not (racine / 'sorties').exists(),
          'Execution deja commencee : reprise interdite, garder preuve partielle')
    sauve(racine / 'execution_demarre.json', dict(utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=sha(racine/'plan.json'), script_sha256=sha(__file__)))
    (racine / 'journaux').mkdir()
    resultats = []
    try:
        for profil in PROFILS:
            controle_originaux(plan)
            res = ressources()
            exige(res['ram_disponible_octets'] >= MIN_RAM_AVANT, 'RAM libre insuffisante avant Setup')
            exige(res['disque_libre_octets'] >= MIN_LIBRE_DISQUE, 'Disque libre insuffisant')
            commande = [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).resolve()),
                        '--worker', profil, '--plan', str(racine)]
            debut = time.monotonic()
            maximum_rss = 0
            raison = None
            with (racine/'journaux'/f'{profil}.stdout.txt').open('xb') as out, \
                 (racine/'journaux'/f'{profil}.stderr.txt').open('xb') as err:
                enfant = subprocess.Popen(commande, stdout=out, stderr=err,
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS,
                    env={**os.environ, 'PYTHONUNBUFFERED':'1', 'PYTHONIOENCODING':'utf-8'}, cwd=ICI)
                try:
                    while enfant.poll() is None:
                        try:
                            maximum_rss = max(maximum_rss, rss_processus(enfant))
                            octets = sum(p.stat().st_size for p in racine.rglob('*') if p.is_file())
                            res = ressources()
                            if octets > MAX_DISQUE: raison = 'plafond_disque_surveille'
                            elif res['disque_libre_octets'] < MIN_LIBRE_DISQUE: raison = 'reserve_disque'
                            elif maximum_rss > MAX_RSS: raison = 'plafond_RSS_surveille'
                            elif res['ram_disponible_octets'] < MIN_RAM_PENDANT: raison = 'reserve_RAM_systeme'
                            elif time.monotonic()-debut > MAX_SECONDES: raison = 'timeout_setup'
                        except Exception as e:
                            if enfant.poll() is not None:
                                break
                            raison = 'surveillance_impossible:' + repr(e)
                        if raison:
                            # Seulement notre enfant direct : aucun autre processus n'est vise.
                            enfant.kill()
                            break
                        time.sleep(INTERVALLE_S)
                    code = enfant.wait()
                finally:
                    # Meme KeyboardInterrupt/SystemExit ne laisse pas un setup orphelin.
                    if enfant.poll() is None:
                        enfant.kill()
                    enfant.wait()
            resultats.append(dict(profil=profil, commande=commande, code_processus=code,
                arret_surveillance=raison, secondes=time.monotonic()-debut, maximum_RSS_observe_octets=maximum_rss))
            exige(raison is None and code == 0, 'Setup non termine correctement : '+profil)
            travail = racine / 'sorties' / profil
            noms = [p.name for p in travail.iterdir() if p.is_file()]
            for prefixe in ('PEC_dump', 'operator_dump', 'box_dump_'):
                exige(any(n.startswith(prefixe) for n in noms), 'Dump manquant : '+prefixe)
            texte = (racine/'journaux'/f'{profil}.stdout.txt').read_text(encoding='utf-8', errors='replace')
            exige('Running FDTD engine' not in texte and not re.search(r'Timestep:\s+\d+', texte),
                  'Trace de timestepping inattendue')
            for p in travail.glob('port_*'):
                exige(not any(l.strip() and not l.lstrip().startswith('%')
                              for l in p.read_text(encoding='utf-8').splitlines()),
                      'Valeur temporelle inattendue dans '+p.name)
            exige(not (travail / 'openEMS_run_stats.txt').exists(), 'Stats RunFDTD inattendues')
            controle_originaux(plan)
        sauve(racine/'execution_terminee.json', dict(code=0, deux_Setup_uniquement=True,
            resultats=resultats, sources18_et_entrees_inchangees=True, aucun_pas_temporel=True))
    except BaseException as e:
        sauve(racine/'execution_echec.json', dict(erreur=repr(e), resultats=resultats,
            donnees_partielles_conservees=True, aucune_reprise_automatique=True))
        raise
    finally:
        sauve(racine/'index_sorties.json', inventaire(racine))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sortie', type=Path, help='Dossier neuf directement sous ce staging ; preparation sans Setup')
    p.add_argument('--executer', type=Path, help='Plan deja prepare ; APRES relecture ROOT seulement')
    p.add_argument('--worker', choices=PROFILS, help=argparse.SUPPRESS)
    p.add_argument('--plan', type=Path, help=argparse.SUPPRESS)
    a = p.parse_args()
    if a.worker:
        exige(a.plan is not None and a.sortie is None and a.executer is None, 'Arguments worker invalides')
        worker(a.plan.resolve(), a.worker)
    elif a.executer:
        exige(a.sortie is None and a.plan is None, 'Modes exclusifs')
        exige(a.executer.resolve().parent == ICI, 'Plan hors staging interdit')
        execute(a.executer.resolve())
    else:
        exige(a.plan is None and a.sortie is not None, 'Specifier --sortie ou --executer')
        prepare(a.sortie.resolve())


if __name__ == '__main__':
    main()
