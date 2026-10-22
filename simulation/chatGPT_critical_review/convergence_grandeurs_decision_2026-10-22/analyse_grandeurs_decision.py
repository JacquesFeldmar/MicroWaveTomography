"""Les niveaux de maillage s'accordent-ils sur ce que l'antenne FAIT ?

LECTURE SEULE. Aucune source gelee n'est touchee, aucun solveur lance, aucune
selection ni qualification creee. Cet outil lit les `s11.s1p` deja archives.

POURQUOI IL EXISTE
------------------
Le controle spatial de la campagne compare S11 point par point : ecart
complexe maximal, RMS complexe, percentile 95 du module en dB. Il echoue pour
les trois antennes, a tous les niveaux essayes depuis le 18 octobre.

Mais la decision de faire fabriquer ne depend pas de S11 a 4,850 GHz. Elle
depend de deux grandeurs : la part de bande ou l'antenne est adaptee, et la
puissance moyenne reflechie. Ce script calcule CES grandeurs-la pour chaque
profil archive, et mesure leur etendue entre niveaux de maillage.

DEUX CONTROLES, ET ILS NE DISENT PAS LA MEME CHOSE
--------------------------------------------------
1. Les grandeurs de decision, par niveau et leur etendue.
2. La MONOTONIE du raffinement : pour les paires spatiales consecutives du
   grand losange, l'ecart complexe doit DECROITRE si la suite converge. Les
   deux metriques complexes sont recalculees ici directement, sans masque et
   sans reutiliser `Q.ecarts` : elles ne dependent d'aucune convention.

Un ecart point par point qui cesse de decroitre pendant que les grandeurs de
decision restent stables ne se lit pas comme « il faut mailler plus fin ». Il
se lit comme « la suite de grilles ne raffine pas ce qu'elle pretend
raffiner » -- ce que le diagnostic des grilles closes avait deja indique en
mesurant un GROSSISSEMENT local pres du port entre extreme_fin et N30.

Ce rapport ne modifie aucun seuil et ne declare aucune qualification. Il
etablit ce que les profils archives permettent, et ce qu'ils ne permettent
pas, de conclure.
"""
import argparse
import glob
import hashlib
import json
import os

import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
RESULTATS = os.path.join(RACINE, "resultats")
BANDE_HZ = (1.4e9, 6.0e9)

# Les paires spatiales consecutives du grand losange, campagne F1, a 12 ns.
# Ce sont celles dont les verdicts sont consignes dans TACHES_REPRISE_PCBWAY.
ECHELLE_F1_GRAND = ["fin_12ns", "tres_fin_12ns", "ultra_fin_12ns",
                    "extreme_fin_12ns", "n30_12ns", "n34_12ns"]


