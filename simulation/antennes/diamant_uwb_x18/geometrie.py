"""Le meme losange, a l'echelle 1,8 -- la version pour la bande du LiteVNA.

Le losange rayonnant et le plan de masse sont multiplies par 1,8 : la carte
passe de 32 x 40 a 58 x 72 mm, et la bande de 2,5-13,5 GHz a environ
1,4-7,5 GHz, c'est-a-dire celle du LiteVNA.

Aucune cote n'est recopiee ici : ce module charge `diamant_uwb/geometrie.py`
et n'en change que l'echelle et deux cotes qui ne se mettent pas a l'echelle.

CE QUI NE SUIT PAS L'ECHELLE, et pourquoi
-----------------------------------------
1. L'EPAISSEUR reste a 1,6 mm au lieu de 2,88. Deux raisons, et chacune
   suffirait : le 2,88 mm n'est pas une epaisseur de catalogue, et les deux
   losanges doivent tenir sur un MEME panneau, donc sur un meme substrat.
2. LA LARGEUR DE LIGNE reste a 3,1 mm. Les 50 ohms d'un micro-ruban se
   jouent sur le rapport largeur/epaisseur : a epaisseur constante, la
   largeur doit l'etre aussi. A 5,58 mm sur 1,6 mm de FR4, la ligne ne
   ferait plus que 28 ohms, et ses 18 mm agiraient en transformateur quart
   d'onde vers 2,5 GHz -- en plein dans la bande visee.

CONSEQUENCE, et elle est importante : cette antenne n'est plus l'homothetique
exacte de la conception publiee. Sa bande N'EST PAS celle de l'article divisee
par 1,8. Le couplage entre le losange et la masse, qui se joue a travers le
substrat, a change. Seule la simulation peut dire ce qu'elle vaut, et c'est
pour cela qu'elle est simulee a part.
"""
import importlib.util
import os

ECHELLE = 1.8
EPAISSEUR = 1.6         # mm, imposee par le panneau commun
LARGEUR_LIGNE = 3.1     # mm, imposee par les 50 ohms a cette epaisseur

_chemin = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "diamant_uwb", "geometrie.py")
_spec = importlib.util.spec_from_file_location("diamant_uwb_base", _chemin)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

NOM = "diamant_uwb_x18"
DESCRIPTION = (f"monopole planaire en losange, conception publiee, "
               f"losange a l'echelle {ECHELLE} sur FR4 de "
               f"{EPAISSEUR:.1f} mm")


def _regle():
    """Impose les trois parametres au module de base avant chaque appel."""
    _base.ECHELLE = ECHELLE
    _base.H_IMPOSE = EPAISSEUR
    _base.WF_IMPOSE = LARGEUR_LIGNE
    return _base


def cotes():
    return _regle().cotes()


def bande_attendue_ghz():
    """PREDICTION, et moins sure que pour la conception publiee.

    L'homothetie donnerait 1,39-7,50 GHz. Le substrat n'ayant pas suivi,
    c'est un ordre de grandeur, pas une attente. La figure trace quand meme
    cette bande : l'ecart entre elle et le resultat est l'information utile.
    """
    return (2.5 / ECHELLE, 13.5 / ECHELLE)


def retard_attendu_ns():
    return _regle().retard_attendu_ns()


def pose(csx, fdtd, acq):
    return _regle().pose(csx, fdtd, acq)


def contours_mm():
    return _regle().contours_mm()


def detail_mini_mm():
    return _regle().detail_mini_mm()


def controles_fabrication():
    d = _regle().cotes()
    return (_base.controles_fabrication()
            + f"\n   - largeur de la ligne d'alimentation : {d['wf']:.2f} mm "
              f"(elle NE suit PAS l'echelle : c'est elle qui fait les "
              f"50 ohms sur {d['h']:.1f} mm de FR4)")
