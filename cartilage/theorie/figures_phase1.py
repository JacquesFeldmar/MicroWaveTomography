"""Figures du guide de mise en oeuvre de la phase 1 (levee de risque FMCW)."""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

BLEU, ORANGE, AQUA, JAUNE = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
ENCRE, ENCRE2, GRIS = "#0b0b0b", "#52514e", "#c9cfd6"


def bloc(ax, x, y, w, h, titre, sous="", couleur=BLEU, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012",
                                linewidth=1.8, edgecolor=couleur,
                                facecolor=couleur + "18"))
    ax.text(x + w / 2, y + h / 2 + (0.055 if sous else 0), titre, ha='center',
            va='center', fontsize=fs, weight='bold', color=ENCRE)
    if sous:
        ax.text(x + w / 2, y + h / 2 - 0.075, sous, ha='center', va='center',
                fontsize=fs - 1.5, color=ENCRE2, style='italic')


def fleche(ax, x1, y1, x2, y2, txt="", couleur=ENCRE2, dec=0.03):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>',
                                 mutation_scale=13, linewidth=1.5,
                                 color=couleur, shrinkA=0, shrinkB=0))
    if txt:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dec, txt, ha='center',
                va='bottom', fontsize=8, color=couleur)


def pt(ax, x, y, nom, dy=-0.42):
    """Repere de point de test, decale du fil pour ne pas gener les etiquettes."""
    ax.plot([x, x], [y, y + dy * 0.45], lw=1.2, color=ORANGE, zorder=4)
    ax.plot([x], [y + dy], 'o', ms=19, color='white', mec=ORANGE, mew=2,
            zorder=5)
    ax.text(x, y + dy, nom, ha='center', va='center', fontsize=8,
            weight='bold', color=ORANGE, zorder=6)


# =====================================================================
# FIG 1 : architecture du banc et points de test
# =====================================================================
fig, ax = plt.subplots(figsize=(13.5, 6.6))
ax.set_xlim(0, 13.5); ax.set_ylim(0, 6.6); ax.axis('off')

bloc(ax, 0.3, 4.6, 2.0, 0.9, "PC", "pilotage + acquisition", ENCRE2)
bloc(ax, 3.0, 4.6, 2.3, 0.9, "EVAL-ADF4159", "boucle a rampe", BLEU)
bloc(ax, 6.0, 4.6, 2.1, 0.9, "VCO 4-8 GHz", "HMC586", BLEU)
bloc(ax, 8.8, 4.6, 2.0, 0.9, "Diviseur", "ZX10-2-852+", AQUA)

bloc(ax, 8.8, 2.9, 2.0, 0.85, "Ampli TX", "ZX60-83W+", AQUA)
bloc(ax, 11.3, 2.9, 1.9, 0.85, "Antenne TX", "", JAUNE)
bloc(ax, 11.3, 1.2, 1.9, 0.85, "Antenne RX", "", JAUNE)
bloc(ax, 8.8, 1.2, 2.0, 0.85, "LNA", "6-8 GHz, NF < 3 dB", AQUA)
bloc(ax, 6.0, 1.2, 2.1, 0.85, "Melangeur", "double equilibre", ORANGE)
bloc(ax, 3.0, 1.2, 2.3, 0.85, "Filtre + ampli", "bande de base", ORANGE)
bloc(ax, 0.3, 1.2, 2.0, 0.85, "Numeriseur", "carte son / DAQ", ENCRE2)

fleche(ax, 2.3, 5.05, 3.0, 5.05, "SPI")
fleche(ax, 5.3, 5.05, 6.0, 5.05, "V_tune")
fleche(ax, 8.1, 5.05, 8.8, 5.05, "RF")
fleche(ax, 9.8, 4.6, 9.8, 3.75, "TX")
fleche(ax, 10.8, 3.32, 11.3, 3.32)
fleche(ax, 11.3, 1.62, 10.8, 1.62)
fleche(ax, 8.8, 1.62, 8.1, 1.62, "RF")
fleche(ax, 6.0, 1.62, 5.3, 1.62, "FI")
fleche(ax, 3.0, 1.62, 2.3, 1.62)
# voie OL : du diviseur vers le melangeur
ax.plot([9.4, 9.4, 7.05, 7.05], [4.6, 3.9, 3.9, 2.05], lw=1.5, color=ORANGE,
        ls='--')
