"""
QUALIFICATION -- juger si l'antenne convient. Ne corrige rien.

C'est ce qui la distingue de calibration.py : celle-ci produit des NOMBRES
appliques a chaque mesure ; celle-la rend un VERDICT sur le materiel, et ne se
relance qu'au changement d'antenne.

    calibration.py    corrige      -> calibration/*.npz, applique en permanence
    qualification.py  juge         -> qualification/*.png, lu une fois

DEUX ESSAIS

  --ringing        Duree de la reponse impulsionnelle de l'antenne.
                   Le signal mesure est h_antenne * h_cible : une antenne
                   resonante "sonne", et ce trainard se superpose a l'echo de
                   fond de couche, qui se situe deja 14,5 dB sous l'echo de
                   surface. Fenetre de Blackman-Harris (lobes a -92 dB) et non
                   de Hann (-31 dB), pour ne pas confondre les jupes de la
                   fenetre avec un vrai ringing.

  --centre-phase   Dispersion du centre de phase, sur plaque metallique.
                   Une plaque metallique est un reflecteur parfait connu : le
                   residu de phase apres retrait d'une droite EST la fonction
                   de transfert de l'antenne. Converti en epaisseur de
                   cartilage equivalente, il donne directement le biais.

                   Seule la COURBURE nuit : la partie lineaire du residu est
                   un simple retard, absorbe par le plan de reference. Une
                   excursion lineaire de 10 mm ne coute que 0,094 mm.

UTILISATION
    python qualification.py --ringing --nom taoglas
    python qualification.py --ringing --nom taoglas --compare nooelec
    python qualification.py --centre-phase --nom taoglas --distances 100 150 200
"""

import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import noyau
import calibration
from noyau import c, DOSSIER_QUAL

BLEU, ORANGE, AQUA, ENCRE = "#2a78d6", "#eb6834", "#1baf7a", "#52514e"
SEUILS_DB = (-20, -30, -40)
STANDOFFS = (100, 150, 200)
ECHO_FOND_DB = -14.5          # echo de fond de couche / echo de surface
EPS_CARTILAGE = 42.5


