"""
QUALIFICATION 1 — Stabilite du centre de phase de l'antenne.

POURQUOI
    La signature d'une couche mince est un terme de phase LINEAIRE en frequence
    (cf. cours_theorie.tex, eq. couche mince) :
            arg(Gamma) contient  2*beta2*d = 4*pi*f*sqrt(eps_r)*d / c
    Une antenne dont le centre de phase se deplace avec la frequence produit,
    elle aussi, une phase variant avec f. LES DEUX SONT DEGENERES : l'antenne
    peut donc se faire passer pour du cartilage.

    Critere : une epaisseur de 0,1 mm de cartilage (eps_r = 40) correspond a un
    trajet apparent de 0,1 * sqrt(40) = 0,63 mm. Le residu dispersif de l'antenne
    doit rester tres inferieur a cela.

PRINCIPE  (ce n'est PAS un simple controle de pente)
    Une plaque metallique est un reflecteur parfait connu : Gamma = -1, a une
    distance D mesuree au reglet. Donc

            S11_mesure(f) = H(f) * (-1) * exp(-j*4*pi*f*D/c)

    En retirant le trajet d'air connu, on obtient DIRECTEMENT la fonction de
    transfert complexe H(f) du systeme (cable + antenne). Son residu de phase,
    apres soustraction de la partie lineaire (= plan de reference constant,
    inoffensif car il se simplifie entre reference et mesure), est la dispersion
    reelle. On la convertit en epaisseur de cartilage equivalente.

    Plusieurs distances servent a separer ce qui vient de l'ANTENNE (identique a
    toutes les distances) de ce qui vient du MONTAGE ou des trajets multiples
    (variable). Elles valident aussi l'echelle des distances.

UTILISATION
    python qualif_centre_phase.py --nom taoglas --start 3.0 --stop 6.3
    python qualif_centre_phase.py --nom antenne_actuelle
"""

import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from skrf.vi.vna.nanovna import NanoVNAv2
import skrf as rf

c = 3e8
EPS_CARTILAGE = 40.0
CIBLE_MM = 0.1                 # precision d'epaisseur visee
PORT_VNA = "ASRL6::INSTR"


def acquiert(vna, n_moy, n_jetes=2):
    """Moyenne VECTORIELLE de n_moy balayages (le bruit decorrele s'efface)."""
    for _ in range(n_jetes):
        vna.get_s11_s21()
    acc, freqs = None, None
    for k in range(n_moy):
        s11, _ = vna.get_s11_s21()
        if freqs is None:
            freqs = s11.f.copy()
            acc = np.zeros(len(freqs), dtype=complex)
        acc += s11.s[:, 0, 0]
        print(f"      balayage {k + 1}/{n_moy}", end="\r", flush=True)
    print(" " * 32, end="\r")
    return freqs, acc / n_moy


def pic_principal(s, freqs, zoom=8):
    """Distance apparente du pic dominant (interpolation parabolique)."""
    w = np.blackman(len(s))
    n_fft = len(s) * zoom
    p = np.abs(np.fft.ifft(s * w, n=n_fft))
    # ATTENTION : le pas frequentiel vaut BW/(N-1), pas BW/N. Utiliser
    # 1/BW comme span temporel introduit une erreur d'echelle de N/(N-1)
    # (1 % a 101 points). C'est le bug present dans radar_cartilage_online.py.
    df = (freqs[-1] - freqs[0]) / (len(s) - 1)
    pas = 1.0 / (n_fft * df) * c / 2 * 1000
    d = np.arange(len(p)) * pas
    demi = len(p) // 2
    i = int(np.argmax(p[:demi]))
    if 0 < i < demi - 1:
        y0, y1, y2 = p[i - 1], p[i], p[i + 1]
        den = y0 - 2 * y1 + y2
        delta = 0.5 * (y0 - y2) / den if abs(den) > 1e-20 else 0.0
    else:
        delta = 0.0
    return d[i] + delta * pas


