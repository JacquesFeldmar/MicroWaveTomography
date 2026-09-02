"""
D'ou vient la "limite de resolution de 30 mm", et que vaut-elle VRAIMENT ?

La formule c/(2B) est le critere de Rayleigh : une regle de l'art, pas un mur.
Avec des donnees parfaites on fait mieux (superresolution) ; avec du bruit on
retombe dessus, voire en dessous. Le seul chiffre utile est donc celui obtenu
avec le bruit REEL du montage.

On simule deux echos, on les passe dans la chaine de traitement EXACTE du
programme principal (Hanning + IFFT zero-paddee x8), on injecte les niveaux de
bruit mesures sur le LiteVNA (script test_bande_phase.py), et on mesure :
   - a partir de quelle separation deux pics sont detectes de facon fiable
   - l'erreur RMS sur l'epaisseur estimee, qui est la vraie grandeur d'interet
"""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

c = 3e8
FREQ_START, FREQ_STOP, NPTS = 1.4e9, 6.3e9, 101   # reglages du programme principal
FACTEUR_ZOOM = 8
BW = FREQ_STOP - FREQ_START
N_TIRAGES = 200
RNG = np.random.default_rng(12345)

# Niveaux de bruit MESURES sur le montage (cf. test_bande_phase.py, 3 runs)
NIVEAUX = [
    ("donnees parfaites (theorique)",      0.0,  0.000),
    ("bruit sweep-a-sweep mesure",         0.3,  0.0015),   # 0,3 deg / 0,013 dB
    ("plancher run-a-run mesure",          2.7,  0.070),    # 2,7 deg / 7 %
]

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diag_bande")
os.makedirs(DOSSIER, exist_ok=True)
freqs = np.linspace(FREQ_START, FREQ_STOP, NPTS)
PAS_MM = (1.0 / BW) / FACTEUR_ZOOM * c / 2 * 1000


def mesure(d1_mm, sep_mm, a2, ph_deg, amp_rel):
    """Un tirage : deux echos + bruit -> profil en distance."""
    d1, d2 = d1_mm / 1000.0, (d1_mm + sep_mm) / 1000.0
    s = (np.exp(-2j * np.pi * freqs * 2 * d1 / c) +
         a2 * np.exp(-2j * np.pi * freqs * 2 * d2 / c))
    if ph_deg or amp_rel:
        s = s * (1 + amp_rel * RNG.standard_normal(NPTS)) * \
            np.exp(1j * np.radians(ph_deg) * RNG.standard_normal(NPTS))
    p = np.abs(np.fft.ifft(s * np.hanning(NPTS), n=NPTS * FACTEUR_ZOOM)) * FACTEUR_ZOOM
    return np.arange(len(p)) * PAS_MM, p


def essai(sep_mm, a2, ph, amp):
    """Taux de detection de 2 pics + erreur RMS sur la separation estimee."""
    ok, erreurs = 0, []
    for _ in range(N_TIRAGES):
        d, p = mesure(100.0, sep_mm, a2, ph, amp)
        m = d <= 400
        d, p = d[m], p[m]
        pics, _ = find_peaks(p, prominence=0.05 * p.max())
        if len(pics) >= 2:
            ok += 1
            deux = pics[np.argsort(p[pics])[-2:]]
            erreurs.append(abs(d[deux].max() - d[deux].min()) - sep_mm)
    rms = np.sqrt(np.mean(np.square(erreurs))) if erreurs else np.nan
    return ok / N_TIRAGES, rms


def seuil(a2, ph, amp, taux_min=0.90, err_max=0.25):
    """Plus petite separation detectee de facon fiable ET mesuree justement."""
    for sep in np.arange(4, 160, 1.0):
        taux, rms = essai(sep, a2, ph, amp)
        if taux >= taux_min and rms <= err_max * sep:
            return sep
    return np.nan


print("=" * 74)
print("  D'OU VIENT LA LIMITE DE 30 mm ?")
print("=" * 74)
print(f"  Bande balayee    B = {BW/1e9:.2f} GHz")
print(f"  Critere de Rayleigh   c/(2B) = {c/(2*BW)*1000:.1f} mm")
print(f"  Pas d'affichage apres zero-padding x{FACTEUR_ZOOM} : {PAS_MM:.2f} mm")
print("     -> ce pas n'est PAS la resolution : c'est de l'interpolation pure.")

print("\n" + "-" * 74)
print("  SEUIL REEL SELON LE BRUIT  (2 pics dans >90% des tirages,")
print("  ET epaisseur juste a mieux que 25%)")
print("-" * 74)
print(f"  {'niveau de bruit':<34} {'echos egaux':>13} {'2e echo -10 dB':>16}")
resultats = {}
for nom, ph, amp in NIVEAUX:
    s_egal = seuil(1.0, ph, amp)
    s_faible = seuil(0.3, ph, amp)
    resultats[nom] = (s_egal, s_faible)
    print(f"  {nom:<34} {s_egal:10.0f} mm {s_faible:13.0f} mm")

s_reel = resultats["plancher run-a-run mesure"][1]
print("\n  Le chiffre qui te concerne est celui d'en bas a droite :")
print(f"  echo de fond affaibli + bruit reel  ->  {s_reel:.0f} mm dans l'air.")

print("\n" + "-" * 74)
print("  TRADUIT DANS LA MATIERE  (divise par racine de eps_r)")
print("-" * 74)
print(f"  {'materiau':<20} {'eps_r':>6} {'Rayleigh':>10} {'cas reel':>10}")
for nom, er in (("Air", 1), ("Plexiglas / livre", 2.5), ("Verre", 6),
                ("Cartilage", 40), ("Gelatine", 45), ("Eau", 78)):
    print(f"  {nom:<20} {er:6.1f} {c/(2*BW)*1000/np.sqrt(er):7.1f} mm"
          f" {s_reel/np.sqrt(er):7.1f} mm")

print("\n" + "-" * 74)
print("  BANDE NECESSAIRE POUR RESOUDRE UN CARTILAGE (eps_r = 40)")
print("-" * 74)
for ep in (3.0, 2.0, 1.0):
    b_th = c / (2 * ep / 1000 * np.sqrt(40)) / 1e9
    print(f"  {ep:4.1f} mm  ->  {b_th:6.1f} GHz (critere de Rayleigh),"
          f" {b_th * s_reel / (c/(2*BW)*1000):6.1f} GHz dans les conditions reelles")
print(f"\n  Tu disposes de {BW/1e9:.1f} GHz.")

# ---------- Figure ----------
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for ax, sep in zip(axes.flat, [20, 30, 40, 55, 75, 110]):
    for (nom, ph, amp), style in zip(NIVEAUX, ['-', '--', ':']):
        d, p = mesure(100.0, sep, 0.3, ph, amp)
        m = d <= 320
        ax.plot(d[m], p[m], style, lw=1.4, label=nom)
    ax.axvline(100, color='g', ls=':', lw=1)
    ax.axvline(100 + sep, color='g', ls=':', lw=1)
    ax.set_title(f"Deux echos separes de {sep} mm (2e a -10 dB)")
    ax.set_xlabel("Distance (mm)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)

fig.suptitle(f"Resolution : B = {BW/1e9:.1f} GHz -> Rayleigh {c/(2*BW)*1000:.0f} mm, "
             f"reel {s_reel:.0f} mm (traits verts = vraies positions)", fontsize=13)
fig.tight_layout()
chemin = os.path.join(DOSSIER, "demo_resolution.png")
fig.savefig(chemin, dpi=130)
print(f"\nFigure : {chemin}")
