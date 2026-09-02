"""
Banc de test : la portion 4,4-6,3 GHz du sweep aide-t-elle ou nuit-elle ?

CONTEXTE
    L'ADF4350 du LiteVNA plafonne nativement à 4,4 GHz. Au-delà, l'instrument
    travaille en régime harmonique : on soupçonne une phase plus bruitée et une
    directivité de pont dégradée, precisement dans la portion de bande qui porte
    l'information sur les couches minces.

PROTOCOLE
    Config A : 1,400 - 6,300 GHz, 101 pts  (pas 49,0 MHz)  <- réglage actuel
    Config B : 1,400 - 4,389 GHz,  62 pts  (pas 49,0 MHz)  <- bornée à ~4,4 GHz

    La grille de B est EXACTEMENT celle des 62 premiers points de A : toute
    différence mesurée est donc imputable au comportement de l'instrument, pas à
    un ré-échantillonnage.

    Les blocs sont ALTERNÉS (A,B,A,B) pour qu'une dérive thermique lente pollue
    les deux configs de façon identique. Les premiers sweeps suivant un
    changement de config sont jetés (transitoire de reconfiguration des PLL).

CE QU'ON MESURE (scène immobile, l'instrument se mesure lui-même)
    1. Écart-type de phase par fréquence, sweep à sweep
    2. Écart-type d'amplitude (dB)
    3. Cohérence  gamma = |moyenne vectorielle| / moyenne des modules
       gamma -> 1 : phase stable, le moyennage cohérent fonctionne
       gamma -> 0 : phase erratique, le moyennage vectoriel s'effondre
    4. Gigue du pic dominant en distance (mm) et en amplitude (dB)

IMPORTANT : ne RIEN toucher (antenne, câbles, scène) pendant toute la mesure.
"""

import os
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")           # pas de fenêtre : on écrit des PNG
import matplotlib.pyplot as plt
from skrf.vi.vna.nanovna import NanoVNAv2
import skrf as rf

# ==========================================
# PARAMÈTRES
# ==========================================
PORT_VNA = "ASRL6::INSTR"
c = 3e8

PAS_HZ = 49.0e6                 # pas commun aux deux configs
F_START = 1.4e9
N_A = 101                       # 1,400 -> 6,300 GHz
N_B = 62                        # 1,400 -> 4,389 GHz (= les 62 premiers points de A)

N_BLOCS = 2                     # nombre d'alternances A/B
N_SWEEPS = 12                   # sweeps retenus par bloc et par config
N_JETES = 2                     # sweeps jetés après chaque reconfiguration

FACTEUR_ZOOM = 8                # identique au programme principal
FENETRE_PIC_MM = (150, 1500)    # où chercher le pic dominant (distance VNA brute)

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diag_bande")
os.makedirs(DOSSIER, exist_ok=True)


# ==========================================
# OUTILS D'ANALYSE
# ==========================================
def metriques_stabilite(S):
    """S : (M sweeps, F fréquences) complexe -> stabilité par fréquence."""
    ref = S.mean(axis=0)                              # moyenne vectorielle
    dphi = np.angle(S * np.conj(ref))                 # écart de phase à la moyenne
    phase_std = np.degrees(dphi.std(axis=0))
    mag_db = 20.0 * np.log10(np.abs(S) + 1e-15)
    mag_std = mag_db.std(axis=0)
    coherence = np.abs(S.mean(axis=0)) / (np.abs(S).mean(axis=0) + 1e-15)
    return phase_std, mag_std, coherence


def profil_distance(s, zoom=FACTEUR_ZOOM):
    """Même traitement que le programme principal : Hanning + IFFT zero-paddée."""
    w = np.hanning(len(s))
    n_fft = len(s) * zoom
    return np.abs(np.fft.ifft(s * w, n=n_fft)) * zoom


def axe_mm(freqs, n_points, zoom=FACTEUR_ZOOM):
    bw = freqs[-1] - freqs[0]
    pas_t = (1.0 / bw) / zoom
    return np.arange(n_points) * pas_t * c / 2.0 * 1000.0


