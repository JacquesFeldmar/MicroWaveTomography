"""
CALIBRATION SOL -- le modele d'erreur a un port, et sa correction.

    G_m = e00 + e10.e01.G / (1 - e11.G)

Trois etalons connus (Short, Open, Load) donnent les trois termes a chaque
frequence ; `applique` les retire ensuite de toute mesure. Rien ici ne sait ou
sont rangees les calibrations : c'est l'affaire de chaque projet.
"""

import numpy as np

Z0 = 50.0

# Coefficients d'etalons. Tout a zero = etalons ideaux.
# Ordre d'importance mesure sur la chaine complete (biais sur une couche de
# 1 a 5 mm) :  CHARGE >> COURT-CIRCUIT >> OUVERT
#     ouvert 20-100 fF ignore ......... 0,01 a 0,04 mm   negligeable
#     court-circuit 0,10 nH ignore .... 0,07 mm          acceptable
#     court-circuit 0,30 nH ignore .... 0,98 mm          redhibitoire
#     charge a -25 dB au lieu de -45 .. 1,24 mm          redhibitoire
# Ce qui est LINEAIRE en frequence (capacite de frange, offsets) est absorbe
# par le reglage du plan de reference ; seule la courbure subsiste.
ETALONS_IDEAUX = dict(
    open_offset_ps=0.0, open_c0=0.0, open_c1=0.0, open_c2=0.0, open_c3=0.0,
    short_offset_ps=0.0, short_l0=0.0, short_l1=0.0, short_l2=0.0, short_l3=0.0,
)


# ======================================================================
# MODELE DES ETALONS
# ======================================================================
def gamma_open(freqs, p):
    f = np.asarray(freqs, dtype=float)
    C = p["open_c0"] + p["open_c1"] * f + p["open_c2"] * f**2 + p["open_c3"] * f**3
    w = 2 * np.pi * f
    return ((1.0 - 1j * w * C * Z0) / (1.0 + 1j * w * C * Z0)
            * np.exp(-2j * w * p["open_offset_ps"] * 1e-12))


def gamma_short(freqs, p):
    f = np.asarray(freqs, dtype=float)
    L = p["short_l0"] + p["short_l1"] * f + p["short_l2"] * f**2 + p["short_l3"] * f**3
    w = 2 * np.pi * f
    Zc = 1j * w * L
    return (Zc - Z0) / (Zc + Z0) * np.exp(-2j * w * p["short_offset_ps"] * 1e-12)


def gamma_load(freqs, p):
    """Charge supposee parfaite : son defaut reel est indiscernable de la
    directivite -- c'est justement ce que mesure --verifier."""
    return np.zeros(len(freqs), dtype=complex)


# ======================================================================
# RESOLUTION ET APPLICATION
# ======================================================================
def resoudre(g_ideaux, g_mesures):
    """Trois etalons, trois inconnues, a chaque frequence.

    En posant d = e00, s = e11, t = e10.e01 - e00.e11, le modele
        G_m = e00 + t.G_a / (1 - e11.G_a)
    devient LINEAIRE :  G_m = d + s.(G_a.G_m) + t.G_a
    -- un systeme 3x3 exact, bien mieux conditionne qu'une inversion directe.
    """
    n = len(g_mesures[0])
    e00 = np.empty(n, dtype=complex)
    e11 = np.empty(n, dtype=complex)
    e10e01 = np.empty(n, dtype=complex)
    conds = np.empty(n)
    for k in range(n):
        A = np.array([[1.0, g_ideaux[i][k] * g_mesures[i][k], g_ideaux[i][k]]
                      for i in range(3)], dtype=complex)
        b = np.array([g_mesures[i][k] for i in range(3)], dtype=complex)
        conds[k] = np.linalg.cond(A)
        d, s, t = np.linalg.solve(A, b)
        e00[k], e11[k], e10e01[k] = d, s, t + d * s
    return dict(e00=e00, e11=e11, e10e01=e10e01), conds


def applique(cal, freqs, s11):
    """G_vrai = (G_mes - e00) / (e10.e01 + e11.(G_mes - e00))."""
    if cal is None:
        return s11
    f_cal, f = cal["freqs"], np.asarray(freqs, dtype=float)
    if len(f) != len(f_cal) or not np.allclose(f, f_cal, rtol=1e-9):
        if not cal.get("_averti", False):
            print("  [cal] ATTENTION : balayage different de la calibration.")
            print(f"        cal    : {f_cal[0]/1e9:.3f}-{f_cal[-1]/1e9:.3f} GHz, "
                  f"{len(f_cal)} pts")
            print(f"        mesure : {f[0]/1e9:.3f}-{f[-1]/1e9:.3f} GHz, "
                  f"{len(f)} pts")
            print("        Termes interpoles -- refais plutot la calibration.")
            cal["_averti"] = True
        if f[0] < f_cal[0] - 1e3 or f[-1] > f_cal[-1] + 1e3:
            print("  [cal] Hors bande : calibration ignoree.")
            return s11
        def it(v):
            return np.interp(f, f_cal, v.real) + 1j * np.interp(f, f_cal, v.imag)
        e00, e11, e10e01 = it(cal["e00"]), it(cal["e11"]), it(cal["e10e01"])
    else:
        e00, e11, e10e01 = cal["e00"], cal["e11"], cal["e10e01"]
    num = np.asarray(s11) - e00
    return num / (e10e01 + e11 * num)
