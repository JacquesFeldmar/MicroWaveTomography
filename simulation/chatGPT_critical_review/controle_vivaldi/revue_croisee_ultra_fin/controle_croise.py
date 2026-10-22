"""Contrelecture Q des sept profils Vivaldi clos, sans nouveau FDTD."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
for nom in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[nom] = '1'
os.environ['MPLBACKEND'] = 'Agg'
SIM = Path(__file__).resolve().parents[3]
ICI = Path(__file__).resolve().parent
BASE = SIM / 'resultats/pcbway_r1/vivaldi_tomographie'
ANCRAGE = SIM / 'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'
PROFILS = ('base_8ns', 'fin_8ns', 'fin_12ns', 'tres_fin_12ns',
           'tres_fin_16ns', 'ultra_fin_12ns', 'ultra_fin_16ns')
sys.path.insert(0, str(SIM))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sources():
    assert sha(ANCRAGE) == '47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383'
    attendu = json.loads(ANCRAGE.read_text(encoding='utf-8'))['sources_controle_sha256']
    courant = {n: sha(SIM / n) for n in attendu}
    assert len(courant) == 17 and courant == attendu
    return courant


def fichiers():
    return {str(p.relative_to(BASE)): sha(p) for nom in PROFILS
            for p in sorted((BASE / nom).rglob('*')) if p.is_file()}


def interdit(*args, **kwargs):
    raise RuntimeError('Cette contrelecture interdit tout calcul ou bilan global')


def main():
    sortie = ICI / 'rapport_croise.json'
    if sortie.exists():
        raise FileExistsError(sortie)
    avant_sources, avant_fichiers = sources(), fichiers()
    import numpy as np
    import qualifie_pcbway as Q
    import raffine_qualification_pcbway as R
    R.enregistre(Q)
    Q.calcule = Q.comparer = Q.F.lance = interdit
    donnees, controles = {}, {}
    for nom in PROFILS:
        niveau, duree = nom.rsplit('_', 1)
        f, s, m, q = Q.charge_calcul(BASE / nom, exiger_courant=True)
        Q.valide_campagne(m, q, 'vivaldi_tomographie', niveau, float(duree[:-2]))
        donnees[nom] = (f, s, m, q)
        controles[nom] = {'n_pas': m['execution']['n_pas'], 'dt_s': m['execution']['dt_s'],
                         'indicateurs': Q.indicateurs(f, s),
                         'manifeste_sha256': sha(BASE / nom / 'simulation_manifest.json')}
    initial = donnees[PROFILS[0]]
    communs = {
        'geometrie': all(Q.G.json_octets(d[3]['geometrie']) == Q.G.json_octets(initial[3]['geometrie']) for d in donnees.values()),
        'contrat': all(d[3]['simulation_contract'] == initial[3]['simulation_contract'] for d in donnees.values()),
        'sources': all(d[2]['sources_sha256'] == initial[2]['sources_sha256'] for d in donnees.values()),
        'environnement': all(d[2]['environnement'] == initial[2]['environnement'] for d in donnees.values()),
        'frequences': all(np.array_equal(d[0], initial[0]) for d in donnees.values()),
    }
    assert all(communs.values())
    a, b, c = (donnees[n] for n in ('tres_fin_16ns', 'ultra_fin_12ns', 'ultra_fin_16ns'))
    spatial = Q.ecarts(a[0], a[1], c[0], c[1])
    temporel = Q.ecarts(b[0], b[1], c[0], c[1], temporel=True)
    coherence = {'maillage_manifeste_identique': b[2]['maillage'] == c[2]['maillage'],
                 'dt_binaire_identique': np.float64(b[2]['execution']['dt_s']).tobytes() == np.float64(c[2]['execution']['dt_s']).tobytes(),
                 'dt_hex': float(c[2]['execution']['dt_s']).hex(), 'axes': {}}
    with np.load(BASE / 'ultra_fin_12ns/maillage.npz', allow_pickle=False) as g12, np.load(BASE / 'ultra_fin_16ns/maillage.npz', allow_pickle=False) as g16:
        assert set(g12.files) == set(g16.files)
        for cle in g12.files:
            x, y = g12[cle], g16[cle]
            identique = x.shape == y.shape and x.dtype == y.dtype and x.tobytes() == y.tobytes()
            coherence['axes'][cle] = {'forme': list(x.shape), 'dtype': str(x.dtype), 'identique_binaire': identique}
            assert identique
    assert coherence['maillage_manifeste_identique'] and coherence['dt_binaire_identique']
    masques = {'spatial': int(np.count_nonzero((abs(a[1]) >= .1) & (abs(c[1]) >= .1))),
               'temporel': int(np.count_nonzero((abs(b[1]) >= .1) & (abs(c[1]) >= .1)))}
    final = Q.indicateurs(c[0], c[1])
    resultat = bool(spatial['reussi'] and temporel['reussi'] and
                    all(d['indicateurs']['passivite_numerique'] for d in controles.values()))
    apres_sources, apres_fichiers = sources(), fichiers()
    assert avant_sources == apres_sources and avant_fichiers == apres_fichiers
    rapport = {'schema': 'revue_croisee_vivaldi_ultra_fin_v1', 'date_utc': datetime.now(timezone.utc).isoformat(),
               'script_sha256': sha(__file__), 'sessions': {'81046': {'sortie_zero_confirmee_par_root': True}},
               'profils': controles, 'nombre_profils': len(PROFILS), 'communs': communs,
               'coherence_temporelle': coherence, 'points_masque_module_ge_0p1': masques,
               'spatial': spatial, 'temporel': temporel, 'indicateurs_reference_ultra_fin16': final,
               'sources_17_sha256': apres_sources, 'fichiers_7_profils_sha256': apres_fichiers,
               'nombre_fichiers_fermes': len(apres_fichiers), 'reussi': resultat,
               'aucun_calcul_ni_resultat_modifie': True, 'qualification_globale_effectuee': False}
    with sortie.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({k: rapport[k] for k in ('spatial', 'temporel', 'points_masque_module_ge_0p1', 'indicateurs_reference_ultra_fin16', 'reussi')}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
