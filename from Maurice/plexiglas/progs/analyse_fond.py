#!/usr/bin/env python3
"""Acquiert et analyse le fond S11 avec l'antenne reconnectée, sans cible.

Deux corrections sont possibles : ``--sol fichier.npz`` lit le LiteVNA en brut
et applique la SOL enregistrée par calibration_sol.py ; ``--interne`` demande au
firmware sa correction active C0. Ne pas utiliser les deux à la fois.
Le TOS de l'antenne est calculé sur ces mêmes sweeps corrigés, sans soustraction
du fond. Son graphique est enregistré et affiché à la fin de l'acquisition.

Exemple logiciel :
  python plexiglas/progs/analyse_fond.py --start-ghz 1 --stop-ghz 6.6 \
      --delta-mhz 28 --nombre 100 --sol plexiglas/calibration/sol_DATE.npz
Exemple correction interne :
  python plexiglas/progs/analyse_fond.py --start-ghz 1 --stop-ghz 6.6 \
      --delta-mhz 28 --nombre 100 --interne
"""

import argparse
from pathlib import Path
import sys

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
PROJET = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from commun import sol  # noqa: E402
import litevna  # noqa: E402
from tos import calculer_tos  # noqa: E402


def charger_sol(chemin):
    with np.load(chemin, allow_pickle=False) as z:
        return {k: z[k].copy() for k in ("freqs", "e00", "e11", "e10e01")}


