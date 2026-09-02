"""
Quelle erreur sur l'epaisseur d'un cartilage de 0 a 3 mm, SANS contact ?

MODELE PHYSIQUE (et non plus deux echos ponctuels)
    Onde plane en incidence normale sur un empilement air / cartilage / substrat.
    Coefficient de reflexion exact, reflexions internes multiples incluses :

        G(f) = (r12 + r23*exp(-2j*beta2*d)) / (1 + r12*r23*exp(-2j*beta2*d))

    avec beta2 = 2*pi*f*n2/c et n2 = sqrt(eps_r - j*sigma/(w*eps0)) : le
    cartilage est DISPERSIF et ABSORBANT, ce que le modele a deux echos ignorait.

ESTIMATEUR
    Filtre adapté sur l'epaisseur : pour chaque d candidat on projette la mesure
    sur le modele en laissant libre un facteur complexe K (gain et phase residuels
    apres tare/calibration), et on retient le d qui maximise la correlation.
    C'est l'estimateur du maximum de vraisemblance a K inconnu.

BRUIT
    Les deux niveaux MESURES sur le LiteVNA (cf. test_bande_phase.py, 3 runs).
"""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

c = 3e8
EPS0 = 8.854e-12
FREQ_START, FREQ_STOP, NPTS = 1.4e9, 6.3e9, 101
freqs = np.linspace(FREQ_START, FREQ_STOP, NPTS)
w = 2 * np.pi * freqs

# --- Proprietes dielectriques (ordres de grandeur 1-6 GHz) ---
CARTILAGE = (40.0, 1.7)     # (eps_r', sigma S/m)
OS        = (12.0, 0.3)
N_TIRAGES = 300
RNG = np.random.default_rng(7)

NIVEAUX = [
    ("bruit court terme (montage rigide + re-tare rapide)", 0.3, 0.0015),
    ("plancher actuel (derive run a run)",                  2.7, 0.070),
]

GRILLE_D = np.linspace(0.0, 6.0, 1201) / 1000.0     # candidats, en metres
DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diag_bande")
os.makedirs(DOSSIER, exist_ok=True)


def indice(eps_r, sigma):
    """Indice complexe n = sqrt(eps_r - j*sigma/(w*eps0))."""
    return np.sqrt(eps_r - 1j * sigma / (w * EPS0))


def gamma(d, eps_cart, substrat):
    """Reflexion d'une couche d'epaisseur d sur un substrat."""
    n1 = np.ones_like(freqs, dtype=complex)
    n2 = indice(*eps_cart)
    r12 = (n1 - n2) / (n1 + n2)
    if substrat == "metal":
        r23 = -np.ones_like(freqs, dtype=complex)
    else:
        n3 = indice(*substrat)
        r23 = (n2 - n3) / (n2 + n3)
    ph = np.exp(-2j * w / c * n2 * d)
    return (r12 + r23 * ph) / (1 + r12 * r23 * ph)


def modeles(eps_cart, substrat):
    """Matrice (n_d x n_freq) des modeles normalises, pour le filtre adapte."""
    M = np.array([gamma(d, eps_cart, substrat) for d in GRILLE_D])
    M /= np.linalg.norm(M, axis=1, keepdims=True)
    return M


def estime(mesure, M):
    """d qui maximise |<modele, mesure>| (K complexe libre)."""
    return GRILLE_D[np.argmax(np.abs(M.conj() @ mesure))] * 1000.0


def campagne(d_vrais, ph, amp, substrat, err_eps=0.0):
    """Erreur RMS (mm) pour chaque epaisseur vraie."""
    M = modeles(CARTILAGE, substrat)          # modele utilise par l'estimateur
    out = []
    for d in d_vrais:
        eps_reel = (CARTILAGE[0] * (1 + err_eps), CARTILAGE[1])
        vrai = gamma(d / 1000.0, eps_reel, substrat)
        err = []
        for _ in range(N_TIRAGES):
            s = vrai * (1 + amp * RNG.standard_normal(NPTS)) * \
                np.exp(1j * np.radians(ph) * RNG.standard_normal(NPTS))
            err.append(estime(s, M) - d)
        out.append(np.sqrt(np.mean(np.square(err))))
    return np.array(out)


