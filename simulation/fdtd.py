"""Scenes openEMS, maillages controles et executions archivables.

Une serie fond/cibles partage exactement les memes lignes, le meme pas de
 temps CFL conservatif et le meme nombre de pas. Les sondes temporelles,
 l'entree XML, le maillage et un manifeste SHA-256 restent dans chaque calcul.
 La construction et l'estimation de cout n'executent jamais le solveur.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil

import numpy as np

from banc import C, Montage
from materiaux import ATTRIBUT_MODELE

ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_ANTENNES = os.path.join(ICI, 'antennes')
_OPENEMS = os.path.join(os.path.dirname(ICI), 'outils', 'openEMS')
if not os.environ.get('CSXCAD_INSTALL_PATH') and os.path.isdir(_OPENEMS):
    os.environ['CSXCAD_INSTALL_PATH'] = _OPENEMS


def antennes_disponibles():
    return sorted(p.parent.name for p in Path(DOSSIER_ANTENNES).glob('*/geometrie.py'))


def charge_antenne(nom):
    chemin = Path(DOSSIER_ANTENNES) / nom / 'geometrie.py'
    if not chemin.is_file():
        raise FileNotFoundError(f'antenne inconnue : {nom}. Disponibles : '
                               + ', '.join(antennes_disponibles()))
    spec = importlib.util.spec_from_file_location(f'antenne_{nom}', chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def marge_air(acq, maillage):
    """Marge d'air en mm, hors les huit cellules de PML."""
    return max(maillage.marge_air_mm, C / acq.f_min * 1e3 / 4)


def _uniques(lignes):
    """Dedoublonne seulement l'arrondi numerique; jamais un vrai detail."""
    valeurs = np.sort(np.asarray(lignes, dtype=float).ravel())
    if not np.all(np.isfinite(valeurs)):
        raise ValueError('ligne de maillage non finie')
    return valeurs[np.r_[True, np.diff(valeurs) > 1e-8]] if valeurs.size else valeurs


def _fusionne(prioritaires, autres, tol):
    """Conserve les interfaces; ecarte les echantillons trop proches."""
    lignes = _uniques(prioritaires)
    for valeur in _uniques(autres):
        i = int(np.searchsorted(lignes, valeur))
        voisins = lignes[max(0, i-1):i+1]
        if not voisins.size or np.all(np.abs(voisins-valeur) >= tol):
            lignes = np.insert(lignes, i, valeur)
    return lignes


