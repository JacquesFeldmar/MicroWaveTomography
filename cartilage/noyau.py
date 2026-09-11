"""
NOYAU DU PROJET CARTILAGE -- modele stratifie, inversion, simulateur.

Ce n'est PAS un programme : c'est la bibliotheque partagee par les trois
programmes du banc.

    calibration.py    corrections appliquees a chaque mesure
    radar.py          mesure en direct, enregistrement, rejeu
    qualification.py  verdicts sur l'antenne

Tout ce qui doit rester coherent entre eux vit ici : la bande de balayage, le
plan de l'antenne, le modele stratifie, les deux estimateurs. Une constante
dupliquee est une constante qui finit par diverger.

Ce qui ne depend pas du banc -- l'instrument, le profil de distance, les
permittivites -- vient de ../commun/, partage avec le projet de tomographie.
C'est re-exporte ici : noyau.acquiert, noyau.milieu... restent valables.
"""

import os
import re
import sys
import time

import numpy as np
from scipy.optimize import minimize
from scipy.signal import find_peaks

# commun/ est a la racine du depot : on le rend importable sans installation,
# pour que "python radar.py" marche tel quel depuis ce dossier.
_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from commun.physique import (c, eps0, MILIEUX, milieu,  # noqa: E402,F401
                             indice, profil_distance, resolution_mm)
from commun.instrument import (PORT_VNA, balayage,  # noqa: E402,F401
                               acquiert, enregistre, relit, ouvrir_reel,
                               ReseauSimule as _Reseau)

# ---------------------------------------------------------------- instrument
BANDE_DEFAUT = (1.4, 6.3)      # GHz
POINTS_DEFAUT = 201            # 101 points echantillonnent trop peu la rampe de
                               # phase du standoff : le cout devient rugueux et
                               # le raffinement 30x plus lent. 201 est le bon
                               # reglage, et il ne coute que 0,25 s de plus.

# ---------------------------------------------------------------- geometrie
# Position du pic fixe de l'antenne sur l'axe brut : les distances affichees en
# sont retranchees, pour se lire depuis le plan rayonnant.
# MESUREE le 21/08/2026 (plaque metallique a 100 puis 200 mm).
# A refaire apres tout changement d'antenne ou de cable : calibration.py --plan
PLAN_ANTENNE_MM = 702.0
# Ecart de pente au-dela duquel une mesure du plan est REFUSEE. Une pente
# fausse n'est jamais une erreur de plan : ce sont les distances annoncees qui
# sont fausses, et l'offset qu'on en tirerait decalerait toutes les mesures.
# Le 22/08/2026, une pente de -21,9 enregistree sans refus a place le plan a
# 1748 mm : toutes les distances decalees d'un metre.
PENTE_TOLERANCE = 0.05

# ---------------------------------------------------------------- dossiers
_ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_CAL = os.path.join(_ICI, "calibration")
DOSSIER_MES = os.path.join(_ICI, "mesures")
DOSSIER_QUAL = os.path.join(_ICI, "qualification")


def plan_antenne():
    """Valeur mesuree si calibration/plan.npz existe, sinon la constante.

    Un fichier dont la pente sort de PENTE_TOLERANCE est ecarte, avec un
    avertissement : calibration.py --plan refuse de l'ecrire, il date donc
    d'avant ce refus ou n'a pas ete produit par le programme.
    """
    ch = os.path.join(DOSSIER_CAL, "plan.npz")
    if not os.path.exists(ch):
        return PLAN_ANTENNE_MM
    try:
        z = np.load(ch)
        plan = float(z["plan_mm"])
        pente = float(z["pente"]) if "pente" in z else 1.0
    except Exception:
        return PLAN_ANTENNE_MM
    if abs(pente - 1.0) > PENTE_TOLERANCE:
        print(f"  [plan] ECARTE : {ch} donne une pente de {pente:.3f} "
              f"(plan {plan:.1f} mm).")
        print(f"         Valeur par defaut utilisee : {PLAN_ANTENNE_MM:.0f} mm."
              "  Refais : python calibration.py --plan 100 200")
        return PLAN_ANTENNE_MM
    return plan


# ======================================================================
# MODELE STRATIFIE
# ======================================================================
def gamma_couche(freqs, d, eps_r, sigma, substrat):
    """Reflexion d'une couche sur un substrat, reflexions internes incluses.

        G(f) = (r12 + r23.exp(-2j.beta2.d)) / (1 + r12.r23.exp(-2j.beta2.d))
    """
    n2 = indice(freqs, eps_r, sigma)
    r12 = (1.0 - n2) / (1.0 + n2)
    if substrat == "metal":
        r23 = -np.ones_like(n2)
    else:
        e3, s3 = milieu(substrat)
        n3 = indice(freqs, e3, s3)
        r23 = (n2 - n3) / (n2 + n3)
    prop = np.exp(-2j * (2 * np.pi * freqs / c) * n2 * d)
    return (r12 + r23 * prop) / (1.0 + r12 * r23 * prop)