def sha256(chemin):
    with open(chemin, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def lit_s1p(chemin):
    d = np.loadtxt(chemin, comments=("!", "#"))
    return d[:, 0], d[:, 1] + 1j * d[:, 2]


def dans_bande(f):
    return (f >= BANDE_HZ[0]) & (f <= BANDE_HZ[1])


def grandeurs(f, s):
    """Les grandeurs sur lesquelles la decision de fabriquer repose."""
    m = np.abs(s[dans_bande(f)])
    if m.size == 0:
        return None
    return dict(
        points=int(m.size),
        part_sous_10db_pct=100.0 * float((m < 10 ** -0.5).mean()),
        part_sous_6db_pct=100.0 * float((m < 10 ** -0.3).mean()),
        puissance_reflechie_moyenne_db=20 * float(
            np.log10(np.sqrt((m ** 2).mean()))),
        pire_point_db=20 * float(np.log10(m.max())),
    )


def ecart_complexe(f1, s1, f2, s2):
    """Maximum et RMS de |S11_a - S11_b|, sans masque ni convention."""
    if f1.shape != f2.shape or not np.allclose(f1, f2):
        raise ValueError("grilles de frequence differentes")
    d = np.abs(s1 - s2)[dans_bande(f1)]
    return dict(maximum_complexe=float(d.max()),
                rms_complexe=float(np.sqrt((d ** 2).mean())))


def recense():
    """Tous les profils archives : (campagne, antenne, niveau) -> chemin."""
    profils = {}
    for chemin in sorted(glob.glob(os.path.join(RESULTATS, "**", "s11.s1p"),
                                   recursive=True)):
        parties = os.path.relpath(chemin, RESULTATS).split(os.sep)
        if len(parties) < 3:
            continue
        profils[(parties[0], parties[-3], parties[-2])] = chemin
    return profils


def principal():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sortie", default=os.path.join(ICI, "rapport.json"))
    args = p.parse_args()

    profils = recense()
    rapport = {"bande_hz": list(BANDE_HZ), "profils": {}, "etendues": {},
               "monotonie_f1_grand_losange": [],
               "avertissement": ("lecture seule ; aucun seuil modifie, "
                                 "aucune qualification declaree")}

    # ------------------------------------------------ grandeurs par profil
    for (campagne, antenne, niveau), chemin in profils.items():
        f, s = lit_s1p(chemin)
        g = grandeurs(f, s)
        if g is None:
            continue
        g["sha256_s1p"] = sha256(chemin)
        rapport["profils"][f"{campagne}/{antenne}/{niveau}"] = g

    # ------------------------------------------------ etendue entre niveaux
    groupes = {}
    for cle, g in rapport["profils"].items():
        campagne, antenne, niveau = cle.split("/")
        groupes.setdefault((campagne, antenne), {})[niveau] = g
    for (campagne, antenne), niveaux in groupes.items():
        if len(niveaux) < 2:
            continue
        etendue = {}
        for champ in ("part_sous_10db_pct", "part_sous_6db_pct",
                      "puissance_reflechie_moyenne_db", "pire_point_db"):
            vals = [n[champ] for n in niveaux.values()]
            etendue[champ] = dict(minimum=min(vals), maximum=max(vals),
                                  etendue=max(vals) - min(vals))
        etendue["niveaux"] = sorted(niveaux)
        rapport["etendues"][f"{campagne}/{antenne}"] = etendue

    # ------------------------------------------------ monotonie du grand F1
    for a, b in zip(ECHELLE_F1_GRAND, ECHELLE_F1_GRAND[1:]):
        ca = profils.get(("pcbway_r1", "diamant_uwb_x18", a))
        cb = profils.get(("pcbway_r1", "diamant_uwb_x18", b))
        if not ca or not cb:
            continue
        fa, sa = lit_s1p(ca)
        fb, sb = lit_s1p(cb)
        e = ecart_complexe(fa, sa, fb, sb)
        e.update(depart=a, arrivee=b)
        rapport["monotonie_f1_grand_losange"].append(e)

    with open(args.sortie, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False, sort_keys=True)

    # ------------------------------------------------ affichage
    print(f"\n  GRANDEURS DE DECISION, bande "
          f"{BANDE_HZ[0]/1e9:.1f}-{BANDE_HZ[1]/1e9:.1f} GHz\n")
    print(f"  {'campagne / antenne':48s} {'<-10dB':>8s} {'<-6dB':>7s} "
          f"{'moyen':>8s} {'pire':>7s}")
    print("  " + "-" * 82)
    for cle in sorted(rapport["etendues"]):
        e = rapport["etendues"][cle]
        print(f"  {cle:48s} "
              f"{e['part_sous_10db_pct']['etendue']:7.2f}p "
              f"{e['part_sous_6db_pct']['etendue']:6.2f}p "
              f"{e['puissance_reflechie_moyenne_db']['etendue']:7.2f}dB "
              f"{e['pire_point_db']['etendue']:6.2f}dB   "
              f"({len(e['niveaux'])} niveaux)")
    print("\n  Les colonnes sont des ETENDUES entre niveaux de maillage : "
          "plus c'est petit,\n  plus les niveaux s'accordent sur ce que "
          "l'antenne fait.")

    if rapport["monotonie_f1_grand_losange"]:
        print("\n\n  MONOTONIE DU RAFFINEMENT -- grand losange, campagne F1, "
              "12 ns")
        print("  (recalcul direct, sans masque ni Q.ecarts)\n")
        print(f"  {'paire spatiale':44s} {'max complexe':>13s} "
              f"{'RMS complexe':>13s}")
        print("  " + "-" * 74)
        precedent = None
        for e in rapport["monotonie_f1_grand_losange"]:
            fleche = ""
            if precedent is not None:
                fleche = "  v" if e["maximum_complexe"] < precedent else "  ^"
            precedent = e["maximum_complexe"]
            print(f"  {e['depart']+' -> '+e['arrivee']:44s} "
                  f"{e['maximum_complexe']:13.7f} "
                  f"{e['rms_complexe']:13.7f}{fleche}")
        print("\n  Une suite qui converge decroit. Les remontees marquees ^ "
              "disent que le\n  raffinement ne raffine pas ce qu'il pretend "
              "raffiner.")

    print("\n  rapport : " + args.sortie)


if __name__ == "__main__":
    principal()
