"""Vivaldi antipodale -- conception du projet, a verifier par simulation.

Antenne a onde progressive, a fente exponentielle, pour la tomographie : elle
est directive sans l'etre trop, continue en frequence, et se fabrique en deux
couches sur un circuit imprime ordinaire.

ATTENTION. Contrairement au losange, cette conception n'a AUCUNE reference
publiee. Les cotes ci-dessous sont des regles de l'art, pas un resultat :

    ouverture   >= lambda/2 a la frequence basse
    longueur    >= lambda   a la frequence basse
    taux d'ouverture R : a regler sur le S11

Elle doit donc etre simulee et retouchee avant d'etre fabriquee, et c'est la
raison d'etre des deux autres etalons du projet : le dipole garantit le
traitement, le losange garantit le modele electromagnetique. Sans eux, une
Vivaldi simulee ne serait qu'une promesse.

ORIENTATION, qui n'est pas celle des antennes planaires du projet. Une Vivaldi
rayonne dans l'axe de sa fente (end-fire), pas perpendiculairement a la carte.
La carte est donc posee de CHANT : elle s'etend en x (ouverture) et en z (axe
de rayonnement), son epaisseur est en y, et elle rayonne vers les z > 0, ou se
trouve la plaque. La bouche est en z = z_total.

LES TROIS BORDS, et c'est tout le dessin
----------------------------------------
    a(z)   bord INTERIEUR du cuivre du dessus : il borde la fente
    b(z)   bord EXTERIEUR du cuivre du dessus
    g(z)   bord du cuivre du dessous, qui part de la masse pleine

    z < z_ligne                a = -w/2, b = +w/2, g = pleine largeur
                               -> micro-ruban 50 ohms ordinaire
    z_ligne < z < z_fente      a glisse vers +x, b = a + w, g se retire
                               -> le RECOUVREMENT reste egal a w
    z > z_fente                a s'evase en exponentielle, b rejoint le
                               bord de carte, g = -a
                               -> fente antipodale qui rayonne

QUATRE FAUTES corrigees les 17 et 18/10/2026, toutes invisibles sur les cotes
et toutes fatales :

  1. L'evasement etait ecrete a l'ouverture. Passe le point de saturation, le
     bord interieur et le bord exterieur se confondaient : le dernier tiers
     de chaque aile etait un fil, pas du cuivre.
  2. L'exponentielle partait du depart sans contrainte a l'arrivee. Elle est
     calee sur ses DEUX bouts, et le taux n'en regle plus que la courbure.
  3. La transition etait une diagonale droite. Elle est en cosinus sureleve,
     donc a pente nulle aux deux bouts.
  4. LE BORD EXTERIEUR DU DESSUS s'ouvrait des la transition, en meme temps
     que la masse se retirait. Les deux cuivres se recouvraient alors sur
     35 mm au-dessus de 1,6 mm de FR4 : une ligne de 10 ohms en plein milieu
     du trajet. La simulation le disait sans ambiguite -- |S11| plat a
     -4 dB de 1 a 6 GHz, ce qui est la signature d'une marche d'impedance
     et non d'un probleme de resonance. Le bord exterieur reste maintenant a
     une largeur de ligne du bord interieur tant que la masse n'a pas fini
     de se retirer.
"""
import numpy as np

NOM = "vivaldi_tomographie"
DESCRIPTION = "Vivaldi antipodale sur FR4, conception du projet"

# ------------------------------------------------- choix de conception
# Arretes le 17/10/2026 : toute la bande du LiteVNA, et du FR4 comme les
# losanges. Les deux options ecartees -- une version a 2 GHz, deux fois plus
# petite, et le substrat Rogers RO4350B -- sont consignees dans BACKLOG.md
# avec la condition qui les ferait revenir.
F_BASSE = 1.4e9         # Hz -- 1,4 GHz : toute la bande du LiteVNA
F_HAUTE = 6.3e9         # Hz
EPS_R = 4.4             # FR4 ; mettre 3.66 pour du Rogers RO4350B
TAN_DELTA = 0.02        # 0.0037 pour du RO4350B
H = 1.6                 # mm, epaisseur du substrat

