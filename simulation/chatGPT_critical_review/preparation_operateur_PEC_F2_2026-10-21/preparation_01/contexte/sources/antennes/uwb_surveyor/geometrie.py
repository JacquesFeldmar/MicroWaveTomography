"""Nooelec UWB Surveyor -- biconique planaire, 120 x 120 x 0,8 mm.

GEOMETRIE APPROXIMATIVE. La fiche technique ne donne que l'encombrement, la
bande (0,7 a 10 GHz), le gain moyen (3 dBi) et la courbe de ROS. Ni les
fichiers de fabrication ni le dessin des conducteurs ne sont publies.

Tout ce qui suit est donc un modele a recaler, et les parametres sont groupes
en tete pour cela. Le critere de recalage disponible est le |S11| mesure sans
plaque, a comparer a la courbe de ROS de la fiche technique (page 3).

Reperes : la carte est dans le plan xy, a z = 0, et rayonne vers les z > 0,
ou se trouve la plaque. L'alimentation est sur le bord y = -60 mm.
"""
import numpy as np

NOM = "uwb_surveyor"
DESCRIPTION = "Nooelec UWB Surveyor, biconique planaire 120 x 120 mm sur FR4"

# ---------------------------------------------------------------- parametres
COTE = 120.0            # mm, cote de la carte
EPAISSEUR = 0.8         # mm, substrat
EPS_R = 4.4             # FR4
TAN_DELTA = 0.02
# Le cuivre est modelise en FEUILLE d'epaisseur nulle. Ses 35 um reels
# imposeraient des cellules de 35 um, donc un pas de temps 300 fois trop
# petit, pour un effet nul a ces frequences.
CUIVRE = 0.0            # mm
# Cotes RELEVEES SUR LA PHOTO de la fiche technique (page 2), en ajustant
# l'echelle sur le cote de 120 mm : 5,35 pixels par mm. Incertitude de
# l'ordre de +/- 3 mm. Elles remplacent mes premieres estimations, qui
# etaient fausses d'un facteur deux sur la ligne.
#
#   - l'arc inferieur du disque passe a 69 mm du bord inferieur ;
#   - un cercle ajuste sur trois points de cet arc donne un rayon de 84 mm,
#     centre 26 mm AU-DESSUS du bord superieur : le disque est tronque ;
#   - la ligne d'alimentation monte du SMA jusqu'a l'arc, soit 69 mm, les
#     deux tiers de la carte. C'est elle qui porte l'essentiel du retard.
RAYON_PETALE = 83.5     # mm, rayon du disque rayonnant (tronque par la carte)
CENTRE_DISQUE = 92.7    # mm, centre en y, donc 32,7 mm au-dela du bord
LARGEUR_LIGNE = 1.5     # mm, ligne 50 ohms sur 0,8 mm de FR4
# La masse de la face arriere n'est pas visible sur la photo. Un monopole
# imprime en a une partielle, qui s'arrete avant le disque : la hauteur de
# son bord superieur est LE parametre d'adaptation, et donc le premier a
# ajuster sur la courbe de ROS.
MASSE_HAUT = 0.0        # mm, bord superieur du plan de masse arriere


# ---------------------------------------------------------------- reference
# La courbe de ROS de la fiche technique (page 3), relevee a l'oeil sur le
# trace, par pas d'environ 0,15 GHz. Incertitude de l'ordre de +/- 0,1 en
# ROS -- et c'est LE seul point de comparaison dont nous disposions pour
# recaler la geometrie, puisque les fichiers de fabrication ne sont pas
# publies. Le |S11| mesure sur l'exemplaire du banc la remplacerait
# avantageusement.
ROS_FICHE = (
    (0.75, 1.40), (0.85, 1.55), (0.90, 1.10), (1.00, 1.40), (1.10, 1.50),
    (1.20, 1.45), (1.25, 1.30), (1.35, 1.90), (1.45, 2.30), (1.55, 2.50),
    (1.70, 3.10), (1.80, 2.90), (1.90, 2.55), (2.00, 2.20), (2.15, 1.80),
    (2.30, 1.50), (2.45, 1.40), (2.60, 1.20), (2.75, 1.50), (2.90, 1.90),
    (3.05, 2.15), (3.20, 2.05), (3.35, 1.60), (3.50, 1.35), (3.65, 1.40),
    (3.80, 1.45), (4.00, 1.40), (4.15, 1.35), (4.40, 1.70), (4.55, 1.60),
    (4.70, 1.20), (4.85, 1.35), (5.00, 1.50), (5.15, 1.60), (5.30, 1.50),
    (5.45, 1.35), (5.60, 1.30), (5.75, 1.55), (5.90, 1.20),
)