def _gradue(lignes, rapport_max, fixes, taille_max):
    """Repartit les cellules libres en conservant toutes les interfaces.

    Les contraintes d_i <= ratio*d_(i+1) sont lineaires. Une repartition
    lineaire minimise le deplacement depuis le lissage initial, avec une
    taille maximale par zone. Des cellules ne sont ajoutees qu'en cas de
    besoin. On evite ainsi de propager une subdivision binaire dans tout
    l'air. scipy est deja une dependance de l'environnement openEMS.
    """
    try:
        from scipy.optimize import linprog
        from scipy.sparse import lil_matrix
    except ImportError as exc:
        raise ImportError("le maillage controle exige scipy (pip install scipy)") from exc
    lignes, fixes = _uniques(np.r_[lignes, fixes]), _uniques(fixes)
    for _ in range(20):
        d = np.diff(lignes)
        if np.all(np.maximum(d[1:]/d[:-1], d[:-1]/d[1:]) <= rapport_max*(1+1e-10)):
            return lignes
        n = len(d)
        # Largeurs et variables d'ecart absolu a la grille initiale.
        a_ub = lil_matrix((2*(n-1)+2*n, 2*n), dtype=float)
        b_ub = np.zeros(a_ub.shape[0])
        for i in range(n-1):
            a_ub[2*i, i], a_ub[2*i, i+1] = 1., -rapport_max
            a_ub[2*i+1, i], a_ub[2*i+1, i+1] = -rapport_max, 1.
        for i in range(n):
            j = 2*(n-1)+2*i
            a_ub[j, i], a_ub[j, n+i], b_ub[j] = 1., -1., d[i]
            a_ub[j+1, i], a_ub[j+1, n+i], b_ub[j+1] = -1., -1., -d[i]
        indices = np.array([int(np.argmin(abs(lignes-f))) for f in fixes])
        a_eq = lil_matrix((len(fixes)-1, 2*n), dtype=float)
        for j, (lo, hi) in enumerate(zip(indices[:-1], indices[1:])):
            a_eq[j, lo:hi] = 1.
        plafonds = [taille_max((lo+hi)/2) for lo, hi in zip(lignes[:-1], lignes[1:])]
        resultat = linprog(np.r_[np.zeros(n), 1/np.maximum(d, 1e-6)],
            A_ub=a_ub.tocsr(), b_ub=b_ub, A_eq=a_eq.tocsr(), b_eq=np.diff(fixes),
            bounds=[(max(1e-6, float(d.min())/4), p) for p in plafonds]+[(0, None)]*n,
            method='highs')
        if resultat.success:
            nouvelles = np.r_[lignes[0], lignes[0]+np.cumsum(resultat.x[:n])]
            # Restaurer les flottants exacts des interfaces apres cumul.
            nouvelles[indices] = fixes
            ecarts = np.diff(nouvelles)
            rapports = np.maximum(ecarts[1:]/ecarts[:-1], ecarts[:-1]/ecarts[1:])
            if rapports.max() <= rapport_max*(1+1e-7):
                return nouvelles
        # Trop peu de cellules au voisinage d'une interface fine : ajouter
        # localement avant de retenter la repartition globale.
        voisin = np.minimum(np.r_[np.inf, d[:-1]], np.r_[d[1:], np.inf])
        idx = np.flatnonzero(d > rapport_max*voisin*(1+1e-10))
        lignes = _uniques(np.r_[lignes, (lignes[idx]+lignes[idx+1])/2])
    raise RuntimeError('impossible de graduer la grille en conservant les interfaces')


def _proprietes_matiere(csx):
    """Interfaces, bornes dielectriques, ports et modeles de materiau."""
    interfaces = {a: [] for a in 'xyz'}
    dielectriques, ports, definitions = [], [], []
    for prop in csx.GetAllProperties():
        nom = prop.GetName()
        # Les sondes de courant sont placees sur la grille duale par openEMS.
        sonde = nom.startswith(('port_it_', 'port_ut_', 'port_excite_'))
        epsilon = None
        if hasattr(prop, 'GetMaterialProperty'):
            epsilon = float(np.max(np.asarray(prop.GetMaterialProperty('epsilon'))))
            definition = None
            try:
                brut = prop.GetAttributeValue(ATTRIBUT_MODELE)
                if brut:
                    definition = json.loads(brut)
            except (ValueError, TypeError):
                pass
            if definition:
                epsilon = max(epsilon, definition.get('epsilon_statique', epsilon))
                definitions.append(dict(nom=nom, **definition))
            else:
                definitions.append(dict(nom=nom, type='material_constant',
                    epsilon=epsilon,
                    kappa_s_m=float(np.max(np.asarray(prop.GetMaterialProperty('kappa'))))))
        for prim in prop.GetAllPrimitives():
            b = np.asarray(prim.GetBoundBox(), dtype=float)
            if not sonde:
                for i, axe in enumerate('xyz'):
                    interfaces[axe].extend(b[:, i])
            if epsilon is not None and epsilon > 1:
                dielectriques.append((b, epsilon))
            if nom.startswith('port_resist_'):
                ports.append(b)
    return interfaces, dielectriques, ports, definitions


def verifie_emprise(csx, demi, lz, marge=1e-6):
    """Refuse une geometrie hors des bornes annoncees par pose()."""
    boites = [np.asarray(p.GetBoundBox(), dtype=float)
              for prop in csx.GetAllProperties() for p in prop.GetAllPrimitives()]
    if not boites:
        return None
    boite = np.array([np.min([b[0] for b in boites], axis=0),
                      np.max([b[1] for b in boites], axis=0)])
    permis = np.array([[-demi, -demi, float(np.min(lz))],
                       [demi, demi, float(np.max(lz))]])
    if np.any(boite[0] < permis[0]-marge) or np.any(boite[1] > permis[1]+marge):
        raise RuntimeError(f'geometrie hors volume annonce : {boite.tolist()} '
                           f'au lieu de {permis.tolist()}. Verifier les axes '
                           'des polygones (normale y : coordonnees z,x).')
    return boite


