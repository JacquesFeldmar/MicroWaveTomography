"""FDTD -- le montage dans openEMS.

Le LiteVNA n'est pas simule : un VNA calibre au plan SOL, c'est exactement un
port de 50 ohms. Tout le reste est geometrique.

    port localise 50 ohms  --  ANTENNE  --  air  --  plaque PEC  --  PML

La geometrie de l'antenne ne vit PAS ici : chaque antenne a son module, dans
`antennes/<nom>/geometrie.py`, qui expose

    NOM, DESCRIPTION
    pose(csx, fdtd, acq)  ->  (port, lignes_x, lignes_y, lignes_z, demi_etendue)
    retard_attendu_ns()   ->  float ou None

Ce fichier ne s'occupe que du reste : la plaque, le maillage, les frontieres,
l'execution et l'ecriture des Touchstone. openEMS est importe paresseusement,
pour que le reste du projet tourne sans lui.
"""
import importlib.util
import os

import numpy as np

from banc import C, Montage

ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_ANTENNES = os.path.join(ICI, "antennes")

# openEMS est livre comme un dossier de DLL : ses modules Python ne se chargent
# que si CSXCAD_INSTALL_PATH le designe. On le pose ici si l'environnement ne
# l'a pas fait, pour que le projet marche depuis n'importe quel terminal.
_OPENEMS = os.path.join(os.path.dirname(ICI), "outils", "openEMS")
if not os.environ.get("CSXCAD_INSTALL_PATH") and os.path.isdir(_OPENEMS):
    os.environ["CSXCAD_INSTALL_PATH"] = _OPENEMS


# ======================================================================
# CHARGEMENT D'UNE ANTENNE
# ======================================================================
def antennes_disponibles():
    if not os.path.isdir(DOSSIER_ANTENNES):
        return []
    return sorted(n for n in os.listdir(DOSSIER_ANTENNES)
                  if os.path.isfile(os.path.join(DOSSIER_ANTENNES, n,
                                                 "geometrie.py")))


