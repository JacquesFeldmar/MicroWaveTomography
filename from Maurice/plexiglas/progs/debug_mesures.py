#!/usr/bin/env python3
"""Rejoue hors ligne les paquets USB, la SOL et les profils sauvegardés.

Exemple :
  python plexiglas/progs/debug_mesures.py plexiglas/mesures/cible_*/cible.npz

Ne communique pas avec le VNA et ne modifie aucun fichier de mesure.
Une égalité parfaite vérifie la cohérence du calcul, pas l'exactitude RF
des étalons, de la fréquence émise ou du zéro temporel physique.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import litevna
from commun import physique, sol


def charger(chemin):
    with np.load(chemin, allow_pickle=False) as z:
        return {k: z[k].copy() for k in z.files}


def erreur(a, b):
    if np.shape(a) != np.shape(b):
        raise ValueError(f"Tailles différentes : {np.shape(a)} / {np.shape(b)}")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("Valeurs non finies.")
    delta = float(np.max(np.abs(np.asarray(a) - np.asarray(b))))
    if not np.allclose(a, b, rtol=1e-12, atol=1e-12):
        raise ValueError(f"Recalcul différent des valeurs sauvegardées : erreur {delta:g}")
    return delta


def verifier(chemin):
    z = charger(chemin)
    f = z["freqs"]
    mode = str(z["correction_mode"])
    sweeps = np.array([litevna.decoder(p.tobytes(), len(f), mode)
                       for p in z["paquets_usb"]])
    bilan = {"fichier": str(chemin), "nombre": len(sweeps), "points": len(f)}
    if mode == "brut":
        bilan["erreur_decodage"] = erreur(sweeps, z["sweeps_bruts"])
        ref = z if "sol_e00" in z else charger(str(z["fichier_fond"]))
        cal = {k: ref["sol_" + k] for k in ("freqs", "e00", "e11", "e10e01")}
        erreur(f, cal["freqs"])
        sweeps = sol.applique(cal, f, sweeps)
    bilan["erreur_sol"] = erreur(sweeps, z["sweeps_calibres"])
    moyenne = sweeps.mean(axis=0)
    bilan["erreur_moyenne"] = erreur(moyenne, z["cible"] if "cible" in z else z["fond"])
    if "residu" in z:
        residu = moyenne - z["fond"]
        bilan["erreur_soustraction"] = erreur(residu, z["residu"])
        # Les nouvelles acquisitions communes A/B ne contiennent pas d'IFFT.
        if "profil" in z:
            distance, profil, _ = physique.profil_distance(f, residu)
            bilan["erreur_profil_A"] = erreur(profil, z["profil"])
            bilan["erreur_axe_mm_A"] = erreur(distance, z["distance_mm"])
    return bilan


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mesures", nargs="+", type=Path)
    ap.add_argument("--sortie", type=Path, help="Rapport JSON facultatif")
    args = ap.parse_args()
    rapports = []
    for chemin in args.mesures:
        try:
            rapports.append(dict(verifier(chemin), resultat="OK"))
        except (ValueError, OSError, KeyError) as exc:
            rapports.append(dict(fichier=str(chemin), resultat="ECHEC", erreur=str(exc)))
    texte = json.dumps(rapports, ensure_ascii=False, indent=2)
    if args.sortie:
        args.sortie.parent.mkdir(parents=True, exist_ok=True)
        args.sortie.write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0 if all(r["resultat"] == "OK" for r in rapports) else 1


if __name__ == "__main__":
    sys.exit(main())
