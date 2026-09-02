"""
Peut-on mesurer 1 a 3 mm de cartilage avec la bande dont on dispose deja ?

IDEE
    La limite de 30 mm (Rayleigh) s'applique a la separation de deux pics dans
    un profil obtenu par IFFT. Elle ne s'applique PAS aux methodes parametriques.

    S11(f) est exactement une somme d'exponentielles complexes :
        S11(f) = somme_k  a_k * exp(-j*4*pi*f*d_k/c)
    C'est le modele pour lequel ESPRIT / matrix-pencil sont concus. Leur pouvoir
    separateur n'est pas fixe par la bande passante mais par le RAPPORT S/B.

    Comme on a MESURE le rapport S/B du LiteVNA (0,3 deg sweep a sweep,
    2,7 deg de plancher run a run), on peut repondre quantitativement.

RAPPEL D'ECHELLE
    Une couche d'epaisseur d et de permittivite eps_r produit un retard
    equivalent, sur un axe gradue en air, de  d * sqrt(eps_r).
    Cartilage eps_r = 40 -> 3 mm de cartilage = 19 mm apparents.
    A comparer aux 53 mm de resolution reelle de la chaine actuelle.
"""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

c = 3e8
FREQ_START, FREQ_STOP, NPTS = 1.4e9, 6.3e9, 101
BW = FREQ_STOP - FREQ_START
DELTA_F = (FREQ_STOP - FREQ_START) / (NPTS - 1)
EPS_CARTILAGE = 40.0
N_TIRAGES = 300
RNG = np.random.default_rng(2024)

NIVEAUX = [
    ("parfait (reference)",              0.0,  0.000),
    ("bruit sweep-a-sweep mesure",       0.3,  0.0015),
    ("plancher run-a-run mesure",        2.7,  0.070),
]

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diag_bande")
os.makedirs(DOSSIER, exist_ok=True)
freqs = np.linspace(FREQ_START, FREQ_STOP, NPTS)


def signal(d_mm_apparent, a2, ph_deg, amp_rel, d1_mm=100.0):
    """Deux echos : surface (fort) et fond de couche (faible)."""
    d1 = d1_mm / 1000.0
    d2 = (d1_mm + d_mm_apparent) / 1000.0
    s = (np.exp(-2j * np.pi * freqs * 2 * d1 / c) +
         a2 * np.exp(-2j * np.pi * freqs * 2 * d2 / c))
    if ph_deg or amp_rel:
        s = s * (1 + amp_rel * RNG.standard_normal(NPTS)) * \
            np.exp(1j * np.radians(ph_deg) * RNG.standard_normal(NPTS))
    return s


def esprit(s, K=2):
    """Estime les retards par ESPRIT (sous-espace signal). Renvoie les distances mm."""
    N = len(s)
    L = N // 3
    # Matrice de Hankel
    Y = np.array([s[i:i + L] for i in range(N - L + 1)])
    _, _, Vh = np.linalg.svd(Y, full_matrices=False)
    S = Vh[:K].conj().T                       # sous-espace signal (L x K)
    S1, S2 = S[:-1, :], S[1:, :]
    psi = np.linalg.pinv(S1) @ S2
    z = np.linalg.eigvals(psi)
    ang = np.angle(z)
    ang = np.where(ang > 0, ang - 2 * np.pi, ang)   # retards positifs
    return np.sort(-ang * c / (4 * np.pi * DELTA_F) * 1000)


def classique(s):
    """Methode actuelle : Hanning + IFFT zero-paddee + find_peaks."""
    zoom = 8
    p = np.abs(np.fft.ifft(s * np.hanning(NPTS), n=NPTS * zoom)) * zoom
    pas = (1.0 / BW) / zoom * c / 2 * 1000
    d = np.arange(len(p)) * pas
    m = d <= 400
    d, p = d[m], p[m]
    pics, _ = find_peaks(p, prominence=0.05 * p.max())
    if len(pics) < 2:
        return np.nan
    deux = pics[np.argsort(p[pics])[-2:]]
    return abs(d[deux].max() - d[deux].min())


print("=" * 78)
print("  MESURER 1 A 3 mm DE CARTILAGE AVEC B = 4,9 GHz ?")
print("=" * 78)
print(f"  Pas frequentiel        : {DELTA_F/1e6:.1f} MHz")
print(f"  Resolution de Rayleigh : {c/(2*BW)*1000:.1f} mm apparents")
print(f"  Resolution de la chaine actuelle (Hanning) : ~53 mm apparents")
print(f"\n  Permittivite du cartilage : {EPS_CARTILAGE}"
      f"  ->  facteur d'echelle sqrt = {np.sqrt(EPS_CARTILAGE):.2f}")

