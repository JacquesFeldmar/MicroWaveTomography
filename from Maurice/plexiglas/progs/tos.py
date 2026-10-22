"""Conversion du S11 complexe en TOS pour les graphiques du banc."""

import numpy as np


def calculer_tos(s11):
    """TOS réel pour |S11| < 1 ; NaN si le rapport est infini ou non physique."""
    module = np.abs(np.asarray(s11))
    resultat = np.full(module.shape, np.nan)
    valide = np.isfinite(module) & (module < 1)
    np.divide(1 + module, 1 - module, out=resultat, where=valide)
    return resultat
