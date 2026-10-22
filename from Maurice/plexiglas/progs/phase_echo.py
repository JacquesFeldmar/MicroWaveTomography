#!/usr/bin/env python3
"""Phase du résidu après retrait du trajet aller-retour vers une cible connue."""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

C = 299792458.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mesure', nargs=2, action='append', required=True,
                    metavar=('FICHIER_NPZ', 'DISTANCE_CM'))
    ap.add_argument('--sortie', type=Path, default=Path('plexiglas/figures/phase_echo.png'))
    args = ap.parse_args()
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), constrained_layout=True)
    rows = []
    for fichier, distance in args.mesure:
        d = float(distance) / 100
        with np.load(fichier, allow_pickle=False) as z:
            f = np.asarray(z['freqs'], float)
            r = np.asarray(z['residu'], complex)
        if len(f) < 3 or f.shape != r.shape or not np.all(np.isfinite(r)) or not np.all(np.diff(f) > 0):
            raise ValueError('Grille ou résidu invalide')
        h = r * np.exp(4j * np.pi * f * d / C)
        amplitude = np.abs(h)
        phase = np.unwrap(np.angle(h))
        # Pondération en puissance : les points proches d'un zéro ont une phase fragile.
        poids = amplitude**2
        if poids.max() == 0:
            raise ValueError('Résidu nul : phase indéfinie')
        poids /= poids.max()
        x = f / 1e9
        centre = np.average(x, weights=poids)
        slope, intercept = np.polynomial.polynomial.polyfit(x-centre, phase, 1, w=np.sqrt(poids))[::-1]
        fit = intercept + slope * (x-centre)
        retard_ns = -slope / (2*np.pi)
        offset_cm = C * retard_ns * 1e-9 / 2 * 100
        label = f'Cible à {d*100:g} cm'
        line, = axes[0].plot(x, 20*np.log10(np.maximum(amplitude, 1e-15)), label=label)
        color = line.get_color()
        axes[1].plot(x, np.degrees(phase), color=color, label=label)
        axes[1].plot(x, np.degrees(fit), '--', color=color, alpha=.7,
                     label=f'Pente globale : équivalent {offset_cm:.1f} cm')
        axes[2].plot(x, np.degrees(phase-fit), color=color, label=label)
        rows.append((fichier, d*100, retard_ns, offset_cm))
    axes[0].set(ylabel='Module du résidu (dB réf. 1)', title='Amplitude : la phase est fragile près des creux')
    axes[1].set(ylabel='Phase déroulée (°)', title='Phase après retrait du trajet géométrique aller-retour')
    axes[2].set(ylabel='Écart à la droite (°)', title='Écart à une réponse de retard constant')
    for ax in axes:
        ax.set_xlabel('Fréquence (GHz)')
        ax.grid(alpha=.3)
        ax.legend(fontsize=8)
    fig.suptitle('Écho cible − fond : phase résiduelle\nInclut antenne aller-retour, cible et trajets supplémentaires')
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.sortie, dpi=160)
    plt.close(fig)
    import csv
    with args.sortie.with_suffix('.csv').open('w', newline='') as out:
        writer = csv.writer(out)
        writer.writerow(['mesure','distance_cm','retard_residuel_ns','offset_pente_cm'])
        writer.writerows(rows)
    for _, d, tau, offset in rows:
        print(f'Cible {d:g} cm : retard résiduel {tau:.3f} ns ; offset de pente {offset:.1f} cm')
    print(f'Figure : {args.sortie.resolve()}')


if __name__ == '__main__':
    main()
