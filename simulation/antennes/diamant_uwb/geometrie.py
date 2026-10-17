"""Monopole planaire en losange -- l'antenne de reference COTEE.

Conception publiee : Singhal et al. (2013), reprise comme exemple de la
Antenna Toolbox de MathWorks, « Diamond-Shaped Antenna for UWB Applications ».
Toutes les cotes sont publiees, et surtout le resultat attendu l'est aussi :

    |S11| < -10 dB de 2,5 a 13,5 GHz environ.

C'est ce qui en fait le second etalon du projet. Le dipole verifie la chaine
de TRAITEMENT ; celui-ci verifie le modele ELECTROMAGNETIQUE : si notre S11
simule retrouve cette bande, le maillage, le port et le substrat sont bons.

Reperes : la carte est dans le plan xy, le cuivre rayonnant en z = h, la masse
semi-circulaire en z = 0, et l'antenne rayonne vers les z > 0, ou se trouve la
plaque. L'alimentation est au bord y = -20 mm.

ECHELLE met toutes les cotes a l'echelle : une antenne planaire multipliee par
k voit ses frequences divisees par k. A 1,8, la bande passe de 2,5-13,5 GHz a
environ 1,4-7,5 GHz, c'est-a-dire celle du LiteVNA. Reserve : le FR4, lui, ne
se met pas a l'echelle -- sa permittivite et ses pertes changent avec la
frequence -- donc la version agrandie doit etre re-verifiee.
"""
import numpy as np

NOM = "diamant_uwb"
DESCRIPTION = ("monopole planaire en losange, conception publiee "
               "(Singhal 2013 / MathWorks)")

ECHELLE = 1.0           # 1,0 = conception publiee ; 1,8 ~ bande du LiteVNA

# DEUX COTES QUI NE SE METTENT PAS A L'ECHELLE, et pour deux raisons
# differentes. Elles valent None tant qu'on reste sur la conception publiee.
#
#   H_IMPOSE   le fabricant ne vend pas toutes les epaisseurs. A l'echelle
#              1,8 le substrat voudrait 2,88 mm : cela n'existe pas, et deux
#              epaisseurs ne tiennent de toute facon pas sur un meme panneau.
#   WF_IMPOSE  la largeur qui fait 50 ohms depend de l'epaisseur, pas de
#              l'echelle. Si le substrat reste a 1,6 mm, la ligne doit rester
#              a 3,1 mm : a 5,58 mm elle ne ferait plus que 28 ohms, et ces
#              18 mm de ligne agiraient en transformateur quart d'onde.
H_IMPOSE = None         # mm
WF_IMPOSE = None        # mm

# ---------------------------------------------- cotes publiees, en mm
CARTE_L = 32.0          # largeur de carte (x)
CARTE_W = 40.0          # hauteur de carte (y)
H = 1.6                 # epaisseur du substrat
EPS_R = 4.8             # FR4 de l'exemple
TAN_DELTA = 0.026
R_MASSE = 15.6          # rayon de la masse semi-circulaire
WF = 3.1                # largeur de la ligne d'alimentation

# Les douze sommets du cuivre rayonnant, dans l'ordre, en mm.
SOMMETS = np.array([
    [-1.55, -20.0], [-1.55, -10.0], [-0.60, -4.0], [-6.50, -2.0],
    [-14.50, 9.0], [-11.00, 14.0], [11.00, 14.0], [14.50, 9.0],
    [6.50, -2.0], [0.60, -4.0], [1.55, -10.0], [1.55, -20.0],
])


def cotes():
    """Toutes les cotes a l'echelle demandee."""
    k = ECHELLE
    h = H * k if H_IMPOSE is None else H_IMPOSE
    wf = WF * k if WF_IMPOSE is None else WF_IMPOSE
    som = SOMMETS * k
    # Les sommets qui appartiennent a la LIGNE -- ceux dont la largeur fixe
    # l'impedance, pas la bande -- suivent la largeur imposee. Le losange
    # rayonnant, lui, suit l'echelle : c'est lui qui porte la frequence.
    ligne = np.abs(SOMMETS[:, 0]) <= WF / 2 + 1e-9
    som[ligne, 0] = SOMMETS[ligne, 0] * (wf / WF)
    return dict(carte_l=CARTE_L * k, carte_w=CARTE_W * k, h=h,
                r_masse=R_MASSE * k, wf=wf, sommets=som)