# ------------------------------------------------- cotes derivees
# LES TROIS COTES REGLEES PAR LA SIMULATION, le 18/10/2026, et le resultat de
# leur reglage est consigne dans fiche.md. Les trois sont contre-intuitives.
MARGE_OUVERTURE = 1.00  # ouverture entre bords interieurs = marge x lambda/2
MARGE_LONGUEUR = 0.75   # longueur de l'evasement = marge x lambda
AILE = 18.0             # mm de cuivre au-dela de l'ouverture, de chaque cote
TAUX = 0.013            # /mm, courbure de l'exponentielle (bouts imposes)
FENTE = 0.8             # mm, largeur de la fente au depart
LARGEUR_LIGNE = 3.0     # mm, ligne 50 ohms sur 1,6 mm de FR4
LONGUEUR_LIGNE = 20.0   # mm, micro-ruban pur, avant la transition
TRANSITION = 100.0      # mm, longueur de la transition micro-ruban / fente
OUVRE_AILE = 0.35       # fraction de l'evasement pour rejoindre le bord
# Demi-largeur du plan de masse AU PIED de la ligne. None = toute la carte.
# Un plan de masse de 143 mm de large, excite sur sa tranche, resonne en
# travers vers 1,05 GHz et a tous ses multiples -- ce qui tombe en plein dans
# la bande. Le retrecir ne coute rien : trois fois la largeur du ruban suffit
# a faire un micro-ruban.
LARGEUR_MASSE = 40.0    # mm

# Controle de dessin : les deux cuivres ne doivent se superposer que sur la
# largeur de la ligne. Au-dela, le substrat fait une ligne de transmission
# trop large, donc de trop basse impedance, et l'antenne desadapte a plat.
RECOUVREMENT_MAX_MM = 1.2 * LARGEUR_LIGNE

# Deux trous de fixation, loin de la ligne et de la fente : ils traversent le
# plan de masse a 60 mm du ruban, ce qui est sans effet a 6 GHz, et ils
# donnent au fabricant le fichier de percage qu'il attend.
TROU_DIAMETRE = 3.0     # mm
TROU_MARGE = 6.0        # mm depuis le bord lateral
TROU_Z = 9.0            # mm depuis le bord d'alimentation


def cotes():
    """Toutes les cotes, en mm, deduites de la frequence basse."""
    lam = 299792458.0 / F_BASSE * 1e3
    ouverture = MARGE_OUVERTURE * lam / 2
    evasement = MARGE_LONGUEUR * lam
    return dict(
        lam_basse=lam,
        ouverture=ouverture,                    # entre bords INTERIEURS
        evasement=evasement,                    # longueur de l'evasement seul
        demi_x=ouverture / 2 + AILE,            # demi-largeur de la carte
        demi_masse=(ouverture / 2 + AILE if LARGEUR_MASSE is None
                    else LARGEUR_MASSE / 2),
        z_ligne=LONGUEUR_LIGNE,
        z_fente=LONGUEUR_LIGNE + TRANSITION,    # debut de l'evasement
        z_total=LONGUEUR_LIGNE + TRANSITION + evasement,
        h=H, fente=FENTE, aile=AILE, taux=TAUX,
        largeur_ligne=LARGEUR_LIGNE, transition=TRANSITION)


def bande_attendue_ghz():
    """Prediction, non garantie : la coupure basse d'une Vivaldi depend de
    l'ouverture ET du taux d'evasement."""
    return (F_BASSE / 1e9, F_HAUTE / 1e9)


def retard_attendu_ns():
    """L'onde parcourt la fente jusqu'a la bouche avant de rayonner.

    C'est le point delicat de cette famille : le rayonnement ne part pas d'un
    point fixe mais de l'endroit ou la fente vaut environ lambda/2, lequel se
    deplace avec la frequence. La valeur rendue est le retard du trajet
    COMPLET, donc une borne haute -- et, pour la mesure de distance, un
    avertissement : ce retard n'est pas constant en frequence.
    """
    d = cotes()
    v = 299792458.0 / np.sqrt((EPS_R + 1) / 2)
    return d["z_total"] * 1e-3 / v * 1e9


# ======================================================================
# LES TROIS BORDS
# ======================================================================
def _cos(t):
    """Cosinus sureleve : vaut 1 en t = 0, 0 en t = 1, pente nulle aux deux."""
    return 0.5 * (1.0 + np.cos(np.pi * np.clip(t, 0.0, 1.0)))