# ======================================================================
# METHODE A -- DETECTION A DEUX PICS
# ======================================================================
def _offset_parabolique(y, i):
    if i <= 0 or i >= len(y) - 1:
        return 0.0
    den = y[i - 1] - 2.0 * y[i] + y[i + 1]
    return 0.0 if den == 0.0 else max(-0.5, min(0.5, 0.5 * (y[i - 1] - y[i + 1]) / den))


def methode_deux_pics(freqs, s11, eps_r, d_min_mm=10.0):
    """Rend (epaisseur_mm, ecart_apparent_mm, [pos1, pos2]) ou None.

    Ne devient fiable qu'au-dela de 2,5 largeurs de resolution : en deca
    l'apodisation biaise l'ecart de plusieurs pour cent, et sous une resolution
    elle rend une valeur fausse mais plausible.
    """
    dist, prof, pas = profil_distance(freqs, s11)
    m = dist >= d_min_mm
    dd, pp = dist[m], prof[m]
    idx, props = find_peaks(pp, prominence=3.0 * np.median(pp),
                            distance=max(1, int(round(15.0 / pas))))
    if len(idx) < 2:
        return None
    deux = np.sort(idx[np.argsort(props["prominences"])[-2:]])
    pos = [dd[i] + _offset_parabolique(pp, i) * pas for i in deux]
    ecart = pos[1] - pos[0]
    return ecart / np.sqrt(eps_r), ecart, pos


# ======================================================================
# METHODE B -- INVERSION SUR MODELE
# ======================================================================
def _cout_projete(g, mod):
    """Residu de ||g - K.mod||^2 minimise sur K complexe (elimine par
    projection : K n'a jamais besoin d'etre cherche)."""
    den = np.sum(np.abs(mod) ** 2, axis=-1)
    num = np.abs(np.tensordot(np.conj(mod), g, axes=([-1], [0]))) ** 2
    return float(np.vdot(g, g).real) - num / den


def _raffine(freqs, g, fabrique, x0, bornes):
    """Simplexe sur des parametres REMIS A L'ECHELLE (tous O(1) a O(100)).

    Sans cette remise a l'echelle, d ~ 1e-2 m et tau ~ 1e-9 s different de sept
    ordres de grandeur ; Nelder-Mead, qui n'a qu'un seul xatol, patauge et met
    trente fois plus de temps pour le meme resultat.
    """
    def cout(x):
        for v, (lo, hi) in zip(x, bornes):
            if not (lo < v < hi):
                return 1e9
        return _cout_projete(g, fabrique(x))
    r = minimize(cout, x0, method="Nelder-Mead",
                 options=dict(xatol=1e-4, fatol=1e-16, maxiter=3000))
    return r.x, r.fun


def mesure_modele(freqs, s11, eps_r, sigma, substrat, d_max_mm=8.0,
                  d0_mm=None, tau0_ps=None):
    """Ajuste (d, tau0) avec K complexe libre.

    Rend (epaisseur_mm, standoff_mm, residu, modele_ajuste). Le standoff est la
    distance a la PREMIERE SURFACE : elle est estimee, jamais fournie. Le
    programme mesure donc la distance ET l'epaisseur d'un seul ajustement.

    d0_mm / tau0_ps : depart impose (mode suivi). Sinon, grille complete.
    """
    g = np.asarray(s11)

    def fabrique(x):
        return np.exp(-2j * np.pi * freqs * x[1] * 1e-12) * gamma_couche(
            freqs, x[0] * 1e-3, eps_r, sigma, substrat)

    if d0_mm is None or tau0_ps is None:
        dist, prof, _ = profil_distance(freqs, g)
        tau_pic = 2.0 * dist[int(np.argmax(prof))] * 1e-3 / c * 1e12
        d_gr = np.linspace(0.05, d_max_mm, max(400, int(d_max_mm * 40)))
        t_gr = tau_pic + np.linspace(-200.0, 200.0, 121)
        mod_d = np.array([gamma_couche(freqs, d * 1e-3, eps_r, sigma, substrat)
                          for d in d_gr])
        best, arg = np.inf, (0, 0)
        for it, t in enumerate(t_gr):
            r = _cout_projete(g, mod_d * np.exp(-2j * np.pi * freqs * t * 1e-12))
            i = int(np.argmin(r))
            if r[i] < best:
                best, arg = r[i], (i, it)
        d0_mm, tau0_ps = d_gr[arg[0]], t_gr[arg[1]]

    x, fun = _raffine(freqs, g, fabrique, [d0_mm, tau0_ps],
                      [(1e-3, d_max_mm * 1.5), (-1e6, 1e6)])
    m = fabrique(x)
    K = np.vdot(m, g) / np.vdot(m, m)
    return (x[0], x[1] * 1e-12 * c / 2.0 * 1e3,
            fun / float(np.vdot(g, g).real), K * m)


