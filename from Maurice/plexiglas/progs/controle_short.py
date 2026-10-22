#!/usr/bin/env python3
"""Nouvelle acquisition SHORT corrigée par SOL, sans retrait de fond."""
import argparse
from pathlib import Path
import sys
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from commun import sol, physique
import litevna


def profil_signe(f, s):
    """Conserve les retards négatifs pour examiner un pic centré sur zéro."""
    f = np.asarray(f, float)
    s = np.asarray(s, complex)
    if (f.ndim != 1 or len(f) < 3 or s.shape != f.shape
            or not np.all(np.isfinite(f)) or not np.all(np.isfinite(s))):
        raise ValueError('Fréquences et signal finis requis, avec au moins trois points.')
    df = np.diff(f)
    if np.any(df <= 0) or not np.allclose(df, df[0], rtol=1e-9, atol=1e-3):
        raise ValueError('Grille uniforme croissante requise.')
    nfft = 16 * len(f)
    h = np.fft.fftshift(np.fft.ifft(s*np.hanning(len(f)), n=nfft))*16
    distance = np.fft.fftshift(np.fft.fftfreq(nfft, d=df[0]))*physique.c/2*100
    return distance, np.abs(h)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sol', type=Path, required=True)
    ap.add_argument('--nombre', type=int, default=20)
    ap.add_argument('--port')
    ap.add_argument('--sans-affichage', action='store_true')
    args = ap.parse_args()
    try:
        with np.load(args.sol, allow_pickle=False) as z:
            cal = {k:z[k].copy() for k in ('freqs','e00','e11','e10e01')}
        f = cal['freqs']
        profil_signe(f, -np.ones(len(f), complex))
        debut, fin, n, delta = litevna.parametres_sweep(f[0]/1e9, f[-1]/1e9, len(f), None)
        litevna.verifier_spec(debut, fin, n, args.nombre)
        grille = litevna.frequences(debut, fin, n)
        if not np.allclose(grille, f, rtol=1e-9, atol=1e-3):
            raise ValueError('La grille SOL ne peut pas être reproduite.')
        print(f'SOL : {args.sol}\nBande : {debut:g}–{fin:g} GHz ; {n} points.')
        input('Rebrancher SHORT au même plan SOL, puis appuyer sur Entrée pour mesurer... ')
        brut, temps, paquets, identite, port = litevna.acquisition(
            args.port, debut, fin, n, args.nombre, 'brut', delta_hz=delta)
        corriges = sol.applique(cal, f, brut)
        moyenne = corriges.mean(axis=0)
        d, h = profil_signe(f, moyenne)
        dossier = RACINE/'plexiglas'/'controle_short'/litevna.nom_utc('short_')
        dossier.mkdir(parents=True)
        np.savez_compressed(dossier/'short.npz', freqs=f, sweeps_bruts=brut,
                            sweeps_calibres=corriges, short=moyenne,
                            distance_cm=d, profil=h, temps=temps, paquets_usb=paquets,
                            fichier_sol=str(args.sol.resolve()), **{'sol_'+k:v for k,v in cal.items()})
        import matplotlib
        if args.sans_affichage:
            matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(3, 1, figsize=(10,9), constrained_layout=True)
        axes[0].plot(f/1e9,20*np.log10(np.maximum(abs(moyenne),1e-15)))
        axes[0].axhline(0,color='gray',ls='--')
        axes[0].set(xlabel='Fréquence (GHz)',ylabel='Module (dB)',title='SHORT idéal : 0 dB')
        axes[1].plot(f/1e9,np.angle(-moyenne,deg=True))
        axes[1].set(xlabel='Fréquence (GHz)',ylabel='Écart de phase (°)',title='Phase relative au SHORT idéal (180°)')
        axes[2].plot(d,20*np.log10(np.maximum(h,1e-15)))
        axes[2].axvline(0,color='gray',ls='--')
        axes[2].set(xlim=(-30,30),xlabel='Distance électrique signée (cm)',ylabel='IFFT (dB réf. 1)')
        for ax in axes: ax.grid(alpha=.3)
        pic=d[np.argmax(h)]
        fig.suptitle(f'Contrôle SHORT après SOL — sans soustraction de fond\nMaximum à {pic:.2f} cm ; attendu : 0 cm')
        fig.savefig(dossier/'short.png',dpi=160)
        print(f'Maximum IFFT : {pic:.2f} cm\nRésultats : {dossier}')
        print('Contrôle de répétabilité avec un étalon ayant servi à calibrer, pas validation indépendante.')
        if not args.sans_affichage: plt.show()
        plt.close(fig)
    except (ValueError, OSError, KeyError, ImportError) as exc:
        ap.exit(1,f'Erreur : {exc}\n')
    except (KeyboardInterrupt, EOFError):
        ap.exit(130,'Contrôle interrompu.\n')


if __name__ == '__main__':
    main()
