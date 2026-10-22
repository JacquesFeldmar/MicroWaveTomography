from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
figures = sorted((ROOT/'plexiglas/figures').glob('cible_20260930*_A.png'))
paths = [ROOT/'plexiglas/mesures'/p.stem.removesuffix('_A')/'cible.npz' for p in figures]
assert paths, 'Aucune figure cible disponible'
fig, axes = plt.subplots(2, 1, figsize=(12, 9), constrained_layout=True)
rows = []
reference = None
for j, path in enumerate(paths):
    with np.load(path) as z:
        current = {k: z[k].copy() for k in ('freqs','fond','sol_e00','sol_e11','sol_e10e01')}
        if reference is None:
            reference = current
        assert all(np.array_equal(current[k],reference[k]) for k in current), 'Grille, fond ou SOL différents'
        n = len(z['sweeps_calibres'])
    with np.load(ROOT/'plexiglas/analyses'/(path.parent.name+'_A')/'resultat_A.npz') as z:
        d = z['distance_mm']/10
        a = z['profil']
        db = 20*np.log10(np.maximum(a,1e-15))
        i = np.argmax(a)
        peaks = sorted(find_peaks(a)[0], key=lambda k:a[k], reverse=True)[:3]
        label = f'C{j+1}'
        for ax in axes:
            ax.plot(d,db,label=label)
        axes[0].plot(d[i],db[i],'o',color=f'C{j}')
        rows.append([label,path.parent.name,n,float(d[i]),float(db[i])])
        print(label, path.parent.name, 'balayages', n, 'pics (cm, dB):', [(round(d[k],2),round(db[k],2)) for k in peaks])
for ax in axes:
    ax.set(xlabel='Distance apparente équivalente air (cm)',ylabel='Profil A (dB réf. 1)',ylim=(-100,-45))
    ax.grid(alpha=.3)
    ax.legend()
axes[0].set(xlim=(0,150),title='Zone 0–150 cm')
axes[1].set(xlim=(0,d[-1]),title='Profil complet')
fig.suptitle('Nouvelle antenne — quatre acquisitions associées aux figures cibles du 30/09/2026\nMéthode A · mêmes grille, fond et SOL vérifiés · amplitudes sans normalisation')
fig.savefig(OUT/'comparaison_A.png',dpi=160)
with (OUT/'pics_A.csv').open('w') as f:
    writer = csv.writer(f)
    writer.writerow(['cible','acquisition','balayages','pic_max_cm','niveau_max_db'])
    writer.writerows(rows)
