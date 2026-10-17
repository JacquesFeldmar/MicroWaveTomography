"""TRAITEMENT -- exactement celui du rapport pour John.

    R_k = S11_plaque(f_k) - S11_fond(f_k)
    P_m = 16 . |IFFT_3216(w_k R_k)_m|          niveau affiche : 20 log10 P_m
    d_m = c.m / (2 . 3216 . df)

La fenetre est une Hann symetrique, le remplissage de zeros vaut 16, et le gain
coherent de la fenetre n'est PAS normalise -- comme dans le rapport, pour que
les niveaux soient comparables aux siens.

Aucune dependance a openEMS : ce module traite indifferemment une mesure, une
simulation FDTD ou le modele analytique.
"""
import numpy as np

from banc import C, Acquisition


# ======================================================================
# PROFIL DE DISTANCE
# ======================================================================
def fenetre(n, nom="hann"):
    """Hann symetrique : w_k = 0.5 (1 - cos(2.pi.k/(N-1)))."""
    if nom == "hann":
        return np.hanning(n)
    if nom == "aucune":
        return np.ones(n)
    raise ValueError(f"fenetre inconnue : {nom}")


def profil(s11, acq: Acquisition, fond=None):
    """Rend (distances en m, profil lineaire P_m).

    Si `fond` est fourni, il est retranche AVANT la fenetre, comme dans le
    rapport. Le profil rendu est |P_m|, non converti en dB.
    """
    r = np.asarray(s11, dtype=complex)
    if fond is not None:
        r = r - np.asarray(fond, dtype=complex)
    w = fenetre(len(r), acq.fenetre)
    p = acq.zero_padding * np.abs(np.fft.ifft(w * r, n=acq.n_fft))
    d = np.arange(acq.n_fft) * acq.pas_distance
    demi = acq.n_fft // 2
    return d[:demi], p[:demi]


def en_db(p):
    return 20 * np.log10(np.maximum(p, 1e-18))


# ======================================================================
# DETECTION DES DEUX PICS
# ======================================================================
def _parabole(y, i):
    """Correction sous-echantillon du sommet, en pas d'axe."""
    if i <= 0 or i >= len(y) - 1:
        return 0.0
    a, b, c_ = y[i - 1], y[i], y[i + 1]
    den = a - 2 * b + c_
    return 0.0 if den == 0 else 0.5 * (a - c_) / den


def maxima_locaux(d, p, fenetre_cm=(40.0, 120.0), combien=2, interpoler=True):
    """Les `combien` plus grands maxima locaux dans la fenetre donnee.

    Rend une liste de (distance_cm, niveau_dB), du plus fort au plus faible,
    comme les points traces sur la figure 2 du rapport.
    """
    d_cm = d * 100
    dans = (d_cm >= fenetre_cm[0]) & (d_cm <= fenetre_cm[1])
    idx = np.where(dans)[0]
    pics = [i for i in idx[1:-1] if p[i] > p[i - 1] and p[i] >= p[i + 1]]
    pics.sort(key=lambda i: p[i], reverse=True)
    sortie = []
    for i in pics[:combien]:
        pas_cm = (d_cm[1] - d_cm[0])
        dec = _parabole(p, i) if interpoler else 0.0
        sortie.append((d_cm[i] + dec * pas_cm, float(en_db(p[i]))))
    return sortie


# ======================================================================
# PHASE : LE TRAJET GEOMETRIQUE RETIRE
# ======================================================================
def phase_sans_trajet(freqs, r, distance_m):
    """H(f) = R(f).exp(+j.4.pi.f.x/c), puis phase deroulee en degres.

    Ce que trace la figure 3 du rapport : il ne reste que la phase
    supplementaire theta(f), c'est-a-dire tout ce qui n'est pas le trajet
    aller-retour dans l'air.
    """
    h = np.asarray(r, dtype=complex) * np.exp(
        1j * 4 * np.pi * np.asarray(freqs) * distance_m / C)
    return np.unwrap(np.angle(h)) * 180 / np.pi, h


def pente_ponderee(freqs, phase_deg, poids=None):
    """Ajustement lineaire pondere de la phase (degres) -> (retard, decalage).

    Rend (tau_aller_retour en s, decalage equivalent en cm, droite ajustee).
    Le decalage equivalent est c.tau/2 : c'est la grandeur que le rapport
    appelle « equivalent offset ».
    """
    f = np.asarray(freqs, dtype=float)
    y = np.asarray(phase_deg, dtype=float)
    w = np.ones_like(f) if poids is None else np.asarray(poids, dtype=float)
    w = w / w.sum()
    fm, ym = (w * f).sum(), (w * y).sum()
    pente = (w * (f - fm) * (y - ym)).sum() / (w * (f - fm) ** 2).sum()
    droite = ym + pente * (f - fm)
    tau = -(pente * np.pi / 180) / (2 * np.pi)     # s, aller-retour
    return tau, C * tau / 2 * 100, droite


# ======================================================================
# BILAN D'UNE SERIE
# ======================================================================
def bilan(freqs, fond, mesures, acq: Acquisition, fenetre_cm=(40.0, 120.0)):
    """mesures : dict {distance_cm : S11}. Rend un dict de resultats par distance."""
    out = {}
    for d_cm, s11 in sorted(mesures.items()):
        r = np.asarray(s11, dtype=complex) - np.asarray(fond, dtype=complex)
        d, p = profil(s11, acq, fond=fond)
        pics = maxima_locaux(d, p, fenetre_cm)
        pics_tries = sorted(pics, key=lambda t: t[0])
        ph, h = phase_sans_trajet(freqs, r, d_cm / 100)
        tau, dec_cm, droite = pente_ponderee(freqs, ph, poids=np.abs(r) ** 2)
        out[d_cm] = dict(
            distances=d, profil=p, residu=r, pics=pics,
            pic_proche=pics_tries[0][0] if pics_tries else np.nan,
            pic_lointain=pics_tries[1][0] if len(pics_tries) > 1 else np.nan,
            phase_deg=ph, droite_deg=droite, tau=tau, decalage_phase_cm=dec_cm)
        out[d_cm]["ecart_proche_cm"] = out[d_cm]["pic_proche"] - d_cm
        out[d_cm]["ecart_lointain_cm"] = out[d_cm]["pic_lointain"] - d_cm
    return out


def table_bilan(res):
    """Le tableau de la page 3 du rapport, en texte."""
    lig = [f"{'plaque':>8s}{'pic proche':>12s}{'pic lointain':>14s}"
           f"{'ecart proche':>14s}{'ecart lointain':>16s}{'pente phase':>13s}"]
    lig.append("-" * len(lig[0]))
    for d_cm, r in sorted(res.items()):
        lig.append(f"{d_cm:>6.0f} cm{r['pic_proche']:>10.2f} cm"
                   f"{r['pic_lointain']:>12.2f} cm"
                   f"{r['ecart_proche_cm']:>12.2f} cm"
                   f"{r['ecart_lointain_cm']:>14.2f} cm"
                   f"{r['decalage_phase_cm']:>11.1f} cm")
    return "\n".join(lig)