# ======================================================================
# RINGING
# ======================================================================
def mode_ringing(args):
    print("=" * 74)
    print(f"  RINGING D'ANTENNE -- {args.nom}")
    print("=" * 74)
    print(f"  {args.start}-{args.stop} GHz, {args.points} pts, {args.moy} "
          f"moyennes (gain {10*np.log10(args.moy):.0f} dB)")
    print("\n  MONTAGE : antenne en espace libre, RIEN devant, rien a moins de")
    print("  2 m dans l'axe. Un absorbant devant l'antenne ameliore l'essai.")
    print("  AUCUNE tare : la reflexion de l'antenne EST l'objet de la mesure.\n")
    input("  Entree quand le montage est pret... ")

    vna = noyau.ouvrir_vna(args.start, args.stop, args.points,
                           simu=['vide'] if args.simu else None)
    try:
        freqs, s = noyau.acquiert(vna, args.moy)
    finally:
        try:
            vna.close()
        except Exception:
            pass
    if args.cal:
        s = calibration.applique(calibration.charger(args.cal), freqs, s)

    dist, prof, _ = noyau.profil_distance(freqs, s, zoom=16,
                                          fenetre="blackman-harris")
    i0 = int(np.argmax(prof))
    db = 20 * np.log10(prof / prof[i0] + 1e-18)
    d = dist - dist[i0]

    # Echo IDEAL a travers la meme chaine : c'est la jupe de la fenetre, donc
    # le plancher instrumental. Ce qui est AU-DESSUS est du vrai ringing.
    d_id, p_id, _ = noyau.profil_distance(freqs, np.ones_like(s), zoom=16,
                                          fenetre="blackman-harris")
    j0 = int(np.argmax(p_id))
    db_id = 20 * np.log10(p_id / p_id[j0] + 1e-18)
    d_id = d_id - d_id[j0]

    loin = d > 1500
    plancher = np.median(db[loin]) if loin.sum() > 10 else np.nan
    ap = d_id > 0
    sous20 = np.where(db_id[ap] < -20)[0]
    lobe = d_id[ap][sous20[0]] if len(sous20) else np.inf

    print("\n" + "-" * 74)
    print("  DECROISSANCE DU TRAINARD")
    print("-" * 74)
    apres = d > 0
    for s_db in SEUILS_DB:
        idx = np.where(~(db[apres] < s_db))[0]
        v = d[apres][idx[-1]] if len(idx) and idx[-1] + 1 < apres.sum() else 0.0
        print(f"  reste sous {s_db:4d} dB au-dela de : {v:8.1f} mm")

    print(f"\n  {'standoff':>10} {'mesure':>10} {'echo ideal':>12} "
          f"{'ringing net':>13}")
    nets = {}
    for so in STANDOFFS:
        i = int(np.argmin(np.abs(d - so)))
        j = int(np.argmin(np.abs(d_id - so)))
        nets[so] = db[i] - db_id[j]
        print(f"  {so:9d} mm {db[i]:9.1f} {db_id[j]:11.1f} {nets[so]:12.1f} dB")

    print(f"\n  Lobe principal (echo ideal sous -20 dB) : {lobe:.0f} mm")
    if lobe > STANDOFFS[0]:
        print(f"  >> Le lobe ({lobe:.0f} mm) depasse le standoff mini "
              f"({STANDOFFS[0]} mm) :")
        print("     echo d'antenne et echo de cible ne sont pas separables.")
    print(f"  Plancher de bruit (>1,5 m) : {plancher:.1f} dB")
    print(f"  Echo de fond a viser : {ECHO_FOND_DB} dB sous la surface")

    pire = max(nets.values())
    print("\n" + "=" * 74)
    if pire < -30:
        v = f"BON -- trainard a {pire:.0f} dB, tres sous l'echo de fond."
    elif pire < -20:
        v = (f"ACCEPTABLE -- trainard a {pire:.0f} dB. Utilisable, mais\n"
             "            l'estimation de l'ordre du modele demandera de la "
             "prudence.")
    else:
        v = (f"INSUFFISANT -- trainard a {pire:.0f} dB, du meme ordre que\n"
             f"            l'echo de fond ({ECHO_FOND_DB} dB). L'antenne le "
             "masquera.")
    print(f"  VERDICT : {v}")
    print("=" * 74)

    os.makedirs(DOSSIER_QUAL, exist_ok=True)
    base = os.path.join(DOSSIER_QUAL, f"ringing_{args.nom}")
    np.savez_compressed(base + ".npz", freqs=freqs, s11=s, dist=d, db=db)

    fig, ax = plt.subplots(figsize=(11, 6))
    m = (d >= -50) & (d <= 600)
    ax.plot(d[m], db[m], lw=1.8, color=BLEU, label=args.nom)
    mi = (d_id >= -50) & (d_id <= 600)
    ax.fill_between(d_id[mi], -100, db_id[mi], color="0.85", alpha=0.7,
                    label="plancher instrumental (echo ideal)")
    if args.compare:
        ref = os.path.join(DOSSIER_QUAL, f"ringing_{args.compare}.npz")
        if os.path.exists(ref):
            z = np.load(ref)
            mr = (z["dist"] >= -50) & (z["dist"] <= 600)
            ax.plot(z["dist"][mr], z["db"][mr], lw=1.6, ls="--", color=ORANGE,
                    alpha=0.85, label=f"{args.compare} (reference)")
        else:
            print(f"  (reference introuvable : {ref})")
    for s_db in SEUILS_DB:
        ax.axhline(s_db, color="0.7", ls=":", lw=1)
    ax.axhline(ECHO_FOND_DB, color="r", ls="--", lw=1.6,
               label=f"echo de fond de couche ({ECHO_FOND_DB} dB)")
    ax.axvspan(STANDOFFS[0], STANDOFFS[-1], color=AQUA, alpha=0.12,
               label="standoff de travail")
    ax.set_xlabel("Distance apres le pic d'antenne (mm)")
    ax.set_ylabel("Niveau relatif au pic (dB)")
    ax.set_ylim(-80, 3)
    ax.set_title(f"Ringing d'antenne — {args.nom} "
                 f"({args.start}-{args.stop} GHz, {args.moy} moyennes)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9, loc="upper right")
    fig.tight_layout()
    fig.savefig(base + ".png", dpi=140)
    print(f"\n  Resultats : {base}.png / .npz")


# ======================================================================
# CENTRE DE PHASE
# ======================================================================
def residu_dispersif(freqs, s11, D_mm):
    """Plaque metallique a distance connue : le residu de phase apres retrait
    d'une droite EST la dispersion de l'antenne.

    Rend (residu_rad, epaisseur_equivalente_mm, longueur_electrique_mm).
    """
    D = D_mm * 1e-3
    psi = np.unwrap(np.angle(s11)) + 4 * np.pi * freqs * D / c
    coef = np.polyfit(freqs, psi, 1)
    residu = psi - np.polyval(coef, freqs)
    d_eq = residu * c / (4 * np.pi * freqs * np.sqrt(EPS_CARTILAGE)) * 1e3
    longueur = -coef[0] * c / (4 * np.pi) * 1e3
    return residu, d_eq, longueur


def mode_centre_phase(args):
    print("=" * 74)
    print(f"  CENTRE DE PHASE -- {args.nom}")
    print("=" * 74)
    print("  Plaque metallique (>= 300 x 300 mm) a distances connues, mesurees")
    print("  au reglet DEPUIS LA FACE DE L'ANTENNE. Rien d'autre dans l'axe.\n")

    cal = calibration.charger(args.cal) if args.cal else None
    vna = noyau.ouvrir_vna(
        args.start, args.stop, args.points,
        simu=[f'metal@{d:.0f}' for d in args.distances] if args.simu else None)
    mesures = []
    try:
        for D in args.distances:
            input(f"  Place la plaque a {D:.0f} mm puis Entree... ")
            freqs, s = noyau.acquiert(vna, args.moy)
            s = calibration.applique(cal, freqs, s)
            mesures.append((D, freqs, s))
    finally:
        try:
            vna.close()
        except Exception:
            pass

    os.makedirs(DOSSIER_QUAL, exist_ok=True)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    pires = []
    print(f"\n  {'distance':>10} {'long. elec.':>13} {'residu c-c':>12} "
          f"{'epaisseur equiv.':>18}")
    print("  " + "-" * 58)
    for k, (D, freqs, s) in enumerate(mesures):
        residu, d_eq, longueur = residu_dispersif(freqs, s, D)
        pc = np.ptp(d_eq)
        pires.append(pc)
        print(f"  {D:8.0f}mm {longueur:11.1f}mm {np.ptp(np.degrees(residu)):10.2f}deg"
              f" {pc:16.3f}mm")
        col = [BLEU, ORANGE, AQUA][k % 3]
        a1.plot(freqs / 1e9, np.degrees(residu), lw=1.7, color=col,
                label=f"{D:.0f} mm")
        a2.plot(freqs / 1e9, d_eq, lw=1.7, color=col, label=f"{D:.0f} mm")

    a1.set_xlabel("Frequence (GHz)")
    a1.set_ylabel("Residu de phase (deg)")
    a1.set_title("Dispersion apres retrait de la droite", fontsize=11)
    a2.axhline(0.1, color="r", ls="--", lw=1.4, label="objectif 0,1 mm")
    a2.axhline(-0.1, color="r", ls="--", lw=1.4)
    a2.set_xlabel("Frequence (GHz)")
    a2.set_ylabel("Epaisseur de cartilage equivalente (mm)")
    a2.set_title("Ce que la dispersion coute en epaisseur", fontsize=11)
    for x in (a1, a2):
        x.grid(alpha=0.3)
        x.legend(fontsize=9)
        for kk in ("top", "right"):
            x.spines[kk].set_visible(False)
    fig.suptitle(f"Centre de phase — {args.nom}", fontsize=12)
    fig.tight_layout()
    base = os.path.join(DOSSIER_QUAL, f"centre_phase_{args.nom}")
    fig.savefig(base + ".png", dpi=140)

    pire = max(pires)
    print("\n" + "=" * 74)
    if pire < 0.05:
        v = f"BON -- dispersion equivalente a {pire:.3f} mm, tres sous 0,1 mm."
    elif pire < 0.15:
        v = f"ACCEPTABLE -- {pire:.3f} mm, du meme ordre que l'objectif."
    else:
        v = (f"INSUFFISANT -- {pire:.3f} mm, superieur a l'objectif de "
             "0,1 mm.\n            Cette antenne biaise la mesure.")
    print(f"  VERDICT : {v}")
    print("=" * 74)
    print("\n  Rappel : seule la COURBURE du residu nuit. La partie lineaire")
    print("  est un retard, absorbe par le plan de reference (calibration.py")
    print("  --plan). Une excursion lineaire de 10 mm ne coute que 0,094 mm.")
    print(f"\n  Resultats : {base}.png")


# ======================================================================
def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ringing", action="store_true")
    ap.add_argument("--centre-phase", action="store_true")
    ap.add_argument("--nom", required=True, help="nom de l'antenne")
    ap.add_argument("--compare", default=None,
                    help="ringing : superposer une qualification precedente")
    ap.add_argument("--distances", nargs="+", type=float,
                    default=[100.0, 150.0, 200.0],
                    help="centre-phase : distances de la plaque, mm")
    ap.add_argument("--cal", default="sol_courante")
    ap.add_argument("--start", type=float, default=noyau.BANDE_DEFAUT[0])
    ap.add_argument("--stop", type=float, default=noyau.BANDE_DEFAUT[1])
    ap.add_argument("--points", type=int, default=noyau.POINTS_DEFAUT)
    ap.add_argument("--moy", type=int, default=32)
    ap.add_argument("--simu", action="store_true",
                    help="instrument SIMULE")
    args = ap.parse_args()

    if args.ringing:
        return mode_ringing(args)
    if args.centre_phase:
        return mode_centre_phase(args)
    ap.error("choisir --ringing ou --centre-phase")


if __name__ == "__main__":
    main()