def appliquer(f, sweeps, cal):
    if len(f) != len(cal["freqs"]) or not np.allclose(f, cal["freqs"], rtol=1e-9, atol=1e-3):
        raise ValueError("La grille de mesure ne correspond pas à la calibration SOL.")
    return sol.applique(cal, f, sweeps)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--debut-ghz", "--start-ghz", dest="debut_ghz",
                    type=float, required=True)
    ap.add_argument("--fin-ghz", "--stop-ghz", dest="fin_ghz",
                    type=float, required=True)
    ap.add_argument("--points", type=int)
    ap.add_argument("--delta-mhz", type=float,
                    help="Pas de fréquence programmé dans le VNA")
    ap.add_argument("--nombre", type=int, default=100)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sol", type=Path)
    mode.add_argument("--interne", action="store_true")
    ap.add_argument("--sans-affichage", action="store_true",
                    help="Enregistrer les figures sans ouvrir la fenêtre du TOS")
    ap.add_argument("--sortie", type=Path, default=PROJET)
    args = ap.parse_args()
    fond_enregistre = None
    try:
        args.debut_ghz, args.fin_ghz, args.points, delta_hz = litevna.parametres_sweep(
            args.debut_ghz, args.fin_ghz, args.points, args.delta_mhz)
        litevna.verifier_spec(args.debut_ghz, args.fin_ghz, args.points, args.nombre)
        cal = None if args.interne else charger_sol(args.sol)
        mode_usb = "interne" if args.interne else "brut"
        correction = "SOL logicielle" if cal is not None else "interne C0"
        f = litevna.frequences(args.debut_ghz, args.fin_ghz, args.points)
        print("Rebrancher l'antenne avant de lancer ce programme ; garder le câble immobile.")
        print("Sans cible : ne rien déplacer devant l'antenne pendant l'acquisition.")
        print(f"START={args.debut_ghz:g} GHz, STOP={args.fin_ghz:g} GHz, "
              f"Δf={delta_hz / 1e6:g} MHz, {args.points} points.")
        s, temps, paquets, identite, port = litevna.acquisition(
            args.port, args.debut_ghz, args.fin_ghz, args.points,
            args.nombre, mode_usb, delta_hz=delta_hz)
        if cal is not None:
            s_brut, s = s.copy(), appliquer(f, s, cal)
        else:
            s_brut = np.empty((0, len(f)), complex)
        fond = s.mean(axis=0)
        sigma = s.std(axis=0, ddof=1) if len(s) > 1 else np.full(len(f), np.nan)
        modules = np.abs(s)
        q05, q95 = np.quantile(modules, (0.05, 0.95), axis=0)
        tos_moyen = calculer_tos(fond)
        tos_sweeps = calculer_tos(s)
        valides = np.all(np.isfinite(tos_sweeps), axis=0)
        tos_q05 = np.full(len(f), np.nan)
        tos_q95 = np.full(len(f), np.nan)
        if np.any(valides):
            tos_q05[valides], tos_q95[valides] = np.quantile(
                tos_sweeps[:, valides], (0.05, 0.95), axis=0)
        tos_invalides = np.count_nonzero(~np.isfinite(tos_sweeps))
        tos_moyennes_invalides = np.count_nonzero(~np.isfinite(tos_moyen))
        phases = np.angle(s)
        resultant = np.abs(np.mean(np.exp(1j * phases), axis=0))
        phase_std_deg = np.degrees(np.sqrt(np.maximum(-2 * np.log(
            np.maximum(resultant, 1e-15)), 0)))
        rms_sweep = np.sqrt(np.mean(np.abs(s - fond) ** 2, axis=1))
        nom = litevna.nom_utc("fond_")
        mesures = args.sortie.resolve() / "mesures" / nom
        mesures.mkdir(parents=True, exist_ok=False)
        (args.sortie / "figures").mkdir(parents=True, exist_ok=True)
        meta = dict(freqs=f, sweeps_calibres=s, fond=fond, sigma_complexe=sigma,
                    module_q05=q05, module_q95=q95,
                    tos_moyen=tos_moyen, tos_q05=tos_q05, tos_q95=tos_q95,
                    phase_std_deg=phase_std_deg, rms_sweep=rms_sweep,
                    temps=temps, simulation=False, etat_s11="SOL_corrige",
                    correction_mode=mode_usb, port=port,
                    **{"usb_" + k: v for k, v in identite.items()})
        if len(s_brut):
            meta["sweeps_bruts"] = s_brut
        if cal is not None:
            meta.update({"sol_" + k: v for k, v in cal.items()})
        np.savez_compressed(mesures / "fond.npz", **meta, paquets_usb=paquets)
        fond_enregistre = mesures / "fond.npz"
        np.savetxt(mesures / "dispersion.csv",
                   np.column_stack((f, fond.real, fond.imag, abs(fond), sigma)),
                   delimiter=",", comments="",
                   header="frequence_hz,fond_reel,fond_imag,module,sigma_complexe")
        import matplotlib
        if args.sans_affichage:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 2, figsize=(12, 8),
                                 constrained_layout=True)
        x = f / 1e9
        ax = axes[0, 0]
        ax.plot(x, 20*np.log10(np.maximum(abs(fond), 1e-15)),
                     label="moyenne complexe")
        ax.fill_between(
            x, 20*np.log10(np.maximum(q05, 1e-15)),
            20*np.log10(np.maximum(q95, 1e-15)), alpha=.25,
            label="quantiles 5–95 % des modules")
        ax.set_ylabel("S11 (dB)")
        ax.set_title("Module du fond")
        ax.legend(fontsize=8)

        ax = axes[0, 1]
        ax.plot(x, 20*np.log10(np.maximum(sigma, 1e-15)),
                label="dispersion entre sweeps")
        ax.plot(x, 20*np.log10(np.maximum(sigma / np.sqrt(len(s)), 1e-15)),
                label="erreur-type (hypothèse iid)")
        ax.set_ylabel("Amplitude (dB réf. 1)")
        ax.set_title("Dispersion fréquentielle")
        ax.legend(fontsize=8)

        ax = axes[1, 0]
        ax.plot(x, phase_std_deg)
        ax.set_xlabel("Fréquence (GHz)")
        ax.set_ylabel("Écart-type circulaire (°)")
        ax.set_title("Dispersion de phase")

        ax = axes[1, 1]
        ax.plot(temps, rms_sweep, marker=".", ms=3)
        ax.set_xlabel("Temps écoulé (s)")
        ax.set_ylabel("RMS complexe de S11")
        ax.set_title("Stabilité au cours des sweeps")

        for ax in axes.flat:
            ax.grid(alpha=.3)
        fig.suptitle(f"Fond sans cible — {len(s)} sweeps — correction {correction}")
        figure = args.sortie.resolve() / "figures" / (nom + ".png")
        fig.savefig(figure, dpi=160)
        plt.close(fig)
        print(f"Fond enregistré : {mesures / 'fond.npz'}")
        print(f"Figure : {figure}")

        figure_tos = figure.with_name(nom + "_tos.png")
        fig_tos, ax = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
        try:
            ax.plot(x, tos_moyen, lw=2, label="TOS de la moyenne complexe")
            if len(s) > 1:
                ax.fill_between(x, tos_q05, tos_q95, alpha=.22,
                                label="Quantiles 5–95 % du TOS entre sweeps")
            ax.axhline(1, color="gray", ls="--", lw=1,
                       label="Adaptation idéale : TOS = 1")
            ax.set(xlabel="Fréquence (GHz)", ylabel="TOS (sans dimension)",
                   xlim=(x[0], x[-1]),
                   title=f"TOS de l'antenne sans cible — {x[0]:g} à {x[-1]:g} GHz"
                         f"\n{len(s)} sweeps — correction {correction}")
            ax.grid(alpha=.3)
            ax.legend(fontsize=9)
            bas, haut = ax.get_ylim()
            ax.set_ylim(min(bas, .999), max(haut, 1.01))
            note = "TOS = (1 + |S11|) / (1 − |S11|) ; avant soustraction du fond."
            if tos_invalides or tos_moyennes_invalides:
                avertissement = (f"TOS non fini ou |S11| ≥ 1 : {tos_invalides} points "
                                 f"de sweeps et {tos_moyennes_invalides} points moyens omis.")
                note += "\n" + avertissement
                print(avertissement)
            fig_tos.supxlabel(note, fontsize=9)
            fig_tos.savefig(figure_tos, dpi=160)
            print(f"Graphique du TOS de l'antenne : {figure_tos}")
            if not args.sans_affichage:
                plt.show()
        finally:
            plt.close(fig_tos)
    except (ValueError, OSError, KeyError, ImportError) as exc:
        ap.exit(1, f"Erreur : {exc}\n")
    except KeyboardInterrupt:
        if fond_enregistre is not None:
            ap.exit(130, f"Affichage ou analyse interrompu ; fond conservé : {fond_enregistre}\n")
        ap.exit(130, "Acquisition interrompue ; fond incomplet non enregistré.\n")


if __name__ == "__main__":
    main()