def mesure_permittivite(freqs, s11, d_mm, sigma, substrat,
                        eps_min=1.5, eps_max=90.0):
    """Probleme INVERSE : epaisseur connue au pied a coulisse, on cherche eps_r.

    C'est la mesure qui valide la chaine entiere, et la repetition, sur un
    materiau connu, de la caracterisation dielectrique du cartilage.
    Rend (eps_r, residu, modele_ajuste).
    """
    g = np.asarray(s11)
    d = d_mm * 1e-3

    def fabrique(x):
        return np.exp(-2j * np.pi * freqs * x[1] * 1e-12) * gamma_couche(
            freqs, d, x[0], sigma, substrat)

    dist, prof, _ = profil_distance(freqs, g)
    tau_pic = 2.0 * dist[int(np.argmax(prof))] * 1e-3 / c * 1e12
    e_gr = np.linspace(eps_min, eps_max, 900)
    t_gr = tau_pic + np.linspace(-200.0, 200.0, 121)
    mod_e = np.array([gamma_couche(freqs, d, e, sigma, substrat) for e in e_gr])
    best, arg = np.inf, (0, 0)
    for it, t in enumerate(t_gr):
        r = _cout_projete(g, mod_e * np.exp(-2j * np.pi * freqs * t * 1e-12))
        i = int(np.argmin(r))
        if r[i] < best:
            best, arg = r[i], (i, it)

    x, fun = _raffine(freqs, g, fabrique, [e_gr[arg[0]], t_gr[arg[1]]],
                      [(eps_min, eps_max), (-1e6, 1e6)])
    m = fabrique(x)
    K = np.vdot(m, g) / np.vdot(m, m)
    return x[0], fun / float(np.vdot(g, g).real), K * m


# ======================================================================
# ACQUISITION
# ======================================================================
def ouvrir_vna(start_ghz=None, stop_ghz=None, points=None, simu=None):
    """Ouvre l'instrument, ou un instrument SIMULE si `simu` est une liste de
    scenes (voir VNASimule). Permet d'apprendre et de tester sans materiel."""
    start = BANDE_DEFAUT[0] if start_ghz is None else start_ghz
    stop = BANDE_DEFAUT[1] if stop_ghz is None else stop_ghz
    npts = POINTS_DEFAUT if points is None else points
    if simu:
        print(f"  [SIMU] instrument simule -- scenario {list(simu)}")
        return VNASimule(np.linspace(start * 1e9, stop * 1e9, npts), simu)
    return ouvrir_reel(start, stop, npts, PORT_VNA)



# ======================================================================
# INSTRUMENT SIMULE
# ======================================================================
class VNASimule:
    """Faux LiteVNA : produit des balayages synthetiques realistes.

    Sert a trois choses : apprendre l'interface sans materiel, capturer les
    copies d'ecran de la documentation, et verifier la chaine complete en
    integration -- pas seulement les fonctions de calcul.

    `scenario` est une liste de scenes jouees dans l'ordre a chaque
    acquisition ; la derniere se repete indefiniment.
    """

    # Termes d'erreur d'un instrument plausible (directivite -30 dB, cable)
    def __init__(self, freqs, scenario=("pmma12",), bruit_db=-45.0,
                 graine=12345):
        self.freqs = np.asarray(freqs, dtype=float)
        self.scenario = list(scenario)
        self.k = 0
        self.rng = np.random.default_rng(graine)
        self.bruit = 10 ** (bruit_db / 20.0)
        f = self.freqs
        self.e00 = 0.03 * np.exp(1j * 2 * np.pi * f * 0.9e-9)
        self.e11 = 0.20 * np.exp(1j * 2 * np.pi * f * 1.2e-9)
        self.t = 0.85 * np.exp(-2j * 2 * np.pi * f * 2.0e-9)
        self.plan = PLAN_ANTENNE_MM * 1e-3          # position du plan d'antenne
        self.antenne = 0.30 * np.exp(-2j * 2 * np.pi * f * self.plan / c)

    def _scene(self, nom):
        """Coefficient de reflexion vrai, au plan du VNA."""
        f = self.freqs
        if nom == "short":
            return -np.ones_like(f, dtype=complex)
        if nom == "open":
            return np.ones_like(f, dtype=complex)
        if nom == "load":
            return np.zeros_like(f, dtype=complex)
        if nom == "vide":
            return self.antenne
        if nom.startswith("metal"):          # metal@150
            D = float(nom.split("@")[1]) if "@" in nom else 150.0
            r = -np.exp(-2j * 2 * np.pi * f * (self.plan + D * 1e-3) / c)
            return self.antenne + 0.5 * r
        # couche : "pmma12@150", "cartilage3@120sur os"
        corps = nom.split("@")
        mat = corps[0]
        D = float(corps[1]) if len(corps) > 1 else 150.0
        m = re.match(r"([a-z_]+)([0-9.]+)", mat)
        milieu_nom, ep = m.group(1), float(m.group(2))
        e, sg = milieu(milieu_nom)
        sub = "os" if milieu_nom in ("cartilage", "peau") else "air"
        g = gamma_couche(f, ep * 1e-3, e, sg, sub)
        return self.antenne + 0.5 * g * np.exp(
            -2j * 2 * np.pi * f * (self.plan + D * 1e-3) / c)

    def get_s11_s21(self):
        nom = self.scenario[min(self.k, len(self.scenario) - 1)]
        ga = self._scene(nom)
        mes = self.e00 + self.t * ga / (1 - self.e11 * ga)
        n = len(self.freqs)
        mes = mes + self.bruit * (self.rng.normal(0, 1, n)
                                  + 1j * self.rng.normal(0, 1, n)) / np.sqrt(2)
        return _Reseau(self.freqs, mes), None

    def avance(self):
        self.k += 1

    def close(self):
        pass



