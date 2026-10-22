#!/usr/bin/env python3
"""Calibration SOL interactive du LiteVNA au bout du câble.

Le LiteVNA est lu en mode brut pour que la correction soit calculée ici. Le
programme règle START, STOP, le pas et le nombre de points par USB, puis demande
successivement SHORT, OPEN et LOAD, moyenne plusieurs sweeps de chaque étalon,
résout e00/e11/e10.e01 et écrit un fichier utilisable par les deux programmes
suivants. La charge LOAD reste branchée pour une nouvelle acquisition de
contrôle : le TOS corrigé est enregistré et affiché en fin de programme.

Exemple :
  python plexiglas/progs/calibration_sol.py --start-ghz 1 --stop-ghz 6.6 \
      --delta-mhz 28 --nombre 8
"""

import argparse
from pathlib import Path
import sys

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
PROJET = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from commun.sol import (ETALONS_IDEAUX, gamma_load, gamma_open, gamma_short,
                        resoudre, applique)  # noqa: E402
import litevna  # noqa: E402
from tos import calculer_tos  # noqa: E402


def resume_etalon(nom, sweeps):
    """Affiche un contrôle rapide après l'acquisition d'un étalon."""
    moyenne = sweeps.mean(axis=0)
    module_db = 20 * np.log10(np.maximum(np.abs(moyenne), 1e-15))
    dispersion = np.sqrt(np.mean(np.abs(sweeps - moyenne) ** 2))
    dispersion_db = 20 * np.log10(max(float(dispersion), 1e-15))
    print(f"  Résultat {nom} :")
    print(f"    |S11| médian sur la bande : {np.median(module_db):.2f} dB "
          f"(min {module_db.min():.2f}, max {module_db.max():.2f} dB)")
    print(f"    dispersion entre sweeps  : {dispersion:.3g} "
          f"({dispersion_db:.2f} dB réf. 1 RMS)")