ax.add_patch(FancyArrowPatch((7.05, 2.3), (7.05, 2.05), arrowstyle='-|>',
                             mutation_scale=13, lw=1.5, color=ORANGE))
ax.text(7.6, 3.62, "OL (référence de démodulation)", fontsize=8.5,
        color=ORANGE, style='italic', ha='center')
fleche(ax, 1.3, 4.6, 1.3, 2.05, "", ENCRE2)
ax.text(1.45, 3.3, "USB", fontsize=8, color=ENCRE2, rotation=90, va='center')

pt(ax, 5.65, 5.05, "TP1")
pt(ax, 8.45, 5.05, "TP2")
pt(ax, 10.15, 4.17, "TP3", dy=0.0)
pt(ax, 5.65, 1.62, "TP4")
pt(ax, 2.65, 1.62, "TP5")

ax.text(6.75, 6.25, "Banc de phase 1 — tout en modules connectorises SMA, "
        "aucune soudure", ha='center', fontsize=12.5, weight='bold',
        color=ENCRE)
ax.text(6.75, 0.45, "TP1 a TP5 : points de test, chacun accessible en "
        "devissant un cable SMA (§ tests de sous-systeme)",
        ha='center', fontsize=9, color=ORANGE)
fig.tight_layout()
fig.savefig(f"{OUT}/fig_p1_banc.png", dpi=150)
plt.close(fig)

# =====================================================================
# FIG 2 : les trois tests de sous-systeme
# =====================================================================
fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6))

# (a) plateau de balayage vu a l'analyseur
a = axes[0]
f = np.linspace(5.0, 9.0, 500)
plateau = np.where((f >= 6.0) & (f <= 8.0), -12.0, -70.0)
plateau = plateau + np.random.default_rng(0).normal(0, 0.35, len(f))
a.plot(f, plateau, lw=1.4, color=BLEU)
a.axvspan(6.0, 8.0, color=BLEU, alpha=0.10)
a.annotate("plateau plat a ±1,5 dB\nsur 6,0–8,0 GHz", (7.0, -25), ha='center',
           fontsize=9, color=ENCRE2)
a.set_xlabel("Fréquence (GHz)"); a.set_ylabel("Niveau (dBm)")
a.set_ylim(-80, 0)
a.set_title("A — Balayage (analyseur, max-hold)", fontsize=10.5)

# (b) linearite mesuree par ligne a retard
b = axes[1]
fb = np.linspace(200, 360, 700)
def raie(centre, largeur, amp):
    return amp * np.exp(-0.5 * ((fb - centre) / largeur) ** 2)
b.plot(fb, 20 * np.log10(raie(280, 1.2, 1) + 1e-4), lw=2, color=AQUA,
       label="rampe asservie (bon)")
b.plot(fb, 20 * np.log10(raie(280, 14, 1) + 1e-4), lw=2, color=ORANGE,
       ls='--', label="rampe en boucle ouverte")
b.axvline(280, color=ENCRE2, ls=':', lw=1.2)
b.annotate("280 kHz\n(3 m de câble)", (280, -70), ha='center', fontsize=8.5,
           color=ENCRE2)
b.set_xlabel("Fréquence de battement (kHz)")
b.set_ylabel("Niveau relatif (dB)")
b.set_ylim(-80, 5)
b.legend(fontsize=8.5)
b.set_title("B — Linéarité de rampe (ligne à retard)", fontsize=10.5)

