"""Consigne le refus N34 et trace les deux comparaisons, sans FDTD."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
for cle in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[cle] = '1'
os.environ['MPLBACKEND'] = 'Agg'
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[2]
BASE = SIM / 'resultats/pcbway_r1/diamant_uwb_x18'
CROSS = ICI.parent / 'revue_croisee_n34/rapport_croise.json'
sys.path.insert(0, str(SIM))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def lit(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def neuf(p, obj):
    with p.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def main():
    sorties = [ICI / ('comparaison_' + k + '.png') for k in ('spatial', 'temporel')]
    bilan_path = BASE / 'bilan_intermediaire_n34.json'
    for p in [*sorties, bilan_path, ICI / 'bilan_intermediaire_n34.json', ICI / 'preuve_integrite.json']:
        if p.exists():
            raise FileExistsError(p)
    c = lit(CROSS)
    assert c['nombre_profils'] == 13 and c['code_terminal_file'] == 0
    assert c['code_terminal_analyse'] == 2 and c['reussi'] is False
    assert all(c['egalite_exacte_helper_structures_pertinentes'].values())
    s17 = c['sources_17_sha256_apres']
    fichiers = c['fichiers_13_profils_sha256_apres']
    assert len(s17) == 17 and len(fichiers) == 360

    def verifie():
        assert all(sha(SIM / n) == h for n, h in s17.items())
        assert all(sha(BASE / n) == h for n, h in fichiers.items())

    verifie()
    import numpy as np
    import matplotlib.pyplot as plt
    import qualifie_pcbway as Q
    import raffine_qualification_plus_pcbway as PLUS
    PLUS.enregistre(Q)

    def interdit(*args, **kwargs):
        raise RuntimeError('Aucun FDTD, selection ou bilan global autorise')

    Q.calcule = Q.comparer = Q.F.lance = interdit
    data = {n: Q.charge_calcul(BASE / n, exiger_courant=True) for n in c['profils']}
    for n, d in data.items():
        niveau, duree = n.rsplit('_', 1)
        Q.valide_campagne(*d[2:], 'diamant_uwb_x18', niveau, float(duree[:-2]))
    cfg = lit(SIM / 'chatGPT_critical_review/preparation_selection_n34_ultra_fin/selection_conditionnelle_n34_ultra_fin.json')
    prelim = []
    for e in cfg['antennes']['diamant_uwb_x18']['preliminaires']:
        a, b = (data[n] for n in e['calculs'])
        ecart = Q.ecarts(*a[:2], *b[:2], temporel=e['type'] == 'temporel')
        prelim.append(dict(**e, ecarts=ecart))
    assert len(prelim) == 10
    pics = {}
    for k, path in zip(('spatial', 'temporel'), sorties):
        noms = c['paires'][k]
        (f, a, *_), (_, b, *_) = (data[n] for n in noms)
        delta = abs(a - b)
        db_a, db_b = 20 * np.log10(abs(a)), 20 * np.log10(abs(b))
        mask = (abs(a) >= .1) & (abs(b) >= .1)
        dd = abs(db_a - db_b)
        e = c[k]
        assert Q.ecarts(f, a, f, b, temporel=k == 'temporel') == e
        assert int(mask.sum()) == c['points_masque_module_ge_0p1'][k]
        idx = np.argsort(delta)[-12:][::-1]
        pics[k] = [dict(frequence_hz=float(f[i]), ecart_complexe=float(delta[i]),
                        module_a_db=float(db_a[i]), module_b_db=float(db_b[i]),
                        phase_diff_deg=float(np.angle(b[i] / a[i], deg=True))) for i in idx]
        fig, ax = plt.subplots(3, 1, figsize=(13, 11), sharex=True,
                               gridspec_kw=dict(height_ratios=[1.25, 1, 1]))
        verdict = 'RÉUSSI' if e['reussi'] else 'REFUSÉ'
        fig.suptitle(f'Grand losange — contrôle {k} N34 : {verdict}\nQualification globale non acquise', fontsize=17)
        x = f / 1e9
        ax[0].plot(x, db_a, label=noms[0]); ax[0].plot(x, db_b, label=noms[1])
        ax[0].axhline(-20, color='grey', ls=':', label='−20 dB : frontière du masque')
        ax[0].set_ylabel('S11 (dB)'); ax[0].legend(loc='lower left', fontsize=9)
        ax[1].plot(x, delta, label='Écart complexe, tous les points')
        ax[1].axhline(e['seuils_acceptation']['maximum_complexe'], color='firebrick', ls='--', label='Seuil du maximum')
        ax[1].set_ylim(0, max(delta.max(), e['seuils_acceptation']['maximum_complexe']) * 1.15)
        ax[1].set_title(f"Maximum {e['valeurs']['maximum_complexe']:.8f} ; RMS {e['valeurs']['rms_complexe']:.8f}")
        ax[1].set_ylabel('|ΔS11|'); ax[1].legend(fontsize=9)
        ax[2].plot(x, dd, color='silver', label='Écart dB complet')
        ax[2].plot(x, np.where(mask, dd, np.nan), color='seagreen', label=f'Masque : {mask.sum()}/213 points')
        ax[2].axhline(e['seuils_acceptation']['percentile95_db'], color='firebrick', ls='--', label='Seuil du percentile 95')
        ax[2].set_title(f"p95 masqué = {e['valeurs']['percentile95_db']:.8f} dB ; le seuil ne porte pas sur chaque point")
        ax[2].set_ylim(0, max(dd.max(), e['seuils_acceptation']['percentile95_db']) * 1.12)
        ax[2].set_ylabel('|Δ module| (dB)'); ax[2].set_xlabel('Fréquence (GHz)')
        ax[2].legend(fontsize=9)
        for axe in ax:
            axe.grid(alpha=.22); axe.set_xlim(1, 6.3)
        fig.tight_layout(rect=(0, 0, 1, .94))
        fig.savefig(path, dpi=160); plt.close(fig)
    bilan = dict(schema='bilan_intermediaire_grand_n34_v1', antenne='diamant_uwb_x18',
        date_utc=datetime.now(timezone.utc).isoformat(), qualification_officielle=False,
        qualification_globale=False, reussi=False, etat='refuse_convergence_spatiale',
        reference_provisoire='n34_12ns', nombre_profils=13, profils=list(data),
        nombre_preliminaires=10, essais_preliminaires=prelim,
        paires=c['paires'], spatial=c['spatial'], temporel=c['temporel'],
        indicateurs_reference=c['indicateurs_reference_n34_12'],
        passivite_tous_profils=c['passivite_tous_profils'],
        coherence_temporelle=c['coherence_temporelle'], points_masque=c['points_masque_module_ge_0p1'],
        plus_grands_ecarts=pics,
        figures_sha256={str(p.relative_to(SIM)): sha(p) for p in sorties},
        preuves_sha256={str(p.relative_to(SIM)): sha(p) for p in [CROSS, ICI.parent / 'controle_final_n34/rapport.json',
            SIM / 'resultats/pcbway_r1/journaux/fin_queue_n34_observee_automatiquement.json',
            SIM / 'resultats/pcbway_r1/journaux/fin_analyse_n34_automatique.json']},
        note='Contrôle temporel et passivité passent ; maximum complexe spatial et p95 dB échouent. '
             'RMS spatial passe. La référence reste provisoire. Aucun seuil ni source gelée modifié.')
    neuf(bilan_path, bilan); neuf(ICI / bilan_path.name, bilan)
    verifie()
    neuf(ICI / 'preuve_integrite.json', dict(script_sha256=sha(__file__),
        sources_17_sha256=s17, fichiers_13_profils_sha256=fichiers,
        invariance_avant_apres=True, qualification_globale_effectuee=False,
        code_python_croise_annonce=2, code_terminal_hote_croise_observe=1,
        code_python_helper_annonce=2, code_terminal_hote_observateur_observe=1,
        note_codes='Le wrapper PowerShell de exec_command transforme ici la sortie native 2 en code hôte 1. '
                   'Les rapports et attestations conservent le code numérique 2 ; aucun incident de solveur.'))
    neuf(ICI / 'index_sha256.json', {p.name: sha(p) for p in sorted(ICI.iterdir()) if p.is_file()})
    print(json.dumps(dict(bilan=str(bilan_path), sha256=sha(bilan_path),
                         spatial_reussi=False, temporel_reussi=True, figures=[str(p) for p in sorties]), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
