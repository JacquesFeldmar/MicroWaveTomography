"""Audit hors matériel des quatre cibles du 18/09 ; lancer depuis la racine.

Décodage struct, SOL analytique et somme fréquentielle indépendants des
fonctions de production. Aucun fichier de mesure n'est modifié.
"""
import json
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from commun.physique import profil_distance


def load(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k].copy() for k in z.files}


def decode(packets, count):
    result = []
    for packet in packets:
        rows = list(struct.iter_unpack('<6iH6x', packet.tobytes()))
        assert sorted(r[6] for r in rows) == list(range(count))
        rows.sort(key=lambda r: r[6])
        result.append([complex(r[2], r[3]) / complex(r[0], r[1]) for r in rows])
    return np.array(result)


def error(a, b):
    np.testing.assert_allclose(a, b, rtol=1e-11, atol=1e-12)
    return float(np.max(np.abs(a - b)))


def main():
    project = ROOT / 'plexiglas'
    cal = load(project / 'calibration/sol_20260918T123239_346802Z.npz')
    f = cal['freqs']
    standards = {}
    checks = {}
    for name in ('short', 'open', 'load'):
        raw = decode(cal['paquets_' + name], len(f))
        checks['decode_' + name] = error(raw, cal['sweeps_' + name])
        standards[name] = raw.mean(axis=0)
        checks['mean_' + name] = error(standards[name], cal['brut_' + name])
    # Solution fermée pour Gamma(short, open, load) = (-1, +1, 0).
    directivity = standards['load']
    op = standards['open'] - directivity
    sh = standards['short'] - directivity
    source_match = (op + sh) / (op - sh)
    tracking = op * (1 - source_match)
    for key, value in [('e00', directivity), ('e11', source_match), ('e10e01', tracking)]:
        checks[key] = error(value, cal[key])

    def correct(raw):
        v = raw - directivity
        return v / (tracking + source_match * v)

    background = load(project / 'mesures/fond_20260918T123802_668873Z/fond.npz')

    def replay(z):
        assert str(z['correction_mode']) == 'brut'
        error(z['freqs'], f)
        for key in ('freqs', 'e00', 'e11', 'e10e01'):
            error(z['sol_' + key], cal[key])
        for key, expected in [('start_hz', 1_000_000_000), ('step_hz', 25_000_000),
                              ('points', 201), ('valeurs_par_frequence', 1)]:
            assert int(z['usb_' + key]) == expected
        raw = decode(z['paquets_usb'], len(f))
        error(raw, z['sweeps_bruts'])
        corrected = correct(raw)
        error(corrected, z['sweeps_calibres'])
        return corrected.mean(axis=0)

    bg = replay(background)
    checks['background'] = error(bg, background['fond'])
    # Recherche directe à pas 0,1 mm sur toute la plage affichable par A,
    # sans FFT, sans appel à la fonction de distance pour construire l'axe.
    c = 299_792_458.0
    distances = np.arange(0, c / (4 * (f[1] - f[0])), .0001)
    window = np.hanning(len(f))

    def direct_peak(signal):
        amplitudes = np.empty(len(distances))
        for start in range(0, len(distances), 1000):
            ds = distances[start:start + 1000]
            amplitudes[start:start + len(ds)] = np.abs(
                np.exp(4j * np.pi * ds[:, None] * f[None, :] / c) @ (window * signal))
        return float(distances[np.argmax(amplitudes)] * 100)

    synthetic = []
    measurements = []
    names = ['124339_777575', '124406_029736', '124436_102295', '124448_947650']
    for nominal, stamp in zip((30, 40, 50, 60), names):
        echo = -.08 * np.exp(-4j * np.pi * f * (nominal / 100) / c)
        axis, profile, step = profil_distance(f, echo)
        peak = float(axis[np.argmax(profile)] / 10)
        assert abs(peak - nominal) <= step / 20
        synthetic.append(dict(nominal_cm=nominal, ifft_cm=peak))
        path = project / f'mesures/cible_20260918T{stamp}Z/cible.npz'
        z = load(path)
        mean = replay(z)
        error(mean, z['cible'])
        error(bg, z['fond'])
        residual = mean - bg
        delta = error(residual, z['residu'])
        direct = direct_peak(residual)
        axis, profile, step = profil_distance(f, z['residu'])
        peak = float(axis[np.argmax(profile)] / 10)
        assert abs(direct - peak) <= step / 20 + .01
        measurements.append(dict(source=str(path.relative_to(ROOT)), nominal_cm=nominal,
                                 independent_residual_error=delta, direct_sum_cm=direct,
                                 ifft_cm=peak))
    report = dict(checks=checks, synthetic=synthetic, measurements=measurements,
                  limitations='Contrôle logiciel hors matériel ; étalons supposés idéaux. '
                  'Ni fréquence RF, ni plan physique, ni firmware validés indépendamment.')
    out = Path(__file__).with_suffix('.json')
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(out)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