print("=" * 78)
print("  ERREUR SUR L'EPAISSEUR D'UN CARTILAGE DE 0 A 3 mm, SANS CONTACT")
print("=" * 78)

n2 = indice(*CARTILAGE)
r12 = np.abs(((1 - n2) / (1 + n2)).mean())
n3 = indice(*OS)
r23 = np.abs(((n2 - n3) / (n2 + n3)).mean())
ecart_db = 20 * np.log10((1 - r12 ** 2) * r23 / r12)
print(f"  Reflexion air/cartilage   |r12| = {r12:.3f}"
      f"  ({100*r12**2:.0f} % de la puissance)")
print(f"  Reflexion cartilage/os    |r23| = {r23:.3f}")
print(f"  Echo de fond par rapport a l'echo de surface : {ecart_db:.1f} dB")
alpha = (w / c * n2.imag).mean()
print(f"  Attenuation aller-retour dans 3 mm : "
      f"{2 * alpha * 0.003 * 8.686:.1f} dB")

d_test = np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0])

print("\n" + "-" * 78)
print("  ERREUR RMS (mm) — cartilage sur OS (cas reel)")
print("-" * 78)
print(f"  {'epaisseur vraie':<22}" + "".join(f"{d:7.2f}" for d in d_test))
res = {}
for nom, ph, amp in NIVEAUX:
    e = campagne(d_test, ph, amp, OS)
    res[nom] = e
    print(f"  {nom[:20]:<22}" + "".join(f"{v:7.3f}" for v in e))

print("\n" + "-" * 78)
print("  ERREUR RMS (mm) — meme couche sur PLAQUE METAL (fantome de labo)")
print("-" * 78)
print(f"  {'epaisseur vraie':<22}" + "".join(f"{d:7.2f}" for d in d_test))
for nom, ph, amp in NIVEAUX:
    e = campagne(d_test, ph, amp, "metal")
    print(f"  {nom[:20]:<22}" + "".join(f"{v:7.3f}" for v in e))

print("\n" + "-" * 78)
print("  COUT D'UNE ERREUR DE 10 % SUR LA PERMITTIVITE (sur os, bruit court terme)")
print("-" * 78)
e0 = campagne(d_test, 0.3, 0.0015, OS, err_eps=0.0)
e10 = campagne(d_test, 0.3, 0.0015, OS, err_eps=0.10)
print(f"  {'epaisseur vraie':<22}" + "".join(f"{d:7.2f}" for d in d_test))
print(f"  {'eps_r exacte':<22}" + "".join(f"{v:7.3f}" for v in e0))
print(f"  {'eps_r fausse de 10%':<22}" + "".join(f"{v:7.3f}" for v in e10))

# ---------- Figure ----------
d_fin = np.linspace(0.1, 3.5, 24)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
for (nom, ph, amp), col in zip(NIVEAUX, ['tab:green', 'tab:red']):
    ax1.plot(d_fin, campagne(d_fin, ph, amp, OS), 'o-', color=col, ms=3,
             lw=1.6, label=nom)
    ax2.plot(d_fin, campagne(d_fin, ph, amp, "metal"), 'o-', color=col, ms=3,
             lw=1.6, label=nom)
for ax, titre in ((ax1, "Cartilage sur OS (cas reel)"),
                  (ax2, "Cartilage sur METAL (fantome)")):
    ax.plot(d_fin, 0.15 * d_fin, 'k--', lw=1.2, label="seuil 15 % d'erreur")
    ax.axhline(0.3, color='gray', ls=':', lw=1.2, label="0,3 mm absolu")
    ax.set_xlabel("Epaisseur vraie (mm)")
    ax.set_ylabel("Erreur RMS (mm)")
    ax.set_title(titre)
    ax.set_yscale('log')
    ax.grid(alpha=0.3, which='both')
    ax.legend(fontsize=8)
fig.suptitle("Erreur d'inversion sur modele stratifie — B = 4,9 GHz, sans contact",
             fontsize=13)
fig.tight_layout()
chemin = os.path.join(DOSSIER, "erreur_epaisseur.png")
fig.savefig(chemin, dpi=130)
print(f"\nFigure : {chemin}")
