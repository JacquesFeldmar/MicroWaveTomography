"""BILAN DU REGLAGE -- renoter tous les essais deja faits, sans en refaire un.

    python bilan_reglage.py

A lancer depuis ce dossier, dans n'importe quel environnement : il ne lit que
les `.s1p` que `regle.py` a laisses dans `resultats/vivaldi_tomographie/
reglage/`.

Il existe pour une raison precise. Un balayage coute une minute et demie par
point, et on change d'avis sur le critere en cours de route -- c'est arrive :
le critere « part de la bande sous -10 dB » s'est revele trop grossier, et il
a fallu lui adjoindre « sous -6 dB », qui dit la meme chose en moins severe.
Renoter les essais passes ne doit pas obliger a les refaire. D'ou la regle :
`regle.py` ecrit toujours le `.s1p`, et la note se recalcule apres coup.
"""
import glob
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.dirname(os.path.dirname(ICI)))

from regle import juge, BANDE                               # noqa: E402

DOSSIER = os.path.join(os.path.dirname(os.path.dirname(ICI)), "resultats",
                       "vivaldi_tomographie", "reglage")


def charge(chemin):
    d = np.loadtxt(chemin, comments=("!", "#"))
    return d[:, 0], d[:, 1] + 1j * d[:, 2]


def principal():
    essais = []
    for chemin in sorted(glob.glob(os.path.join(DOSSIER, "*.s1p"))):
        freqs, s11 = charge(chemin)
        note = juge(freqs, s11)
        essais.append((note["moyen"], os.path.basename(chemin)[:-4], note,
                       freqs, s11))
    if not essais:
        raise SystemExit(f"aucun essai dans {DOSSIER} : lancer regle.py")
    essais.sort(reverse=True)

    print(f"\n  {len(essais)} essais, du moins bon au meilleur "
          f"(bande {BANDE[0]}-{BANDE[1]} GHz)\n")
    print(f"  {'variante':32s} | <-10dB | <-6dB |   pire |  moyen")
    print("  " + "-" * 72)
    for _, nom, n, _, _ in essais:
        print(f"  {nom:32s} | {n['couverture']:5.1f} % | {n['sous_6']:4.1f} % "
              f"| {n['pire']:6.1f} | {n['moyen']:6.1f}")

    fig, (ax, bx) = plt.subplots(2, 1, figsize=(12, 10),
                                 gridspec_kw={"height_ratios": [2, 1]})
    for rang, (_, nom, n, freqs, s11) in enumerate(essais):
        meilleur = rang >= len(essais) - 3
        ax.plot(freqs / 1e9, 20 * np.log10(np.abs(s11)),
                lw=2.0 if meilleur else 0.8,
                alpha=1.0 if meilleur else 0.35,
                label=f"{nom} ({n['sous_6']:.0f} %, {n['moyen']:.1f} dB)"
                if meilleur else None)
    ax.axhline(-10, color="k", ls=":", lw=1)
    ax.axhline(-6, color="k", ls="--", lw=0.8)
    ax.axvspan(*BANDE, color="#2ecc71", alpha=0.07)
    ax.set_xlabel("fréquence (GHz)")
    ax.set_ylabel("$|S_{11}|$ (dB)")
    ax.set_ylim(-35, 0)
    ax.set_title("Vivaldi — tous les essais de réglage, les trois meilleurs "
                 "en gras")
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(alpha=0.3)

    noms = [e[1] for e in essais]
    bx.barh(range(len(essais)), [e[2]["sous_6"] for e in essais],
            color="#2980b9", label="sous −6 dB")
    bx.barh(range(len(essais)), [e[2]["couverture"] for e in essais],
            color="#c0392b", height=0.5, label="sous −10 dB")
    bx.set_yticks(range(len(essais)))
    bx.set_yticklabels(noms, fontsize=8)
    bx.set_xlabel("part de la bande 1,4–6,0 GHz (%)")
    bx.legend(fontsize=9)
    bx.grid(alpha=0.3, axis="x")

    chemin = os.path.join(DOSSIER, "bilan.png")
    fig.tight_layout()
    fig.savefig(chemin, dpi=130)
    print("\n  figure : " + chemin)


if __name__ == "__main__":
    principal()