def resume_maillage(csx):
    axes = {}
    for axe in 'xyz':
        lignes = np.asarray(csx.GetGrid().GetLines(axe), dtype='<f8')
        d = np.diff(lignes)
        if not d.size or np.any(d <= 0) or not np.all(np.isfinite(lignes)):
            raise ValueError('maillage invalide sur '+axe)
        rapports = np.maximum(d[1:]/d[:-1], d[:-1]/d[1:])
        axes[axe] = dict(lignes=len(lignes), minimum_mm=float(d.min()),
                         maximum_mm=float(d.max()),
                         rapport_voisin_max=float(rapports.max()) if rapports.size else 1.,
                         bornes_mm=[float(lignes[0]), float(lignes[-1])],
                         sha256=hashlib.sha256(lignes.tobytes()).hexdigest())
    mini_m = np.array([axes[a]['minimum_mm'] for a in 'xyz'])*1e-3
    return dict(axes=axes,
                cellules=int(np.prod([axes[a]['lignes']-1 for a in 'xyz'])),
                dt_cfl_vide_s=float(1/(C*np.sqrt(np.sum(1/mini_m**2)))))


def verifie_maillage(csx, maille_cible, rapport_max=None):
    """Controle maille AIR finale; rend (minima mm, CFL anisotrope s)."""
    resume = resume_maillage(csx)
    for axe, d in resume['axes'].items():
        if d['maximum_mm'] > maille_cible*(1+1e-8):
            raise ValueError(f'maille trop grande sur {axe}: {d["maximum_mm"]:.6g} '
                             f'> {maille_cible:.6g} mm')
        if rapport_max and d['rapport_voisin_max'] > rapport_max*(1+1e-8):
            raise ValueError('rapport de cellules excessif sur '+axe)
    return ({a: d['minimum_mm'] for a, d in resume['axes'].items()},
            resume['dt_cfl_vide_s'])


def _durations(montage, csx, n_pas=None, duree_ns=None, dt_s=None):
    a, m = montage.acquisition, montage.maillage
    resume = resume_maillage(csx)
    dt = dt_s if dt_s is not None else m.facteur_courant*resume['dt_cfl_vide_s']
    taille_z_m = np.ptp(resume['axes']['z']['bornes_mm'])*1e-3
    explicite = duree_ns if duree_ns is not None else m.duree_ns
    duree = (explicite*1e-9 if explicite is not None else
             max(1/a.df, 4*taille_z_m/C+20e-9))
    if not np.isfinite(duree) or duree <= 0:
        raise ValueError('duree physique invalide')
    # La derniere sonde est a (NrTS-1)*dt : prevoir un pas de plus.
    nombre = int(n_pas) if n_pas is not None else int(np.ceil(duree/dt))+1
    if nombre < 2 or nombre > m.n_pas_max:
        raise ValueError(f'{nombre} pas necessaires, n_pas_max={m.n_pas_max}; '
                         'augmenter la limite, jamais tronquer en silence')
    return dict(dt_s=dt, n_pas=nombre, duree_demandee_s=float(duree),
                duree_prevue_s=(nombre-1)*dt, fin_energie_active=False,
                critere_fin_db_configure=m.critere_fin,
                couvre_inverse_df=bool((nombre-1)*dt >= 1/a.df),
                dt_calibre_operateur=dt_s is not None,
                methode=('TimeStep calibre sur operateur openEMS reel' if dt_s is not None
                         else 'ESTIMATION CFL vide; calibration operateur requise avant Run'))


