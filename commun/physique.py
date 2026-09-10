"""
PHYSIQUE ET TRAITEMENT -- ce qui vaut quel que soit le banc.

Constantes, permittivites des milieux, indice complexe, profil de distance et
resolution. Aucune geometrie, aucun modele de scene : chaque projet construit
les siens a partir d'ici.
"""

import numpy as np

c = 299_792_458.0
eps0 = 8.8541878128e-12


# ---------------------------------------------------------------- milieux
# (eps_r, sigma en S/m) vers 3 GHz
MILIEUX = {
    "air":          (1.0, 0.0),
    "pmma":         (2.6, 0.0),
    "ptfe":         (2.1, 0.0),
    "verre":        (6.9, 0.05),
    "os":           (11.0, 0.30),
    "os_spongieux": (20.0, 0.80),
    "peau":         (39.0, 1.40),
    "cartilage":    (42.5, 1.60),
    "eau":          (70.0, 0.05),
    "metal":        (None, None),      # r23 = -1
}


def milieu(nom):
    """Rend (eps_r, sigma) a partir d'un nom ou d'une valeur numerique."""
    if isinstance(nom, (int, float)):
        e = float(nom)
        return e, (0.0 if e < 10.0 else 1.6)
    if nom not in MILIEUX:
        raise ValueError(f"milieu inconnu : {nom}. Connus : "
                         + ", ".join(MILIEUX))
    return MILIEUX[nom]


# ======================================================================
# MODELE PHYSIQUE
# ======================================================================
def indice(freqs, eps_r, sigma):
    return np.sqrt(eps_r - 1j * sigma / (2 * np.pi * freqs * eps0))


# ======================================================================
# PROFIL DE DISTANCE
# ======================================================================
def profil_distance(freqs, s11, zoom=16, fenetre="hann"):
    """Enveloppe et axe des distances (aller simple, mm) depuis le plan du VNA.

    Le pas temporel vaut 1/(n_fft.df) avec df = BW/(N-1). Utiliser 1/BW
    surestime toutes les distances de N/(N-1) -- 1 % a 101 points.
    """
    n = len(s11)
    if fenetre == "hann":
        fen = np.hanning(n)
    elif fenetre == "blackman-harris":
        k = np.arange(n) / (n - 1)
        fen = (0.35875 - 0.48829 * np.cos(2 * np.pi * k)
               + 0.14128 * np.cos(4 * np.pi * k)
               - 0.01168 * np.cos(6 * np.pi * k))
    else:
        fen = np.ones(n)
    n_fft = n * zoom
    prof = np.abs(np.fft.ifft(np.asarray(s11) * fen, n=n_fft)) * zoom
    df = (freqs[-1] - freqs[0]) / (n - 1)
    pas = 1.0 / (n_fft * df) * c / 2.0 * 1e3
    dist = np.arange(n_fft) * pas
    demi = n_fft // 2
    return dist[:demi], prof[:demi], pas


def resolution_mm(freqs, fenetre="hann"):
    """Largeur du lobe principal : k.c/(2B), k = 1,7 pour Hann."""
    k = 1.7 if fenetre == "hann" else 2.3
    return k * c / (2 * (freqs[-1] - freqs[0])) * 1e3
