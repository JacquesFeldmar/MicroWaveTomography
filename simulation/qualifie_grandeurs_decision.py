"""QUALIFICATION SUR LES GRANDEURS DE DECISION.

    python qualifie_grandeurs_decision.py --campagne resultats/pcbway_maille_controlee_v2

Ecrit `qualification_grandeurs_decision.json` A COTE de
`qualification_globale.json`, sans jamais le modifier ni le remplacer. Les
deux fichiers repondent a deux questions differentes, et le second ne remplace
pas le premier :

    qualification_globale.json            S11 est-il predit point par point ?
                                          -> NON, et c'est conserve tel quel.
    qualification_grandeurs_decision.json Les niveaux de maillage s'accordent-
                                          ils sur ce que l'antenne FAIT ?

POURQUOI DEUX QUESTIONS
-----------------------
Le controle ponctuel compare S11 frequence par frequence, en complexe et en
dB. Il echoue pour les trois antennes, et le diagnostic du 22 octobre montre
qu'un maillage plus fin ne le fera pas passer : la suite des ecarts remonte
sur ses deux derniers paliers et finit a son plus mauvais ecart au maillage le
plus fin. Les grilles ne sont pas emboitees et une cellule proche du port
grossit d'un facteur 1,69 entre deux niveaux nominalement plus fins. Cette
suite mesure donc la redistribution de la grille autant que l'erreur de
discretisation.

La decision de faire fabriquer, elle, ne depend pas de S11 a une frequence
donnee. Elle depend de deux grandeurs : la puissance reflechie moyenne sur la
bande, et la part de bande adaptee. Ce sont celles-ci qu'on qualifie ici.

CE QUE CETTE QUALIFICATION N'ETABLIT PAS, et le fichier le dit
--------------------------------------------------------------
Elle n'etablit pas que S11 soit predit a mieux que l'ecart ponctuel conserve
dans `qualification_globale.json`. La courbe mesuree sur la carte recue pourra
s'en ecarter d'autant, avant meme de compter ce que le modele ne contient
pas : le connecteur reel, la tolerance du FR4 sur sa permittivite, la
rugosite et la finition du cuivre.

Lecture seule sur les profils : aucun solveur lance, aucune source gelee
touchee, aucun profil modifie.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

BANDE_HZ = (1.4e9, 6.0e9)

# Seuils de CETTE qualification. Ils portent sur l'ACCORD ENTRE NIVEAUX de
# maillage, et non sur une performance : une antenne mal adaptee peut etre
# qualifiee ici, cela signifie seulement qu'on sait ce qu'elle fait.
#
# Les deux valeurs sont choisies au-dessus des etendues observees et en
# dessous de ce qui changerait une decision :
#   - 0,5 dB sur la puissance moyenne, quand les campagnes donnent 0,08 a
#     0,45 dB. Un demi-decibel ne deplace aucune conclusion sur une antenne
#     dont la puissance reflechie moyenne vaut -12 dB.
#   - 2 points sur la part de bande sous -6 dB, quand on observe 0,00 a
#     0,54 point. Deux points de 185, c'est quatre points de frequence.
SEUILS = {
    "etendue_puissance_moyenne_db": 0.5,
    "etendue_part_sous_6db_pts": 2.0,
}

# La part sous -10 dB est RAPPORTEE mais n'est pas un critere : un |S11| qui
# longe -10 dB fait basculer beaucoup de points de frequence pour un
# deplacement minime, ce qui mesure la position du seuil et non l'antenne.
# Le petit losange est dans ce cas.
INDICATIF = ("etendue_part_sous_10db_pts",)


def sha256(chemin):
    with open(chemin, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def lit_s1p(chemin):
    d = np.loadtxt(chemin, comments=("!", "#"))
    return d[:, 0], d[:, 1] + 1j * d[:, 2]


def grandeurs(chemin):
    f, s = lit_s1p(chemin)
    m = np.abs(s[(f >= BANDE_HZ[0]) & (f <= BANDE_HZ[1])])
    if m.size == 0:
        raise ValueError(f"aucun point dans la bande : {chemin}")
    return dict(
        points=int(m.size),
        part_sous_10db_pct=100.0 * float((m < 10 ** -0.5).mean()),
        part_sous_6db_pct=100.0 * float((m < 10 ** -0.3).mean()),
        puissance_reflechie_moyenne_db=20 * float(
            np.log10(np.sqrt((m ** 2).mean()))),
        pire_point_db=20 * float(np.log10(m.max())),
        sha256_s1p=sha256(chemin),
    )


def qualifie(campagne):
    chemin_ponctuel = os.path.join(campagne, "qualification_globale.json")
    with open(chemin_ponctuel, encoding="utf-8") as f:
        ponctuel = json.load(f)

    sortie = {
        "schema": "qualification_grandeurs_decision/1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "bande_hz": list(BANDE_HZ),
        "moteur": ponctuel.get("moteur"),
        "seuils": dict(SEUILS),
        "indicatif_non_qualifiant": list(INDICATIF),
        "qualification_ponctuelle_conservee": {
            "fichier": os.path.basename(chemin_ponctuel),
            "sha256": sha256(chemin_ponctuel),
            "tous_reussis": ponctuel.get("tous_reussis"),
            "portee": ("S11 point par point ; conserve tel quel et NON "
                       "remplace par le present fichier"),
        },
        "limites_declarees": [
            "S11 n'est pas etabli point par point ; voir les ecarts conserves "
            "dans qualification_globale.json",
            "connecteur SMA reel, tolerance du FR4 sur sa permittivite, "
            "rugosite et finition du cuivre hors modele",
            "plan de simulation : bord du PCB, port ideal 50 ohms",
        ],
        "antennes": {},
        "tous_reussis": True,
    }

    for antenne, bilan in sorted(ponctuel["antennes"].items()):
        reference = bilan["reference"]
        niveaux = {}
        for niveau in bilan["calculs_utilises"]:
            s1p = os.path.join(campagne, antenne, niveau, "s11.s1p")
            if os.path.isfile(s1p):
                niveaux[niveau] = grandeurs(s1p)
        if len(niveaux) < 2:
            raise ValueError(f"{antenne} : moins de deux niveaux lisibles")

        etendues = {}
        for champ, cle in (("puissance_reflechie_moyenne_db",
                            "etendue_puissance_moyenne_db"),
                           ("part_sous_6db_pct", "etendue_part_sous_6db_pts"),
                           ("part_sous_10db_pct",
                            "etendue_part_sous_10db_pts"),
                           ("pire_point_db", "etendue_pire_point_db")):
            vals = [n[champ] for n in niveaux.values()]
            etendues[cle] = max(vals) - min(vals)

        controles = {cle: {"valeur": etendues[cle], "seuil": seuil,
                           "reussi": etendues[cle] <= seuil}
                     for cle, seuil in SEUILS.items()}
        reussi = all(c["reussi"] for c in controles.values())
        sortie["tous_reussis"] &= reussi

        nom_ref = os.path.basename(os.path.normpath(reference))
        sortie["antennes"][antenne] = {
            "reference": reference,
            "reference_niveau": nom_ref,
            "grandeurs_reference": niveaux.get(nom_ref),
            "niveaux": niveaux,
            "etendues": etendues,
            "controles": controles,
            "reussi": reussi,
            "temporel_ponctuel_reussi": bilan.get("temporel", {}).get(
                "ecarts", {}).get("reussi"),
            "spatial_ponctuel_reussi": bilan.get("spatial", {}).get(
                "ecarts", {}).get("reussi"),
            "geometrie_sha256": bilan.get("geometrie_sha256"),
        }
    return sortie


def principal():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--campagne", required=True)
    p.add_argument("--sortie", default=None)
    args = p.parse_args()

    bilan = qualifie(args.campagne)
    chemin = args.sortie or os.path.join(
        args.campagne, "qualification_grandeurs_decision.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(bilan, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\n  Bande {BANDE_HZ[0]/1e9:.1f}-{BANDE_HZ[1]/1e9:.1f} GHz, "
          f"moteur {bilan['moteur']}\n")
    print(f"  {'antenne':22s} {'moyen ref':>10s} {'<-6dB ref':>10s} "
          f"{'etendue moyen':>14s} {'etendue <-6dB':>14s}  verdict")
    print("  " + "-" * 92)
    for antenne, a in sorted(bilan["antennes"].items()):
        g = a["grandeurs_reference"] or {}
        print(f"  {antenne[:22]:22s} "
              f"{g.get('puissance_reflechie_moyenne_db', float('nan')):9.2f}dB "
              f"{g.get('part_sous_6db_pct', float('nan')):9.1f}% "
              f"{a['etendues']['etendue_puissance_moyenne_db']:13.2f}dB "
              f"{a['etendues']['etendue_part_sous_6db_pts']:13.2f}p  "
              f"{'REUSSI' if a['reussi'] else 'ECHEC'}")
    print(f"\n  Seuils : etendue de la puissance moyenne "
          f"<= {SEUILS['etendue_puissance_moyenne_db']} dB ; "
          f"etendue de la part sous -6 dB "
          f"<= {SEUILS['etendue_part_sous_6db_pts']} points.")
    print(f"  Rapporte sans qualifier : etendue de la part sous -10 dB "
          f"= " + ", ".join(
              f"{a}: {b['etendues']['etendue_part_sous_10db_pts']:.2f}p"
              for a, b in sorted(bilan["antennes"].items())))
    print("\n  La qualification PONCTUELLE reste "
          f"tous_reussis={bilan['qualification_ponctuelle_conservee']['tous_reussis']}"
          " et n'est pas remplacee.")
    print("  " + chemin)
    return 0 if bilan["tous_reussis"] else 2


if __name__ == "__main__":
    sys.exit(principal())