def s11_fiche():
    """La courbe de la fiche technique, convertie en (freqs, S11).

    |S11| = (ROS - 1) / (ROS + 1). La PHASE est inconnue : seul le module
    est publie, ce qui suffit pour recaler l'adaptation mais pas le retard.
    """
    f = np.array([p[0] for p in ROS_FICHE]) * 1e9
    ros = np.array([p[1] for p in ROS_FICHE])
    return f, (ros - 1) / (ros + 1)


def eps_eff():
    """Permittivite effective du microruban d'alimentation."""
    return ((EPS_R + 1) / 2 + (EPS_R - 1) / 2
            * (1 + 12 * EPAISSEUR / LARGEUR_LIGNE) ** -0.5)


def arc_bas():
    """Ordonnee du point le plus bas du disque, en mm.

    C'est la qu'aboutit la ligne d'alimentation, donc la longueur de celle-ci
    s'en deduit : de -COTE/2 (le connecteur) jusqu'ici.
    """
    return CENTRE_DISQUE - RAYON_PETALE


def longueur_ligne():
    return arc_bas() + COTE / 2


def retard_attendu_ns():
    """Retard ALLER SIMPLE de la seule ligne d'alimentation.

    Ce n'est PAS le retard total : le rayonnement part de quelque part SUR le
    disque, d'autant plus haut que la frequence est basse. C'est donc une
    borne basse -- mais elle vaut deja 12 cm de decalage affiche, soit
    l'essentiel des 20 cm mesures le 9 octobre.
    """
    c = 299792458.0
    return longueur_ligne() * 1e-3 * eps_eff() ** 0.5 / c * 1e9


def pose(csx, fdtd, acq):
    """Pose l'antenne dans la scene. Rend (port, lx, ly, lz, demi_etendue)."""
    eps0 = 8.8541878128e-12
    f0 = 0.5 * (acq.f_min + acq.f_max)
    kappa = 2 * np.pi * f0 * eps0 * EPS_R * TAN_DELTA

    sub = csx.AddMaterial("FR4", epsilon=EPS_R, kappa=kappa)
    sub.AddBox([-COTE / 2, -COTE / 2, -EPAISSEUR],
               [COTE / 2, COTE / 2, 0.0], priority=1)

    metal = csx.AddMetal("cuivre")
    demi = COTE / 2

    # FACE AVANT (z = 0) : le disque tronque par la carte, plus la ligne.
    # Le cercle coupe les bords x = +/- demi a l'ordonnee y_bord ; le contour
    # suit l'arc, puis remonte par les bords jusqu'au haut de la carte.
    y_bord = CENTRE_DISQUE - np.sqrt(max(RAYON_PETALE ** 2 - demi ** 2, 0.0))
    a_max = np.arccos(np.clip(demi / RAYON_PETALE, -1, 1))
    angles = np.linspace(np.pi + a_max, 2 * np.pi - a_max, 60)
    arc = [(float(RAYON_PETALE * np.cos(t)),
            float(CENTRE_DISQUE + RAYON_PETALE * np.sin(t))) for t in angles]
    contour = [(-demi, y_bord)] + arc + [(demi, y_bord), (demi, demi),
                                         (-demi, demi)]
    metal.AddPolygon(np.array(contour).T, norm_dir=2, elevation=0.0,
                     priority=10)
    metal.AddBox([-LARGEUR_LIGNE / 2, -demi, 0.0],
                 [LARGEUR_LIGNE / 2, arc_bas(), 0.0], priority=11)

    # FACE ARRIERE (z = -EPAISSEUR) : plan de masse partiel.
    masse = csx.AddMetal("masse")
    masse.AddBox([-demi, -demi, -EPAISSEUR], [demi, MASSE_HAUT, -EPAISSEUR],
                 priority=10)

    # Port vertical au bord de la carte, entre la ligne et la masse : c'est
    # le connecteur SMA, et donc le plan de calibration.
    port = fdtd.AddLumpedPort(
        1, acq.z_ref,
        [-LARGEUR_LIGNE / 2, -demi, -EPAISSEUR],
        [LARGEUR_LIGNE / 2, -demi, 0.0],
        "z", 1.0, priority=20, edges2grid="all")

    maille = 299792458.0 / acq.f_max * 1e3 / 20          # lambda/20 a f_max
    lx = np.concatenate([
        np.arange(-demi, demi + maille, maille),
        [-LARGEUR_LIGNE / 2, LARGEUR_LIGNE / 2]])
    ly = np.concatenate([
        np.arange(-demi, demi + maille, maille),
        [arc_bas(), MASSE_HAUT, y_bord]])
    lz = np.array([-EPAISSEUR, -EPAISSEUR / 2, 0.0])
    return port, lx, ly, lz, demi