def pic_dominant(profil, dist_mm, fenetre=FENETRE_PIC_MM):
    """Position (interpolation parabolique) et amplitude du pic dominant."""
    masque = (dist_mm >= fenetre[0]) & (dist_mm <= fenetre[1])
    idx_valides = np.where(masque)[0]
    if len(idx_valides) < 3:
        return np.nan, np.nan
    i_loc = idx_valides[np.argmax(profil[idx_valides])]
    if i_loc <= 0 or i_loc >= len(profil) - 1:
        return dist_mm[i_loc], profil[i_loc]
    y0, y1, y2 = profil[i_loc - 1], profil[i_loc], profil[i_loc + 1]
    denom = y0 - 2 * y1 + y2
    delta = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-20 else 0.0
    pas = dist_mm[1] - dist_mm[0]
    return dist_mm[i_loc] + delta * pas, y1


def gigue_pic(S, freqs):
    """Dispersion sweep à sweep de la position et de l'amplitude du pic dominant."""
    n_fft = S.shape[1] * FACTEUR_ZOOM
    dist = axe_mm(freqs, n_fft)
    positions, amplitudes = [], []
    for s in S:
        p, a = pic_dominant(profil_distance(s), dist)
        positions.append(p)
        amplitudes.append(a)
    positions = np.array(positions)
    amplitudes = np.array(amplitudes)
    bons = np.isfinite(positions) & np.isfinite(amplitudes) & (amplitudes > 0)
    if bons.sum() < 2:
        return np.nan, np.nan, np.nan
    amp_db = 20.0 * np.log10(amplitudes[bons])
    return positions[bons].mean(), positions[bons].std(), amp_db.std()


# ==========================================
# ACQUISITION
# ==========================================
def configure(vna, n_points, f_stop):
    vna.frequency = rf.Frequency(start=F_START / 1e9, stop=f_stop / 1e9,
                                 npoints=n_points, unit='GHz')


def acquiert(vna, n_sweeps, n_jetes):
    """Renvoie (freqs, S) avec S de forme (n_sweeps, F)."""
    for _ in range(n_jetes):                       # transitoire de reconfiguration
        vna.get_s11_s21()
    lignes, freqs = [], None
    for k in range(n_sweeps):
        s11, _ = vna.get_s11_s21()
        if freqs is None:
            freqs = s11.f.copy()
        lignes.append(s11.s[:, 0, 0].copy())
        print(f"      sweep {k + 1}/{n_sweeps}", end="\r", flush=True)
    print(" " * 30, end="\r")
    return freqs, np.array(lignes)


