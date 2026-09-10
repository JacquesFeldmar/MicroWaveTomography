"""
Genere les figures quantitatives du cours (application TKA, cartilage 0-5 mm,
sans contact, sonde portee par un robot 6 axes).
"""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

c = 3e8
EPS0 = 8.854e-12
F1, F2, NPTS = 1.4e9, 6.3e9, 101
freqs = np.linspace(F1, F2, NPTS)
w = 2 * np.pi * freqs
B = F2 - F1

CARTILAGE = (40.0, 1.7)
OS = (12.0, 0.3)
D_MAX = 5.0                      # mm : epaisseur max visee
CIBLE = 0.1                      # mm : precision visee

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(11)


def n_of(eps_r, sigma, ff=freqs):
    return np.sqrt(eps_r - 1j * sigma / (2 * np.pi * ff * EPS0))


def gamma(d_mm, eps_cart=CARTILAGE, sub=OS, ff=freqs):
    n1 = np.ones_like(ff, dtype=complex)
    n2 = n_of(*eps_cart, ff=ff)
    n3 = n_of(*sub, ff=ff)
    r12 = (n1 - n2) / (n1 + n2)
    r23 = (n2 - n3) / (n2 + n3)
    ph = np.exp(-2j * (2 * np.pi * ff / c) * n2 * (d_mm / 1000.0))
    return (r12 + r23 * ph) / (1 + r12 * r23 * ph)


def dgamma_dd(d_mm, h=1e-4):
    return (gamma(d_mm + h) - gamma(d_mm - h)) / (2 * h)     # par mm


# =====================================================================
# FIG 1 : la signature d'une couche — ce que la mesure "voit"
# =====================================================================
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
for d in (0, 0.5, 1, 2, 3, 5):
    g = gamma(d)
    a1.plot(freqs / 1e9, 20 * np.log10(np.abs(g)), lw=1.6, label=f"d = {d} mm")
    a2.plot(freqs / 1e9, np.degrees(np.angle(g / gamma(0))), lw=1.6,
            label=f"d = {d} mm")
a1.set_xlabel("Fréquence (GHz)"); a1.set_ylabel(r"$|\Gamma|$ (dB)")
a1.set_title("Module du coefficient de réflexion")
a2.set_xlabel("Fréquence (GHz)")
a2.set_ylabel(r"arg$(\Gamma/\Gamma_0)$ (degrés)")
a2.set_title("Phase relative à la couche nulle")
for a in (a1, a2):
    a.grid(alpha=0.3); a.legend(fontsize=8, ncol=2)
fig.suptitle("Signature spectrale d'une couche de cartilage sur os "
             "— c'est cela que l'inversion exploite", fontsize=12)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_signature.png", dpi=140); plt.close(fig)

# =====================================================================
# FIG 2 : sensibilite et information de Fisher vs frequence
# =====================================================================
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
for d in (0.2, 1, 2, 5):
    s = np.abs(dgamma_dd(d))
    a1.plot(freqs / 1e9, s, lw=1.7, label=f"d = {d} mm")
a1.set_xlabel("Fréquence (GHz)")
a1.set_ylabel(r"$|\partial\Gamma/\partial d|$  (mm$^{-1}$)")
a1.set_title("Sensibilité à l'épaisseur")
a1.grid(alpha=0.3); a1.legend(fontsize=9)

for d in (0.2, 1, 2, 5):
    info = np.abs(dgamma_dd(d)) ** 2
    cum = np.cumsum(info) / np.sum(info)
    a2.plot(freqs / 1e9, 100 * (1 - cum), lw=1.7, label=f"d = {d} mm")
a2.axvline(3.0, color='r', ls='--', lw=1.3,
           label="seuil 3 GHz (antenne 2,3x plus petite)")
a2.set_xlabel("Fréquence (GHz)")
a2.set_ylabel("% de l'information au-dessus de f")
a2.set_title("Information de Fisher cumulée")
a2.grid(alpha=0.3); a2.legend(fontsize=8)
fig.suptitle("L'information sur l'épaisseur est portée par le HAUT de la bande",
             fontsize=12)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_sensibilite.png", dpi=140); plt.close(fig)

frac3 = [100 * np.sum(np.abs(dgamma_dd(d))[freqs >= 3e9] ** 2)
         / np.sum(np.abs(dgamma_dd(d)) ** 2) for d in (0.2, 1, 2, 5)]
print("Part de l'information au-dessus de 3 GHz :")
for d, f in zip((0.2, 1, 2, 5), frac3):
    print(f"   d = {d:4.1f} mm : {f:5.1f} %")

