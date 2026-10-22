"""Prepare une selection conditionnelle, sans ouvrir les calculs ni lancer Q."""
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
SIM = Path(__file__).resolve().parents[2]
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(SIM))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    sorties = (ICI / 'selection_conditionnelle_n34_ultra_fin.json',
               ICI / 'validation_structurelle.json')
    if any(p.exists() for p in sorties):
        raise FileExistsError('Les sorties doivent etre neuves')
    ancrage = SIM / 'chatGPT_critical_review/analyse_grilles_fermees_n30/checkpoint_n34_fige.json'
    assert sha(ancrage) == '47dacd80fd860c33e5b5bc0dce61332db1b0d31405936359a2ad22ac7add4383'
    attendu = json.loads(ancrage.read_text(encoding='utf-8'))['sources_controle_sha256']
    avant = {n: sha(SIM / n) for n in attendu}
    assert avant == attendu and len(avant) == 17
    import qualifie_pcbway as Q
    import raffine_qualification_plus_pcbway as PLUS
    PLUS.enregistre(Q)  # Catalogue en memoire seulement, y compris N34 exact.
    import qualification_adaptative as AP

    def interdit(*args, **kwargs):
        raise RuntimeError('Aucune lecture de calcul ou qualification dans cette preparation')

    Q.charge_calcul = Q.calcule = Q.comparer = Q.F.lance = interdit

    def essai(type_, a, b, motif):
        return dict(type=type_, calculs=[a, b], motif=motif)

    initiaux = lambda: [
        essai('spatial', 'base_8ns', 'fin_8ns', 'Premiere comparaison spatiale conservee'),
        essai('temporel', 'fin_8ns', 'fin_12ns', 'Premiere comparaison temporelle conservee'),
    ]
    petit = dict(spatial=['base_16ns', 'fin_16ns'],
                 temporel=['fin_12ns', 'fin_16ns'], reference='fin_16ns',
                 preliminaires=initiaux() + [essai('temporel', 'base_8ns', 'base_16ns',
                     'Diagnostic supplementaire de la fenetre courte sur la grille de base')])
    g_prelim = initiaux()
    for ancien, nouveau in (('fin', 'tres_fin'), ('tres_fin', 'ultra_fin'),
                             ('ultra_fin', 'extreme_fin'), ('extreme_fin', 'n30')):
        g_prelim.extend([
            essai('spatial', ancien + '_12ns', nouveau + '_12ns',
                  'Palier spatial precedent conserve ; ses seuils ont ete depasses'),
            essai('temporel', nouveau + '_8ns', nouveau + '_12ns',
                  'Controle temporel du palier precedent conserve'),
        ])
    grand = dict(spatial=['n30_12ns', 'n34_12ns'],
                 temporel=['n34_8ns', 'n34_12ns'], reference='n34_12ns',
                 preliminaires=g_prelim)
    vivaldi = dict(spatial=['tres_fin_16ns', 'ultra_fin_16ns'],
                   temporel=['ultra_fin_12ns', 'ultra_fin_16ns'], reference='ultra_fin_16ns',
                   preliminaires=initiaux() + [
                       essai('spatial', 'fin_12ns', 'tres_fin_12ns',
                             'Raffinement precedent insuffisant, conserve avec son echec'),
                       essai('temporel', 'tres_fin_12ns', 'tres_fin_16ns',
                             'Controle temporel du palier precedent conserve'),
                   ])
    cfg = dict(schema=AP.SCHEMA_SELECTION,
               antennes=dict(diamant_uwb=petit, diamant_uwb_x18=grand,
                             vivaldi_tomographie=vivaldi))
    effectives = AP._normalise_configuration(cfg)
    comptes = {n: dict(profils=len(AP._profils_selection(spec)),
                        preliminaires=len(spec['preliminaires']), reference=spec['reference'])
               for n, spec in effectives.items()}
    assert {n: d['profils'] for n, d in comptes.items()} == {
        'diamant_uwb': 5, 'diamant_uwb_x18': 13, 'vivaldi_tomographie': 7}
    assert sum(d['preliminaires'] for d in comptes.values()) == 17
    assert {n: sha(SIM / n) for n in attendu} == avant
    with sorties[0].open('x', encoding='utf-8', newline='\n') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    relu, eff, digest, _ = AP.lire_fichier_selection(sorties[0])
    assert relu == cfg and eff == effectives
    rapport = dict(schema='preparation_selection_conditionnelle_v1',
                   date_utc=datetime.now(timezone.utc).isoformat(),
                   selection=str(sorties[0].relative_to(SIM)), selection_sha256=digest,
                   script_sha256=sha(__file__), validation_structurelle_reussie=True,
                   profils_total=sum(d['profils'] for d in comptes.values()),
                   preliminaires_total=17, comptes=comptes,
                   niveaux_enregistres_en_memoire=Q.NIVEAUX,
                   sources_17_inchangees_sha256=avant,
                   resultats_fdtd_ouverts=False, qualification_globale_effectuee=False,
                   selection_campagne_creee=False,
                   condition='Ne copier dans BASE qu apres fin de toutes les files, '
                             'reussite des deux controles N34 et integration finale R/Q/CSV. '
                             'Si N34 echoue, conserver ce brouillon comme historique et adapter '
                             'la campagne sans changer les seuils.')
    with sorties[1].open('x', encoding='utf-8', newline='\n') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({k: rapport[k] for k in ('selection_sha256', 'validation_structurelle_reussie',
                                             'profils_total', 'preliminaires_total', 'comptes')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