# (c) profil de distance sur plaque metallique
cx = axes[2]
d = np.linspace(0, 400, 900)
for D, col, lab in ((100, BLEU, "100 mm"), (200, AQUA, "200 mm"),
                    (300, ORANGE, "300 mm")):
    prof = 20 * np.log10(np.exp(-0.5 * ((d - D) / 26) ** 2) + 1e-3)
    cx.plot(d, prof, lw=1.8, color=col, label=lab)
cx.axhline(-40, color=ENCRE2, ls=':', lw=1.2)
cx.set_xlabel("Distance apparente (mm)")
cx.set_ylabel("Niveau relatif (dB)")
cx.set_ylim(-60, 5)
cx.legend(fontsize=8.5, title="plaque à", title_fontsize=8.5)
cx.set_title("C — Justesse d'échelle (plaque métal)", fontsize=10.5)

for x in axes:
    x.grid(alpha=0.25, lw=0.6)
    for cote in ('top', 'right'):
        x.spines[cote].set_visible(False)
    x.tick_params(colors=ENCRE2)
fig.suptitle("Résultats attendus des trois tests de sous-système",
             fontsize=12.5)
fig.tight_layout()
fig.savefig(f"{OUT}/fig_p1_tests.png", dpi=150)
plt.close(fig)

# =====================================================================
# FIG 3 : critere de reussite quantifie sur la linearite
# =====================================================================
fig, (g1, g2) = plt.subplots(1, 2, figsize=(13.5, 4.8))

nl = np.logspace(-4, -1.3, 200)
for d_mm, col in ((1.0, BLEU), (3.0, AQUA), (5.0, ORANGE)):
    g1.plot(nl * 100, nl * d_mm, lw=2, color=col, label=f"d = {d_mm:g} mm")
g1.axhline(0.1, color=ENCRE2, ls='--', lw=1.5)
g1.axvline(0.1, color=ORANGE, ls='-.', lw=1.8)
g1.annotate("objectif 0,1 mm", (1.2e-2, 0.115), fontsize=9, color=ENCRE2)
g1.annotate("critère retenu\n0,1 %", (0.11, 0.0015), fontsize=9, color=ORANGE)
g1.set_xscale('log'); g1.set_yscale('log')
g1.set_xlabel("Non-linéarité de rampe (%)")
g1.set_ylabel("Biais sur l'épaisseur (mm)")
g1.set_title("Pourquoi 0,1 % suffit", fontsize=11)
g1.legend(fontsize=9)

L = np.linspace(0.5, 10, 300)
tau = 2 * L * 0.7 / 299_792_458.0
fb = (2.0e9 / 100e-6) * tau
g2.plot(L, fb / 1e3, lw=2.2, color=BLEU)
for Lc, lab in ((3.0, "3 m — recommandé"), (1.0, "1 m"), (10.0, "10 m")):
    tc = 2 * Lc * 0.7 / 299_792_458.0
    g2.plot([Lc], [(2.0e9 / 100e-6) * tc / 1e3], 'o', ms=9, color=ORANGE)
    g2.annotate(lab, (Lc, (2.0e9 / 100e-6) * tc / 1e3), (Lc + 0.3,
                (2.0e9 / 100e-6) * tc / 1e3 - 60), fontsize=8.5, color=ENCRE2)
g2.set_xlabel("Longueur de la ligne à retard (m)")
g2.set_ylabel("Fréquence de battement (kHz)")
g2.set_title("Choix de la ligne à retard (câble, $v = 0{,}7c$)", fontsize=11)

for x in (g1, g2):
    x.grid(alpha=0.25, which='both', lw=0.6)
    for cote in ('top', 'right'):
        x.spines[cote].set_visible(False)
    x.tick_params(colors=ENCRE2)
fig.tight_layout()
fig.savefig(f"{OUT}/fig_p1_critere.png", dpi=150)
print("Figures ecrites : fig_p1_banc.png, fig_p1_tests.png, fig_p1_critere.png")