def construit(montage: Montage, antenne_mod, x_cm=None, dossier=None,
              x_domaine=None, n_pas=None, distances_communes_cm=None,
              duree_ns=None, dt_impose_s=None):
    """Rend (FDTD, CSX, port, chemin absolu), sans ecrire ni calculer.

    distances_communes_cm impose toutes les faces de toutes les plaques,
    meme dans le fond. x_domaine est conserve pour les anciens appelants.
    """
    from openEMS import openEMS
    from CSXCAD import ContinuousStructure
    from CSXCAD.SmoothMeshLines import SmoothMeshLines
    a, pl, m = montage.acquisition, montage.plaque, montage.maillage
    if m.symetrie:
        raise ValueError('plans de symetrie non implementes : utiliser symetrie=False')
    if not (0 < a.f_min < a.f_max and a.points >= 2):
        raise ValueError('acquisition invalide')
    if m.marge_pml != 8:
        raise ValueError('PML_8 impose marge_pml=8 cellules')
    fdtd = openEMS(NrTS=m.n_pas_max, EndCriteria=0, TimeStepMethod=1)
    fdtd.SetGaussExcite(0.5*(a.f_min+a.f_max), 0.5*(a.f_max-a.f_min))
    fdtd.SetBoundaryCond(['PML_8']*6)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    grille = csx.GetGrid()
    grille.SetDeltaUnit(1e-3)
    port, lx, ly, lz, demi = antenne_mod.pose(csx, fdtd, a)
    verifie_emprise(csx, demi, lz)
    interfaces, dielectriques, ports, _ = _proprietes_matiere(csx)
    distances = list(distances_communes_cm or ())
    if x_domaine is not None:
        distances.append(x_domaine)
    if x_cm is not None:
        if distances_communes_cm is not None and x_cm not in distances:
            raise ValueError('la cible ne figure pas dans distances_communes_cm')
        distances.append(x_cm)
    distances = sorted(set(float(x) for x in distances))
    if any(not np.isfinite(x) or x <= 0 for x in distances):
        raise ValueError('distances de plaque non positives ou non finies')
    if distances:
        demi = max(demi, pl.cote/2)
        for axe in 'xy':
            interfaces[axe].extend([-pl.cote/2, pl.cote/2])
        for x in distances:
            interfaces['z'].extend([x*10, x*10+pl.epaisseur])
    if x_cm is not None:
        csx.AddMetal('plaque').AddBox(
            [-pl.cote/2, -pl.cote/2, x_cm*10],
            [pl.cote/2, pl.cote/2, x_cm*10+pl.epaisseur], priority=10)
    air = C/a.f_max*1e3/m.mailles_par_lambda_air
    marge = marge_air(a, m)+8*air
    z_min = min(0., float(np.min(lz)))-marge
    z_max = max(float(np.max(lz)),
                distances[-1]*10+pl.epaisseur if distances else 0.)+marge
    bornes = dict(x=[-demi-marge, demi+marge], y=[-demi-marge, demi+marge],
                  z=[z_min, z_max])
    declares = dict(x=lx, y=ly, z=lz)
    for i, axe in enumerate('xyz'):
        fixes = interfaces[axe]+bornes[axe]
        lignes = _fusionne(fixes, declares[axe], m.maille_min/2)
        detail_zones = []
        for b in ports:
            zone = [b[0, i]-2*m.maille_min, b[1, i]+2*m.maille_min]
            detail_zones.append(zone)
            lignes = _fusionne(lignes, zone, m.maille_min/2)
            fixes.extend([float(lignes[np.argmin(abs(lignes-z))]) for z in zone])
        def taille_max(milieu):
            cible = air
            for b, epsilon in dielectriques:
                if b[0, i]-1e-8 <= milieu <= b[1, i]+1e-8:
                    cible = min(cible, C/a.f_max*1e3/(np.sqrt(epsilon)*m.mailles_par_lambda))
            if any(za <= milieu <= zb for za, zb in detail_zones):
                cible = min(cible, m.maille_min)
            return cible
        nouvelles = [lignes]
        for lo, hi in zip(lignes[:-1], lignes[1:]):
            cible = taille_max((lo+hi)/2)
            # L'air sera gradue depuis les cellules fines, plutot que rempli
            # d'emblee par des intervalles grossiers presque uniformes.
            if cible < air*(1-1e-12):
                n = max(1, int(np.ceil((hi-lo)/cible)))
                nouvelles.append(np.linspace(lo, hi, n+1))
        lissees = SmoothMeshLines(np.concatenate(nouvelles), air,
                                  ratio=1.2, check_symmetry=False)
        grille.SetLines(axe, _gradue(lissees, m.rapport_max, fixes, taille_max))
    verifie_maillage(csx, air, m.rapport_max)
    # Verification independante des tailles dans TOUTE la projection du
    # substrat, apres redistribution des points libres.
    for b, epsilon in dielectriques:
        limite = C/a.f_max*1e3/(np.sqrt(epsilon)*m.mailles_par_lambda)
        for i, axe in enumerate('xyz'):
            l = np.asarray(grille.GetLines(axe))
            milieu = (l[:-1]+l[1:])/2
            d = np.diff(l)[(milieu >= b[0, i]-1e-8) & (milieu <= b[1, i]+1e-8)]
            if d.size and d.max() > limite*(1+1e-7):
                raise ValueError(f'maille de substrat excessive sur {axe}')
    # Les minima par axe rendent le CFL conservatif meme s'ils se trouvent
    # en des lieux differents. Le modele Debye impose epsilon_inf > 1.
    execution = _durations(montage, csx, n_pas, duree_ns, dt_impose_s)
    if dt_impose_s is not None:
        fdtd.SetTimeStep(execution['dt_s'])
    else:
        fdtd.SetTimeStepFactor(m.facteur_courant)
    fdtd.SetNumberOfTimeSteps(execution['n_pas'])
    # Sondes a chaque pas pour verifier le pas de temps effectif et la duree.
    fdtd.SetOverSampling(int(np.ceil(1/(2*a.f_max*execution['dt_s'])))+1)
    dossier = os.path.abspath(dossier or os.path.join(
        'resultats', 'fdtd', antenne_mod.NOM,
        'antenne_seule' if x_cm is None else f'plaque_{x_cm:g}cm'))
    return fdtd, csx, port, dossier


