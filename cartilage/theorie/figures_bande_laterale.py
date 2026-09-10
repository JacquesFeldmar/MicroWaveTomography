"""Figures des sections 'choix de la bande' et 'resolution laterale exacte'."""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

c = 299_792_458.0
eps0 = 8.8541878128e-12
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

BLEU, ORANGE, AQUA, JAUNE = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
ENCRE2 = "#52514e"
EPS_S, EPS_INF, TAU_D, SIG_I = 45.0, 5.0, 8.5e-12, 0.9
EPS_OS, SIG_OS = 11.0, 0.3


def eps_cart(f):
    w = 2 * np.pi * f
    return EPS_INF + (EPS_S - EPS_INF) / (1 + 1j * w * TAU_D) - 1j * SIG_I / (w * eps0)


# =====================================================================
# FIG 1 : resolution laterale exacte
#   dx = lambda / (4 sin(theta/2)),  theta = 2 arctan(L/2R)
# =====================================================================
L = np.linspace(20, 400, 400)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.5, 5.2), sharey=True)

for ax, R, titre in ((a1, 20, "Standoff $R = 20$ mm"),
                     (a2, 100, "Standoff $R = 100$ mm")):
    for f0, col in ((6.3, BLEU), (10.0, AQUA), (15.0, ORANGE)):
        lam = c / (f0 * 1e9) * 1000
        dx = lam / (4 * np.sin(np.arctan(L / (2 * R))))
        ax.plot(L, dx, lw=2, color=col, label=f"{f0:g} GHz")
        ax.axhline(lam / 4, color=col, ls=':', lw=1.2)
    ax.axhline(5, color=ENCRE2, ls='--', lw=1.4)
    ax.set_xlabel("Ouverture synthétique $L$ (mm)")
    ax.set_title(titre)
    ax.set_ylim(0, 40)
    ax.grid(alpha=0.25, lw=0.6)
    for cote in ('top', 'right'):
        ax.spines[cote].set_visible(False)
    ax.tick_params(colors=ENCRE2)

a1.set_ylabel("Résolution latérale $\\delta x$ (mm)")
a1.annotate("plancher $\\lambda/4$ = 11,9 mm", (250, 13.5), fontsize=9, color=BLEU)
a1.annotate("objectif 5 mm", (250, 6), fontsize=9, color=ENCRE2)
a1.legend(fontsize=9, title="fréquence haute", title_fontsize=9)
a2.annotate("à 100 mm, 15 GHz ne suffit plus\navec une ouverture réaliste",
            (150, 22), fontsize=9, color=ENCRE2)
fig.suptitle("Résolution latérale : $\\delta x = \\lambda\\,/\\,4\\sin(\\theta/2)$, "
             "$\\theta = 2\\arctan(L/2R)$", fontsize=12)
fig.tight_layout()
fig.savefig(f"{OUT}/fig_laterale_exacte.png", dpi=150)
plt.close(fig)

# =====================================================================
# FIG 2 : saturation de la CRB avec la bande
# =====================================================================
TAU0 = 2 * 0.100 / c


def gamma_couche(F, d):
    n2 = np.sqrt(eps_cart(F))
    n3 = np.sqrt(EPS_OS - 1j * SIG_OS / (2 * np.pi * F * eps0))
    r12 = (1 - n2) / (1 + n2)
    r23 = (n2 - n3) / (n2 + n3)
    pr = np.exp(-2j * (2 * np.pi * F / c) * n2 * d)
    return (r12 + r23 * pr) / (1 + r12 * r23 * pr)


