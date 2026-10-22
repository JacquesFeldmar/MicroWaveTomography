"""PROTOTYPE de grilles uniquement : aucun Run, aucune qualification.

La geometrie/materialisation provient des neuf sources F1 inchangees.
Les politiques ci-dessous sont des propositions, pas un catalogue approuve.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                 'NUMEXPR_NUM_THREADS'):
    os.environ[variable] = '1'
os.environ['MPLBACKEND'] = 'Agg'
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[2]
ANCRE = SIM/'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'
sys.path.insert(0, str(SIM))
import numpy as np
import fdtd as F
from banc import Acquisition, Maillage, Montage, C
import connectique as K

ANTENNES = ('diamant_uwb', 'diamant_uwb_x18', 'vivaldi_tomographie')
POLITIQUES = {
    'base': dict(lambda_substrat=16, normal=11, via=4, sma_max_mm=.15),
    'fin': dict(lambda_substrat=24, normal=17, via=6, sma_max_mm=.10),
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sources():
    if sha(ANCRE) != '47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383':
        raise ValueError('Ancrage historique modifie')
    attendu = json.loads(ANCRE.read_text(encoding='utf-8'))['sources_controle_sha256']
    actuel = {n: sha(SIM/n) for n in attendu}
    if len(actuel) != 17 or actuel != attendu:
        raise ValueError('Sources historiques17 modifiees')
    return actuel


def unique(valeurs):
    return F._uniques(valeurs)


def ligne_exacte(g, p):
    return bool(np.any(g == p))


def largeur_locale(g, p):
    j = int(np.clip(np.searchsorted(g, p, side='right')-1, 0, len(g)-2))
    return dict(point_mm=float(p), bornes_mm=[float(g[j]), float(g[j+1])],
                pas_mm=float(g[j+1]-g[j]), sur_ligne=ligne_exacte(g, p))


def subdivisions(lo, hi, maximum):
    n = max(1, int(math.ceil((hi-lo)/maximum-1e-11)))
    return np.linspace(lo, hi, n+1)


def arêtes_rectilignes(mod):
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


def scene(montage, mod):
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS
    fdtd = openEMS(NrTS=2, EndCriteria=0, TimeStepMethod=1)
    a = montage.acquisition
    fdtd.SetGaussExcite((a.f_min+a.f_max)/2, (a.f_max-a.f_min)/2)
    fdtd.SetBoundaryCond(['PML_8']*6)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    csx.GetGrid().SetDeltaUnit(1e-3)
    port, lx, ly, lz, demi = mod.pose(csx, fdtd, a)
    F.verifie_emprise(csx, demi, lz)
    return fdtd, csx, port, demi, lz


def construit(mod, niveau):
    """Grille proposee, sans fichier solveur, calibration ou Run."""
    from CSXCAD.SmoothMeshLines import SmoothMeshLines
    p = POLITIQUES[niveau]
    montage = Montage(acquisition=Acquisition(f_min=1e9, f_max=6.3e9, points=213),
        maillage=Maillage(mailles_par_lambda=p['lambda_substrat'],
            mailles_par_lambda_air=16, maille_min=p['sma_max_mm'], n_pas_max=500000))
    fdtd, csx, port, demi, lz = scene(montage, mod)
    interfaces, dielectriques, ports, definitions = F._proprietes_matiere(csx)
    d = mod.cotes()
    h = float(d['h'])
    verticale = mod.NOM == 'vivaldi_tomographie'
    normal, propagation = ('y', 'z') if verticale else ('z', 'y')
    u0 = 0.0 if verticale else -float(d['carte_w'])/2
    largeur = float(d['largeur_ligne'] if verticale else d['wf'])
    air = C/montage.acquisition.f_max*1e3/16
    garde = F.marge_air(montage.acquisition, montage.maillage)
    # Boite physique reelle, pas une demi-etendue cubique. Garder75mm
    # (lambda a f_min /4), puis huit cellules PML exactes aux deux niveaux.
    boites = [np.asarray(prim.GetBoundBox(), dtype=float)
              for prop in csx.GetAllProperties()
              if not prop.GetName().startswith(('port_ut_', 'port_it_', 'port_excite_'))
              for prim in prop.GetAllPrimitives()]
    boite = np.array([np.min([b[0] for b in boites], axis=0),
                      np.max([b[1] for b in boites], axis=0)])
    interieurs = {axe: [float(boite[0,i]-garde), float(boite[1,i]+garde)]
                  for i,axe in enumerate('xyz')}
    droits_x, droits_u = arêtes_rectilignes(mod)
    ancres = {a: list(interfaces[a]) for a in 'xyz'}
    ancres['x'].extend(droits_x + [0., -largeur/2, largeur/2])
    ancres['x'].extend(x for x, _, _ in mod.vias_mm())
    ancres[propagation].extend(droits_u)
    g, details = {}, {}
    for i, axe in enumerate('xyz'):
        lo, hi = interieurs[axe]
        pml = np.r_[lo-air*np.arange(8, -1, -1), hi+air*np.arange(0, 9)]
        fixes = unique(np.r_[ancres[axe], pml])
        protegees = []
        if axe == normal:
            # Omettre h/2 primaire volontairement : I est dual, h/2 doit
            # etre le centre de la cellule centrale d'un compte impair.
            fixe_normal = np.linspace(0., h, p['normal']+1)
            k = int(np.ceil((h/3)/min(p['sma_max_mm'], h/p['normal'])))
            fixe_normal = np.r_[np.linspace(-h/3, 0., k+1),
                                 fixe_normal, np.linspace(h, 4*h/3, k+1)]
            protegees.extend(fixe_normal)
        if axe == 'x':
            bornes_sma = unique(np.r_[fixes[(fixes >= -K.MASSE_EXTERIEUR_MM-1e-8) &
                                           (fixes <= K.MASSE_EXTERIEUR_MM+1e-8)],
                -K.MASSE_EXTERIEUR_MM, 0., K.MASSE_EXTERIEUR_MM,
                -K.LARGEUR_SIGNAL_MM/2, K.LARGEUR_SIGNAL_MM/2])
            for a, b in zip(bornes_sma[:-1], bornes_sma[1:]):
                protegees.extend(subdivisions(a, b, p['sma_max_mm']))
            for x, u, diam in mod.vias_mm():
                # Les parois et le centre etaient deja ancres. Diviser
                # chaque demi-diametre donne 4 ou6 cellules reelles.
                protegees.extend(np.linspace(x-diam/2, x+diam/2, p['via']+1))
        if axe == propagation:
            # Port au centre d'une zone UNIFORME de longueur3,2mm, meme
            # longueur physique aux deux resolutions, source a u0 exact.
            cellules_par_h = int(np.ceil(h/p['sma_max_mm']))
            protegees.extend(u0+np.linspace(-h, h, 2*cellules_par_h+1))
            limite = max(u+K.PASTILLE_DIAMETRE_MM/2 for _, u, _ in mod.vias_mm())
            a_sma = unique(np.r_[fixes[(fixes >= u0+h-1e-8) & (fixes <= limite+1e-8)], u0+h, limite])
            for a, b in zip(a_sma[:-1], a_sma[1:]):
                protegees.extend(subdivisions(a, b, p['sma_max_mm']))
            for x, u, diam in mod.vias_mm():
                protegees.extend(np.linspace(u-diam/2, u+diam/2, p['via']+1))
        fixes = unique(np.r_[fixes, protegees])

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
            if axe == 'x' and -K.MASSE_EXTERIEUR_MM <= milieu <= K.MASSE_EXTERIEUR_MM:
                cible = min(cible, p['sma_max_mm'])
            if axe == propagation and u0-h <= milieu <= limite:
                cible = min(cible, p['sma_max_mm'])
            return cible

        depart = [fixes]
        for a, b in zip(fixes[:-1], fixes[1:]):
            depart.append(subdivisions(a, b, maximum((a+b)/2)))
        lisse = SmoothMeshLines(np.concatenate(depart), air, ratio=1.2, check_symmetry=False)
        # Les points libres du lissage ne doivent pas fabriquer de cellule
        # plus petite que les details explicitement resolus. Les contraintes
        # physiques restent prioritaires et ne sont jamais supprimees.
        plancher = min(np.diff(unique(protegees)))
        lisse = F._fusionne(fixes, lisse, plancher*(1-1e-10))
        try:
            lignes = F._gradue(lisse, 1.5, fixes, maximum)
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
            plancher_points_libres_mm=float(plancher),
            pml_gauche_mm=pml[:9].tolist(), pml_droite_mm=pml[9:].tolist(),
            bloc_port_normal_mm=[-h/3, 4*h/3] if axe == normal else None,
            bloc_port_propagation_mm=[u0-h, u0+h] if axe == propagation else None)
    F.verifie_maillage(csx, air, 1.5)
    if not ligne_exacte(g['x'], 0.):
        raise ValueError('U x0 primaire absent')
    dz = g[normal][(g[normal] >= 0.) & (g[normal] <= h)]
    milieu_dual = (dz[:-1]+dz[1:])/2
    if len(dz)-1 != p['normal'] or np.min(abs(milieu_dual-h/2)) > 1e-14:
        raise ValueError('I h/2 dual non respecte')
    return montage, fdtd, csx, g, dict(normal=normal, propagation=propagation,
        u0_mm=u0, h_mm=h, largeur_ligne_mm=largeur, air_mm=air,
        boite_physique_mm=boite.tolist(),garde_hors_pml_mm=garde,
        details=details, definitions_materiaux=definitions)


def main():
    sortie = ICI/'proposition_06_filtre_cellules_libres'
    sortie.mkdir(exist_ok=False)
    rapport = sortie/'rapport_prototype.json'
    if rapport.exists():
        raise FileExistsError('Rapport prototype deja present')
    avant = sources()
    # Interdiction explicite des chemins qui executent un solveur.
    def interdit(*args, **kwargs):
        raise RuntimeError('Prototype : Run/calibration interdit')
    F.lance = F.serie = F._calibre_dt = interdit
    resultats = []
    for nom in ANTENNES:
        mod = F.charge_antenne(nom)
        construits = {}
        for niveau in POLITIQUES:
            montage, fdtd, csx, g, infos = construit(mod, niveau)
            resume = F.resume_maillage(csx)
            fichier = sortie/(nom+'_'+niveau+'_GRILLE_SEULE.npz')
            if fichier.exists():
                raise FileExistsError(str(fichier))
            np.savez_compressed(fichier, **g)
            dt = .8*resume['dt_cfl_vide_s']
            points = int(np.prod([len(g[a]) for a in 'xyz']))
            couts = {}
            for duree in (12, 16):
                n = int(np.ceil(duree*1e-9/dt))+1
                couts[str(duree)+'ns'] = dict(pas_projetes=n,
                    heures_25M=points*n/25e6/3600,
                    heures_35M=points*n/35e6/3600)
            normal, prop, h, u0 = infos['normal'], infos['propagation'], infos['h_mm'], infos['u0_mm']
            diagnostics = dict(U_x0_primaire_exact=ligne_exacte(g['x'], 0.),
                normal_cellules=int(sum((g[normal][:-1] >= 0.) & (g[normal][1:] <= h))),
                I_hsur2_dual_ecart_mm=float(np.min(abs((g[normal][:-1]+g[normal][1:])/2-h/2))),
                cellules_via=[dict(x_mm=x,u_mm=u,diametre_mm=diam,
                    transversales=int(sum((g['x'][:-1] >= x-diam/2-1e-8) & (g['x'][1:] <= x+diam/2+1e-8))),
                    longitudinales=int(sum((g[prop][:-1] >= u-diam/2-1e-8) & (g[prop][1:] <= u+diam/2+1e-8))))
                    for x,u,diam in mod.vias_mm()],
                largeur_locale=dict(x_flanc=largeur_locale(g['x'],1.2275619047618136),
                    propagation_apres_port=largeur_locale(g[prop],u0+.26297619047622),
                    normal_au_dessus_cuivre=largeur_locale(g[normal],h+.0277777777777778),
                    microstrip=largeur_locale(g['x'],infos['largeur_ligne_mm']/2)))
            entree = dict(antenne=nom,niveau=niveau,montage=asdict(montage),
                politique=POLITIQUES[niveau],grille=resume,points_operateur_estimes=points,
                dt_projection_non_calibre_s=dt,couts_projetes=couts,
                RAM_projection_Gio=[points*300/2**30,points*700/2**30],
                npz=fichier.name,npz_sha256=sha(fichier),diagnostics=diagnostics,**infos)
            resultats.append(entree)
            construits[niveau]=g
            print(json.dumps({k:entree[k] for k in ('antenne','niveau','grille','couts_projetes','diagnostics')},ensure_ascii=False), flush=True)
        for axe in 'xyz':
            a,b=construits['base'][axe],construits['fin'][axe]
            if not np.array_equal(a[:9],b[:9]) or not np.array_equal(a[-9:],b[-9:]):
                raise ValueError('PML non identiques : '+nom+'/'+axe)
    apres=sources()
    if avant != apres:
        raise ValueError('Sources17 modifiees pendant prototype')
    contenu=dict(schema='prototype_maillage_controle_v2_sans_run_v1',
        utc=datetime.now(timezone.utc).isoformat(),script_sha256=sha(__file__),
        python=sys.version,numpy=np.__version__,fils=1,aucun_Run=True,
        aucune_calibration=True,aucune_qualification=True,
        sources17_avant=avant,sources17_apres=apres,resultats=resultats,
        choix='Aretes rectilignes primaires exactes, pas de regle tiers generalisee.',
        limites=['Catalogue propose non approuve ; module racine F2 non cree.',
            'Grilles non emboitees. Seuls blocs/ancres et PML sont explicitement proteges.',
            'Cout projete par CFLvide*0.8 ; stabilite et dtoperateur inconnus sans calibration.',
            'RAM 300–700octets/point : projection conservatrice indicative, pas mesure.',
            'Aucune nouvelle prediction S11 ; les3antennes exigeraient nouvelle campagneF2.'])
    with rapport.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(contenu,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')
    print('Rapport :',rapport)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