def profils(d, n=200):
    """Rend (z, a, b, g, o), les quatre bords, de z_ligne a z_total.

    a : bord interieur du dessus     b : bord exterieur du dessus
    g : bord interieur du dessous    o : bord exterieur du dessous

    Le point cle est `b = a + largeur_ligne` dans la transition. C'est lui
    qui maintient le recouvrement des deux cuivres egal a la largeur de la
    ligne, donc l'impedance a 50 ohms, pendant que la masse se retire.
    """
    s, lw, dx = d["fente"], d["largeur_ligne"], d["demi_x"]
    m = d["demi_masse"]
    z_l, z_f, z_t = d["z_ligne"], d["z_fente"], d["z_total"]
    z_aile = z_f + OUVRE_AILE * d["evasement"]

    # --- transition : le ruban glisse, la masse se retire
    z1 = np.linspace(z_l, z_f, n // 2, endpoint=False)
    c = _cos((z1 - z_l) / (z_f - z_l))
    a1 = s / 2 + (-lw / 2 - s / 2) * c
    b1 = a1 + lw
    g1 = -s / 2 + (m + s / 2) * c

    # --- evasement : exponentielle calee sur ses deux bouts
    z2 = np.linspace(z_f, z_t, n)
    c1 = ((d["ouverture"] - s) / 2) / (np.exp(d["taux"] * d["evasement"]) - 1)
    c2 = s / 2 - c1
    a2 = c1 * np.exp(d["taux"] * (z2 - z_f)) + c2
    # le bord exterieur rejoint le bord de carte sur la premiere fraction
    b2 = dx + (s / 2 + lw - dx) * _cos((z2 - z_f)
                                       / (OUVRE_AILE * d["evasement"]))
    g2 = -a2

    # Le bord EXTERIEUR du dessous s'ouvre de la largeur de masse jusqu'au
    # bord de carte, sur le meme intervalle que celui du dessus. Quand la
    # masse est deja pleine largeur, c'est une droite et rien ne change.
    z = np.concatenate([z1, z2])
    o = -dx + (dx - m) * _cos((z - z_l) / (z_aile - z_l))
    return (z, np.concatenate([a1, a2]), np.concatenate([b1, b2]),
            np.concatenate([g1, g2]), o)


def _polygones(d):
    """Les deux cuivres, dans le repere de la CARTE : (largeur, longueur).

    Une seule definition, utilisee par la simulation comme par l'export de
    fabrication. Dans la scene openEMS, la premiere coordonnee est x et la
    seconde z ; sur le circuit imprime, ce sont x et y.
    """
    z, a, b, g, o = profils(d)
    lw, dx, m, z_t = (d["largeur_ligne"], d["demi_x"], d["demi_masse"],
                      d["z_total"])

    dessus = [(-lw / 2, 0.0), (lw / 2, 0.0)]
    dessus += [(float(xi), float(zi)) for zi, xi in zip(z, b)]
    dessus += [(float(xi), float(zi)) for zi, xi in zip(z[::-1], a[::-1])]

    dessous = [(-m, 0.0), (m, 0.0)]
    dessous += [(float(xi), float(zi)) for zi, xi in zip(z, g)]
    dessous += [(-dx, z_t)]
    dessous += [(float(xi), float(zi)) for zi, xi in zip(z[::-1], o[::-1])]
    return dessus, dessous


def contours_mm():
    """Les contours a plat, pour l'export de fabrication."""
    d = cotes()
    dessus, dessous = _polygones(d)
    dx, z_t = d["demi_x"], d["z_total"]
    return {
        "F_Cu": [dessus],
        "B_Cu": [dessous],
        "Edge_Cuts": [[(-dx, 0.0), (dx, 0.0), (dx, z_t), (-dx, z_t)]],
    }


def percages_mm():
    """Trous non metallises : (x, y, diametre) en mm, repere de la carte."""
    d = cotes()
    x = d["demi_x"] - TROU_MARGE
    return [(-x, TROU_Z, TROU_DIAMETRE), (x, TROU_Z, TROU_DIAMETRE)]


def controles_fabrication():
    d = cotes()
    return (f"   - largeur de la carte : {2*d['demi_x']:.2f} mm\n"
            f"   - longueur de la carte : {d['z_total']:.2f} mm\n"
            f"   - ouverture de la bouche, entre les deux bords interieurs "
            f"du cuivre : {d['ouverture']:.2f} mm\n"
            f"   - largeur de la ligne d'alimentation : "
            f"{d['largeur_ligne']:.2f} mm (c'est elle qui fixe les 50 ohms)\n"
            f"   - largeur du cuivre restant a la bouche, de chaque cote : "
            f"{d['aile']:.2f} mm")


# ======================================================================
# SCENE
# ======================================================================
def pose(csx, fdtd, acq):
    """Pose l'antenne de chant. Rend (port, lx, ly, lz, demi_etendue_xy)."""
    d = cotes()
    eps0 = 8.8541878128e-12
    f0 = 0.5 * (acq.f_min + acq.f_max)
    kappa = 2 * np.pi * f0 * eps0 * EPS_R * TAN_DELTA
    dx, lw, z_t = d["demi_x"], d["largeur_ligne"], d["z_total"]

    sub = csx.AddMaterial("substrat", epsilon=EPS_R, kappa=kappa)
    sub.AddBox([-dx, 0.0, 0.0], [dx, d["h"], z_t], priority=1)

    metal = csx.AddMetal("cuivre")
    dessus, dessous = _polygones(d)

    # CONVENTION CSXCAD, verifiee a la main le 18/10/2026 et nulle part
    # ecrite : pour un polygone de normale n, les deux coordonnees sont les
    # axes (n+1, n+2) modulo 3. Normale z, ce sont (x, y) -- c'est le cas
    # des antennes planaires du projet, et c'est pourquoi le losange, lui,
    # s'est toujours bien comporte. Normale y, ce sont (z, x), et NON (x, z).
    #
    # Cette antenne a ete simulee TROIS FOIS avec les coordonnees inversees.
    # Le dessin etait transpose -- 279 mm de large pour 143 de long -- et
    # debordait largement dans la PML. Les trois resultats etaient du bruit,
    # et deux « corrections » de conception ont ete faites pour rien. Le
    # garde-fou de fdtd.verifie_emprise() est la pour que cela ne recommence
    # pas : il refuse toute matiere posee hors du volume annonce.
    def _zx(poly):
        return np.array([(zi, xi) for xi, zi in poly]).T

    # Face du dessus (y = h) : ligne d'alimentation puis evasement vers +x.
    metal.AddPolygon(_zx(dessus), norm_dir=1, elevation=d["h"], priority=10)
    # Face du dessous (y = 0) : evasement symetrique vers -x. C'est ce qui
    # fait l'antipodale.
    metal.AddPolygon(_zx(dessous), norm_dir=1, elevation=0.0, priority=10)

    # Port vertical au pied de la ligne, entre les deux faces.
    port = fdtd.AddLumpedPort(
        1, acq.z_ref, [-lw / 2, 0.0, 0.0], [lw / 2, d["h"], 0.0],
        "y", 1.0, priority=20, edges2grid="all")

    # Uniquement les lignes que la geometrie IMPOSE. Surtout pas de grille
    # reguliere ici : ses lignes tomberaient a un dixieme de millimetre des
    # lignes fines, et le pas de temps s'effondrerait. SmoothMeshLines
    # remplit le reste.
    #
    # L'evasement est echantillonne a pas constant en X et non en z : a pas
    # constant en z, les points se tassent la ou la courbe est raide et
    # imposent des cellules de quelques centiemes de millimetre.
    z, a, _, _, _ = profils(d, n=600)
    bords = np.array([dx, lw / 2, d["demi_masse"], d["fente"] / 2,
                      d["ouverture"] / 2])
    cibles = np.linspace(d["fente"] / 2, d["ouverture"] / 2, 9)[1:-1]
    # Une ligne d'ECHANTILLONNAGE qui tombe a cote d'un BORD DE MATIERE ne
    # decrit rien de plus et impose une cellule minuscule : la 20,32 mm de
    # l'evasement contre la 20,00 du bord de masse coutait un pas de temps
    # 2,4 fois plus court. Les bords restent, les echantillons cedent.
    ecart_mini = 299792458.0 / acq.f_max * 1e3 / 100        # lambda/100
    cibles = cibles[np.min(np.abs(cibles[:, None] - bords[None, :]),
                           axis=1) > ecart_mini]
    z_pts = np.interp(cibles, a[a.size // 3:], z[a.size // 3:])
    lx = np.concatenate([bords, -bords, cibles, -cibles])
    ly = np.array([0.0, d["h"] / 2, d["h"]])     # deux cellules dans le FR4
    lz = np.concatenate([[0.0, d["z_ligne"], d["z_fente"], z_t], z_pts])
    return port, lx, ly, lz, dx
