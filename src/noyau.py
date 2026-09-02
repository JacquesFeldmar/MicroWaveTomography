"""
NOYAU COMMUN -- modele physique, traitement, acquisition.

Ce n'est PAS un programme : c'est la bibliotheque partagee par les trois
programmes du banc.

    calibration.py    corrections appliquees a chaque mesure
    radar.py          mesure en direct, enregistrement, rejeu
    qualification.py  verdicts sur l'antenne

Tout ce qui doit rester coherent entre eux vit ici : la bande de balayage, le
plan de l'antenne, le modele stratifie, les deux estimateurs. Une constante
dupliquee est une constante qui finit par diverger.
"""

import os
import re
import time

import numpy as np
from scipy.optimize import minimize
from scipy.signal import find_peaks

c = 299_792_458.0
eps0 = 8.8541878128e-12

# ---------------------------------------------------------------- instrument
PORT_VNA = "ASRL6::INSTR"
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

# ---------------------------------------------------------------- dossiers
_ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_CAL = os.path.join(_ICI, "calibration")
DOSSIER_MES = os.path.join(_ICI, "mesures")
DOSSIER_QUAL = os.path.join(_ICI, "qualification")


def plan_antenne():
    """Valeur mesuree si calibration/plan.npz existe, sinon la constante."""
    ch = os.path.join(DOSSIER_CAL, "plan.npz")
    if os.path.exists(ch):
        try:
            return float(np.load(ch)["plan_mm"])
        except Exception:
            pass
    return PLAN_ANTENNE_MM


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
    from skrf.vi.vna.nanovna import NanoVNAv2
    import skrf as rf
    vna = NanoVNAv2(PORT_VNA, backend="@py")
    vna.frequency = rf.Frequency(start=start, stop=stop, npoints=npts,
                                 unit="GHz")
    return vna


def balayage(vna):
    """Un balayage brut. Rend (freqs, s11)."""
    s11, _ = vna.get_s11_s21()
    return s11.f, s11.s[:, 0, 0]


def acquiert(vna, n_moy=16, n_jetes=2, silencieux=False):
    """Moyennage VECTORIEL : abaisse le plancher de 10.log10(N) dB."""
    for _ in range(n_jetes):
        vna.get_s11_s21()
    acc, freqs = None, None
    for k in range(n_moy):
        f, s = balayage(vna)
        if freqs is None:
            freqs, acc = f.copy(), np.zeros(len(f), dtype=complex)
        acc += s
        if not silencieux:
            print(f"      balayage {k + 1}/{n_moy}", end="\r", flush=True)
    if not silencieux:
        print(" " * 32, end="\r")
    if hasattr(vna, "avance"):     # simulateur : scene suivante
        vna.avance()
    return freqs, acc / n_moy



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


class _Reseau:
    """Imite juste ce que le code utilise d'un objet skrf.Network."""
    def __init__(self, f, s):
        self.f = f
        self.s = s.reshape(-1, 1, 1)


# ======================================================================
# ENREGISTREMENT / RELECTURE
# ======================================================================
def enregistre(chemin, freqs, sweeps, temps=None, **meta):
    """Un ou plusieurs balayages BRUTS, avec leurs instants.

    Format unique pour une mesure isolee comme pour une sequence : sweeps est
    toujours un tableau (n_balayages, n_frequences). Les donnees enregistrees
    sont NON CALIBREES, pour pouvoir etre recalculees plus tard avec une
    meilleure calibration.
    """
    sweeps = np.atleast_2d(np.asarray(sweeps))
    if temps is None:
        temps = np.zeros(len(sweeps))
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    np.savez_compressed(chemin, freqs=freqs, sweeps=sweeps,
                        temps=np.asarray(temps), **meta)
    return chemin


def relit(chemin):
    """Rend (freqs, sweeps, temps). Accepte l'ancien format a un balayage."""
    z = np.load(chemin, allow_pickle=True)
    freqs = z["freqs"]
    if "sweeps" in z:
        return freqs, np.atleast_2d(z["sweeps"]), z["temps"]
    return freqs, np.atleast_2d(z["s11"]), np.zeros(1)   # ancien format


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
