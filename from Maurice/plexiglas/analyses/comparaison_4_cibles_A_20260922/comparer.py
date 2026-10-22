from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from commun.physique import profil_distance, resolution_mm
OUT = Path(__file__).resolve().parent
NAMES = ['cible_20260922T075637_160158Z', 'cible_20260922T075722_271970Z',
         'cible_20260922T075754_481031Z', 'cible_20260922T075808_614309Z']
fig, axs = plt.subplots(2, 1, figsize=(12, 9), constrained_layout=True)
fig2, small = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True, sharex=True, sharey=True)
rows = []
reference = None
for j, name in enumerate(NAMES):
    with np.load(ROOT/'plexiglas/mesures'/name/'cible.npz', allow_pickle=False) as z:
        if reference is None:
            reference = {k:z[k].copy() for k in ('freqs', 'fond', 'sol_e00', 'sol_e11', 'sol_e10e01')}
        assert all(np.array_equal(z[k], v) for k,v in reference.items())
        f = z['freqs']
        d, a, step = profil_distance(f, z['residu'], zoom=16, fenetre='hann')
        saved = ROOT/'plexiglas/analyses'/(name+'_A')/'resultat_A.npz'
        with np.load(saved) as result:
            np.testing.assert_allclose(result['profil'], a)
            np.testing.assert_allclose(result['distance_mm'], d)
        peaks = find_peaks(a)[0]
        best = sorted(peaks, key=lambda i:a[i], reverse=True)[:2]
        spatial = sorted(best, key=lambda i:d[i])
        hour = datetime.strptime(name, 'cible_%Y%m%dT%H%M%S_%fZ').replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Europe/Paris')).strftime('%H:%M:%S')
        label = f'C{j+1} — {hour}'
        color = f'C{j}'
        db = 20*np.log10(np.maximum(a, 1e-15))
        for ax in axs:
            ax.plot(d/10, db, label=label, color=color)
        axs[0].plot(d[best]/10, db[best], 'o', color=color)
        ax = small.flat[j]
        for s in z['sweeps_calibres']:
            _, single, _ = profil_distance(f, s-z['fond'], zoom=16, fenetre='hann')
            ax.plot(d/10, 20*np.log10(np.maximum(single, 1e-15)), color=color, alpha=.22, lw=.8)
        ax.plot(d/10, db, color=color, lw=2, label='Moyenne complexe (10 balayages)')
        ax.set(title=label, xlim=(50,125), ylim=(-85,-50), xlabel='Distance équivalente air (cm)', ylabel='Profil A (dB réf. 1)')
        ax.grid(alpha=.3)
        ax.legend(fontsize=8)
        rows.append([f'C{j+1}',hour,name,*[v for i in spatial for v in (d[i]/10, db[i])], d[best[0]]/10, db[best[0]]])
for ax in axs:
    ax.set(xlabel='Distance équivalente air depuis le plan SOL (cm)', ylabel='Profil A (dB réf. 1)', ylim=(-95,-50))
    ax.grid(alpha=.3)
    ax.legend()
axs[0].set(xlim=(50,125), title='Zone des deux pics dominants — mêmes échelles, sans normalisation')
axs[1].set(xlim=(0,d[-1]/10), title='Profil complet calculé par la méthode A')
fig.suptitle('Quatre cibles — méthode A : soustraction complexe du fond, IFFT Hann\n1–6 GHz · 201 points · 10 balayages · fond et SOL identiques')
fig2.suptitle('Stabilité des profils : balayages individuels pâles et moyenne complexe épaisse')
fig.savefig(OUT/'comparaison_A.png',dpi=170)
fig2.savefig(OUT/'balayages_A.png',dpi=170)
with (OUT/'pics_A.csv').open('w') as file:
    writer=csv.writer(file)
    writer.writerow(['cible','heure_Paris','acquisition','pic_proche_cm','niveau_proche_db','pic_lointain_cm','niveau_lointain_db','pic_max_cm','niveau_max_db'])
    writer.writerows(rows)
lines=['# Comparaison des quatre acquisitions avec A','',
       'Même grille, même fond et mêmes coefficients SOL vérifiés. Profils recalculés identiques aux résultats A enregistrés.', '',
       '| Cible | Heure Paris | Pic proche (cm ; dB) | Pic lointain (cm ; dB) |',
       '|---|---|---|---|']
for r in rows:
    lines.append(f'| {r[0]} | {r[1]} | {r[3]:.2f} ; {r[4]:.2f} | {r[5]:.2f} ; {r[6]:.2f} |')
lines += ['', 'Les deux maxima locaux les plus forts se déplacent vers des distances croissantes. Leur séparation vaut environ 5,6 à 6,5 cm. Le maximum dominant alterne entre ces deux pics sur les balayages individuels : il ne fournit donc pas seul un repère stable.', '',
          f'Pas interpolé : {step:.2f} mm. Largeur de lobe indicative Hann selon le code : {resolution_mm(f):.1f} mm. Le pas interpolé ne représente pas la résolution physique.', '',
          "Les distances sont équivalentes air depuis le plan SOL. La réponse de l’antenne n’est pas déconvoluée ; ces deux pics ne suffisent pas à identifier deux faces ni à déduire une épaisseur. Les objets et positions réels ne sont pas renseignés dans ces fichiers.", '',
          'Fichiers : comparaison_A.png, balayages_A.png, pics_A.csv. Reproduction : python '+str(Path(__file__).relative_to(ROOT))]
(OUT/'comparaison_A.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
