"""Empreinte commune de SMA femelle Cinch/Johnson 142-0701-851.

Repere local : x transversal, u depuis le bord du PCB vers l'antenne.
Dimensions du catalogue Johnson, page 58 (pouces convertis en mm).
Le boitier coaxial n'est pas de-embarquable par ce dessin : la simulation
est referencee au bord du PCB, apres une alimentation ideale 50 ohms.
"""
import numpy as np

REFERENCE = "Cinch Johnson 142-0701-851"
URL = "https://www.cinch.com/products/rf-microwave/connectors/142-0701-851"
CATALOGUE = "https://www.cinch.com/media/catalogs/products/rf-microwave/cable-assemblies/cable-assembly/ca-Johnson-Catalog.pdf"
EPAISSEUR_PCB_MM = 1.6
LARGEUR_SIGNAL_MM = 0.090 * 25.4
LONGUEUR_PAD_MM = 0.200 * 25.4
MASSE_INTERIEUR_MM = 0.250 * 25.4 / 2
MASSE_EXTERIEUR_MM = 0.440 * 25.4 / 2
VIA_X_MM = 0.170 * 25.4
VIA_U_MM = LONGUEUR_PAD_MM + 0.035 * 25.4
VIA_DIAMETRE_MM = 0.018 * 25.4
PASTILLE_DIAMETRE_MM = 0.038 * 25.4


def cercle(x, u, rayon, n=48):
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    return [(float(x+rayon*np.cos(a)), float(u+rayon*np.sin(a))) for a in angles]


def empreinte_mm(origine_u=0.0):
    """Cuivres a ajouter au radiateur, sans repercer les polygones Gerber."""
    dessus, dessous = [], []
    r = PASTILLE_DIAMETRE_MM/2
    for signe in (-1, 1):
        x0, x1 = sorted([signe*MASSE_INTERIEUR_MM, signe*MASSE_EXTERIEUR_MM])
        dessus.append([(x0, origine_u), (x1, origine_u),
                       (x1, origine_u+LONGUEUR_PAD_MM), (x0, origine_u+LONGUEUR_PAD_MM)])
        x = signe*VIA_X_MM
        demi_attache = VIA_DIAMETRE_MM/2  # neck .018 du catalogue
        dessus.append([(x-demi_attache, origine_u+LONGUEUR_PAD_MM),
                       (x+demi_attache, origine_u+LONGUEUR_PAD_MM),
                       (x+demi_attache, origine_u+VIA_U_MM),
                       (x-demi_attache, origine_u+VIA_U_MM)])
        pad = cercle(x, origine_u+VIA_U_MM, r)
        dessus.append(pad)
        # La face inferieure des trois cartes est deja une masse continue
        # sous cette empreinte. Ne pas superposer un disque redondant :
        # CSXCAD le signalerait comme primitive inutilisee.
    return {"F_Cu": dessus, "B_Cu": dessous}


def vias_mm(origine_u=0.0):
    """Diametre FINI des trous metallises, pas diametre d'outil avant placage."""
    return [(signe*VIA_X_MM, origine_u+VIA_U_MM, VIA_DIAMETRE_MM) for signe in (-1, 1)]


def ruban_losange(sommets, origine_u, largeur):
    """Taper de l'empreinte jusqu'au microruban original, sans changer le losange."""
    b, fin = LARGEUR_SIGNAL_MM/2, LONGUEUR_PAD_MM
    transition = fin + abs(largeur-LARGEUR_SIGNAL_MM)/2
    milieu = [tuple(map(float, p)) for p in sommets[1:-1]]
    return ([(-b, origine_u), (-b, origine_u+fin), (-largeur/2, origine_u+transition)]
            + milieu + [(largeur/2, origine_u+transition), (b, origine_u+fin), (b, origine_u)])


def ruban_vivaldi(polygone, largeur):
    b, fin = LARGEUR_SIGNAL_MM/2, LONGUEUR_PAD_MM
    transition = fin + abs(largeur-LARGEUR_SIGNAL_MM)/2
    return ([(-b, 0.0), (b, 0.0), (b, fin), (largeur/2, transition)]
            + polygone[2:] + [(-largeur/2, transition), (-b, fin)])


def pose_vias(csx, trous, epaisseur, normale="z", origine_normale=0.0):
    """Vias courts PEC equivalents (ame pleine), empreinte exterieure du trou.

    Approximation quasi-statique du fut metallise ; elle evite de mailler une
    paroi de 25 um. Le modele et ses limites sont conserves dans le manifeste.
    """
    metal = csx.AddMetal("vias_sma_pec_equivalents")
    for x, u, diametre in trous:
        if normale == "z":
            debut, fin = [x, u, origine_normale], [x, u, origine_normale+epaisseur]
        else:
            debut, fin = [x, origine_normale, u], [x, origine_normale+epaisseur, u]
        metal.AddCylinder(debut, fin, radius=diametre/2, priority=30)


def manifeste():
    return dict(reference=REFERENCE, genre="SMA femelle standard (non RP-SMA)",
        epaisseur_pcb_mm=EPAISSEUR_PCB_MM, source=CATALOGUE, page=58,
        largeur_signal_mm=LARGEUR_SIGNAL_MM, longueur_pad_mm=LONGUEUR_PAD_MM,
        vias_diametre_fini_mm=VIA_DIAMETRE_MM,
        plan_simulation="bord du PCB, port ideal 50 ohms",
        modele_vias="cylindres PEC pleins equivalents, pas paroi mince",
        limite="boitier SMA, PTFE, broche et soudure non modelises en 3D")