def estime_cout(montage: Montage, x_cm=None, demi_etendue_mm=60.0, *,
                antenne_mod=None, distances_communes_cm=None, duree_ns=None):
    """Cellules reelles, pas imposes, minutes indicatives a 30 Mcellules/s.

    Construit la vraie grille sans Run ni fichiers. demi_etendue_mm reste
    accepte pour compatibilite; l'encombrement vient maintenant de pose().
    """
    antenne_mod = antenne_mod or charge_antenne('uwb_surveyor')
    fdtd, csx, _, _ = construit(montage, antenne_mod, x_cm=x_cm,
                               distances_communes_cm=distances_communes_cm,
                               duree_ns=duree_ns)
    resume = resume_maillage(csx)
    pas = _durations(montage, csx, duree_ns=duree_ns)['n_pas']
    return resume['cellules'], pas, resume['cellules']*pas/30e6/60


def _sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, 'rb') as f:
        for bloc in iter(lambda: f.read(1024*1024), b''):
            h.update(bloc)
    return h.hexdigest()


def _sources():
    sources = list(Path(DOSSIER_ANTENNES).glob('*/geometrie.py'))
    sources += [Path(ICI)/n for n in ('fdtd.py', 'banc.py', 'materiaux.py',
                                     'connectique.py') if (Path(ICI)/n).is_file()]
    return {str(p.relative_to(ICI)).replace('\\', '/'): _sha256(p) for p in sources}


def _sauve_manifeste(dossier, manifeste):
    chemin = Path(dossier)/'simulation_manifest.json'
    temporaire = chemin.with_suffix('.json.tmp')
    temporaire.write_text(json.dumps(manifeste, ensure_ascii=False, indent=2,
                                     allow_nan=False), encoding='utf-8')
    temporaire.replace(chemin)