def bande_attendue_ghz():
    """La bande publiee, ramenee a l'echelle."""
    return (2.5 / ECHELLE, 13.5 / ECHELLE)


def retard_attendu_ns():
    """Inconnu : c'est justement ce que la simulation doit donner.

    Borne basse : le trajet du bord de carte jusqu'au centre du losange,
    environ 24 mm a l'echelle 1, parcouru a la vitesse du microruban.
    """
    c = 299792458.0
    eps_eff = (EPS_R + 1) / 2
    return 24.0 * ECHELLE * 1e-3 * eps_eff ** 0.5 / c * 1e9


def contours_mm():
    """Les contours a plat, pour l'export DXF puis KiCad.

    Memes cotes que la simulation, meme repere : x la largeur, y la hauteur,
    l'alimentation au bord y = -carte_w/2.
    """
    d = cotes()
    l, w = d["carte_l"] / 2, d["carte_w"] / 2
    return {
        "F_Cu": [[(float(x), float(y)) for x, y in d["sommets"]]],
        "B_Cu": [[(float(p), float(q)) for p, q in
                  _demi_disque(d["r_masse"], -w).T]],
        "Edge_Cuts": [[(-l, -w), (l, -w), (l, w), (-l, w)]],
    }


def controles_fabrication():
    """Les deux cotes a verifier dans KiCad apres l'import."""
    d = cotes()
    som = d["sommets"]
    return (f"   - largeur du losange a son maximum : "
            f"{som[:, 0].max() - som[:, 0].min():.2f} mm\n"
            f"   - du bord inferieur au sommet du losange : "
            f"{som[:, 1].max() - som[:, 1].min():.2f} mm")


def _demi_disque(rayon, centre_y, n=48):
    """Polygone du demi-disque de masse, partie superieure."""
    a = np.linspace(0, np.pi, n)
    x = rayon * np.cos(a)
    y = centre_y + rayon * np.sin(a)
    return np.vstack([np.append(x, [-rayon]), np.append(y, [centre_y])])


def pose(csx, fdtd, acq):
    """Pose l'antenne. Rend (port, lx, ly, lz, demi_etendue)."""
    d = cotes()
    eps0 = 8.8541878128e-12
    f0 = 0.5 * (acq.f_min + acq.f_max)
    kappa = 2 * np.pi * f0 * eps0 * EPS_R * TAN_DELTA

    sub = csx.AddMaterial("FR4", epsilon=EPS_R, kappa=kappa)
    sub.AddBox([-d["carte_l"] / 2, -d["carte_w"] / 2, 0.0],
               [d["carte_l"] / 2, d["carte_w"] / 2, d["h"]], priority=1)

    metal = csx.AddMetal("cuivre")
    # cuivre rayonnant, face superieure
    metal.AddPolygon(d["sommets"].T, norm_dir=2, elevation=d["h"], priority=10)
    # masse semi-circulaire, face inferieure
    metal.AddPolygon(_demi_disque(d["r_masse"], -d["carte_w"] / 2),
                     norm_dir=2, elevation=0.0, priority=10)

    # Port vertical au bord de la carte : le pin central du SMA rejoint le
    # cuivre du dessus, son blindage la masse du dessous.
    port = fdtd.AddLumpedPort(
        1, acq.z_ref,
        [-d["wf"] / 2, -d["carte_w"] / 2, 0.0],
        [d["wf"] / 2, -d["carte_w"] / 2, d["h"]],
        "z", 1.0, priority=20, edges2grid="all")

    maille = 299792458.0 / acq.f_max * 1e3 / 20
    fine = min(1.0 * ECHELLE, maille)
    lx = np.concatenate([
        np.unique(np.abs(d["sommets"][:, 0])), -np.unique(np.abs(d["sommets"][:, 0])),
        np.arange(-d["carte_l"] / 2, d["carte_l"] / 2 + fine, fine),
        [-d["r_masse"], d["r_masse"]]])
    ly = np.concatenate([
        d["sommets"][:, 1],
        np.arange(-d["carte_w"] / 2, d["carte_w"] / 2 + fine, fine),
        [-d["carte_w"] / 2 + d["r_masse"]]])
    lz = np.array([0.0, d["h"] / 2, d["h"]])
    demi = max(d["carte_l"], d["carte_w"]) / 2
    return port, lx, ly, lz, demi
