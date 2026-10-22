#!/usr/bin/env python3
"""Méthode B : ajustement paramétrique des S11 complexes après retrait du fond.

--modele echos (défaut) : retards et gains complexes de 1 à 4 contributions.
--modele plaque : épaisseur e, amplitude arrière alpha, retard et gain libres,
avec indice connu. La réponse fréquentielle de l'antenne n'est pas calibrée.
Acquisition avec --fond/--sol, ou traitement hors ligne avec --mesure cible.npz.
"""
import json
import numpy as np
from mesure_cible import arguments, obtenir_mesure, chemins_resultats, variance_moyenne
from ajustement_B import ajuster_echos, ajuster_plaque


def serialisable(value):
    if isinstance(value, np.ndarray):
        return serialisable(value.tolist())
    if isinstance(value, complex):
        return {"reel": value.real, "imag": value.imag}
    if isinstance(value, np.generic):
        return serialisable(value.item())
    if isinstance(value, dict):
        return {k: serialisable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialisable(v) for v in value]
    return value


def graphique(f, y, fit, figure):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    modele = fit["modele_complexe"]
    x = f/1e9
    for z, label in ((y, "S11 − fond mesuré"), (modele, "Modèle B ajusté"),
                     (y-modele, "Erreur complexe du modèle")):
        axes[0, 0].plot(x, 20*np.log10(np.maximum(abs(z), 1e-15)), label=label)
    axes[0, 0].set(xlabel="Fréquence (GHz)", ylabel="Module (dB réf. 1)")
    for ax, composante, titre in ((axes[0, 1], np.real, "Partie réelle"),
                                   (axes[1, 0], np.imag, "Partie imaginaire")):
        ax.plot(x, composante(y), label="Mesure")
        ax.plot(x, composante(modele), "--", label="Modèle B")
        ax.set(xlabel="Fréquence (GHz)", ylabel=titre)
    ax = axes[1, 1]
    if fit["modele"] == "echos":
        amplitudes = abs(fit["gains"])
        libelles = [f"Écho {j+1}" for j in range(len(amplitudes))]
    else:
        r = (1-fit["indice"])/(1+fit["indice"])
        amplitudes = abs(fit["gains"][0])*np.array([abs(r), fit["alpha"]*abs((1-r*r)*r)])
        libelles = ["Face avant", "Face arrière (distance optique)"]
    db = 20*np.log10(np.maximum(amplitudes, 1e-15))
    bas = float(min(db.min()-15, -80))
    for d, niveau, label in zip(fit["distances_cm"], db, libelles):
        ax.vlines(d, bas, niveau)
        ax.plot(d, niveau, "o", label=f"{label} : {d:.2f} cm")
    ax.set(xlabel="Distance apparente ajustée (cm)", ylabel="Amplitude ajustée (dB réf. 1)",
           title="Paramètres du modèle B — sans IFFT", ylim=(bas, max(db)+10))
    for ax in axes.flat:
        ax.grid(alpha=.3)
        ax.legend(fontsize=8)
    note = f"Résidu RMS relatif : {100*fit['erreur_rms_relative']:.1f} %"
    if fit["chi2_reduit"] is not None:
        note += f" ; χ² réduit (bruit iid estimé) : {fit['chi2_reduit']:.1f}"
    if fit["modele"] == "plaque":
        note += f"\ne = {fit['epaisseur_mm']:.3f} mm ; α = {fit['alpha']:.3f} ; n = {fit['indice']:.3f}"
    fig.suptitle(f"Méthode B — modèle {fit['modele']}\n{note}")
    fig.supxlabel("Distances apparentes : retard de l'antenne inclus. Un écho ajusté n'identifie pas à lui seul un trajet physique.", fontsize=9)
    fig.savefig(figure, dpi=160)
    plt.close(fig)