def _jsonable(valeur):
    if isinstance(valeur, np.ndarray):
        return valeur.tolist()
    if isinstance(valeur, np.generic):
        return valeur.item()
    if isinstance(valeur, dict):
        return {str(k): _jsonable(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_jsonable(v) for v in valeur]
    return valeur


def _calibre_dt(montage, antenne_mod, x_cm, dossier, *,
                x_domaine=None, distances_communes_cm=None, fils=None):
    """Deux iterations auto pour lire le dt de l'operateur REEL, archivees.

    Le calcul du solveur tient compte des cellules, des PEC et des elements
    localises. Son dt peut etre plus petit que le CFL vide sur les minima.
    La troncature volontaire du pulse n'affecte pas le dt de l'operateur.
    """
    p = Path(dossier).resolve()
    if p.exists() and any(p.iterdir()):
        raise FileExistsError('calibration de dt existante : '+str(p))
    p.mkdir(parents=True, exist_ok=True)
    f, c, _, _ = construit(montage, antenne_mod, x_cm, dossier=str(p),
        x_domaine=x_domaine, n_pas=2, distances_communes_cm=distances_communes_cm)
    f.Write2XML(str(p/'entree_calibration.xml'))
    retour = os.getcwd()
    try:
        resultat = f.Run(str(p), cleanup=False, numThreads=fils or 0,
                         verbose=0, dump_statistics=True)
        if resultat not in (None, 0):
            raise RuntimeError(f'echec de preparation operateur : {resultat}')
    finally:
        os.chdir(retour)
    stats = np.loadtxt(p/'openEMS_stats.txt', comments='%')
    dt = float(stats[1])
    if not np.isfinite(dt) or dt <= 0:
        raise RuntimeError('dt operateur non valide')
    poles = [t for definition in _proprietes_matiere(c)[3]
             for t in definition.get('relaxation_s', [])]
    # openEMS ignore une relaxation plus courte que trois pas de temps.
    # Conserver une marge et ne jamais ignorer un pole du modele annonce.
    dt_final = min(dt*0.999, min(poles)/4 if poles else dt)
    primitives = [dict(propriete=prop.GetName(), index=i,
                       type=pr.GetType(), utilise=bool(pr.GetPrimitiveUsed()),
                       bornes_mm=np.asarray(pr.GetBoundBox()).tolist())
                  for prop in c.GetAllProperties()
                  for i, pr in enumerate(prop.GetAllPrimitives())]
    details = dict(dt_operateur_s=dt, dt_retenu_s=dt_final,
                   cellules_annoncees_solveur=int(stats[0]),
                   iterations_calibration=int(stats[2]),
                   finalite='calibration du dt uniquement, pulse volontairement tronque',
                   primitives=primitives,
                   fichiers_sha256={f.name: _sha256(f) for f in p.iterdir() if f.is_file()})
    (p/'calibration.json').write_text(json.dumps(details, ensure_ascii=False,
                                    indent=2), encoding='utf-8')
    return dt_final, details


def lance(montage: Montage, antenne_mod, x_cm=None, dossier=None,
          apercu=False, fils=None, verbose=0, x_domaine=None, n_pas=None,
          distances_communes_cm=None, duree_ns=None, dt_impose_s=None,
          calibration_info=None):
    """Execute dans un dossier neuf; rend (frequences, S11 complexe)."""
    fdtd, csx, port, dossier = construit(montage, antenne_mod, x_cm, dossier,
        x_domaine, n_pas, distances_communes_cm, duree_ns)
    p = Path(dossier)
    if p.exists() and any(p.iterdir()):
        raise FileExistsError(f'dossier de calcul non vide : {dossier}; '
                              'choisir un nouveau dossier pour preserver les preuves')
    p.mkdir(parents=True, exist_ok=True)
    if dt_impose_s is None:
        dt_impose_s, calibration_info = _calibre_dt(
            montage, antenne_mod, x_cm, p/'_calibration_dt',
            x_domaine=x_domaine, distances_communes_cm=distances_communes_cm, fils=fils)
        fdtd, csx, port, dossier = construit(montage, antenne_mod, x_cm,
            dossier, x_domaine, n_pas, distances_communes_cm, duree_ns, dt_impose_s)
    else:
        fdtd, csx, port, dossier = construit(montage, antenne_mod, x_cm,
            dossier, x_domaine, n_pas, distances_communes_cm, duree_ns, dt_impose_s)
    execution = _durations(montage, csx, n_pas, duree_ns, dt_impose_s)
    resume = resume_maillage(csx)
    np.savez_compressed(p/'maillage.npz',
        **{a: np.asarray(csx.GetGrid().GetLines(a), dtype='<f8') for a in 'xyz'})
    fdtd.Write2XML(str(p/'entree_openems.xml'))
    geometrie = {nom: _jsonable(getattr(antenne_mod, nom)())
                 for nom in ('cotes', 'contours_mm', 'vias_mm', 'trous_mm', 'materiau')
                 if callable(getattr(antenne_mod, nom, None))}
    (p/'geometrie.json').write_text(json.dumps(geometrie, ensure_ascii=False,
                                  indent=2, allow_nan=False), encoding='utf-8')
    import openEMS
    import CSXCAD
    import scipy
    for source in _sources():
        destination = p/'sources'/source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(ICI)/source, destination)
    manifeste = dict(schema_version=1, etat='prepare', antenne=antenne_mod.NOM,
        cible_cm=x_cm, distances_communes_cm=list(distances_communes_cm or ()),
        x_domaine_cm=x_domaine, montage=asdict(montage), maillage=resume,
        execution=execution, materiaux=_proprietes_matiere(csx)[3],
        calibration_dt=calibration_info,
        sources_sha256=_sources(), entree_xml_sha256=_sha256(p/'entree_openems.xml'),
        geometrie_sha256=_sha256(p/'geometrie.json'),
        environnement=dict(python=platform.python_version(), numpy=np.__version__,
            scipy=scipy.__version__, csxcad=getattr(CSXCAD, '__version__', 'inconnu'),
            dtype_maillage='float64 little-endian',
            openems=getattr(openEMS, '__version__', 'inconnu')),
        debut_utc=datetime.now(timezone.utc).isoformat())
    _sauve_manifeste(dossier, manifeste)
    print(f'  maillage : {resume["cellules"]:,} cellules, '
          f'dt={execution["dt_s"]*1e12:.4f} ps, {execution["n_pas"]} pas, '
          f'{execution["duree_prevue_s"]*1e9:.3f} ns imposes')
    retour = os.getcwd()
    try:
        manifeste['etat'] = 'apercu' if apercu else 'calcul_en_cours'
        _sauve_manifeste(dossier, manifeste)
        fdtd.Run(dossier, cleanup=False, setup_only=apercu,
                 numThreads=fils or 0, verbose=verbose, dump_statistics=True)
        if apercu:
            return None, None
        sondes = {}
        for nom in ('port_ut_1', 'port_it_1'):
            donnees = np.loadtxt(p/nom, comments='%')
            if donnees.ndim != 2 or len(donnees) < 2 or not np.all(np.isfinite(donnees)):
                raise RuntimeError('sonde absente, trop courte ou non finie : '+nom)
            dt_reel = float(np.median(np.diff(donnees[:, 0])))
            if not np.isclose(dt_reel, execution['dt_s'], rtol=2e-7, atol=1e-18):
                raise RuntimeError(f'dt mesure {dt_reel} != dt impose '
                                   f'{execution["dt_s"]}; extraction refusee')
            if donnees[-1, 0]-donnees[0, 0] < execution['duree_prevue_s']-2*dt_reel:
                raise RuntimeError('sonde tronquee avant la duree imposee : '+nom)
            sondes[nom] = dict(echantillons=len(donnees), dt_effectif_s=dt_reel,
                debut_s=float(donnees[0, 0]), fin_s=float(donnees[-1, 0]),
                sha256=_sha256(p/nom))
        a = montage.acquisition
        freqs = np.linspace(a.f_min, a.f_max, a.points)
        port.CalcPort(dossier, freqs, ref_impedance=a.z_ref)
        s11 = port.uf_ref/port.uf_inc
        if not np.all(np.isfinite(s11)):
            raise RuntimeError('S11 non fini : verifier excitation et port')
        ecrit_s1p(str(p/'s11.s1p'), freqs, s11, z_ref=a.z_ref,
                   commentaire=f'openEMS, {antenne_mod.NOM}; voir simulation_manifest.json')
        manifeste.update(etat='termine', sondes=sondes)
        return freqs, s11
    except Exception as exc:
        manifeste.update(etat='echec', erreur=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        os.chdir(retour)
        manifeste['fin_utc'] = datetime.now(timezone.utc).isoformat()
        manifeste['fichiers_sha256'] = {
            str(f.relative_to(p)).replace('\\', '/'): _sha256(f)
            for f in p.rglob('*') if f.is_file() and
            f.name not in ('simulation_manifest.json', 'simulation_manifest.json.tmp')}
        _sauve_manifeste(dossier, manifeste)


def serie(montage: Montage, antenne_mod, distances_cm, dossier_base=None,
          fils=None, verbose=0, duree_ns=None):
    """Fond puis cibles, grilles et durees strictement identiques."""
    distances = sorted(set(float(x) for x in distances_cm))
    if not distances:
        raise ValueError('serie vide')
    base = Path(dossier_base or os.path.join('resultats', 'fdtd', antenne_mod.NOM))
    plans = []
    for x in [None]+distances:
        nom = 'fond' if x is None else f'plaque_{x:g}cm'
        if (base/nom).exists() and any((base/nom).iterdir()):
            raise FileExistsError(f'dossier existant : {base/nom}')
        f, c, _, _ = construit(montage, antenne_mod, x_cm=x,
            distances_communes_cm=distances, duree_ns=duree_ns, dossier=str(base/nom))
        plans.append((resume_maillage(c), _durations(montage, c, duree_ns=duree_ns)))
    if any(p != plans[0] for p in plans[1:]):
        raise RuntimeError('les scenes de serie ne partagent pas le meme maillage/temps')
    calibrations = {}
    for x in [None]+distances:
        nom = 'fond' if x is None else f'plaque_{x:g}cm'
        calibrations[nom] = _calibre_dt(montage, antenne_mod, x,
            base/'_calibrations_dt'/nom, distances_communes_cm=distances, fils=fils)
    dt_commun = min(c[0] for c in calibrations.values())
    infos = dict(dt_commun_s=dt_commun,
                 scenes={nom: c[1] for nom, c in calibrations.items()})
    freqs, fond = lance(montage, antenne_mod, dossier=str(base/'fond'),
        distances_communes_cm=distances, duree_ns=duree_ns, fils=fils, verbose=verbose,
        dt_impose_s=dt_commun, calibration_info=infos)
    mesures = {}
    for x in distances:
        _, mesures[x] = lance(montage, antenne_mod, x,
            dossier=str(base/f'plaque_{x:g}cm'), distances_communes_cm=distances,
            duree_ns=duree_ns, fils=fils, verbose=verbose,
            dt_impose_s=dt_commun, calibration_info=infos)
    return freqs, fond, mesures


def ecrit_s1p(chemin, freqs, s11, z_ref=50.0, commentaire=''):
    """Touchstone 1 port complexe, grille et valeurs controlees."""
    f, s = np.asarray(freqs), np.asarray(s11)
    if (f.ndim != 1 or s.shape != f.shape or not len(f) or
            not np.all(np.isfinite(f)) or not np.all(np.isfinite(s))):
        raise ValueError('frequences/S11 incompatibles ou non finis')
    if np.any(np.diff(f) <= 0):
        raise ValueError('frequences non croissantes')
    os.makedirs(os.path.dirname(chemin) or '.', exist_ok=True)
    with open(chemin, 'w', encoding='ascii') as out:
        if commentaire:
            out.write('! '+commentaire.encode('ascii', 'replace').decode()+'\n')
        out.write(f'# Hz S RI R {z_ref:g}\n')
        for fr, valeur in zip(f, s):
            out.write(f'{fr:.12g} {valeur.real:.12e} {valeur.imag:.12e}\n')
    return chemin
