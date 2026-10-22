"""Moteur separe maillage_controle_v2 ; copie de F1, physique/CAD identiques.

Scenes openEMS, maillages controles et executions archivables.

Une serie fond/cibles partage exactement les memes lignes, le meme pas de
 temps CFL conservatif et le meme nombre de pas. Les sondes temporelles,
 l'entree XML, le maillage et un manifeste SHA-256 restent dans chaque calcul.
 La construction et l'estimation de cout n'executent jamais le solveur.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
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





NOM_MOTEUR = 'maillage_controle_v2'
NIVEAUX = {
    'base': dict(mailles_par_lambda=16, mailles_par_lambda_air=16, maille_min=.15),
    'fin': dict(mailles_par_lambda=24, mailles_par_lambda_air=16, maille_min=.10),
}


def _configuration_base(m):
    return all(getattr(m, k) == v for k, v in NIVEAUX['base'].items())


def _reglages_controles(montage, mod):
    m = montage.maillage
    if mod.NOM not in ('diamant_uwb', 'diamant_uwb_x18', 'vivaldi_tomographie'):
        raise ValueError('moteur controle reserve aux trois PCB de production')
    if (m.mailles_par_lambda < 16 or m.mailles_par_lambda_air != 16 or
            not 0 < m.maille_min <= .15 or m.rapport_max != 1.5 or m.marge_pml != 8):
        raise ValueError('resolution F2 inconnue ou plus grossiere ; air16, rapport1.5, PML8 imposes')
    h = float(mod.cotes()['h'])
    normale = int(math.ceil(h/m.maille_min))
    if normale % 2 == 0:
        normale += 1
    diametres = [float(d) for _, _, d in mod.vias_mm()]
    if not diametres or len(set(diametres)) != 1:
        raise ValueError('vias de diametre commun requis pour cette politique')
    via = 2*int(math.ceil((diametres[0]/(.8*m.maille_min))/2))
    return dict(lambda_substrat=m.mailles_par_lambda, normal=normale,
                via=via, sma_max_mm=m.maille_min)


def _unique_controle(valeurs):
    return _uniques(valeurs)

def _ligne_exacte(g, p):
    return bool(np.any(g == p))

def _largeur_locale(g, p):
    j = int(np.clip(np.searchsorted(g, p, side='right')-1, 0, len(g)-2))
    return dict(point_mm=float(p), bornes_mm=[float(g[j]), float(g[j+1])],
                pas_mm=float(g[j+1]-g[j]), sur_ligne=_ligne_exacte(g, p))

def _subdivisions_controle(lo, hi, maximum):
    n = max(1, int(math.ceil((hi-lo)/maximum-1e-11)))
    return np.linspace(lo, hi, n+1)

def _gradue_plancher(lignes, rapport_max, fixes, taille_max, plancher):
    """Meme probleme lineaire que F1, avec minimum PHYSIQUE explicite.

    Un point libre de lissage ne justifie pas un pas moindre que la plus
    petite cellule prescrite. Les ancres restent toutes exactes ; si elles
    etaient incompatibles le prototype echoue au lieu de les deplacer.
    """
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix
    lignes, fixes = _unique_controle(np.r_[lignes, fixes]), _unique_controle(fixes)
    for _ in range(20):
        d = np.diff(lignes)
        ratios = np.maximum(d[1:]/d[:-1], d[:-1]/d[1:])
        caps_ok = all(v <= taille_max((a+b)/2)*(1+1e-8)
                      for a,b,v in zip(lignes[:-1],lignes[1:],d))
        if caps_ok and d.min() >= plancher*(1-1e-8) and ratios.max() <= rapport_max*(1+1e-10):
            return lignes
        n = len(d)
        au = lil_matrix((2*(n-1)+2*n, 2*n), dtype=float)
        bu = np.zeros(au.shape[0])
        for j in range(n-1):
            au[2*j,j],au[2*j,j+1] = 1.,-rapport_max
            au[2*j+1,j],au[2*j+1,j+1] = -rapport_max,1.
        for j in range(n):
            k = 2*(n-1)+2*j
            au[k,j],au[k,n+j],bu[k] = 1.,-1.,d[j]
            au[k+1,j],au[k+1,n+j],bu[k+1] = -1.,-1.,-d[j]
        indices = np.array([int(np.argmin(abs(lignes-v))) for v in fixes])
        ae = lil_matrix((len(fixes)-1,2*n),dtype=float)
        for j,(a,b) in enumerate(zip(indices[:-1],indices[1:])):
            ae[j,a:b] = 1.
        plafonds = [taille_max((a+b)/2) for a,b in zip(lignes[:-1],lignes[1:])]
        r = linprog(np.r_[np.zeros(n),1/np.maximum(d,1e-6)],
            A_ub=au.tocsr(),b_ub=bu,A_eq=ae.tocsr(),b_eq=np.diff(fixes),
            bounds=[(plancher*(1-1e-10),v) for v in plafonds]+[(0,None)]*n,
            method='highs')
        if r.success:
            resultat = np.r_[lignes[0],lignes[0]+np.cumsum(r.x[:n])]
            resultat[indices] = fixes
            dd = np.diff(resultat)
            caps_ok = all(v <= taille_max((a+b)/2)*(1+1e-8)
                          for a,b,v in zip(resultat[:-1],resultat[1:],dd))
            if caps_ok and dd.min() >= plancher*(1-1e-8) and np.max(np.maximum(dd[1:]/dd[:-1],dd[:-1]/dd[1:])) <= rapport_max*(1+1e-7):
                return resultat
        voisin = np.minimum(np.r_[np.inf,d[:-1]],np.r_[d[1:],np.inf])
        idx = np.flatnonzero((d > rapport_max*voisin*(1+1e-10)) &
                             (d >= 2*plancher*(1-1e-10)))
        if not len(idx):
            raise RuntimeError('Ancres/graduation incompatibles avec plancher physique')
        lignes = _unique_controle(np.r_[lignes,(lignes[idx]+lignes[idx+1])/2])
    raise RuntimeError('Graduation controlee non resolue')

def _aretes_rectilignes(mod):
    """Ancre la coordonnee constante, pas les deux extremites d'une diagonale.

    Les segments droits >1mm sont reels. Les petits segments des cercles,
    et les extremites des tapers, ne sont pas des plans a projeter partout.
    """
    resultat = [[], []]
    for couche in ('F_Cu', 'B_Cu'):
        for contour in mod.contours_mm()[couche]:
            pts = np.asarray(contour, dtype=float)
            for p, q in zip(pts, np.roll(pts, -1, axis=0)):
                delta = abs(q-p)
                if delta[0] < 1e-9 and delta[1] > 1.0:
                    resultat[0].append(float(p[0]))
                elif delta[1] < 1e-9 and delta[0] > 1.0:
                    resultat[1].append(float(p[1]))
    return resultat

def _applique_grille_controlee(montage, mod, csx, boite_pcb, boite_domaine,
                               interfaces, dielectriques, *, grille_base=None):
    from CSXCAD.SmoothMeshLines import SmoothMeshLines
    import connectique
    p = _reglages_controles(montage, mod)
    niveau = 'base' if _configuration_base(montage.maillage) else 'fin'
    d = mod.cotes()
    h = float(d['h'])
    verticale = mod.NOM == 'vivaldi_tomographie'
    normal, propagation = ('y', 'z') if verticale else ('z', 'y')
    u0 = 0.0 if verticale else -float(d['carte_w'])/2
    largeur = float(d['largeur_ligne'] if verticale else d['wf'])
    air = C/montage.acquisition.f_max*1e3/16
    garde = marge_air(montage.acquisition, montage.maillage)
    boite = np.asarray(boite_pcb, dtype=float)
    interieurs = {axe: [float(boite_domaine[0,i]-garde), float(boite_domaine[1,i]+garde)]
                  for i,axe in enumerate('xyz')}
    droits_x, droits_u = _aretes_rectilignes(mod)
    ancres = {a: list(interfaces[a]) for a in 'xyz'}
    ancres['x'].extend(droits_x + [0., -largeur/2, largeur/2])
    ancres['x'].extend(x for x, _, _ in mod.vias_mm())
    ancres[propagation].extend(droits_u)
    g, details = {}, {}
    for i, axe in enumerate('xyz'):
        lo, hi = interieurs[axe]
        pml = np.r_[lo-air*np.arange(8, -1, -1), hi+air*np.arange(0, 9)]
        fixes = _unique_controle(np.r_[ancres[axe], pml])
        protegees = []
        interpolations_sma = []
        if axe == normal:
            # Omettre h/2 primaire volontairement : I est dual, h/2 doit
            # etre le centre de la cellule centrale d'un compte impair.
            fixe_normal = np.linspace(0., h, p['normal']+1)
            k = int(np.ceil((h/3)/p['sma_max_mm']))
            fixe_normal = np.r_[np.linspace(-h/3, 0., k+1),
                                 fixe_normal, np.linspace(h, 4*h/3, k+1)]
            protegees.extend(fixe_normal)
        if axe == 'x':
            bornes_sma = _unique_controle(np.r_[fixes[(fixes >= -connectique.MASSE_EXTERIEUR_MM-1e-8) &
                                           (fixes <= connectique.MASSE_EXTERIEUR_MM+1e-8)],
                -connectique.MASSE_EXTERIEUR_MM, 0., connectique.MASSE_EXTERIEUR_MM,
                -connectique.LARGEUR_SIGNAL_MM/2, connectique.LARGEUR_SIGNAL_MM/2])
            for a, b in zip(bornes_sma[:-1], bornes_sma[1:]):
                points = _subdivisions_controle(a, b, p['sma_max_mm'])
                if niveau == 'fin' and not (-connectique.LARGEUR_SIGNAL_MM/2-1e-8 <= a and
                                            b <= connectique.LARGEUR_SIGNAL_MM/2+1e-8):
                    interpolations_sma.extend(points)
                else:
                    protegees.extend(points)
            for x, u, diam in mod.vias_mm():
                # Les parois et le centre etaient deja ancres. Diviser
                # chaque demi-diametre donne 4 ou6 cellules reelles.
                protegees.extend(np.linspace(x-diam/2, x+diam/2, p['via']+1))
        if axe == propagation:
            # Port au centre d'une zone UNIFORME de longueur3,2mm, meme
            # longueur physique aux deux resolutions, source a u0 exact.
            cellules_par_h = int(np.ceil(h/p['sma_max_mm']))
            protegees.extend(u0+np.linspace(-h, h, 2*cellules_par_h+1))
            limite = max(u+connectique.PASTILLE_DIAMETRE_MM/2 for _, u, _ in mod.vias_mm())
            a_sma = _unique_controle(np.r_[fixes[(fixes >= u0+h-1e-8) & (fixes <= limite+1e-8)], u0+h, limite])
            for a, b in zip(a_sma[:-1], a_sma[1:]):
                points = _subdivisions_controle(a, b, p['sma_max_mm'])
                if niveau == 'fin':
                    interpolations_sma.extend(points)
                else:
                    protegees.extend(points)
            for x, u, diam in mod.vias_mm():
                protegees.extend(np.linspace(u-diam/2, u+diam/2, p['via']+1))
        fixes = _unique_controle(np.r_[fixes, protegees])
        if grille_base is not None:
            if axe == 'x':
                bloc = [-connectique.MASSE_EXTERIEUR_MM,connectique.MASSE_EXTERIEUR_MM]
            elif axe == normal:
                bloc = [-h/3,4*h/3]
            else:
                bloc = [u0-h,limite]
            base_axe = grille_base[axe]
            # Variante09 : seul le PCB reel conserve les primaires BASE.
            # L'air peut redistribuer sa graduation jusqu'aux PML fixes.
            dans_pcb = (base_axe >= boite[0,i]-1e-8) & (base_axe <= boite[1,i]+1e-8)
            dehors = base_axe[dans_pcb & ((base_axe <= bloc[0]+1e-8) |
                                         (base_axe >= bloc[1]-1e-8))]
            fixes = _unique_controle(np.r_[fixes,dehors])

        def maximum(milieu):
            if milieu < lo or milieu > hi:
                return air
            cible = air
            for boite, eps in dielectriques:
                if boite[0, i]-1e-8 <= milieu <= boite[1, i]+1e-8:
                    cible = min(cible, C/montage.acquisition.f_max*1e3/
                                (np.sqrt(eps)*p['lambda_substrat']))
            if axe == normal and -h/3 <= milieu <= 4*h/3:
                cible = min(cible, h/p['normal'])
            if axe == 'x' and -connectique.MASSE_EXTERIEUR_MM <= milieu <= connectique.MASSE_EXTERIEUR_MM:
                cible = min(cible, p['sma_max_mm'])
            if axe == propagation and u0-h <= milieu <= limite:
                cible = min(cible, p['sma_max_mm'])
            return cible

        depart = [fixes, np.asarray(interpolations_sma)]
        for a, b in zip(fixes[:-1], fixes[1:]):
            depart.append(_subdivisions_controle(a, b, maximum((a+b)/2)))
        lisse = SmoothMeshLines(np.concatenate(depart), air, ratio=1.2, check_symmetry=False)
        # Les points libres du lissage ne doivent pas fabriquer de cellule
        # plus petite que les details explicitement resolus. Les contraintes
        # physiques restent prioritaires et ne sont jamais supprimees.
        plancher = min(np.diff(_unique_controle(protegees)))
        lisse = _fusionne(fixes, lisse, plancher*(1-1e-10))
        try:
            lignes = _gradue_plancher(lisse, 1.5, fixes, maximum, plancher)
        except RuntimeError as e:
            largeurs = np.diff(fixes)
            j = np.flatnonzero(np.maximum(largeurs[1:]/largeurs[:-1],
                                         largeurs[:-1]/largeurs[1:]) > 1.5+1e-8)
            raise RuntimeError(str(e)+'; '+mod.NOM+'/'+niveau+'/'+axe+
                '; intervalles ancres='+repr([(fixes[k:k+3].tolist(),
                largeurs[k:k+2].tolist()) for k in j[:30]])) from e
        if not all(np.any(lignes == v) for v in fixes):
            raise ValueError('Ancre critique deplacee : '+axe)
        csx.GetGrid().SetLines(axe, lignes)
        g[axe] = np.asarray(csx.GetGrid().GetLines(axe), dtype='<f8')
        details[axe] = dict(ancres_protegees_mm=fixes.tolist(),
            interpolations_sma_initiales_non_protegees_mm=_unique_controle(interpolations_sma).tolist(),
            plancher_points_libres_mm=float(plancher),
            pml_gauche_mm=pml[:9].tolist(), pml_droite_mm=pml[9:].tolist(),
            bloc_port_normal_mm=[-h/3, 4*h/3] if axe == normal else None,
            bloc_port_propagation_mm=[u0-h, u0+h] if axe == propagation else None)
    verifie_maillage(csx, air, 1.5)
    if not _ligne_exacte(g['x'], 0.):
        raise ValueError('Ux0 primaire absent')
    dz = g[normal][(g[normal] >= 0.) & (g[normal] <= h)]
    if len(dz)-1 != p['normal'] or np.min(abs((dz[:-1]+dz[1:])/2-h/2)) > 1e-14:
        raise ValueError('I h/2 dual non respecte')
    return g



def _boite_primitives(csx):
    boites = [np.asarray(pr.GetBoundBox(), dtype=float)
              for prop in csx.GetAllProperties()
              if not prop.GetName().startswith(('port_ut_', 'port_it_', 'port_excite_'))
              for pr in prop.GetAllPrimitives()]
    return np.array([np.min([b[0] for b in boites], axis=0),
                     np.max([b[1] for b in boites], axis=0)])


def _verifie_non_grossissement(grossier, fin, zones):
    for axe, intervalles in zones.items():
        a, b = grossier[axe], fin[axe]
        for lo, hi in intervalles:
            t = np.unique(np.r_[lo, hi, a[(a>lo)&(a<hi)], b[(b>lo)&(b<hi)]])
            milieux = (t[:-1]+t[1:])/2
            da = np.diff(a)[np.clip(np.searchsorted(a,milieux,side='right')-1,0,len(a)-2)]
            db = np.diff(b)[np.clip(np.searchsorted(b,milieux,side='right')-1,0,len(b)-2)]
            if np.any(db > da*(1+1e-8)):
                raise ValueError('grossissement local F2 sur PCB/bloc : '+axe)


def politique_maillage(montage, mod, csx):
    """Metadonnees quantitatives verifiables, derivees des vrais axes."""
    import connectique
    p = _reglages_controles(montage, mod)
    d = mod.cotes()
    verticale = mod.NOM == 'vivaldi_tomographie'
    normal, propagation = ('y','z') if verticale else ('z','y')
    h = float(d['h'])
    u0 = 0. if verticale else -float(d['carte_w'])/2
    grille = {a: np.asarray(csx.GetGrid().GetLines(a),dtype='<f8') for a in 'xyz'}
    faces = grille[normal][(grille[normal]>=0.)&(grille[normal]<=h)]
    return dict(nom=NOM_MOTEUR,configuration={k:getattr(montage.maillage,k) for k in NIVEAUX['base']},
        seed_base=NIVEAUX['base'].copy(),reglages=p,
        normales_mm=[0.,h],axe_normal=normal,axe_propagation=propagation,
        bloc_normal_mm=[-h/3,4*h/3],bloc_propagation_mm=[u0-h,u0+h],
        bloc_sma_x_mm=[-connectique.MASSE_EXTERIEUR_MM,connectique.MASSE_EXTERIEUR_MM],
        bloc_sma_u_mm=[u0-h,max(u+connectique.PASTILLE_DIAMETRE_MM/2 for _,u,_ in mod.vias_mm())],
        U_x0_primaire_exact=bool(np.any(grille['x']==0.)),
        I_dual_hsur2_ecart_mm=float(np.min(abs((faces[:-1]+faces[1:])/2-h/2))),
        cellules_normales=len(faces)-1,
        vias=[dict(x_mm=float(x),u_mm=float(u),diametre_mm=float(diam),
            cellules_transversales=int(sum((grille['x'][:-1]>=x-diam/2-1e-8)&(grille['x'][1:]<=x+diam/2+1e-8))),
            cellules_longitudinales=int(sum((grille[propagation][:-1]>=u-diam/2-1e-8)&(grille[propagation][1:]<=u+diam/2+1e-8))))
            for x,u,diam in mod.vias_mm()],
        garde_hors_pml_mm=marge_air(montage.acquisition,montage.maillage),
        pml8={a:dict(gauche_mm=grille[a][:9].tolist(),droite_mm=grille[a][-9:].tolist()) for a in 'xyz'},
        ancres='primaires BASE conservees dans projection PCB hors blocs SMA ; air libre',
        interpolation_sma='libre hors port uniforme et vias ; interfaces exactes',
        aretes='rectilignes primaires exactes ; pas de regle tiers generalisee',
        port='ideal50ohms au bord PCB ; connecteur coaxial3D non modelise')



def construit(montage: Montage, antenne_mod, x_cm=None, dossier=None,
              x_domaine=None, n_pas=None, distances_communes_cm=None,
              duree_ns=None, dt_impose_s=None):
    """Rend (FDTD, CSX, port, chemin absolu), sans ecrire ni calculer.

    distances_communes_cm impose toutes les faces de toutes les plaques,
    meme dans le fond. x_domaine est conserve pour les anciens appelants.
    """
    from openEMS import openEMS
    from CSXCAD import ContinuousStructure
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
    _reglages_controles(montage, antenne_mod)
    boite_pcb = _boite_primitives(csx)
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
    boite_domaine = boite_pcb.copy()
    if distances:
        boite_domaine[0,:2] = np.minimum(boite_domaine[0,:2],-pl.cote/2)
        boite_domaine[1,:2] = np.maximum(boite_domaine[1,:2],pl.cote/2)
        boite_domaine[1,2] = max(boite_domaine[1,2],distances[-1]*10+pl.epaisseur)
    commun = dict(interfaces=interfaces,dielectriques=dielectriques)
    base = None
    if not _configuration_base(m):
        montage_base = replace(montage,maillage=replace(m,**NIVEAUX['base']))
        base = _applique_grille_controlee(montage_base,antenne_mod,csx,
            boite_pcb,boite_domaine,**commun)
    grille_finale = _applique_grille_controlee(montage,antenne_mod,csx,
        boite_pcb,boite_domaine,grille_base=base,**commun)
    if base is not None:
        d = antenne_mod.cotes()
        normal, propagation = ('y','z') if antenne_mod.NOM == 'vivaldi_tomographie' else ('z','y')
        h = float(d['h'])
        u0 = 0. if propagation == 'z' else -float(d['carte_w'])/2
        import connectique
        zones = {a:[[float(boite_pcb[0,i]),float(boite_pcb[1,i])]] for i,a in enumerate('xyz')}
        zones['x'].append([-connectique.MASSE_EXTERIEUR_MM,connectique.MASSE_EXTERIEUR_MM])
        zones[normal].append([-h/3,4*h/3])
        zones[propagation].append([u0-h,max(u+connectique.PASTILLE_DIAMETRE_MM/2 for _,u,_ in antenne_mod.vias_mm())])
        _verifie_non_grossissement(base,grille_finale,zones)
        for axe in 'xyz':
            if not (np.array_equal(base[axe][:9],grille_finale[axe][:9]) and
                    np.array_equal(base[axe][-9:],grille_finale[axe][-9:])):
                raise ValueError('coordonnees PML F2 differentes de la base')
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
    sources.append(Path(ICI)/'fdtd_maille_controlee.py')
    return {str(p.relative_to(ICI)).replace('\\', '/'): _sha256(p) for p in sources}


def _sauve_manifeste(dossier, manifeste):
    manifeste['moteur'] = NOM_MOTEUR
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
        politique_maillage=politique_maillage(montage, antenne_mod, csx),
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