def main():
    ap = arguments(__doc__)
    ap.add_argument("--modele", choices=("echos", "plaque"), default="echos")
    ap.add_argument("--echos", type=int, choices=range(1, 5), default=2)
    ap.add_argument("--distance-min-cm", type=float, default=0.)
    ap.add_argument("--distance-max-cm", type=float, default=150.)
    ap.add_argument("--indice", type=float, help="Indice réel connu, requis pour --modele plaque")
    ap.add_argument("--epaisseur-min-mm", type=float, default=1.)
    ap.add_argument("--epaisseur-max-mm", type=float, default=40.)
    ap.add_argument("--alpha-max", type=float, default=2.)
    ap.add_argument("--ponderation", choices=("uniforme", "bruit"), default="uniforme")
    args = ap.parse_args()
    try:
        if args.modele == "plaque":
            if args.indice is None or not np.isfinite(args.indice) or args.indice <= 1:
                raise ValueError("--indice réel fini > 1 requis pour la plaque diélectrique.")
            if (not np.isfinite([args.epaisseur_min_mm, args.epaisseur_max_mm, args.alpha_max]).all()
                    or not 0 < args.epaisseur_min_mm < args.epaisseur_max_mm or args.alpha_max <= 0):
                raise ValueError("Bornes d'épaisseur/alpha invalides.")
        if not np.isfinite([args.distance_min_cm, args.distance_max_cm]).all() or not 0 <= args.distance_min_cm < args.distance_max_cm:
            raise ValueError("Intervalle de distance invalide.")
        chemin, data = obtenir_mesure(args)
        f, y = data["freqs"], data["residu"]
        variance = variance_moyenne(data, args.fond if args.mesure else None)
        options = dict(bornes=(args.distance_min_cm, args.distance_max_cm),
                       variance=variance, ponderation=args.ponderation)
        if args.modele == "echos":
            fit = ajuster_echos(f, y, nombre=args.echos, **options)
            suffixe = f"B_echos{args.echos}"
        else:
            fit = ajuster_plaque(f, y, args.indice,
                                 epaisseurs=(args.epaisseur_min_mm, args.epaisseur_max_mm),
                                 alpha_max=args.alpha_max, **options)
            suffixe = "B_plaque"
        dossier, figure = chemins_resultats(args.sortie, chemin, suffixe)
        tableaux = {k: v for k, v in fit.items() if isinstance(v, np.ndarray)}
        if variance is not None:
            tableaux["variance_moyenne"] = variance
        np.savez_compressed(dossier / "resultat_B.npz", methode="B", freqs=f, residu=y,
                            fichier_mesure=str(chemin), **tableaux)
        rapport = dict(methode="B", fichier_mesure=str(chemin), ponderation=args.ponderation,
                       domaine_distance_cm=list(options["bornes"]),
                       bruit="CN propre, covariance diagonale estimée, sweeps indépendants",
                       **{k: v for k, v in fit.items() if k not in ("modele_complexe", "erreur_complexe")})
        if args.modele == "plaque":
            rapport.update(domaine_epaisseur_mm=[args.epaisseur_min_mm, args.epaisseur_max_mm],
                           domaine_alpha=[0., args.alpha_max])
        (dossier / "resultat_B.json").write_text(json.dumps(serialisable(rapport), ensure_ascii=False,
                                                           indent=2, allow_nan=False)+"\n", encoding="utf-8")
        np.savetxt(dossier / "ajustement_B.csv",
                   np.column_stack((f, y.real, y.imag, fit["modele_complexe"].real,
                                    fit["modele_complexe"].imag, fit["erreur_complexe"].real,
                                    fit["erreur_complexe"].imag)), delimiter=",",
                   header="frequence_hz,mesure_reel,mesure_imag,modele_reel,modele_imag,erreur_reel,erreur_imag")
        graphique(f, y, fit, figure)
        print("Distances apparentes B (cm) : " + ", ".join(f"{d:.3f}" for d in fit["distances_cm"]))
        if args.modele == "plaque":
            print(f"e = {fit['epaisseur_mm']:.4f} mm ; alpha = {fit['alpha']:.4f}")
        print(f"Résidu RMS relatif : {100*fit['erreur_rms_relative']:.1f} %")
        for avertissement in fit["avertissements"]:
            print(avertissement)
        print(f"Résultat B : {dossier / 'resultat_B.json'}")
        print(f"Figure : {figure}")
    except (ValueError, OSError, KeyError, ImportError, np.linalg.LinAlgError) as exc:
        ap.exit(1, f"Erreur : {exc}\n")
    except KeyboardInterrupt:
        ap.exit(130, "Interrompu ; toute acquisition déjà enregistrée est conservée.\n")


if __name__ == "__main__":
    main()