# =====================================================================
# FIG 3 : budget d'erreur 0-5 mm, avec la cible 0,1 mm
# =====================================================================
GRILLE = np.linspace(0.0, 7.0, 1401)
MOD = np.array([gamma(d) for d in GRILLE])
MOD /= np.linalg.norm(MOD, axis=1, keepdims=True)


def estime(mes):
    return GRILLE[np.argmax(np.abs(MOD.conj() @ mes))]


def rms(d_vrais, ph, amp, n_moy=1, err_eps=0.0, n_tir=200):
    out = []
    for d in d_vrais:
        vrai = gamma(d, eps_cart=(CARTILAGE[0] * (1 + err_eps), CARTILAGE[1]))
        e = []
        for _ in range(n_tir):
            acc = np.zeros(NPTS, dtype=complex)
            for _ in range(n_moy):
                acc += vrai * (1 + amp * RNG.standard_normal(NPTS)) * \
                    np.exp(1j * np.radians(ph) * RNG.standard_normal(NPTS))
            e.append(estime(acc / n_moy) - d)
        out.append(np.sqrt(np.mean(np.square(e))))
    return np.array(out)


dd = np.linspace(0.1, 5.0, 22)
fig, ax = plt.subplots(figsize=(9.5, 5.8))
ax.plot(dd, rms(dd, 0.3, 0.0015), 'o-', ms=3.5, lw=1.8,
        label="bruit seul, montage stabilisé (0,3°)")
ax.plot(dd, rms(dd, 0.3, 0.0015, err_eps=0.01), 's-', ms=3.5, lw=1.8,
        label=r"+ $\varepsilon_r$ connue à 1 %")
ax.plot(dd, rms(dd, 0.3, 0.0015, err_eps=0.04), '^-', ms=3.5, lw=1.8,
        label=r"+ $\varepsilon_r$ connue à 4 %")
ax.plot(dd, rms(dd, 0.3, 0.0015, err_eps=0.10), 'v-', ms=3.5, lw=1.8,
        label=r"+ $\varepsilon_r$ connue à 10 %")
ax.plot(dd, rms(dd, 13.0, 0.150), 'x-', ms=4, lw=1.8, color='0.4',
        label="dérive actuelle non corrigée (13°)")
ax.axhline(CIBLE, color='r', ls='--', lw=1.8, label="objectif 0,1 mm")
ax.set_xlabel("Épaisseur réelle de cartilage (mm)")
ax.set_ylabel("Erreur RMS sur l'épaisseur (mm)")
ax.set_yscale('log'); ax.grid(alpha=0.3, which='both')
ax.legend(fontsize=8.5, loc='upper left')
ax.set_title("Budget d'erreur sur 0–5 mm — c'est la permittivité qui décide")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_budget.png", dpi=140); plt.close(fig)

# =====================================================================
# FIG 4 : precision requise sur eps_r pour tenir 0,1 mm
# =====================================================================
dd2 = np.linspace(0.2, 5.0, 60)
fig, ax = plt.subplots(figsize=(8.5, 5))
ax.plot(dd2, 100 * 2 * CIBLE / dd2, lw=2.2, color='tab:red')
ax.fill_between(dd2, 100 * 2 * CIBLE / dd2, 100, alpha=0.12, color='tab:green')
ax.fill_between(dd2, 0, 100 * 2 * CIBLE / dd2, alpha=0.12, color='tab:red')
ax.set_xlabel("Épaisseur de cartilage (mm)")
ax.set_ylabel(r"Précision requise sur $\varepsilon_r$ (%)")
ax.set_title(r"Pour tenir 0,1 mm : $\delta\varepsilon_r/\varepsilon_r "
             r"\leq 2\,\delta d/d$")
ax.set_ylim(0, 60); ax.grid(alpha=0.3)
ax.annotate("zone atteignable", (3.5, 40), color='darkgreen', fontsize=11)
ax.annotate("zone interdite", (1.0, 5), color='darkred', fontsize=11)
for d in (1, 2, 3, 5):
    ax.plot(d, 100 * 2 * CIBLE / d, 'ko', ms=6)
    ax.annotate(f"{100*2*CIBLE/d:.0f} %", (d, 100 * 2 * CIBLE / d),
                textcoords="offset points", xytext=(6, 6), fontsize=9)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_eps_requis.png", dpi=140); plt.close(fig)

