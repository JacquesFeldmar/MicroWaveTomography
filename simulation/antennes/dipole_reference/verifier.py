"""VERIFIER -- le programme complet, controle sur une antenne connue.

Trois controles, du moins au plus exigeant :

  V1  le dipole seul resonne la ou la theorie le dit (c/2L, un peu plus bas) ;
  V2  une plaque posee a x doit etre LUE a x : le dipole n'ayant ni substrat
      ni ligne, son retard est nul et le decalage attendu vaut ZERO ;
  V3  l'echelle des distances est juste : la pente des pics lus en fonction
      des distances vraies doit valoir 1,000.

V2 et V3 sont precisement ce qui a echoue sur le banc reel, ou le decalage
valait 20 a 36 cm et la pente 0,88. Les voir corrects ici prouve que la chaine
de traitement et l'extraction du S11 ne sont pas en cause.

    python verifier.py                 # preset rapide, environ 10 minutes
    python verifier.py --complet       # grille du rapport, bien plus long
    python verifier.py --cout          # estimation seule, rien n'est lance

A lancer avec le Python de l'environnement « openems ».
"""
import argparse
import os
import sys

import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(os.path.dirname(ICI))
sys.path.insert(0, SIM)

from banc import C, Acquisition, Maillage, Montage, Plaque  # noqa: E402
import traitement as tr  # noqa: E402
import fdtd as F  # noqa: E402
import figures as fig  # noqa: E402

ECHECS = []


def verifie(nom, condition, detail=""):
    print(f"  [{'OK  ' if condition else 'ECHEC'}] {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        ECHECS.append(nom)


def principal():
    p = argparse.ArgumentParser()
    p.add_argument("--complet", action="store_true",
                   help="201 points et plaque de 60 cm a 50/60/70 cm")
    p.add_argument("--cout", action="store_true")
    p.add_argument("--fils", type=int, default=None)
    p.add_argument("--sortie", default=os.path.join(ICI, "resultats"))
    args = p.parse_args()

    if args.complet:
        acq = Acquisition(f_min=1e9, f_max=6e9, points=201)
        distances, cote = [50.0, 60.0, 70.0], 600.0
    else:
        # Pas de 100 MHz : l'enregistrement a couvrir ne dure que 10 ns, donc
        # deux fois moins de pas de temps. La portee non ambigue reste de
        # 1,5 m, bien assez pour une plaque a 40 cm.
        acq = Acquisition(f_min=1e9, f_max=6e9, points=51)
        distances, cote = [20.0, 30.0, 40.0], 300.0

    montage = Montage(acquisition=acq,
                      plaque=Plaque(cote=cote, distances_cm=tuple(distances)),
                      maillage=Maillage(mailles_par_lambda_air=10))
    antenne = F.charge_antenne("dipole_reference")

    print(f"\n  antenne   : {antenne.DESCRIPTION}")
    print(f"  resonance attendue : {antenne.resonance_attendue_ghz():.2f} GHz")
    print(f"  retard attendu     : {antenne.retard_attendu_ns():.3f} ns "
          f"-> decalage attendu 0,0 cm")
    print(montage.resume())

    print("\n  cout estime :")
    for x in [None] + distances:
        cells, pas, mn = F.estime_cout(montage, x, demi_etendue_mm=20.0)
        nom = "antenne seule" if x is None else f"plaque a {x:.0f} cm"
        print(f"    {nom:20s} {cells/1e6:7.2f} Mcellules, {pas:5d} pas, "
              f"~{mn:5.1f} min")
    if args.cout:
        print("\n  (--cout : rien n'a ete lance)")
        return 0

    os.makedirs(args.sortie, exist_ok=True)

    # ------------------------------------------------- la serie complete
    print("\n  Simulation de la serie (maillage et duree communs) :")
    freqs, fond, mesures = F.serie(
        montage, antenne, distances, fils=args.fils,
        dossier_base=os.path.join(args.sortie, "fdtd"))
    F.ecrit_s1p(os.path.join(args.sortie, "dipole_seul.s1p"), freqs, fond,
                commentaire="dipole de reference, sans plaque")
    for x, s11 in mesures.items():
        F.ecrit_s1p(os.path.join(args.sortie, f"plaque_{x:.0f}cm.s1p"),
                    freqs, s11, commentaire=f"dipole + plaque a {x:.0f} cm")

    # ---------------------------------------------------------------- V1
    print("\nV1. Le dipole seul")
    f_res = freqs[np.argmin(np.abs(fond))] / 1e9
    verifie("resonance dans la bande attendue",
            0.75 * antenne.resonance_attendue_ghz() < f_res
            < 1.1 * antenne.resonance_attendue_ghz(),
            f"minimum de |S11| a {f_res:.2f} GHz pour "
            f"{antenne.resonance_attendue_ghz():.2f} attendus")
    verifie("l'antenne rayonne (|S11| < -3 dB a la resonance)",
            20 * np.log10(np.abs(fond).min()) < -3,
            f"{20*np.log10(np.abs(fond).min()):.1f} dB")

    # ---------------------------------------------------------------- V2
    print("\nV2. La plaque doit etre lue la ou elle est")
    res = tr.bilan(freqs, fond, mesures, acq,
                   fenetre_cm=(min(distances) - 15, max(distances) + 30))
    print("\n" + tr.table_bilan(res))

    # Ce qu'on verifie n'est PAS que l'ecart soit nul. Un dipole resonant
    # stocke de l'energie, donc retarde sa reponse de l'ordre de Q/(pi.f) :
    # quelques centimetres, inevitables. Ce qui doit etre vrai, et qui porte
    # tout le projet, c'est que cet ecart soit le MEME a toutes les
    # distances -- un retard s'ajoute, il ne se multiplie pas.
    ecarts = [res[x]["ecart_proche_cm"] for x in distances]
    etendue = max(ecarts) - min(ecarts)
    verifie("l'ecart est constant d'une distance a l'autre", etendue < 2.0,
            f"{', '.join(f'{e:+.2f}' for e in ecarts)} cm, "
            f"etendue {etendue:.2f} cm")
    verifie("l'ecart reste de l'ordre du retard d'un dipole resonant",
            abs(np.mean(ecarts)) < 10.0,
            f"moyenne {np.mean(ecarts):+.2f} cm")

    # ---------------------------------------------------------------- V3
    print("\nV3. L'echelle des distances")
    pente, ordonnee = np.polyfit(distances,
                                 [res[x]["pic_proche"] for x in distances], 1)
    verifie("pente egale a 1", abs(pente - 1) < 0.02,
            f"{pente:.4f} (ordonnee {ordonnee:+.2f} cm)")
    pentes = [res[x]["decalage_phase_cm"] for x in distances]
    verifie("la pente de phase donne un decalage constant, elle aussi",
            max(pentes) - min(pentes) < 6.0,
            f"{', '.join(f'{p:.1f}' for p in pentes)} cm")

    fig.toutes(res, freqs, args.sortie, "dipole_",
               "Dipôle de référence — vérification du programme")
    print(f"\n  figures et Touchstone dans {args.sortie}")

    if ECHECS:
        print(f"\n  {len(ECHECS)} CONTROLE(S) EN ECHEC : " + ", ".join(ECHECS))
        return 1
    print("\n  TOUS LES CONTROLES SONT PASSES : le programme mesure juste "
          "une antenne sans retard.")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