def residu_dispersif(freqs, s11, D_mm):
    """
    Retire le trajet d'air connu et la partie lineaire, puis convertit le
    residu de phase en epaisseur de cartilage equivalente (mm).
    """
    D = D_mm / 1000.0
    # Phase mesuree + trajet d'air retire -> phase propre au systeme
    psi = np.unwrap(np.angle(s11)) + 4 * np.pi * freqs * D / c
    # La partie affine est un plan de reference constant : inoffensive
    coeffs = np.polyfit(freqs, psi, 1)
    residu = psi - np.polyval(coeffs, freqs)
    # Epaisseur de cartilage produisant la meme phase : d = phi*c/(4*pi*f*sqrt(eps))
    d_eq_mm = residu * c / (4 * np.pi * freqs * np.sqrt(EPS_CARTILAGE)) * 1000
    # Longueur electrique moyenne (informative)
    longueur_mm = -coeffs[0] * c / (4 * np.pi) * 1000
    return residu, d_eq_mm, longueur_mm


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nom", required=True, help="nom de l'antenne testee")
    ap.add_argument("--start", type=float, default=1.4, help="GHz")
    ap.add_argument("--stop", type=float, default=6.3, help="GHz")
    ap.add_argument("--points", type=int, default=201)
    ap.add_argument("--moy", type=int, default=16, help="balayages moyennes")
    ap.add_argument("--distances", type=float, nargs="+",
                    default=[50, 75, 100, 125],
                    help="distances plaque metal (mm), mesurees au reglet")
    args = ap.parse_args()

    dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "qualification")
    os.makedirs(dossier, exist_ok=True)

    print("=" * 76)
    print(f"  QUALIFICATION 1 — centre de phase : {args.nom}")
    print("=" * 76)
    print(f"  Bande {args.start}-{args.stop} GHz, {args.points} points, "
          f"{args.moy} balayages moyennes par position")
    print(f"  Critere : residu << {CIBLE_MM} mm d'epaisseur de cartilage "
          f"equivalente\n")
    print("  MONTAGE : plaque metallique PLANE, perpendiculaire a l'axe de")
    print("  l'antenne, plus large que l'antenne. Distances mesurees au reglet")
    print("  depuis la FACE AVANT de l'antenne. Rien d'autre a moins d'un metre.\n")

    try:
        vna = NanoVNAv2(PORT_VNA, backend='@py')
        vna.frequency = rf.Frequency(start=args.start, stop=args.stop,
                                     npoints=args.points, unit='GHz')
        print(f"  LiteVNA connecte ({vna.id}).\n")
    except Exception as e:
        print(f"  ERREUR de connexion : {e}")
        sys.exit(1)

    mesures, freqs = {}, None
    try:
        for D in args.distances:
            print(f"  >>> Place la plaque a {D:.0f} mm, puis Entree "
                  f"(ou 's' pour sauter) : ", end="")
            if input().strip().lower().startswith('s'):
                continue
            freqs, s = acquiert(vna, args.moy)
            mesures[D] = s
            app = pic_principal(s, freqs)
            print(f"      distance apparente du pic : {app:8.2f} mm")
    finally:
        try:
            vna.close()
        except Exception:
            pass

    if len(mesures) < 2:
        print("\n  Pas assez de positions mesurees. Abandon.")
        sys.exit(1)

    D_list = np.array(sorted(mesures))
    app_list = np.array([pic_principal(mesures[D], freqs) for D in D_list])

    # --- 1. Echelle des distances (controle de sanite) ---
    pente, offset = np.polyfit(D_list, app_list, 1)
    resid_lin = app_list - (pente * D_list + offset)
    print("\n" + "-" * 76)
    print("  1. ECHELLE DES DISTANCES (controle de sanite de la chaine)")
    print("-" * 76)
    print(f"  {'D reelle':>10} {'D apparente':>13} {'ecart au fit':>14}")
    for D, a, r in zip(D_list, app_list, resid_lin):
        print(f"  {D:9.1f} {a:13.2f} {r:13.3f}")
    print(f"\n  pente = {pente:.4f}   (attendu 1,000)")
    print(f"  offset = {offset:.2f} mm   (= plan de reference de l'antenne)")
    print(f"  ecart max a la droite : {np.abs(resid_lin).max():.3f} mm")
    if abs(pente - 1) > 0.02:
        print("  >> ANOMALIE : l'echelle des distances est fausse de "
              f"{abs(pente-1)*100:.1f} %. Verifie la bande reellement balayee.")

    # --- 2. Residu dispersif : LE test du centre de phase ---
    print("\n" + "-" * 76)
    print("  2. RESIDU DISPERSIF  (le vrai test du centre de phase)")
    print("-" * 76)
    print(f"  {'D':>7} {'long. elec.':>13} {'residu RMS':>13} "
          f"{'residu c-a-c':>14}")
    print(f"  {'mm':>7} {'mm':>13} {'mm cartilage':>13} {'mm cartilage':>14}")
    tous = {}
    for D in D_list:
        _, d_eq, longueur = residu_dispersif(freqs, mesures[D], D)
        tous[D] = d_eq
        print(f"  {D:7.1f} {longueur:13.1f} {np.std(d_eq):13.4f} "
              f"{np.ptp(d_eq):14.4f}")

    # Ce qui est commun a toutes les distances = l'antenne
    commun = np.mean([tous[D] for D in D_list], axis=0)
    dispersion_entre_D = np.mean([np.std(tous[D] - commun) for D in D_list])
    print(f"\n  Residu COMMUN (= antenne)   : RMS {np.std(commun):.4f} mm, "
          f"crete-a-crete {np.ptp(commun):.4f} mm")
    print(f"  Variabilite entre distances : {dispersion_entre_D:.4f} mm "
          f"(= montage / trajets multiples)")

    # --- Verdict ---
    print("\n" + "=" * 76)
    marge = CIBLE_MM / max(np.std(commun), 1e-9)
    if np.std(commun) < CIBLE_MM / 3:
        verdict = f"BON — marge x{marge:.1f} sur l'objectif de {CIBLE_MM} mm"
    elif np.std(commun) < CIBLE_MM:
        verdict = (f"LIMITE — residu {np.std(commun):.3f} mm, du meme ordre que "
                   f"l'objectif.\n     Il faudra caracteriser et deconvoluer "
                   f"H(f).")
    else:
        verdict = (f"INSUFFISANT — residu {np.std(commun):.3f} mm > objectif "
                   f"{CIBLE_MM} mm.\n     Cette antenne biaisera l'inversion.")
    print(f"  VERDICT : {verdict}")
    print("=" * 76)

    # --- Sauvegardes ---
    base = os.path.join(dossier, f"centre_phase_{args.nom}")
    np.savez_compressed(base + ".npz", freqs=freqs,
                        distances=D_list, apparentes=app_list,
                        **{f"s11_{D:.0f}": mesures[D] for D in D_list})

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.5, 5))
    a1.plot(D_list, app_list, 'o-', ms=7, lw=1.8, label="mesure")
    a1.plot(D_list, pente * D_list + offset, 'r--', lw=1.4,
            label=f"droite (pente {pente:.4f})")
    a1.set_xlabel("Distance reelle au reglet (mm)")
    a1.set_ylabel("Distance apparente du pic (mm)")
    a1.set_title("Echelle des distances")
    a1.grid(alpha=0.3); a1.legend(fontsize=9)

    for D in D_list:
        a2.plot(freqs / 1e9, tous[D], lw=1.2, alpha=0.55, label=f"D = {D:.0f} mm")
    a2.plot(freqs / 1e9, commun, 'k-', lw=2.4, label="commun (= antenne)")
    a2.axhline(CIBLE_MM, color='r', ls='--', lw=1.5,
               label=f"objectif $\\pm${CIBLE_MM} mm")
    a2.axhline(-CIBLE_MM, color='r', ls='--', lw=1.5)
    a2.set_xlabel("Frequence (GHz)")
    a2.set_ylabel("Epaisseur de cartilage equivalente (mm)")
    a2.set_title("Residu dispersif du centre de phase")
    a2.grid(alpha=0.3); a2.legend(fontsize=8)
    fig.suptitle(f"Qualification centre de phase — {args.nom}", fontsize=13)
    fig.tight_layout(); fig.savefig(base + ".png", dpi=140)
    print(f"\n  Resultats : {base}.png / .npz")


if __name__ == "__main__":
    main()