# ======================================================================
# AUTOTEST DU NOYAU
# ======================================================================
def autotest():
    print("=" * 74)
    print("  AUTOTEST DU NOYAU -- donnees synthetiques, aucun instrument")
    print("=" * 74)
    freqs = np.linspace(BANDE_DEFAUT[0] * 1e9, BANDE_DEFAUT[1] * 1e9,
                        POINTS_DEFAUT)
    R = 0.150
    cas = [("PMMA 80 mm / air", 80.0, "pmma", "air", 110.0),
           ("PMMA 20 mm / air", 20.0, "pmma", "air", 30.0),
           ("PMMA 12 mm / air", 12.0, "pmma", "air", 20.0),
           ("PMMA  4 mm / air", 4.0, "pmma", "air", 10.0),
           ("PMMA  2 mm / air", 2.0, "pmma", "air", 8.0),
           ("Cartilage 3 mm / os", 3.0, "cartilage", "os", 8.0),
           ("Cartilage 1 mm / os", 1.0, "cartilage", "os", 8.0)]
    res = resolution_mm(freqs)
    print(f"\n  Resolution {res:.0f} mm\n")
    print(f"  {'cas':<22}{'vrai':>7}{'2 pics':>11}{'modele':>11}"
          f"{'err. mod.':>12}{'standoff':>11}{'ms':>7}")
    print("  " + "-" * 72)
    ok = True
    for nom, d, mat, sub, dmax in cas:
        e, s = milieu(mat)
        g = np.exp(-2j * np.pi * freqs * 2 * R / c) * gamma_couche(
            freqs, d * 1e-3, e, s, sub)
        a = methode_deux_pics(freqs, g, e)
        t0 = time.perf_counter()
        b, so, _, _ = mesure_modele(freqs, g, e, s, sub, d_max_mm=dmax)
        ms = (time.perf_counter() - t0) * 1e3
        if abs(b - d) > 0.02 or abs(so - R * 1e3) > 0.5:
            ok = False
        print(f"  {nom:<22}{d:6.1f} " + (f"{a[0]:10.3f}" if a else f"{'echec':>10}")
              + f"{b:11.3f}{b - d:+12.4f}{so:10.1f}{ms:7.0f}")

    # permittivite : probleme inverse
    print(f"\n  {'inverse (eps_r)':<22}{'vrai':>7}{'mesure':>11}{'erreur':>12}")
    print("  " + "-" * 52)
    for mat, d, sub in (("pmma", 12.0, "air"), ("verre", 10.0, "air"),
                        ("cartilage", 3.0, "os")):
        e, s = milieu(mat)
        g = np.exp(-2j * np.pi * freqs * 2 * R / c) * gamma_couche(
            freqs, d * 1e-3, e, s, sub)
        eh, _, _ = mesure_permittivite(freqs, g, d, s, sub)
        if abs(eh - e) > 0.01:
            ok = False
        print(f"  {mat + f' {d:.0f} mm':<22}{e:6.2f} {eh:10.4f}{eh - e:+12.5f}")

    print(f"\n  VERDICT : {'REUSSI' if ok else 'ECHEC'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(autotest())
