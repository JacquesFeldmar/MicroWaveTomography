"""Figure hors ligne du SHORT, avec axe de retard signé autour de zéro."""
from pathlib import Path
import os
import json

os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/mwt-mpl-short')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent / 'cable_court_circuit'
SOURCE = BASE / 'mesures/fond_20260919T070733_099664Z/fond.npz'


def main():
    with np.load(SOURCE, allow_pickle=False) as z:
        f = z['freqs'].copy()
        s = z['fond'].copy()
        count = len(z['sweeps_calibres'])
    df = np.diff(f)
    assert np.allclose(df, df[0], rtol=1e-9, atol=1e-3)
    phase = np.unwrap(np.angle(s)) * 180 / np.pi
    # Choix de branche à 360 degrés près, sans retirer de pente de phase.
    phase -= 360 * np.round((np.median(phase) - 180) / 360)
    nfft = len(f) * 64
    window = np.hanning(len(f))
    profile = np.abs(np.fft.fftshift(np.fft.ifft(s * window, n=nfft)))
    delay_ns = np.fft.fftshift(np.fft.fftfreq(nfft, d=df[0])) * 1e9
    relative_db = 20 * np.log10(np.maximum(profile / profile.max(), 1e-12))
    peak = float(delay_ns[np.argmax(profile)])
    cm_per_ns = 299_792_458.0 * 1e-9 * 100 / 2
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), constrained_layout=True)
    axes[0].plot(f / 1e9, 20 * np.log10(np.maximum(abs(s), 1e-15)), color='#0072B2')
    axes[0].axhline(0, color='black', ls='--', lw=1, label='SHORT idéal : 0 dB')
    axes[0].set(xlabel='Fréquence (GHz)', ylabel='Module S11 (dB)', title='Réflexion après correction SOL')
    axes[0].legend()
    axes[1].plot(f / 1e9, phase, color='#009E73')
    axes[1].axhline(180, color='black', ls='--', lw=1, label='SHORT idéal au plan SOL : 180°')
    axes[1].set(xlabel='Fréquence (GHz)', ylabel='Phase déroulée (°)', title='Phase corrigée — aucune pente retirée')
    axes[1].legend()
    ax = axes[2]
    ax.plot(delay_ns, relative_db, color='#0072B2', lw=1.8)
    ax.axvline(0, color='black', ls='--', lw=1, label='Zéro du plan SOL')
    ax.axvline(.38 * 2 / 299_792_458 * 1e9, color='#D55E00', ls=':', lw=1.6, label='+38 cm ≈ +2,54 ns')
    ax.plot(peak, 0, 'o', color='#0072B2', label=f'Maximum : {peak:+.3f} ns ({peak * cm_per_ns:+.2f} cm équiv. air)')
    ax.set(xlabel='Retard aller-retour (ns)', ylabel='Amplitude relative (dB)',
           title='Profil IFFT avec fenêtre de Hann — normalisé au maximum',
           xlim=(-4, 6), ylim=(-65, 4))
    top = ax.secondary_xaxis('top', functions=(lambda t: t * cm_per_ns, lambda d: d / cm_per_ns))
    top.set_xlabel('Distance équivalente air signée (cm)')
    ax.legend(loc='lower right', fontsize=9)
    for axis in axes:
        axis.grid(alpha=.25)
    fig.suptitle(f'Contrôle du SHORT — 19 septembre 2026, 09 h 07\n1–6 GHz · 201 points · {count} balayages · SOL du 18 septembre', fontsize=14)
    fig.supxlabel('S11 corrigé sans soustraction de fond · Retards négatifs conservés pour examiner le zéro\nLe maximum du profil ne suffit pas à valider la calibration sur toute la bande.', fontsize=9)
    out = BASE / 'figures/short_20260919T070733_099664Z_retard'
    for suffix in ('.png', '.pdf'):
        fig.savefig(out.with_suffix(suffix), dpi=180)
        print(out.with_suffix(suffix))
    plt.close(fig)
    report = dict(source=str(SOURCE),peak_delay_ns=peak,peak_equivalent_air_cm=peak * cm_per_ns,
                  min_abs_s11=float(abs(s).min()),max_abs_s11=float(abs(s).max()),
                  note='Maximum IFFT, pas une estimation de retard constant ni une incertitude.')
    out.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
