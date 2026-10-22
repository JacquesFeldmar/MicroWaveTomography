"""Figures de l'explication du slide 8 : de la pente de phase a la distance.

Produit, dans le dossier du document :
  fig_pente_phase.png   un retard est une droite dans la phase
  fig_dispersion.png    ce que fait une phase supplementaire dependante de f
  fig_bande.png         la distance mesuree depend alors de la bande utilisee

Lancer depuis ce dossier :  python figures_explication_slide_8.py
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ICI = os.path.dirname(os.path.abspath(__file__))
CART = os.path.join(os.path.dirname(ICI), "cartilage")
sys.path.insert(0, CART)
import noyau  # noqa: E402  (profil_distance, resolution_mm)

c = 299792458.0
F1, F2, NPTS = 1.4e9, 6.3e9, 201
FREQS = np.linspace(F1, F2, NPTS)
D_CIBLE = 0.30                      # m, plaque a 30 cm
TAU_A = 0.55e-9                     # s, retard ALLER SIMPLE d'antenne
TAU_DISP = (0.55e-9, 0.35e-9)       # dispersif : de 1,4 GHz a 6,3 GHz


def phase_cible(freqs, d):
    """Phase de l'aller-retour dans l'air, en radians (non deroulee)."""
    return -4 * np.pi * freqs * d / c


def theta_retard(freqs, tau_a):
    """Phase supplementaire d'un retard pur : -2.pi.f.(2.tau_a)."""
    return -2 * np.pi * freqs * (2 * tau_a)


def theta_dispersif(freqs, tau_debut, tau_fin):
    """Phase dont le retard de groupe varie lineairement avec la frequence.

    tau_g(f) = 2.tau_a(f) et theta(f) = -2.pi.integrale(tau_g).
    """
    tau_a = tau_debut + (tau_fin - tau_debut) * (freqs - freqs[0]) / (
        freqs[-1] - freqs[0])
    tau_g = 2 * tau_a
    theta = -2 * np.pi * np.concatenate(
        [[0.0], np.cumsum(0.5 * (tau_g[1:] + tau_g[:-1]) * np.diff(freqs))])
    return theta, tau_a


def distance_affichee(freqs, s11):
    """Maximum du profil de distance, en mm."""
    d, prof, pas = noyau.profil_distance(freqs, s11)
    i = int(np.argmax(prof))
    return d[i] + noyau._offset_parabolique(prof, i) * pas, d, prof


# =====================================================================
# Figure 1 : un retard est une droite
# =====================================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))

cas = (("cible seule à 30 cm", phase_cible(FREQS, D_CIBLE), "#1f77b4"),
       ("cible + retard d'antenne (0,55 ns)",
        phase_cible(FREQS, D_CIBLE) + theta_retard(FREQS, TAU_A), "#d62728"),
       ("cible + phase constante (+90°)",
        phase_cible(FREQS, D_CIBLE) + np.pi / 2, "#2ca02c"))
for nom, phi, coul in cas:
    tau = -np.polyfit(FREQS, np.unwrap(phi), 1)[0] / (2 * np.pi)
    ax1.plot(FREQS / 1e9, np.unwrap(phi) / (2 * np.pi), color=coul, lw=2.2,
             label=f"{nom}\n  pente → {tau*1e9:.2f} ns → "
                   f"$\\hat d$ = {c*tau/2*100:.1f} cm")
ax1.set_xlabel("fréquence (GHz)")
ax1.set_ylabel("phase déroulée (tours)")
ax1.set_title("La phase déroulée est une droite ; sa pente est le retard",
              fontsize=11)
ax1.grid(alpha=0.3)
ax1.legend(fontsize=8.5, loc="lower left")

for nom, phi, coul in cas:
    tau = -np.gradient(np.unwrap(phi), FREQS) / (2 * np.pi)
    ax2.plot(FREQS / 1e9, tau * 1e9, color=coul, lw=2.2)
ax2.set_xlabel("fréquence (GHz)")
ax2.set_ylabel(r"retard de groupe $\tau_{\rm mes}$ (ns)")
ax2.set_ylim(0, 4)
ax2.set_title("Le même résultat, vu comme un retard de groupe", fontsize=11)
ax2.grid(alpha=0.3)
ax2.annotate("une phase CONSTANTE ne change rien :\nles deux courbes se "
             "superposent à 2,00 ns", xy=(3.2, 2.0), xytext=(2.4, 0.5),
             fontsize=9, arrowprops=dict(arrowstyle="->", color="#2ca02c"))
ax2.annotate("un RETARD ajoute 2τ$_a$ = 1,10 ns :\nla distance est décalée de "
             "c·τ$_a$ = 16,5 cm", xy=(4.6, 3.1), xytext=(3.0, 3.4),
             fontsize=9, arrowprops=dict(arrowstyle="->", color="#d62728"))
fig.tight_layout()
fig.savefig(os.path.join(ICI, "fig_pente_phase.png"), dpi=120)

# =====================================================================
# Figure 2 : phase supplementaire dependante de la frequence
# =====================================================================
theta_d, tau_a_f = theta_dispersif(FREQS, *TAU_DISP)
s_pur = np.exp(1j * (phase_cible(FREQS, D_CIBLE) + theta_retard(FREQS, TAU_A)))
s_disp = np.exp(1j * (phase_cible(FREQS, D_CIBLE) + theta_d))

fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))

axs[0].plot(FREQS / 1e9, np.full_like(FREQS, TAU_A) * 1e9, color="#d62728",
            lw=2.2, label="retard constant (antenne idéale)")
