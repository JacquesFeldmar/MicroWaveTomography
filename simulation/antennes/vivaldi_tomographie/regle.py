"""REGLE -- balayer un parametre de la Vivaldi et comparer les |S11|.

    python regle.py --parametre TAUX --valeurs 0.008 0.013 0.020 0.030
    python regle.py --parametre MARGE_LONGUEUR --valeurs 1.0 1.3
    python regle.py --fixe TRANSITION=100 --parametre MARGE_LONGUEUR --valeurs 0.75

A lancer depuis ce dossier, dans l'environnement `openems`.

Une Vivaldi n'a pas de formule de conception : ses regles de l'art donnent un
point de depart, et le reste se regle sur le |S11| simule. Ce script fait donc
ce que ferait la main, mais en gardant la trace : une ligne par valeur, trois
chiffres comparables, et une figure ou les courbes se superposent.

LES TROIS CHIFFRES
LES QUATRE CHIFFRES
    <-10dB       part de la bande sous -10 dB. Le critere de catalogue.
    <-6dB        part de la bande sous -6 dB, soit un ROS de 3 : les trois
                 quarts de la puissance entrent. C'est la vraie limite
                 d'exploitabilite en tomographie.
    pire         le plus mauvais |S11| de la bande. Le plus fragile des
                 quatre : un seul pic etroit en bord de bande le ruine.
    moyen        moyenne de |S11| en puissance, ramenee en dB. C'est lui qui
                 compte le plus : il mesure la part de puissance qui n'entre
                 pas dans l'antenne, sur toute la bande.

RESERVE. Un balayage a un parametre ne trouve pas un optimum : il montre une
pente. Deux parametres qui se compensent -- ici l'ouverture et le taux
d'evasement -- demanderaient un plan a deux entrees, et beaucoup plus de
machine.
"""
import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, RACINE)

import fdtd as F                                       # noqa: E402
from banc import Acquisition, Antenne, Maillage, Montage, Plaque  # noqa: E402

BANDE = (1.4, 6.0)          # GHz, la bande jugee (bornee par la simulation)


def juge(freqs, s11, bande=BANDE):
    """Quatre chiffres, parce qu'un seul se laisse trop facilement flatter.

    `pire` est le plus fragile : un unique pic etroit en bord de bande le
    ruine, alors que l'antenne est bonne partout ailleurs. `sous_6` le
    tempere : -6 dB, c'est un ROS de 3, soit 75 % de la puissance qui entre.
    Pour de la tomographie, c'est la vraie limite d'exploitabilite ; -10 dB
    est un critere de catalogue.
    """
    f = freqs / 1e9
    dans = (f >= bande[0]) & (f <= bande[1])
    mod = np.abs(s11[dans])
    return dict(couverture=100.0 * (mod < 10 ** (-0.5)).mean(),
                sous_6=100.0 * (mod < 10 ** (-0.3)).mean(),
                pire=20 * np.log10(mod.max()),
                moyen=20 * np.log10(np.sqrt((mod ** 2).mean())))


def principal():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--parametre", required=True)
    p.add_argument("--valeurs", type=float, nargs="+", required=True)
    p.add_argument("--fixe", nargs="*", default=[], metavar="NOM=VALEUR",
                   help="autres parametres imposes pendant tout le balayage. "
                        "Sert a echanger deux cotes a carte constante : "
                        "--fixe TRANSITION=100 --parametre MARGE_LONGUEUR")
    p.add_argument("--fils", type=int, default=None)
    p.add_argument("--sortie", default=os.path.join(RACINE, "resultats",
                                                    "vivaldi_tomographie",
                                                    "reglage"))
    args = p.parse_args()

    ant = F.charge_antenne("vivaldi_tomographie")
    if not hasattr(ant, args.parametre):
        raise SystemExit(f"{args.parametre} n'est pas un parametre de "
                         f"vivaldi_tomographie")
    for impose in args.fixe:
        nom, _, val = impose.partition("=")
        if not hasattr(ant, nom):
            raise SystemExit(f"{nom} n'est pas un parametre de "
                             f"vivaldi_tomographie")
        setattr(ant, nom, float(val))
        print(f"  impose : {nom} = {float(val):g}")
    depart = getattr(ant, args.parametre)
    montage = Montage(acquisition=Acquisition(), antenne=Antenne(),
                      plaque=Plaque(), maillage=Maillage())
    os.makedirs(args.sortie, exist_ok=True)

    # Le nom d'un essai doit porter TOUTE sa configuration, pas seulement le
    # parametre balaye. Sans cela, deux essais qui ne different que par un
    # parametre impose s'ecrivent dans le meme fichier, et le second efface
    # le premier sans rien dire -- c'est arrive le 18/10/2026, et il a fallu
    # relire les journaux pour savoir quel essai avait survecu.
    prefixe = "".join(f"{f.replace('=', '_')}__" for f in args.fixe)

    resultats = []
    for v in args.valeurs:
        setattr(ant, args.parametre, v)
        d = ant.cotes()
        print(f"\n=== {args.parametre} = {v} "
              f"(carte {2*d['demi_x']:.1f} x {d['z_total']:.1f} mm) ===")
        freqs, s11 = F.lance(
            montage, ant, None, fils=args.fils,
            dossier=os.path.join(RACINE, "resultats", "fdtd",
                                 "vivaldi_tomographie",
                                 f"{prefixe}{args.parametre}_{v}"))
        note = juge(freqs, s11)
        note.update(valeur=v, largeur=2 * d["demi_x"], longueur=d["z_total"])
        resultats.append((note, freqs, s11))
        etiquette = f"{prefixe}{args.parametre}_{v}"
        F.ecrit_s1p(os.path.join(args.sortie, f"{etiquette}.s1p"), freqs, s11,
                    commentaire=" ".join(args.fixe
                                         + [f"{args.parametre}={v}"]))
        print(f"    sous -10 dB {note['couverture']:5.1f} %   "
              f"sous -6 dB {note['sous_6']:5.1f} %   "
              f"pire {note['pire']:6.1f} dB   moyen {note['moyen']:6.1f} dB")
    setattr(ant, args.parametre, depart)

    print(f"\n  {args.parametre:>16s} | carte (mm)     | couverture |   pire |"
          f"  moyen")
    print("  " + "-" * 70)
    for note, _, _ in resultats:
        print(f"  {note['valeur']:16g} | {note['largeur']:6.1f} x "
              f"{note['longueur']:6.1f} | {note['couverture']:8.1f} % | "
              f"{note['pire']:6.1f} | {note['moyen']:6.1f}")

    fig, ax = plt.subplots(figsize=(11, 6))
    for note, freqs, s11 in resultats:
        ax.plot(freqs / 1e9, 20 * np.log10(np.abs(s11)),
                label=f"{args.parametre} = {note['valeur']:g}  "
                      f"({note['couverture']:.0f} % / {note['sous_6']:.0f} %, "
                      f"moyen {note['moyen']:.1f} dB)")
    ax.axhline(-10, color="k", ls=":", lw=1)
    ax.axvspan(*BANDE, color="#2ecc71", alpha=0.08)
    ax.set_xlabel("fréquence (GHz)")
    ax.set_ylabel("$|S_{11}|$ (dB)")
    ax.set_ylim(-35, 0)
    ax.set_title(f"Vivaldi — réglage de {args.parametre}")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    chemin = os.path.join(args.sortie, f"reglage_{args.parametre}.png")
    fig.tight_layout()
    fig.savefig(chemin, dpi=130)
    print("\n  figure : " + chemin)


if __name__ == "__main__":
    principal()
