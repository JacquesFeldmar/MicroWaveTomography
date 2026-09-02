"""Figures de la section SAR et de la section faisabilite LiteVNA."""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

c = 3e8
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

BANDES = ((1.4e9, "1,4 GHz"), (3.0e9, "3 GHz"), (6.3e9, "6,3 GHz"))

# =====================================================================
# FIG A : perte de cohérence due à une erreur de pose
#   phase aller-retour : phi = 4*pi*dr/lambda ; perte = 8.686*sigma_phi^2 dB
# =====================================================================
dr = np.logspace(-2, 1.2, 300)          # erreur de pose RMS, mm
fig, ax = plt.subplots(figsize=(9, 5.4))
for f0, lab in BANDES:
    lam = c / f0 * 1000                  # mm
    sig = 4 * np.pi * dr / lam
    ax.plot(dr, 8.686 * sig ** 2, lw=2, label=f"{lab}  ($\\lambda$ = {lam:.0f} mm)")
ax.axhline(1.0, color='r', ls='--', lw=1.5, label="perte de 1 dB (tolérable)")
ax.axvline(0.1, color='g', ls='-.', lw=2,
           label="robot chirurgical typique (0,1 mm)")
ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlabel("Erreur RMS de pose (mm)")
ax.set_ylabel("Perte de sommation cohérente (dB)")
ax.set_ylim(1e-4, 30)
ax.set_title("Budget de cohérence du SAR : la précision robot n'est pas limitante")
ax.grid(alpha=0.3, which='both'); ax.legend(fontsize=9, loc='upper left')
fig.tight_layout(); fig.savefig(f"{OUT}/fig_sar_coherence.png", dpi=140)
plt.close(fig)

for f0, lab in BANDES:
    lam = c / f0 * 1000
    dr1 = np.sqrt(1.0 / 8.686) * lam / (4 * np.pi)
    print(f"Erreur de pose donnant 1 dB de perte a {lab:8s} : {dr1:.2f} mm")

# =====================================================================
# FIG B : nombre de poses et temps de balayage
#   echantillonnage de l'ouverture synthetique : pas <= lambda_min/4
# =====================================================================
aire = np.linspace(10, 200, 200)                  # cote de la zone balayee, mm
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.5, 5))
for f0, lab in BANDES:
    pas = c / f0 * 1000 / 4
    n = (aire / pas) ** 2
    a1.plot(aire, n, lw=2, label=f"$f_{{max}}$ = {lab} (pas {pas:.0f} mm)")
a1.axvspan(60, 100, color='green', alpha=0.10)
a1.annotate("condyle fémoral", (80, 3), ha='center', fontsize=9,
            color='darkgreen')
a1.set_xlabel("Côté de la zone balayée (mm)")
a1.set_ylabel("Nombre de poses")
a1.set_yscale('log'); a1.grid(alpha=0.3, which='both'); a1.legend(fontsize=9)
a1.set_title("Poses nécessaires (échantillonnage $\\lambda/4$)")

n_poses = np.arange(1, 400)
for t_pose, lab in ((0.25, "acquisition seule (0,25 s)"),
                    (0.75, "arrêt-mesure-marche (0,75 s)"),
                    (1.50, "pose lente (1,5 s)")):
    a2.plot(n_poses, n_poses * t_pose / 60, lw=2, label=lab)
a2.axhline(2, color='r', ls='--', lw=1.5, label="2 min (acceptable au bloc)")
a2.axvline(57, color='g', ls='-.', lw=1.8, label="57 poses (100x80 mm à 6,3 GHz)")
a2.set_xlabel("Nombre de poses")
a2.set_ylabel("Durée du balayage (min)")
a2.set_ylim(0, 8); a2.grid(alpha=0.3); a2.legend(fontsize=8.5)
a2.set_title("Durée, au débit mesuré sur le LiteVNA")
fig.suptitle("Dimensionnement du balayage robotisé", fontsize=12)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_sar_poses.png", dpi=140); plt.close(fig)

for f0, lab in BANDES:
    pas = c / f0 * 1000 / 4
    print(f"Pas d'echantillonnage a {lab:8s} : {pas:5.1f} mm  "
          f"-> {(100/pas)*(80/pas):5.0f} poses pour 100x80 mm")

print(f"\nFigures ecrites dans {OUT}")