def charge_antenne(nom):
    """Importe antennes/<nom>/geometrie.py."""
    chemin = os.path.join(DOSSIER_ANTENNES, nom, "geometrie.py")
    if not os.path.isfile(chemin):
        raise FileNotFoundError(
            f"antenne inconnue : {nom}. Disponibles : "
            f"{', '.join(antennes_disponibles()) or 'aucune'}")
    spec = importlib.util.spec_from_file_location(f"antenne_{nom}", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ======================================================================
# MARGE D'AIR
# ======================================================================
def marge_air(acq, maillage):
    """Air a laisser entre l'objet et la PML, en mm.

    C'est le BAS de la bande qui commande : une PML placee a moins d'un quart
    de la plus grande longueur d'onde ne joue plus son role, l'energie ne
    descend plus et la simulation tourne jusqu'au nombre de pas maximal sans
    jamais converger. A 1 GHz, lambda vaut 300 mm : il faut 75 mm d'air.
    """
    lam_max = C / acq.f_min * 1e3
    return max(maillage.marge_air_mm, lam_max / 4)


# ======================================================================
# COUT
# ======================================================================
def estime_cout(montage: Montage, x_cm=None, demi_etendue_mm=60.0):
    """(cellules, pas de temps, minutes). Plancher : le raffinement local
    autour de l'alimentation n'est pas compte."""
    a, m = montage.acquisition, montage.maillage
    pas_air = C / a.f_max * 1e3 / m.mailles_par_lambda_air       # mm
    marge = marge_air(a, m) + m.marge_pml * pas_air
    demi = max(demi_etendue_mm, montage.plaque.cote / 2 if x_cm else 0)
    lx = ly = 2 * (demi + marge)
    lz = (x_cm * 10 if x_cm else 0) + 2 * marge + montage.plaque.epaisseur
    cellules = (lx / pas_air) * (ly / pas_air) * (lz / pas_air)
    if m.symetrie:
        cellules /= 4
    pas_temps = pas_air * 1e-3 / (C * np.sqrt(3)) * 0.98          # Courant
    # Deux contraintes sur la duree simulee :
    #   - laisser les echos aller et revenir, plus une marge d'extinction ;
    #   - couvrir 1/df, sinon les echos de la portee non ambigue (6 m avec un
    #     pas de 25 MHz) sont tronques et la comparaison avec la mesure n'a
    #     plus de sens.
    duree = max(1.0 / a.df, 4 * (lz * 1e-3) / C + 20e-9)
    n_pas = min(m.n_pas_max, int(duree / pas_temps))
    minutes = cellules * n_pas / 30e6 / 60             # ~30 Mcellules/s
    return int(cellules), n_pas, minutes


# ======================================================================
# MAILLAGE
# ======================================================================
TOL_PRIORITAIRE = 0.1      # mm : plus petit detail qu'on accepte de distinguer


def _fusionne(prioritaires, autres, tol):
    """Lignes de maillage, sans deux lignes plus proches que `tol`.

    Les prioritaires -- les bords de matiere -- sont conservees, mais
    dedoublonnees entre elles a TOL_PRIORITAIRE : deux lignes distantes de
    quelques micrometres ne decrivent aucun detail reel et ne font que
    diviser le pas de temps. Une ligne de remplissage n'est retenue que si
    elle s'eloigne de ses voisines d'au moins `tol`.
    """
    brutes = np.sort(np.unique(np.asarray(prioritaires, dtype=float)))
    lignes = brutes[:1]
    for v in brutes[1:]:
        if v - lignes[-1] > TOL_PRIORITAIRE:
            lignes = np.append(lignes, v)
    for v in np.sort(np.unique(np.asarray(autres, dtype=float))):
        i = int(np.searchsorted(lignes, v))
        voisins = lignes[max(0, i - 1):min(len(lignes), i + 1)]
        if voisins.size == 0 or np.all(np.abs(voisins - v) > tol):
            lignes = np.insert(lignes, i, v)
    return lignes


def _nettoie_apres_lissage(grille, prio, maille_air):
    """Retire les cellules minuscules creees par le lissage lui-meme.

    SmoothMeshLines gradue les intervalles avec un rapport donne, et termine
    parfois sa progression a quelques dixiemes de millimetre d'une ligne
    imposee -- 399,723 juste avant 400,000, par exemple. Cette cellule ne
    decrit rien et divise le pas de temps de toute la simulation.

    Le seuil obeit a DEUX bornes, et il faut les deux :

      - moitie du plus petit intervalle que l'antenne a demande, pour ne
        jamais effacer un detail voulu ;
      - un dixieme de la maille d'air visee, pour ne jamais effacer le
        remplissage legitime. Sans ce plafond, une antenne dont les lignes
        sont espacees de 20 mm donne un seuil de 9 mm, qui supprime toutes
        les lignes a 4,8 mm posees par le lissage -- le maillage devient
        deux fois trop grossier et le resultat ne veut plus rien dire.

    En cas de conflit, la ligne prioritaire -- un bord de matiere -- reste.
    """
    for axe in "xyz":
        lignes = np.asarray(grille.GetLines(axe), dtype=float)
        p = np.asarray(sorted(set(np.round(prio[axe], 6))), dtype=float)
        ecarts = np.diff(p)
        seuil = min(0.45 * ecarts.min(), maille_air / 10) if ecarts.size \
            else maille_air / 10
        seuil = max(0.05, seuil)
        garde = [lignes[0]]
        for v in lignes[1:]:
            if v - garde[-1] > seuil:
                garde.append(v)
            elif (np.any(np.abs(p - v) < 1e-6)
                  and not np.any(np.abs(p - garde[-1]) < 1e-6)):
                garde[-1] = v          # la prioritaire l'emporte
        grille.SetLines(axe, np.array(garde))


def verifie_emprise(csx, demi, lz, marge=1e-6):
    """Refuse toute matiere posee hors du volume que l'antenne annonce.

    `pose()` rend son demi-encombrement en x et y, et ses lignes imposees en
    z. Tout ce qu'elle a dessine doit tenir dedans. Si ce n'est pas le cas,
    c'est que la geometrie n'est pas celle qu'on croit -- et la simulation
    n'aura aucun sens, sans rien signaler.

    Ce garde-fou a ete ecrit apres la faute qui lui donne son nom. Les
    polygones de CSXCAD prennent leurs coordonnees dans les axes (n+1, n+2)
    modulo 3, ou n est la normale : (x, y) pour une normale z, mais (z, x)
    pour une normale y. La Vivaldi, posee de chant, a donc ete simulee trois
    fois transposee -- 279 mm de large pour 143 de long. Rien ne le disait :
    ni openEMS, ni le maillage, ni le |S11|, qui etait simplement mauvais.
    Deux corrections de conception ont ete faites sur ce bruit-la.
    """
    boite = None
    for prop in csx.GetAllProperties():
        for prim in prop.GetAllPrimitives():
            b = np.asarray(prim.GetBoundBox(), dtype=float)
            boite = b if boite is None else np.array(
                [np.minimum(boite[0], b[0]), np.maximum(boite[1], b[1])])
    if boite is None:
        return boite
    permis = np.array([[-demi, -demi, float(np.min(lz))],
                       [demi, demi, float(np.max(lz))]])
    deborde = (boite[0] < permis[0] - marge) | (boite[1] > permis[1] + marge)
    if deborde.any():
        axes = "".join(a for a, d in zip("xyz", deborde) if d)
        raise RuntimeError(
            f"la geometrie deborde du volume annonce sur l'axe/les axes "
            f"{axes} : matiere de {boite[0]} a {boite[1]}, alors que pose() "
            f"annonce {permis[0]} a {permis[1]}. Verifie l'ordre des "
            f"coordonnees des polygones : pour une normale n, CSXCAD les lit "
            f"dans les axes (n+1, n+2) modulo 3.")
    return boite


def verifie_maillage(csx, maille_cible):
    """Rend (pas minimal par axe, pas de temps impose). A appeler avant de lancer."""
    g = csx.GetGrid()
    mini = {}
    for axe in "xyz":
        d = np.diff(np.asarray(g.GetLines(axe)))
        mini[axe] = float(d.min()) if d.size else float("nan")
    pas = min(mini.values())
    return mini, pas * 1e-3 / (C * np.sqrt(3))


# ======================================================================
# SCENE
# ======================================================================
def construit(montage: Montage, antenne_mod, x_cm=None, dossier=None,
              x_domaine=None, n_pas=None):
    """Monte la scene openEMS. Rend (FDTD, CSX, port, dossier).

    x_domaine : distance qui fixe la TAILLE du domaine et les lignes de
        maillage, independamment de la presence de la plaque. Deux
        simulations d'une meme serie doivent partager le meme maillage,
        sans quoi leur difference n'a aucun sens.
    n_pas : nombre de pas impose. S'il est donne, le critere d'arret par
        l'energie est desactive, pour que toutes les simulations de la serie
        couvrent exactement la meme duree.
    """
    from openEMS import openEMS
    from CSXCAD import ContinuousStructure

    a, pl, m = montage.acquisition, montage.plaque, montage.maillage
    f0 = 0.5 * (a.f_min + a.f_max)
    fc = 0.5 * (a.f_max - a.f_min)

    if n_pas:
        fdtd = openEMS(NrTS=n_pas, EndCriteria=0)
    else:
        fdtd = openEMS(NrTS=m.n_pas_max,
                       EndCriteria=10 ** (m.critere_fin / 10))
    fdtd.SetGaussExcite(f0, fc)
    fdtd.SetBoundaryCond(["PML_8"] * 6)

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    grille = csx.GetGrid()
    grille.SetDeltaUnit(1e-3)                          # tout en mm

    port, lx, ly, lz, demi = antenne_mod.pose(csx, fdtd, a)
    verifie_emprise(csx, demi, lz)

    x_dom = x_domaine if x_domaine is not None else x_cm
    if x_cm is not None:
        plaque = csx.AddMetal("plaque")
        z = x_cm * 10.0
        plaque.AddBox([-pl.cote / 2, -pl.cote / 2, z],
                      [pl.cote / 2, pl.cote / 2, z + pl.epaisseur], priority=10)
    if x_dom is not None:
        demi = max(demi, pl.cote / 2)

    maille_air = C / a.f_max * 1e3 / m.mailles_par_lambda_air
    marge = marge_air(a, m) + m.marge_pml * maille_air
    etendue = demi + marge
    # L'ANTENNE AUSSI occupe de la place en z, et il faut de l'air au-dela.
    # Une Vivaldi est posee de chant : elle s'etend sur 280 mm le long de
    # l'axe de rayonnement. Sans ce max, la PML tombait pile sur sa bouche,
    # absorbait le dernier tiers de l'evasement, et le |S11| rendu n'etait
    # pas celui de l'antenne mais celui d'une antenne tronquee.
    z_antenne = float(np.max(lz))
    z_max = max((x_dom * 10 + pl.epaisseur if x_dom else 0.0),
                z_antenne) + marge
    z_min = min(0.0, float(np.min(lz))) - marge

    # Les lignes de la GEOMETRIE sont prioritaires ; celles qui remplissent
    # l'air ne sont retenues que si elles ne tombent pas a cote d'une
    # prioritaire. Sans cela, deux lignes distantes de quelques micrometres
    # imposent un pas de temps mille fois trop petit : la simulation n'avance
    # plus et n'atteint jamais son critere d'arret.
    tol = maille_air / 20
    prio = {"x": lx, "y": ly, "z": lz}
    if x_dom is not None:
        # Les lignes de la plaque sont posees meme quand elle est absente :
        # c'est ce qui garantit un maillage identique dans toute la serie.
        prio["z"] = np.concatenate([lz, [x_dom * 10, x_dom * 10 + pl.epaisseur]])
    remplissage = {
        "x": np.array([-etendue, etendue]),
        "y": np.array([-etendue, etendue]),
        "z": np.concatenate([[z_min, z_max], np.arange(0, z_max, maille_air)]),
    }
    for axe in "xyz":
        grille.AddLine(axe, _fusionne(prio[axe], remplissage[axe], tol))
    grille.SmoothMeshLines("all", maille_air, ratio=1.4)
    _nettoie_apres_lissage(grille, prio, maille_air)

    # Chemin ABSOLU : openEMS change de repertoire courant pendant le calcul
    # et ne le restaure pas, donc un chemin relatif ne designe plus le meme
    # dossier au moment de relire les sondes du port.
    dossier = os.path.abspath(dossier or os.path.join(
        "resultats", "fdtd", antenne_mod.NOM,
        "antenne_seule" if x_cm is None else f"plaque_{x_cm:.0f}cm"))
    os.makedirs(dossier, exist_ok=True)
    return fdtd, csx, port, dossier


# ======================================================================
# EXECUTION
# ======================================================================
def lance(montage: Montage, antenne_mod, x_cm=None, dossier=None,
          apercu=False, fils=None, verbose=0, x_domaine=None, n_pas=None):
    """Lance une simulation. Rend (freqs, S11) sur la grille de l'acquisition."""
    fdtd, csx, port, dossier = construit(montage, antenne_mod, x_cm, dossier,
                                         x_domaine=x_domaine, n_pas=n_pas)

    a = montage.acquisition
    mini, dt = verifie_maillage(csx, C / a.f_max * 1e3
                                / montage.maillage.mailles_par_lambda_air)
    n_pas = int((1.0 / a.df) / dt)
    print(f"  maillage : pas min {min(mini.values()):.3f} mm "
          f"({', '.join(f'{k}={v:.2f}' for k, v in mini.items())}) -> "
          f"dt = {dt*1e12:.2f} ps -> {n_pas} pas pour couvrir 1/df")
    if dt < 0.2e-12:
        raise RuntimeError(
            f"pas de temps de {dt*1e15:.1f} fs : une cellule microscopique "
            f"s'est glissee dans le maillage (pas min "
            f"{min(mini.values())*1e3:.1f} um). Regarde les lignes rendues "
            f"par pose() : deux d'entre elles sont probablement presque "
            f"confondues.")
    if n_pas > montage.maillage.n_pas_max:
        print(f"  ATTENTION : il faudrait {n_pas} pas et le maximum est "
              f"{montage.maillage.n_pas_max}. La reponse sera tronquee.")

    # openEMS se place dans le dossier de simulation et n'en ressort pas :
    # sans cette precaution, la deuxieme simulation d'une serie ecrirait au
    # mauvais endroit.
    retour = os.getcwd()
    try:
        if apercu:
            fdtd.Run(dossier, cleanup=False, setup_only=True)
            return None, None
        fdtd.Run(dossier, cleanup=True, numThreads=fils or 0, verbose=verbose)
    finally:
        os.chdir(retour)

    freqs = np.linspace(a.f_min, a.f_max, a.points)
    port.CalcPort(dossier, freqs, ref_impedance=a.z_ref)
    return freqs, port.uf_ref / port.uf_inc


def serie(montage: Montage, antenne_mod, distances_cm, dossier_base=None,
          fils=None, verbose=0):
    """Une campagne simulee : le fond puis chaque distance de plaque.

    Les simulations d'une serie partagent OBLIGATOIREMENT le meme maillage et
    la meme duree. Sans cela, leur difference R = S11_plaque - S11_fond est
    dominee par l'ecart entre deux troncatures, et non par l'echo de la
    plaque. C'est la transposition exacte de la regle de mesure : un fond
    n'est valable que pris dans la meme configuration.

    Rend (freqs, S11_fond, {distance_cm : S11}).
    """
    x_dom = max(distances_cm)
    a = montage.acquisition

    # Un premier montage, uniquement pour connaitre le pas de temps du
    # maillage commun, et en deduire le nombre de pas a imposer.
    # Garder la reference au FDTD : il possede la structure C++, et la laisser
    # partir detruirait le maillage qu'on veut justement inspecter.
    sonde = construit(montage, antenne_mod, None, x_domaine=x_dom,
                      dossier=os.path.join(ICI, "resultats", "_sonde"))
    _, dt = verifie_maillage(sonde[1], C / a.f_max * 1e3
                             / montage.maillage.mailles_par_lambda_air)
    n_pas = min(montage.maillage.n_pas_max, int(np.ceil((1.0 / a.df) / dt)))
    print(f"  serie : maillage commun, dt = {dt*1e12:.2f} ps, "
          f"{n_pas} pas imposes a toutes les simulations "
          f"({n_pas*dt*1e9:.1f} ns, il en faut {1/a.df*1e9:.1f})")

    base = dossier_base or os.path.join("resultats", "fdtd", antenne_mod.NOM)
    freqs, fond = lance(montage, antenne_mod, None,
                        dossier=os.path.join(base, "fond"),
                        x_domaine=x_dom, n_pas=n_pas, fils=fils,
                        verbose=verbose)
    mesures = {}
    for x in distances_cm:
        _, s11 = lance(montage, antenne_mod, x,
                       dossier=os.path.join(base, f"plaque_{x:.0f}cm"),
                       x_domaine=x_dom, n_pas=n_pas, fils=fils,
                       verbose=verbose)
        mesures[x] = s11
    return freqs, fond, mesures


def ecrit_s1p(chemin, freqs, s11, z_ref=50.0, commentaire=""):
    """Touchstone 1 port, reel/imaginaire : le format des fichiers du rapport."""
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="ascii") as f:
        if commentaire:
            f.write(f"! {commentaire}\n")
        f.write(f"# Hz S RI R {z_ref:.0f}\n")
        for fr, s in zip(freqs, s11):
            f.write(f"{fr:.0f} {s.real:.9e} {s.imag:.9e}\n")
    return chemin
