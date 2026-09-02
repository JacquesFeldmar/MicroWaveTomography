"""
QUALIFICATION 2 — Ringing de l'antenne (duree de la reponse impulsionnelle).

POURQUOI
    Le signal mesure est le produit de convolution
            s(t) = h_antenne(t) * h_cible(t)
    Une antenne resonante possede un h_antenne(t) long : elle "sonne". Ce
    trainard se superpose a l'echo de la cible, brouille l'estimation de l'ordre
    du modele (nombre d'echos) dont dependent ESPRIT et l'inversion, et masque
    l'echo de fond de couche — qui se situe deja 14,5 dB sous l'echo de surface.

    Critere pratique : au standoff de travail (80-120 mm), le trainard de
    l'antenne doit etre tombe NETTEMENT sous le niveau de l'echo de fond de
    couche, soit au moins 20 a 30 dB sous le pic d'antenne.

PRINCIPE
    Antenne en espace libre, RIEN devant (ou un absorbant), rien a moins de
    2 metres. On ne fait PAS de tare : la reflexion propre de l'antenne est
    precisement ce que l'on veut mesurer.

    Fenetre de Blackman-Harris et non de Hann : ses lobes secondaires sont
    beaucoup plus bas (~ -92 dB contre -31 dB), ce qui evite de confondre les
    lobes de la fenetre avec un vrai ringing. Le prix est un lobe principal plus
    large, sans importance ici puisqu'on mesure une decroissance, pas une
    separation.

    Le moyennage VECTORIEL de N balayages abaisse le plancher de bruit de
    10*log10(N) dB.

UTILISATION
    python qualif_ringing.py --nom taoglas --start 3.0 --stop 6.3
    python qualif_ringing.py --nom antenne_actuelle
    python qualif_ringing.py --nom taoglas --compare antenne_actuelle
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
PORT_VNA = "ASRL6::INSTR"
ZOOM = 16
SEUILS_DB = (-20, -30, -40)
STANDOFFS = (100, 150, 200)     # mm apres le pic d'antenne. En bande reduite
                                # (3-6,3 GHz) le lobe principal fait ~105 mm :
                                # travailler a 80 mm ne separerait pas l'echo
                                # d'antenne de celui de la cible.
ECHO_FOND_DB = -14.5            # echo de fond de couche / echo de surface


def blackman_harris(n):
    k = np.arange(n) / (n - 1)
    return (0.35875 - 0.48829 * np.cos(2 * np.pi * k)
            + 0.14128 * np.cos(4 * np.pi * k)
            - 0.01168 * np.cos(6 * np.pi * k))


def acquiert(vna, n_moy, n_jetes=2):
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


def profil_db(s, freqs):
    """Enveloppe en dB rapportee au pic, et axe des distances APRES le pic."""
    n_fft = len(s) * ZOOM
    p = np.abs(np.fft.ifft(s * blackman_harris(len(s)), n=n_fft))
    # Le pas frequentiel vaut BW/(N-1) et non BW/N : utiliser 1/BW comme span
    # temporel fausse l'echelle de N/(N-1) (1 % a 101 points).
    df = (freqs[-1] - freqs[0]) / (len(s) - 1)
    pas = 1.0 / (n_fft * df) * c / 2 * 1000
    d = np.arange(n_fft) * pas
    demi = n_fft // 2
    d, p = d[:demi], p[:demi]
    i_pic = int(np.argmax(p))
    db = 20 * np.log10(p / p[i_pic] + 1e-18)
    return d - d[i_pic], db, pas


def franchissements(dist, db, seuils):
    """Distance apres laquelle l'enveloppe reste durablement sous chaque seuil."""
    out = {}
    apres = dist > 0
    da, ba = dist[apres], db[apres]
    for s in seuils:
        sous = ba < s
        # dernier point AU-DESSUS du seuil -> on reste sous apres
        idx = np.where(~sous)[0]
        out[s] = da[idx[-1]] if len(idx) and idx[-1] + 1 < len(da) else (
            0.0 if not len(idx) else np.nan)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nom", required=True)
    ap.add_argument("--start", type=float, default=1.4, help="GHz")
    ap.add_argument("--stop", type=float, default=6.3, help="GHz")
    ap.add_argument("--points", type=int, default=201)
    ap.add_argument("--moy", type=int, default=32)
    ap.add_argument("--compare", default=None,
                    help="nom d'une qualification precedente a superposer")
    args = ap.parse_args()

    dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "qualification")
    os.makedirs(dossier, exist_ok=True)

    print("=" * 76)
    print(f"  QUALIFICATION 2 — ringing d'antenne : {args.nom}")
    print("=" * 76)
    print(f"  Bande {args.start}-{args.stop} GHz, {args.points} points, "
          f"{args.moy} balayages (gain {10*np.log10(args.moy):.0f} dB)")
    print("\n  MONTAGE : antenne en espace libre, RIEN devant, rien a moins de")
    print("  2 m dans l'axe. Un absorbant devant l'antenne ameliore la mesure.")
    print("  AUCUNE tare : la reflexion de l'antenne est l'objet de la mesure.\n")
    input("  Appuie sur Entree quand le montage est pret... ")

    try:
        vna = NanoVNAv2(PORT_VNA, backend='@py')
        vna.frequency = rf.Frequency(start=args.start, stop=args.stop,
                                     npoints=args.points, unit='GHz')
        print(f"\n  LiteVNA connecte ({vna.id}).")
        freqs, s = acquiert(vna, args.moy)
    except Exception as e:
        print(f"  ERREUR : {e}")
        sys.exit(1)
    finally:
        try:
            vna.close()
        except Exception:
            pass

    dist, db, pas = profil_db(s, freqs)

    # Reponse d'un echo IDEAL a travers la meme chaine : c'est la jupe de la
    # fenetre, donc le plancher instrumental. Tout ce qui est AU-DESSUS d'elle
    # est du vrai ringing ; ce qui la suit n'est qu'un artefact de traitement.
    dist_id, db_id, _ = profil_db(np.ones_like(s), freqs)

    # Plancher de bruit : niveau median tres loin (au-dela de 1,5 m)
    loin = dist > 1500
    plancher = np.median(db[loin]) if loin.sum() > 10 else np.nan

    # Largeur du lobe principal : en deca, on ne mesure rien d'exploitable
    apres_id = dist_id > 0
    sous20 = np.where(db_id[apres_id] < -20)[0]
    lobe_mm = dist_id[apres_id][sous20[0]] if len(sous20) else np.inf

    print("\n" + "-" * 76)
    print("  DECROISSANCE DU TRAINARD")
    print("-" * 76)
    fr = franchissements(dist, db, SEUILS_DB)
    for s_db in SEUILS_DB:
        v = fr[s_db]
        txt = f"{v:8.1f} mm" if np.isfinite(v) else "   jamais"
        print(f"  reste sous {s_db:4d} dB au-dela de : {txt}")

    print(f"\n  {'standoff':>10} {'mesure':>10} {'echo ideal':>12} "
          f"{'ringing net':>13}")
    niveaux, nets = {}, {}
    for so in STANDOFFS:
        i = int(np.argmin(np.abs(dist - so)))
        j = int(np.argmin(np.abs(dist_id - so)))
        niveaux[so] = db[i]
        nets[so] = db[i] - db_id[j]
        print(f"  {so:9d} mm {db[i]:9.1f} {db_id[j]:11.1f} {nets[so]:12.1f} dB")

    print(f"\n  Lobe principal (echo ideal sous -20 dB) : {lobe_mm:.0f} mm")
    if lobe_mm > STANDOFFS[0]:
        print(f"  >> ATTENTION : le lobe principal ({lobe_mm:.0f} mm) depasse le")
        print(f"     standoff mini ({STANDOFFS[0]} mm). Avec cette bande, l'echo")
        print(f"     de l'antenne et celui de la cible ne sont pas separables.")
        print(f"     Recule le standoff au-dela de {lobe_mm:.0f} mm, ou elargis")
        print(f"     la bande.")
    print(f"  Plancher de bruit (>1,5 m) : {plancher:.1f} dB")
    print(f"  Echo de fond de couche a viser : {ECHO_FOND_DB} dB sous la surface")

    # --- Verdict : sur le ringing NET, corrige du plancher instrumental ---
    pire = max(nets.values())
    print("\n" + "=" * 76)
    if pire < -30:
        v = (f"BON — trainard a {pire:.0f} dB au standoff, tres en dessous de "
             f"l'echo de fond.")
    elif pire < -20:
        v = (f"ACCEPTABLE — trainard a {pire:.0f} dB. Utilisable, mais "
             f"l'estimation\n     de l'ordre du modele demandera de la prudence.")
    else:
        v = (f"INSUFFISANT — trainard a {pire:.0f} dB au standoff, du meme "
             f"ordre que\n     l'echo de fond de couche ({ECHO_FOND_DB} dB). "
             f"L'antenne masquera le signal.")
    print(f"  VERDICT : {v}")
    print("=" * 76)

    base = os.path.join(dossier, f"ringing_{args.nom}")
    np.savez_compressed(base + ".npz", freqs=freqs, s11=s,
                        dist=dist, db=db, bande=(args.start, args.stop))

    fig, ax = plt.subplots(figsize=(11, 6))
    m = (dist >= -50) & (dist <= 600)
    ax.plot(dist[m], db[m], lw=1.8, label=f"{args.nom}")
    mi = (dist_id >= -50) & (dist_id <= 600)
    ax.fill_between(dist_id[mi], -100, db_id[mi], color='0.85', alpha=0.7,
                    label="plancher instrumental (echo ideal)")

    if args.compare:
        ref = os.path.join(dossier, f"ringing_{args.compare}.npz")
        if os.path.exists(ref):
            r = np.load(ref)
            dr, br = r["dist"], r["db"]
            mr = (dr >= -50) & (dr <= 600)
            ax.plot(dr[mr], br[mr], lw=1.6, ls='--', alpha=0.85,
                    label=f"{args.compare} (reference)")
        else:
            print(f"  (reference introuvable : {ref})")

    for s_db in SEUILS_DB:
        ax.axhline(s_db, color='0.7', ls=':', lw=1)
    ax.axhline(ECHO_FOND_DB, color='r', ls='--', lw=1.6,
               label=f"echo de fond de couche ({ECHO_FOND_DB} dB)")
    ax.axvspan(STANDOFFS[0], STANDOFFS[-1], color='green', alpha=0.10,
               label="standoff de travail")
    if np.isfinite(plancher):
        ax.axhline(plancher, color='0.5', ls='-.', lw=1,
                   label=f"plancher de mesure ({plancher:.0f} dB)")
    ax.set_xlabel("Distance apres le pic d'antenne (mm)")
    ax.set_ylabel("Niveau relatif au pic (dB)")
    ax.set_ylim(-80, 3)
    ax.set_title(f"Ringing d'antenne — {args.nom}  "
                 f"({args.start}-{args.stop} GHz, {args.moy} moyennes)")
    ax.grid(alpha=0.3); ax.legend(fontsize=9, loc='upper right')
    fig.tight_layout(); fig.savefig(base + ".png", dpi=140)
    print(f"\n  Resultats : {base}.png / .npz")


if __name__ == "__main__":
    main()