print("\n" + "-" * 78)
print("  ERREUR RMS SUR L'EPAISSEUR ESTIMEE  (2e echo a -10 dB, 300 tirages)")
print("-" * 78)
print(f"  {'epaisseur':>10} {'apparent':>10}   {'niveau de bruit':<30} "
      f"{'ESPRIT':>10} {'classique':>11}")

resultats = {}
for d_vrai in (3.0, 2.0, 1.0):
    app = d_vrai * np.sqrt(EPS_CARTILAGE)
    for nom, ph, amp in NIVEAUX:
        err_e, err_c = [], []
        for _ in range(N_TIRAGES):
            s = signal(app, 0.3, ph, amp)
            try:
                dd = esprit(s, K=2)
                err_e.append((dd[1] - dd[0]) / np.sqrt(EPS_CARTILAGE) - d_vrai)
            except np.linalg.LinAlgError:
                pass
            sep = classique(s)
            if np.isfinite(sep):
                err_c.append(sep / np.sqrt(EPS_CARTILAGE) - d_vrai)
        rms_e = np.sqrt(np.mean(np.square(err_e))) if err_e else np.nan
        rms_c = np.sqrt(np.mean(np.square(err_c))) if err_c else np.nan
        resultats[(d_vrai, nom)] = rms_e
        tag = f"{d_vrai:8.1f} mm {app:8.1f} mm" if nom == NIVEAUX[0][0] else " " * 20
        c_txt = f"{rms_c:8.2f} mm" if np.isfinite(rms_c) else "   echec"
        print(f"  {tag}   {nom:<30} {rms_e:7.3f} mm {c_txt:>11}")
    print()

print("-" * 78)
print("  LECTURE : 'echec' = la methode actuelle ne detecte meme pas deux pics.")
print("-" * 78)

print("\n  Avec le bruit reellement mesure sur ton montage :")
for d_vrai in (3.0, 2.0, 1.0):
    r = resultats[(d_vrai, "plancher run-a-run mesure")]
    verdict = "OK" if r < 0.15 * d_vrai else ("limite" if r < 0.4 * d_vrai else "hors de portee")
    print(f"    {d_vrai:.0f} mm  ->  erreur RMS {r:.2f} mm  ({r/d_vrai*100:.0f} %)   {verdict}")

# ---------- Figure : erreur vs epaisseur ----------
eps_test = np.arange(0.5, 6.1, 0.25)
fig, ax = plt.subplots(figsize=(9, 5.5))
for (nom, ph, amp), style in zip(NIVEAUX, ['-', '-', '-']):
    courbe = []
    for d_vrai in eps_test:
        app = d_vrai * np.sqrt(EPS_CARTILAGE)
        err = []
        for _ in range(120):
            try:
                dd = esprit(signal(app, 0.3, ph, amp), K=2)
                err.append((dd[1] - dd[0]) / np.sqrt(EPS_CARTILAGE) - d_vrai)
            except np.linalg.LinAlgError:
                pass
        courbe.append(np.sqrt(np.mean(np.square(err))) if err else np.nan)
    ax.plot(eps_test, courbe, style, lw=1.8, label=f"ESPRIT - {nom}")

ax.plot(eps_test, 0.15 * eps_test, 'k--', lw=1.2, label="seuil 15 % d'erreur")
ax.axvspan(1, 3, color='g', alpha=0.10, label="cartilage vise (1-3 mm)")
ax.set_xlabel("Epaisseur reelle de cartilage (mm)")
ax.set_ylabel("Erreur RMS sur l'epaisseur (mm)")
ax.set_title("Superresolution parametrique : erreur vs epaisseur\n"
             f"B = {BW/1e9:.1f} GHz, eps_r = {EPS_CARTILAGE:.0f}, "
             "bruit mesure sur le LiteVNA")
ax.set_yscale('log')
ax.grid(alpha=0.3, which='both')
ax.legend(fontsize=8)
fig.tight_layout()
chemin = os.path.join(DOSSIER, "superresolution.png")
fig.savefig(chemin, dpi=130)
print(f"\nFigure : {chemin}")