def tracer_tos_charge(freqs, sweeps_corriges, figure, afficher=True):
    """Trace le TOS de la moyenne complexe et les quantiles entre sweeps."""
    import matplotlib
    if not afficher:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tos_moyen = calculer_tos(sweeps_corriges.mean(axis=0))
    tos_sweeps = calculer_tos(sweeps_corriges)
    # Une fréquence avec un sweep hors domaine est omise de l'enveloppe.
    # Ne pas ramener artificiellement |S11| à une valeur inférieure à 1.
    valides = np.all(np.isfinite(tos_sweeps), axis=0)
    q05 = np.full(len(freqs), np.nan)
    q95 = np.full(len(freqs), np.nan)
    if np.any(valides):
        q05[valides], q95[valides] = np.quantile(
            tos_sweeps[:, valides], (0.05, 0.95), axis=0)
    invalides = np.count_nonzero(~np.isfinite(tos_sweeps))
    moyennes_invalides = np.count_nonzero(~np.isfinite(tos_moyen))

    fig, ax = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
    try:
        x = freqs / 1e9
        ax.plot(x, tos_moyen, label="TOS de la moyenne complexe", lw=2)
        if len(sweeps_corriges) > 1:
            ax.fill_between(x, q05, q95, alpha=.22,
                            label="Quantiles 5–95 % du TOS entre sweeps")
        ax.axhline(1, color="gray", ls="--", lw=1, label="Charge idéale : TOS = 1")
        ax.set(xlabel="Fréquence (GHz)", ylabel="TOS (sans dimension)",
               title=f"Charge 50 Ω après calibration SOL — {len(sweeps_corriges)} nouveaux sweeps")
        ax.grid(alpha=.3)
        ax.legend(fontsize=9)
        # Garder une échelle lisible quand le résidu est très proche de zéro.
        bas, haut = ax.get_ylim()
        ax.set_ylim(min(bas, .999), max(haut, 1.01))
        note = "Contrôle de répétabilité avec la même charge que pour la calibration."
        if invalides or moyennes_invalides:
            note += (f"\nTOS non fini ou |S11| ≥ 1 : {invalides} points de sweeps "
                     f"et {moyennes_invalides} points moyens omis.")
        fig.supxlabel(note, fontsize=9)
        fig.savefig(figure, dpi=160)
        print(f"Graphique du TOS enregistré : {figure}")
        if invalides or moyennes_invalides:
            print(note.split("\n")[-1])
        if afficher:
            plt.show()
    finally:
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--debut-ghz", "--start-ghz", dest="debut_ghz",
                    type=float, required=True)
    ap.add_argument("--fin-ghz", "--stop-ghz", dest="fin_ghz",
                    type=float, required=True)
    ap.add_argument("--points", type=int)
    ap.add_argument("--delta-mhz", type=float,
                    help="Pas de fréquence programmé dans le VNA")
    ap.add_argument("--nombre", type=int, default=8,
                    help="Sweeps moyennés par étalon (défaut : 8)")
    ap.add_argument("--nombre-verification", type=int, default=100,
                    help="Nouveaux sweeps sur LOAD après calibration (défaut : 100)")
    ap.add_argument("--sans-affichage", action="store_true",
                    help="Enregistrer le graphique du TOS sans ouvrir de fenêtre")
    ap.add_argument("--sortie", type=Path, default=PROJET / "calibration")
    args = ap.parse_args()
    calibration_enregistree = None
    try:
        args.debut_ghz, args.fin_ghz, args.points, delta_hz = litevna.parametres_sweep(
            args.debut_ghz, args.fin_ghz, args.points, args.delta_mhz)
        litevna.verifier_spec(args.debut_ghz, args.fin_ghz, args.points, args.nombre)
        litevna.verifier_spec(args.debut_ghz, args.fin_ghz, args.points,
                             args.nombre_verification)
        f = litevna.frequences(args.debut_ghz, args.fin_ghz, args.points)
        print("Le programme va régler le LiteVNA par USB avec cette grille.")
        print(f"  START={args.debut_ghz:g} GHz, STOP={args.fin_ghz:g} GHz, "
              f"Δf={delta_hz / 1e6:g} MHz, {args.points} points.")
        print("La calibration précédente n'est pas utilisée : lecture USB brute.")
        mesures, sweeps, temps, paquets, identite, port = [], [], [], [], None, None
        for code, nom in (("S", "SHORT"), ("O", "OPEN"), ("L", "LOAD")):
            input(f"[{code}] Connecter {nom} au bout du câble, puis appuyer sur Entrée...")
            s, t, p, identite, port = litevna.acquisition(
                args.port, args.debut_ghz, args.fin_ghz, args.points,
                args.nombre, "brut", delta_hz=delta_hz)
            sweeps.append(s)
            mesures.append(s.mean(axis=0))
            temps.append(t)
            paquets.append(p)
            print(f"  {nom} acquis : {len(s)} sweeps.")
            resume_etalon(nom, s)
        ideaux = [gamma_short(f, ETALONS_IDEAUX),
                  gamma_open(f, ETALONS_IDEAUX),
                  gamma_load(f, ETALONS_IDEAUX)]
        coefs, conds = resoudre(ideaux, mesures)
        if not np.all(np.isfinite(conds)):
            raise ValueError("Système SOL mal conditionné ou valeurs non finies.")
        args.sortie.mkdir(parents=True, exist_ok=True)
        chemin = args.sortie / litevna.nom_utc("sol_")
        chemin = chemin.with_suffix(".npz")
        np.savez_compressed(
            chemin, freqs=f, **coefs, conds=conds,
            brut_short=mesures[0], brut_open=mesures[1], brut_load=mesures[2],
            sweeps_short=sweeps[0], sweeps_open=sweeps[1], sweeps_load=sweeps[2],
            temps_short=temps[0], temps_open=temps[1], temps_load=temps[2],
            paquets_short=paquets[0], paquets_open=paquets[1], paquets_load=paquets[2],
            etalons=np.array(["short=ideal", "open=ideal", "load=ideal"]),
            correction="SOL_logicielle",
            port=port, usb_firmware_majeur=identite["firmware_majeur"],
            usb_firmware_mineur=identite["firmware_mineur"])
        calibration_enregistree = chemin
        print(f"\nCalibration SOL enregistrée : {chemin}")
        print(f"Condition médiane/maximale : {np.median(conds):.3g}/{np.max(conds):.3g}")
        print("Coefficients corrigés (médiane sur la bande) : "
              f"|e00|={np.median(np.abs(coefs['e00'])):.3g}, "
              f"|e11|={np.median(np.abs(coefs['e11'])):.3g}, "
              f"|e10e01|={np.median(np.abs(coefs['e10e01'])):.3g}")
        if np.max(conds) > 1e6:
            print("ATTENTION : calibration mal conditionnée ; vérifier les "
                  "branchements SHORT/OPEN/LOAD et refaire la mesure.")
        print(f"\nLaisser la charge LOAD branchée : contrôle automatique "
              f"sur {args.nombre_verification} nouveaux sweeps.")
        controle, t_controle, p_controle, _, _ = litevna.acquisition(
            port, args.debut_ghz, args.fin_ghz, args.points,
            args.nombre_verification, "brut", delta_hz=delta_hz)
        corriges = applique(dict(freqs=f, **coefs), f, controle)
        verification = chemin.with_name(chemin.stem + "_verification_load.npz")
        np.savez_compressed(
            verification, freqs=f, sweeps_bruts=controle,
            sweeps_corriges=corriges, moyenne_corrigee=corriges.mean(axis=0),
            temps=t_controle, paquets_usb=p_controle,
            fichier_sol=str(chemin.resolve()), correction="SOL_logicielle",
            etalon="load", acquisition="controle_apres_calibration")
        print(f"Contrôle LOAD enregistré : {verification}")
        resume_etalon("LOAD après correction SOL", corriges)
        print("Ne pas déplacer le câble entre cette calibration et l'antenne.")
        tracer_tos_charge(f, corriges, chemin.with_name(chemin.stem + "_tos_load.png"),
                         afficher=not args.sans_affichage)
    except (ValueError, OSError, KeyError, ImportError) as exc:
        if calibration_enregistree is not None:
            print(f"Calibration déjà enregistrée et conservée : {calibration_enregistree}")
        ap.exit(1, f"Erreur : {exc}\n")
    except KeyboardInterrupt:
        if calibration_enregistree is not None:
            ap.exit(130, f"Contrôle interrompu ; calibration conservée : "
                        f"{calibration_enregistree}\n")
        ap.exit(130, "Calibration interrompue ; fichier non écrit.\n")


if __name__ == "__main__":
    main()
