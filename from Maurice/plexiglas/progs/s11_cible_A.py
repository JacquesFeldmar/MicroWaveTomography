#!/usr/bin/env python3
"""Méthode A : profil non paramétrique, IFFT du résidu complexe avec Hann.

Acquisition avec --fond et --sol, ou relecture avec --mesure cible.npz.
Les mesures sont communes à A/B ; les résultats portent le suffixe _A.
"""
import numpy as np
from mesure_cible import arguments, obtenir_mesure, chemins_resultats
from commun import physique


def main():
    ap = arguments(__doc__)
    args = ap.parse_args()
    try:
        chemin, data = obtenir_mesure(args)
        f, residu = data["freqs"], data["residu"]
        distance, profil, pas = physique.profil_distance(f, residu, zoom=16, fenetre="hann")
        dossier, figure = chemins_resultats(args.sortie, chemin, "A")
        np.savez_compressed(dossier / "resultat_A.npz", methode="A", fichier_mesure=str(chemin),
                            freqs=f, residu=residu, distance_mm=distance, profil=profil, pas_mm=pas)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(10, 8), constrained_layout=True)
        for k, label in (("cible", "S11 avec cible"), ("fond", "Fond"), ("residu", "S11 − fond")):
            if k in data:
                axes[0].plot(f/1e9, 20*np.log10(np.maximum(abs(data[k]), 1e-15)), label=label)
        axes[0].set(xlabel="Fréquence (GHz)", ylabel="Module (dB)")
        axes[0].legend()
        axes[1].plot(distance, 20*np.log10(np.maximum(profil, 1e-15)))
        axes[1].set(xlabel="Distance équivalente air (mm)", ylabel="Écho résiduel (dB réf. 1)")
        for ax in axes:
            ax.grid(alpha=.3)
        fig.suptitle("Méthode A — soustraction complexe du fond — IFFT avec Hann")
        fig.savefig(figure, dpi=160)
        plt.close(fig)
        print(f"Résultat A : {dossier / 'resultat_A.npz'}")
        print(f"Figure : {figure}")
    except (ValueError, OSError, KeyError, ImportError) as exc:
        ap.exit(1, f"Erreur : {exc}\n")
    except KeyboardInterrupt:
        ap.exit(130, "Interrompu ; toute acquisition déjà enregistrée est conservée.\n")


if __name__ == "__main__":
    main()