def crb(F, d):
    th = [d, TAU0, 1.0, 0.0]
    pas = [1e-9, 1e-14, 1e-6, 1e-6]

    def mod(t):
        dd, tt, Kr, Ki = t
        return (Kr + 1j * Ki) * np.exp(-2j * np.pi * F * tt) * gamma_couche(F, dd)

    J = np.empty((len(F), 4), dtype=complex)
    for i in range(4):
        tp = list(th); tp[i] += pas[i]
        tm = list(th); tm[i] -= pas[i]
        J[:, i] = (mod(tp) - mod(tm)) / (2 * pas[i])
    n2 = np.sqrt(eps_cart(3e9))
    s2 = abs((1 - n2) / (1 + n2)) ** 2 / 10 ** 3.0
    I = (2.0 / s2) * np.real(J.conj().T @ J)
    g = np.zeros(4); g[0] = 1.0
    try:
        return float(np.sqrt(g @ np.linalg.inv(I) @ g)) * 1e3
    except np.linalg.LinAlgError:
        return np.nan


FMAX = np.array([6.3, 8, 10, 12, 15, 20, 24, 30, 40, 55, 70])
DF = (6.3 - 1.4) * 1e9 / 200            # pas frequentiel conserve
fig, (b1, b2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

for d_mm, col in ((1.0, BLEU), (3.0, AQUA), (5.0, ORANGE)):
    v = []
    for fm in FMAX:
        N = int(round((fm - 1.4) * 1e9 / DF)) + 1
        v.append(crb(np.linspace(1.4e9, fm * 1e9, N), d_mm * 1e-3))
    b1.plot(FMAX, v, 'o-', lw=2, ms=6, color=col, label=f"$d$ = {d_mm:g} mm")

b1.axvspan(1.4, 6.3, color=AQUA, alpha=0.13)
b1.annotate("bande\nLiteVNA", (3.0, 0.0042), fontsize=9, color=ENCRE2, ha='center')
b1.set_xscale('log'); b1.set_yscale('log')
b1.set_xlabel("Fréquence haute de la bande (GHz)")
b1.set_ylabel("CRB sur l'épaisseur (mm)")
b1.set_title("La précision en épaisseur sature")
b1.grid(alpha=0.25, which='both', lw=0.6)
b1.legend(fontsize=9)
b1.annotate("au-delà de 15 GHz,\nplus aucun gain", (22, 0.016), fontsize=9,
            color=ENCRE2)

fg = np.logspace(np.log10(1e9), np.log10(70e9), 400)
n = np.sqrt(eps_cart(fg))
alpha = 2 * np.pi * fg * (-n.imag) / c
for ep, col in ((3.0, AQUA), (5.0, ORANGE)):
    b2.plot(fg / 1e9, 2 * 8.686 * alpha * ep * 1e-3, lw=2, color=col,
            label=f"couche de {ep:g} mm")
b2.axhline(40, color=ENCRE2, ls='--', lw=1.3)
b2.axvspan(1.4, 6.3, color=AQUA, alpha=0.13)
b2.annotate("budget 40 dB", (1.2, 43), fontsize=9, color=ENCRE2)
b2.annotate("13 GHz\n(5 mm)", (12.2, 88), fontsize=9, color=ORANGE, ha='right')
b2.annotate("18,8 GHz\n(3 mm)", (20, 55), fontsize=9, color=AQUA, ha='left')
for f0, col in ((13.0, ORANGE), (18.8, AQUA)):
    b2.axvline(f0, color=col, ls=':', lw=1.4)
b2.set_xscale('log')
b2.set_xlabel("Fréquence haute de la bande (GHz)")
b2.set_ylabel("Atténuation aller-retour (dB)")
b2.set_title("...parce que l'absorption ferme la bande")
b2.set_ylim(0, 150)
b2.grid(alpha=0.25, which='both', lw=0.6)
b2.legend(fontsize=9, loc='upper left')

for ax in (b1, b2):
    for cote in ('top', 'right'):
        ax.spines[cote].set_visible(False)
    ax.tick_params(colors=ENCRE2)

fig.tight_layout()
fig.savefig(f"{OUT}/fig_saturation_bande.png", dpi=150)
print("Figures ecrites : fig_laterale_exacte.png, fig_saturation_bande.png")
