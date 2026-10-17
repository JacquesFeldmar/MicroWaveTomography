"""Dipole de reference -- l'antenne dont on connait la reponse.

Elle n'existe pas sur le banc : elle sert a VERIFIER le programme. Son interet
est d'etre la seule antenne dont le plan de phase soit connu d'avance.

    deux brins metalliques dans le vide, de part et d'autre d'une fente de
    2 mm ou se trouve le port de 50 ohms

Il n'y a ni substrat, ni ligne d'alimentation, ni connecteur : le point d'ou
part l'onde est la fente, c'est-a-dire le plan du port, c'est-a-dire le plan
de calibration. Le retard d'antenne attendu est donc NUL, et une plaque posee
a 50 cm doit etre lue a 50 cm.

C'est le controle qui manque sur une antenne reelle : si la chaine complete
-- geometrie, FDTD, extraction du S11, fenetre, IFFT, detection de pic --
rend autre chose que la distance vraie, l'erreur est dans le programme, pas
dans l'antenne.

Resonance : un dipole de longueur L resonne vers c/(2L), un peu plus bas a
cause de l'epaisseur des brins. Avec L = 30 mm, on attend 4,5 a 5 GHz.
"""
import numpy as np

NOM = "dipole_reference"
DESCRIPTION = "dipole demi-onde dans le vide, port au centre, retard nul"

LONGUEUR = 30.0        # mm, longueur totale des deux brins
FENTE = 2.0            # mm, fente d'alimentation
SECTION = 2.0          # mm, cote de la section carree des brins


def resonance_attendue_ghz():
    return 299792458.0 / (2 * LONGUEUR * 1e-3) / 1e9


def retard_attendu_ns():
    """Retard GEOMETRIQUE : zero, le rayonnement part du plan du port.

    Attention a ne pas en conclure que l'ecart mesure sera nul. Un dipole
    resonne, donc il stocke de l'energie, donc il retarde sa reponse de
    l'ordre de Q/(pi.f) -- quelques centimetres sur l'axe des distances.
    Ce qui doit etre verifie, c'est que cet ecart soit le MEME a toutes les
    distances : un retard s'ajoute, il ne se multiplie pas.
    """
    return 0.0


def pose(csx, fdtd, acq):
    """Pose le dipole. Rend (port, lx, ly, lz, demi_etendue)."""
    metal = csx.AddMetal("brins")
    g, s, b = FENTE / 2, SECTION / 2, LONGUEUR / 2
    # brin superieur (+y) et brin inferieur (-y), dipole oriente selon y
    metal.AddBox([-s, g, -s], [s, b, s], priority=10)
    metal.AddBox([-s, -b, -s], [s, -g, s], priority=10)

    port = fdtd.AddLumpedPort(1, acq.z_ref, [-s, -g, -s], [s, g, s],
                              "y", 1.0, priority=20, edges2grid="all")

    # Seules les lignes utiles : les bords de matiere, et une grille fine
    # autour de la fente d'alimentation. SmoothMeshLines remplit le reste.
    # Surtout pas de grille grossiere ici : ses lignes tomberaient a quelques
    # micrometres de celles de l'air et effondreraient le pas de temps.
    fin = FENTE / 2                                     # 1 mm au port
    lx = np.concatenate([np.arange(-3 * SECTION, 3 * SECTION + fin, fin),
                         [-s, s]])
    ly = np.concatenate([np.arange(-3 * FENTE, 3 * FENTE + fin, fin),
                         [-b, -g, g, b]])
    lz = np.concatenate([np.arange(-3 * SECTION, 3 * SECTION + fin, fin),
                         [-s, s]])
    return port, lx, ly, lz, LONGUEUR / 2 + SECTION