def main():
    f_stop_a = F_START + (N_A - 1) * PAS_HZ
    f_stop_b = F_START + (N_B - 1) * PAS_HZ

    print("=" * 74)
    print(" Test : la portion 4,4-6,3 GHz aide-t-elle ou nuit-elle ?")
    print("=" * 74)
    print(f" Config A : {F_START/1e9:.3f} - {f_stop_a/1e9:.3f} GHz, {N_A} pts "
          f"(BW {(f_stop_a-F_START)/1e9:.3f} GHz)")
    print(f" Config B : {F_START/1e9:.3f} - {f_stop_b/1e9:.3f} GHz, {N_B} pts "
          f"(BW {(f_stop_b-F_START)/1e9:.3f} GHz)")
    print(f" {N_BLOCS} blocs alternés x {N_SWEEPS} sweeps par config")
    print("\n >>> NE RIEN TOUCHER pendant la mesure (antenne, câbles, scène) <<<\n")

    print(f"Connexion au LiteVNA sur {PORT_VNA}...")
    try:
        vna = NanoVNAv2(PORT_VNA, backend='@py')
        print(f"Connecté : {vna.id}\n")
    except Exception as e:
        print(f"ERREUR : impossible de se connecter ({e})")
        print("Vérifie que le LiteVNA est allumé, branché, et qu'aucun autre")
        print("programme (radar_cartilage_online.py, NanoVNASaver) ne tient le port.")
        sys.exit(1)

    blocs_a, blocs_b = [], []
    freqs_a = freqs_b = None
    t_debut = time.perf_counter()

    try:
        for bloc in range(N_BLOCS):
            print(f"  Bloc {bloc + 1}/{N_BLOCS} - config A (large, 6,3 GHz)")
            configure(vna, N_A, f_stop_a)
            freqs_a, Sa = acquiert(vna, N_SWEEPS, N_JETES)
            blocs_a.append(Sa)

            print(f"  Bloc {bloc + 1}/{N_BLOCS} - config B (bornée, 4,4 GHz)")
            configure(vna, N_B, f_stop_b)
            freqs_b, Sb = acquiert(vna, N_SWEEPS, N_JETES)
            blocs_b.append(Sb)
    finally:
        try:
            vna.close()
        except Exception:
            pass

    print(f"\nAcquisition terminée en {time.perf_counter() - t_debut:.0f} s.\n")

    S_A = np.vstack(blocs_a)
    S_B = np.vstack(blocs_b)

    # Vérification : les grilles coïncident-elles vraiment ?
    ecart_grille = np.max(np.abs(freqs_b - freqs_a[:len(freqs_b)])) if freqs_b is not None else np.inf
    print(f"[grille] A : {freqs_a[0]/1e9:.4f} - {freqs_a[-1]/1e9:.4f} GHz, {len(freqs_a)} pts")
    print(f"[grille] B : {freqs_b[0]/1e9:.4f} - {freqs_b[-1]/1e9:.4f} GHz, {len(freqs_b)} pts")
    print(f"[grille] écart max B vs 62 premiers points de A : {ecart_grille/1e6:.3f} MHz")
    if ecart_grille > 1e6:
        print("         ATTENTION : les grilles ne coïncident pas, comparaison")
        print("         point à point invalide (le VNA a quantifié autrement).")
    print()

    # --- Stabilité par fréquence ---
    ph_a, mag_a, coh_a = metriques_stabilite(S_A)
    ph_b, mag_b, coh_b = metriques_stabilite(S_B)

    n_bas = len(freqs_b)
    bas = slice(0, n_bas)            # 1,4 - 4,4 GHz dans la config A
    haut = slice(n_bas, len(freqs_a))  # 4,4 - 6,3 GHz dans la config A

    def resume(nom, ph, mag, coh):
        print(f"  {nom:<34} {np.median(ph):8.2f}  {np.median(mag):8.3f}  {np.median(coh):8.4f}")

    print("-" * 74)
    print("  STABILITÉ SWEEP À SWEEP (médianes)")
    print(f"  {'':<34} {'phase':>8}  {'ampl.':>8}  {'cohér.':>8}")
    print(f"  {'':<34} {'deg':>8}  {'dB':>8}  {'gamma':>8}")
    print("-" * 74)
    resume("A - bas de bande  1,4-4,4 GHz", ph_a[bas], mag_a[bas], coh_a[bas])
    resume("A - haut de bande 4,4-6,3 GHz", ph_a[haut], mag_a[haut], coh_a[haut])
    resume("B - sweep borné   1,4-4,4 GHz", ph_b, mag_b, coh_b)
    print("-" * 74)

    r_haut_bas = np.median(ph_a[haut]) / max(np.median(ph_a[bas]), 1e-9)
    r_b_a = np.median(ph_b) / max(np.median(ph_a[bas]), 1e-9)
    print(f"\n  Bruit de phase haut/bas (dans la config A)  : x{r_haut_bas:.2f}")
    print(f"  Bruit de phase B / A sur le MÊME bas de bande : x{r_b_a:.2f}")

    # --- Gigue du pic dominant ---
    S_A_tronq = S_A[:, :n_bas]        # A tronquée NUMÉRIQUEMENT (mêmes données)
    print("\n" + "-" * 74)
    print("  GIGUE DU PIC DOMINANT (réflexion fixe de l'antenne)")
    print(f"  {'':<34} {'pos.':>9}  {'gigue':>9}  {'gigue':>9}")
    print(f"  {'':<34} {'mm':>9}  {'mm':>9}  {'dB':>9}")
    print("-" * 74)
    for nom, S, fr in (("A - large 1,4-6,3 GHz", S_A, freqs_a),
                       ("A - tronquée a posteriori", S_A_tronq, freqs_a[:n_bas]),
                       ("B - sweep borné matériel", S_B, freqs_b)):
        pos, gig_mm, gig_db = gigue_pic(S, fr)
        print(f"  {nom:<34} {pos:9.2f}  {gig_mm:9.3f}  {gig_db:9.3f}")
    print("-" * 74)

    # --- Sauvegardes ---
    np.savez_compressed(os.path.join(DOSSIER, "donnees_brutes.npz"),
                        freqs_a=freqs_a, S_A=S_A, freqs_b=freqs_b, S_B=S_B)

    with open(os.path.join(DOSSIER, "metriques.csv"), "w", encoding="utf-8") as f:
        f.write("config,freq_hz,phase_std_deg,mag_std_db,coherence\n")
        for i, fr in enumerate(freqs_a):
            f.write(f"A,{fr:.0f},{ph_a[i]:.4f},{mag_a[i]:.4f},{coh_a[i]:.6f}\n")
        for i, fr in enumerate(freqs_b):
            f.write(f"B,{fr:.0f},{ph_b[i]:.4f},{mag_b[i]:.4f},{coh_b[i]:.6f}\n")

    # --- Figures ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fa, fb = freqs_a / 1e9, freqs_b / 1e9
    limite = f_stop_b / 1e9

    for ax, (ya, yb, titre, ylab) in zip(
            axes.flat[:3],
            [(ph_a, ph_b, "Écart-type de phase sweep à sweep", "deg"),
             (mag_a, mag_b, "Écart-type d'amplitude", "dB"),
             (coh_a, coh_b, "Cohérence (1 = phase parfaitement stable)", "gamma")]):
        ax.plot(fa, ya, label="A - sweep large (6,3 GHz)", lw=1.4)
        ax.plot(fb, yb, label="B - sweep borné (4,4 GHz)", lw=1.4, ls='--')
        ax.axvline(limite, color='r', ls=':', lw=1.2, label="limite ADF4350 (4,4 GHz)")
        ax.axvspan(limite, fa[-1], color='r', alpha=0.06)
        ax.set_title(titre)
        ax.set_xlabel("Fréquence (GHz)")
        ax.set_ylabel(ylab)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

    ax = axes.flat[3]
    for nom, S, fr, style in (("A - large 1,4-6,3 GHz", S_A, freqs_a, '-'),
                              ("A - tronquée a posteriori", S_A_tronq, freqs_a[:n_bas], '--'),
                              ("B - sweep borné matériel", S_B, freqs_b, ':')):
        moy = S.mean(axis=0)
        p = profil_distance(moy)
        d = axe_mm(fr, len(p))
        m = d <= 1500
        ax.plot(d[m], 20 * np.log10(p[m] + 1e-15), style, lw=1.3, label=nom)
    ax.set_title("Profil en distance (moyenne vectorielle)")
    ax.set_xlabel("Distance VNA brute (mm)")
    ax.set_ylabel("Amplitude (dB)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    fig.suptitle("LiteVNA - la portion 4,4-6,3 GHz aide-t-elle ou nuit-elle ?", fontsize=13)
    fig.tight_layout()
    chemin = os.path.join(DOSSIER, "comparaison_bande.png")
    fig.savefig(chemin, dpi=130)
    print(f"\nRésultats écrits dans : {DOSSIER}")
    print("  comparaison_bande.png / metriques.csv / donnees_brutes.npz")


if __name__ == "__main__":
    main()
