#!/usr/bin/env python3
"""Compare hors ligne l'IFFT complète à celle d'une sous-bande du même résidu."""
import argparse
from pathlib import Path
import sys

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
PROJET = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
from commun import physique


def selectionner(freqs, residu, debut, fin):
    f = np.asarray(freqs, dtype=float)
    y = np.asarray(residu, dtype=complex)
    if (f.ndim != 1 or y.shape != f.shape or len(f) < 2
            or not np.all(np.isfinite(f)) or not np.all(np.isfinite(y))):
        raise ValueError("Fréquences et résidu : vecteurs finis de même taille requis.")
    if not np.isfinite(debut) or not np.isfinite(fin) or debut >= fin:
        raise ValueError("Les bornes doivent être finies avec start < stop.")
    pas = np.diff(f)
    if np.any(pas <= 0) or not np.allclose(pas, pas[0], rtol=1e-9, atol=1e-3):
        raise ValueError("La grille doit être croissante et régulièrement espacée.")
    if debut < f[0] - 1e-3 or fin > f[-1] + 1e-3:
        raise ValueError("La bande demandée dépasse celle de l'acquisition.")
    masque = (f >= debut - 1e-3) & (f <= fin + 1e-3)
    if np.count_nonzero(masque) < 3:
        raise ValueError("Sélectionner au moins trois fréquences pour la fenêtre de Hann.")
    return f[masque], y[masque]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mesure', type=Path, help='cible.npz ; sinon dernière acquisition disponible')
    ap.add_argument('--start-ghz', type=float, default=1.)
    ap.add_argument('--stop-ghz', type=float, default=4.)
    ap.add_argument('--distance-cm', type=float, help='Distance réelle facultative pour calculer les offsets apparents')
    ap.add_argument('--sortie', type=Path, default=PROJET)
    args = ap.parse_args()
    try:
        chemin = args.mesure
        if chemin is None:
            fichiers = list((PROJET / 'mesures').glob('cible_*/cible.npz'))
            if not fichiers:
                raise ValueError("Aucune acquisition cible disponible ; préciser --mesure.")
            chemin = max(fichiers, key=lambda p: p.stat().st_mtime)
        chemin = chemin.resolve()
        if args.distance_cm is not None and (not np.isfinite(args.distance_cm) or args.distance_cm < 0):
            raise ValueError("La distance réelle doit être positive ou nulle et finie.")
        with np.load(chemin, allow_pickle=False) as z:
            f = z['freqs'].copy()
            y = z['residu'].copy()
        fs, ys = selectionner(f, y, args.start_ghz * 1e9, args.stop_ghz * 1e9)
        # Le résidu enregistré contient déjà la correction SOL et le retrait du fond.
        # Aucune normalisation spectrale ni nouvelle calibration n'est appliquée.
        d, h, pas = physique.profil_distance(f, y, zoom=16, fenetre='hann')
        ds, hs, passub = physique.profil_distance(fs, ys, zoom=16, fenetre='hann')
        nom = chemin.parent.name if chemin.name == 'cible.npz' else chemin.stem
        suffixe = f'ifft_{fs[0]/1e9:g}-{fs[-1]/1e9:g}GHz'
        dossier = args.sortie.resolve() / 'analyses' / f'{nom}_{suffixe}'
        figures = args.sortie.resolve() / 'figures'
        dossier.mkdir(parents=True, exist_ok=True)
        figures.mkdir(parents=True, exist_ok=True)
        figure = figures / f'{nom}_{suffixe}.png'
        np.savez_compressed(dossier / 'comparaison.npz', fichier_mesure=str(chemin),
                            freqs=f, residu=y, distance_mm=d, profil=h, pas_mm=pas,
                            freqs_selection=fs, residu_selection=ys, distance_selection_mm=ds,
                            profil_selection=hs, pas_selection_mm=passub, fenetre='hann')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(10, 8), constrained_layout=True)
        db = lambda a: 20 * np.log10(np.maximum(np.abs(a), 1e-15))
        ax[0].plot(f / 1e9, db(y), label='Résidu complexe enregistré : cible − fond')
        ax[0].axvspan(fs[0]/1e9, fs[-1]/1e9, alpha=.15, color='tab:orange', label='Sous-bande retenue')
        ax[0].set(xlabel='Fréquence (GHz)', ylabel='Module (dB réf. 1)')
        lignes = []
        for ff, dd, hh, nom_bande, color in ((f, d, h, 'complète', 'tab:blue'),
                                           (fs, ds, hs, 'sélection', 'tab:orange')):
            pic = int(np.argmax(hh))
            pic_cm = float(dd[pic]/10)
            label = f'{ff[0]/1e9:g}–{ff[-1]/1e9:g} GHz ({len(ff)} points)'
            ax[1].plot(dd/10, db(hh), label=label, color=color)
            ax[1].plot(pic_cm, db(hh[pic]), 'o', color=color)
            offset = None if args.distance_cm is None else pic_cm - args.distance_cm
            print(f'{label} : maximum à {pic_cm:.2f} cm'
                  + ('' if offset is None else f' ; offset apparent {offset:+.2f} cm'))
            lignes.append((nom_bande, ff[0], ff[-1], len(ff), pic_cm, offset))
        if args.distance_cm is not None:
            ax[1].axvline(args.distance_cm, color='black', ls=':', label='Distance réelle')
        ax[1].set(xlabel='Distance équivalente air (cm)', ylabel='Écho résiduel (dB réf. 1)')
        for a in ax:
            a.grid(alpha=.3)
            a.legend(fontsize=9)
        fig.suptitle('Même acquisition et même fond — comparaison IFFT avec Hann\n'
                     'Amplitudes sans normalisation au maximum ; une sous-bande élargit les pics')
        fig.savefig(figure, dpi=160)
        plt.close(fig)
        with (dossier / 'pics.csv').open('w') as out:
            out.write('bande,debut_hz,fin_hz,points,pic_cm,offset_apparent_cm\n')
            for ligne in lignes:
                out.write(','.join('' if v is None else str(v) for v in ligne) + '\n')
        print(f'Mesure utilisée : {chemin}')
        print(f'Figure : {figure}')
        print(f'Résultats : {dossier}')
        print("Le maximum global n'est pas nécessairement l'écho de la cible. "
              "La sélection de bande modifie aussi la résolution et la pondération.")
    except (ValueError, OSError, KeyError, ImportError) as exc:
        ap.exit(1, f'Erreur : {exc}\n')


if __name__ == '__main__':
    main()