# =====================================================================
# FIG 5 : resolution laterale — taille d'antenne et ouverture synthetique
# =====================================================================
R = 0.10                                    # standoff 100 mm
D_ant = np.linspace(0.01, 0.15, 200)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
for f0, lab in ((1.4e9, "1,4 GHz"), (3.0e9, "3 GHz"), (6.3e9, "6,3 GHz")):
    lam = c / f0
    spot = np.maximum(D_ant, lam * R / D_ant)
    a1.plot(D_ant * 1000, spot * 1000, lw=1.8, label=f"tache éclairée, {lab}")
a1.axhline(20, color='r', ls='--', lw=1.5, label="cible ~20 mm (condyle)")
a1.set_xlabel("Taille d'antenne D (mm)")
a1.set_ylabel("Largeur de la tache éclairée (mm)")
a1.set_title(f"Antenne seule, standoff {R*1000:.0f} mm")
a1.set_yscale('log'); a1.grid(alpha=0.3, which='both'); a1.legend(fontsize=8)

L = np.linspace(0.02, 0.30, 200)            # ouverture synthetique balayee
for f0, lab in ((1.4e9, "1,4 GHz"), (3.0e9, "3 GHz"), (6.3e9, "6,3 GHz")):
    lam = c / f0
    res = np.maximum(lam * R / (2 * L), lam / 4)
    a2.plot(L * 1000, res * 1000, lw=1.8, label=f"SAR, {lab}")
a2.axhline(20, color='r', ls='--', lw=1.5, label="cible ~20 mm")
a2.set_xlabel("Étendue balayée par le robot L (mm)")
a2.set_ylabel("Résolution latérale (mm)")
a2.set_title("Avec ouverture synthétique (robot 6 axes)")
a2.set_yscale('log'); a2.grid(alpha=0.3, which='both'); a2.legend(fontsize=8)
fig.suptitle("La taille d'antenne fixe la résolution latérale — "
             "seul le balayage cohérent la rattrape", fontsize=12)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_lateral.png", dpi=140); plt.close(fig)

# =====================================================================
# FIG 6 : effet de volume partiel (variation d'epaisseur sous l'antenne)
# =====================================================================
delta = np.linspace(0, 4, 200)                       # variation d'epaisseur (mm)
fig, ax = plt.subplots(figsize=(8.5, 5))
for f0, lab in ((1.4e9, "1,4 GHz"), (3.0e9, "3 GHz"), (6.3e9, "6,3 GHz")):
    n2 = np.sqrt(CARTILAGE[0])
    beta = 2 * np.pi * f0 * n2 / c
    contraste = np.abs(np.sinc(beta * delta / 1000.0 / np.pi))
    ax.plot(delta, contraste, lw=1.9, label=lab)
ax.axhline(0.5, color='r', ls='--', lw=1.4, label="perte de contraste de 50 %")
ax.set_xlabel("Variation d'épaisseur sous l'empreinte de l'antenne (mm)")
ax.set_ylabel("Contraste de la signature (1 = intact)")
ax.set_title("Volume partiel : au-delà de ~2 mm de variation,\n"
             "le haut de bande se brouille et l'information se perd")
ax.grid(alpha=0.3); ax.legend(fontsize=9)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_volume_partiel.png", dpi=140)
plt.close(fig)

n2 = np.sqrt(CARTILAGE[0])
for f0 in (1.4e9, 3e9, 6.3e9):
    beta = 2 * np.pi * f0 * n2 / c
    print(f"Brouillage a {f0/1e9:.1f} GHz : variation critique "
          f"{np.pi/beta*1000:.2f} mm")

# =====================================================================
# FIG 7 : gain du moyennage spatial (robot = N poses)
# =====================================================================
Ns = np.array([1, 2, 4, 8, 16, 32, 64])
fig, ax = plt.subplots(figsize=(8.5, 5))
for ph, amp, lab in ((0.3, 0.0015, "montage stabilisé (0,3°)"),
                     (13.0, 0.150, "dérive actuelle (13°)")):
    e = [rms(np.array([2.0]), ph, amp, n_moy=int(n), n_tir=150)[0] for n in Ns]
    ax.plot(Ns, e, 'o-', lw=1.9, ms=5, label=lab)
ax.axhline(CIBLE, color='r', ls='--', lw=1.8, label="objectif 0,1 mm")
ax.set_xscale('log', base=2); ax.set_yscale('log')
ax.set_xlabel("Nombre de poses moyennées (robot)")
ax.set_ylabel("Erreur RMS sur l'épaisseur (mm)")
ax.set_title("Le balayage robotisé apporte un gain en $1/\\sqrt{N}$  (d = 2 mm)")
ax.grid(alpha=0.3, which='both'); ax.legend(fontsize=9)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_moyennage.png", dpi=140); plt.close(fig)

print(f"\nFigures ecrites dans {OUT}")