axs[0].plot(FREQS / 1e9, tau_a_f * 1e9, color="#9467bd", lw=2.2,
            label="retard qui dérive (centre de phase mobile)")
axs[0].set_xlabel("fréquence (GHz)")
axs[0].set_ylabel(r"retard aller simple $\tau_a$ (ns)")
axs[0].set_title("a)  La phase supplémentaire θ(f)", fontsize=11)
axs[0].set_ylim(0.2, 0.7)
axs[0].grid(alpha=0.3)
axs[0].legend(fontsize=8.5, loc="lower left")

for s, nom, coul in ((s_pur, "retard constant", "#d62728"),
                     (s_disp, "retard qui dérive", "#9467bd")):
    tau = -np.gradient(np.unwrap(np.angle(s)), FREQS) / (2 * np.pi)
    axs[1].plot(FREQS / 1e9, c * tau / 2 * 100, color=coul, lw=2.2, label=nom)
axs[1].axhline(D_CIBLE * 100 + c * TAU_A * 100, color="gray", ls="--", lw=1)
axs[1].set_xlabel("fréquence (GHz)")
axs[1].set_ylabel(r"$\hat d$ lue localement (cm)")
axs[1].set_title("b)  La distance lue dépend alors de la fréquence",
                 fontsize=11)
axs[1].grid(alpha=0.3)
axs[1].legend(fontsize=9, loc="upper right")

for s, nom, coul in ((s_pur, "retard constant", "#d62728"),
                     (s_disp, "retard qui dérive", "#9467bd")):
    pic, dist, prof = distance_affichee(FREQS, s)
    axs[2].plot(dist / 10, prof / prof.max(), color=coul, lw=2.2,
                label=f"{nom} — maximum à {pic/10:.1f} cm")
axs[2].axvline(D_CIBLE * 100 + c * TAU_A * 100, color="gray", ls="--", lw=1)
axs[2].set_xlim(20, 90)
axs[2].set_xlabel("distance affichée (cm)")
axs[2].set_ylabel("enveloppe (normalisée)")
axs[2].set_title("c)  Et l'écho s'étale et se déplace", fontsize=11)
axs[2].grid(alpha=0.3)
axs[2].legend(fontsize=9, loc="upper right")
fig.tight_layout()
fig.savefig(os.path.join(ICI, "fig_dispersion.png"), dpi=120)

# =====================================================================
# Figure 3 : la distance mesuree depend de la bande utilisee
# =====================================================================
fig, (axa, axb) = plt.subplots(1, 2, figsize=(13, 4.8))

largeur = 1.2e9
centres = np.linspace(F1 + largeur / 2, F2 - largeur / 2, 40)
lues = []
for fc in centres:
    masque = (FREQS >= fc - largeur / 2) & (FREQS <= fc + largeur / 2)
    f = FREQS[masque]
    phi = np.unwrap(np.angle(s_disp[masque]))
    tau = -np.polyfit(f, phi, 1)[0] / (2 * np.pi)
    lues.append(c * tau / 2 * 100)
axa.plot(centres / 1e9, lues, color="#9467bd", lw=2.4)
axa.axhline(D_CIBLE * 100, color="gray", ls=":", lw=1.2)
axa.text(2.0, D_CIBLE * 100 + 1.0, "distance vraie, 30 cm", fontsize=9,
         color="gray")
axa.set_xlabel("centre de la sous-bande de 1,2 GHz utilisée (GHz)")
axa.set_ylabel(r"$\hat d$ (cm)")
axa.set_title("a)  Avec un θ(f) qui dérive, la distance lue\n"
              "dépend de la partie de la bande utilisée", fontsize=11)
axa.grid(alpha=0.3)

d_mes = np.array([30.0, 40.0, 50.0, 60.0])
p_mes = np.array([68.6, 76.4, 86.1, 94.7])
axb.plot(d_mes, p_mes - d_mes, "o-", color="#1f77b4", lw=2,
         label="mesure du 17/09/2026")
pente, ord0 = np.polyfit(d_mes, p_mes, 1)
axb.plot(d_mes, ord0 + (pente - 1) * d_mes, "--", color="#1f77b4", lw=1,
         label=f"droite ajustée : pente du pic {pente:.3f}")
axb.axhline((p_mes - d_mes).mean(), color="gray", ls=":", lw=1.2)
axb.text(31, (p_mes - d_mes).mean() + 0.25,
         f"moyenne {(p_mes-d_mes).mean():.1f} cm", fontsize=9, color="gray")
axb.set_xlabel("distance vraie de la plaque (cm)")
axb.set_ylabel("écart mesuré (cm)")
axb.set_title("b)  Le symptôme observé : un écart qui n'est\n"
              "pas constant, mais décroît de 3,9 cm", fontsize=11)
axb.grid(alpha=0.3)
axb.legend(fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(ICI, "fig_bande.png"), dpi=120)

print("Figures ecrites dans", ICI)
for nom, s in (("retard constant", s_pur), ("retard qui derive", s_disp)):
    pic, _, _ = distance_affichee(FREQS, s)
    tau = -np.polyfit(FREQS, np.unwrap(np.angle(s)), 1)[0] / (2 * np.pi)
    print(f"  {nom:20s} : maximum du profil {pic/10:5.1f} cm, "
          f"pente de phase {c*tau/2*100:5.1f} cm")
print(f"  sous-bandes : de {min(lues):.1f} a {max(lues):.1f} cm "
      f"(etendue {max(lues)-min(lues):.1f} cm)")
print(f"  periode de phase pour 36,45 cm : "
      f"{1/(2*0.3645/c)/1e6:.0f} MHz")
