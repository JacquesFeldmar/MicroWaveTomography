"""Figure : le modele de Debye du cartilage et ce qu'il implique pour la bande.

C'est cette courbe qui decide seule la question "faut-il monter en frequence ?".
"""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

c = 299_792_458.0
eps0 = 8.8541878128e-12
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

# Palette categorielle de reference, emplacements 1-3 dans l'ordre fixe
BLEU, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
ENCRE, ENCRE2 = "#0b0b0b", "#52514e"

# --- Parametres ajustes sur les valeurs publiees du cartilage ---
EPS_S, EPS_INF, TAU, SIG_I = 45.0, 5.0, 8.5e-12, 0.9
F_RELAX = 1 / (2 * np.pi * TAU)

f = np.logspace(np.log10(0.1e9), np.log10(100e9), 600)
w = 2 * np.pi * f

eps_p = EPS_INF + (EPS_S - EPS_INF) / (1 + (w * TAU) ** 2)          # partie reelle
eps_pp_dip = (EPS_S - EPS_INF) * w * TAU / (1 + (w * TAU) ** 2)     # pertes dipolaires
eps_pp_ion = SIG_I / (w * eps0)                                     # pertes ioniques
eps_pp = eps_pp_dip + eps_pp_ion

fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.5, 5.2))

# ---------------------------------------------------------------- panneau 1
a1.plot(f / 1e9, eps_p, lw=2, color=BLEU, label=r"$\varepsilon'$ (stockage)")
a1.plot(f / 1e9, eps_pp, lw=2, color=ORANGE, label=r"$\varepsilon''$ (pertes, total)")
a1.plot(f / 1e9, eps_pp_ion, lw=2, ls=':', color=AQUA,
        label=r"$\varepsilon''$ part ionique seule")
a1.axvline(F_RELAX / 1e9, color=ENCRE2, ls='--', lw=1.2)
a1.annotate(f"relaxation de l'eau\n$1/2\\pi\\tau$ = {F_RELAX/1e9:.0f} GHz",
            (F_RELAX / 1e9 * 0.88, 47), fontsize=9, color=ENCRE2,
            ha='right', va='top')
a1.annotate(r"$\varepsilon_s$ = 45", (0.12, 45), fontsize=9, color=BLEU, va='bottom')
a1.annotate(r"$\varepsilon_\infty$ = 5", (60, 6.5), fontsize=9, color=BLEU)
a1.set_xscale('log')
a1.set_xlabel("Fréquence (GHz)")
a1.set_ylabel("Permittivité relative")
a1.set_ylim(0, 50)
a1.set_title("Modèle de Debye ajusté sur le cartilage", color=ENCRE)
a1.grid(alpha=0.25, which='both', lw=0.6)
a1.legend(fontsize=9, framealpha=0.9)

# points d'ancrage publies
for fg, ep in ((2.45, 42.0), (10.0, 32.0)):
    a1.plot(fg, ep, 'o', ms=8, color=BLEU, mec='white', mew=1.6, zorder=5)
a1.annotate("valeurs publiées\n(points d'ancrage)", (10, 32), (16, 33),
            fontsize=8.5, color=ENCRE2,
            arrowprops=dict(arrowstyle='-', color=ENCRE2, lw=0.8))

# ---------------------------------------------------------------- panneau 2
n = np.sqrt(eps_p - 1j * eps_pp)
alpha = w * (-n.imag) / c                                # Np/m
for ep_mm, col, lab in ((3.0, BLEU, "3 mm"), (5.0, ORANGE, "5 mm")):
    a2.plot(f / 1e9, 2 * 8.686 * alpha * ep_mm * 1e-3, lw=2, color=col,
            label=f"couche de {lab}")
a2.axvspan(1.4, 6.3, color=AQUA, alpha=0.13)
a2.annotate("LiteVNA\n1,4-6,3 GHz", (3.0, 190), fontsize=9, color=ENCRE2,
            ha='center')
a2.axhline(40, color=ENCRE2, ls='--', lw=1.2)
a2.annotate("au-delà de ~40 dB l'écho de fond\nest sous le plancher",
            (0.12, 44), fontsize=9, color=ENCRE2, va='bottom')
a2.set_xscale('log')
a2.set_xlabel("Fréquence (GHz)")
a2.set_ylabel("Atténuation aller-retour (dB)")
a2.set_ylim(0, 220)
a2.set_title("Ce que coûte la montée en fréquence", color=ENCRE)
a2.grid(alpha=0.25, which='both', lw=0.6)
a2.legend(fontsize=9, loc='upper left', framealpha=0.9)

for ax in (a1, a2):
    for cote in ('top', 'right'):
        ax.spines[cote].set_visible(False)
    ax.tick_params(colors=ENCRE2)

fig.tight_layout()
fig.savefig(f"{OUT}/fig_debye.png", dpi=150)
print(f"Figure ecrite : {OUT}/fig_debye.png")

print(f"\nControle des points d'ancrage (ajustement) :")
for fg in (2.45, 10.0):
    ff = fg * 1e9; ww = 2 * np.pi * ff
    ep = EPS_INF + (EPS_S - EPS_INF) / (1 + (ww * TAU) ** 2)
    epp = (EPS_S - EPS_INF) * ww * TAU / (1 + (ww * TAU) ** 2) + SIG_I / (ww * eps0)
    print(f"   {fg:5.2f} GHz : eps' = {ep:5.1f}   sigma = {ww*eps0*epp:5.2f} S/m")
