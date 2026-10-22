"""Lecture seule des cinq profils GRAND F2 clos, sans construction ni solveur."""
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
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[1]
sys.path.insert(0, str(SIM))
import numpy as np
import qualifie_pcbway as Q

BASE = SIM / 'resultats/pcbway_maille_controlee_v2/diamant_uwb_x18'
PROFILS = (('base_8ns', 'base', 8), ('base_12ns', 'base', 12),
           ('fin_8ns', 'fin', 8), ('fin_12ns', 'fin', 12), ('fin_16ns', 'fin', 16))
GEL = SIM / 'chatGPT_critical_review/integration_finale_f2/gel_campagne_F2.json'


def sha(chemin):
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def exige(condition, message):
    if not condition:
        raise ValueError(message)


def inventaire():
    # Liste blanche explicite : aucun parcours du parent ou de la Vivaldi active.
    return {p.relative_to(BASE).as_posix(): sha(p)
            for nom, _, _ in PROFILS for p in sorted((BASE / nom).rglob('*')) if p.is_file()}


def ecarts_numpy(fa, sa, fb, sb, temporel=False):
    exige(np.array_equal(fa, fb), 'Frequences differentes')
    delta = np.abs(sa - sb)
    masque = (np.abs(sa) >= .1) & (np.abs(sb) >= .1)
    db = np.abs(20 * np.log10(np.maximum(np.abs(sa), 1e-15) / np.maximum(np.abs(sb), 1e-15)))
    phase = np.abs(np.angle(sa * np.conj(sb), deg=True))
    valeurs = dict(maximum_complexe=float(np.max(delta)),
                   rms_complexe=float(np.sqrt(np.mean(delta ** 2))),
                   percentile95_db=float(np.percentile(db[masque], 95)) if masque.any() else None,
                   percentile95_phase_deg=float(np.percentile(phase[masque], 95)) if masque.any() else None)
    seuils = dict(maximum_complexe=.015 if temporel else .05,
                  rms_complexe=.005 if temporel else .02, percentile95_db=.5 if temporel else 1.)
    reussi = all(valeurs[k] is not None and valeurs[k] <= v for k, v in seuils.items())
    return dict(valeurs=valeurs, seuils_acceptation=seuils, reussi=reussi,
                masque_db_indices=np.flatnonzero(masque).tolist(), nombre_masque_db=int(masque.sum()),
                maximum_complexe_frequence_hz=float(fa[int(np.argmax(delta))]),
                points_ecart_complexe_principaux=[dict(frequence_hz=float(fa[k]),
                    delta_complexe=float(delta[k]), module_a=float(abs(sa[k])), module_b=float(abs(sb[k])),
                    delta_db=float(db[k]), dans_masque_db=bool(masque[k]), phase_ecart_deg=float(phase[k]))
                    for k in np.argsort(delta)[-10:][::-1]])


def main():
    sortie = ICI / 'lecture_independante.json'
    exige(not sortie.exists(), 'Rapport deja present')
    gel = json.loads(GEL.read_text(encoding='utf-8'))
    attendus = {**gel['sources_physiques_sha256'], **gel['controles_sha256']}
    exige(len(attendus) == 18, 'Inventaire gele attendu18')
    avant = {n: sha(SIM / n) for n in attendus}
    exige(avant == attendus, 'Source gelee changee')
    fichiers_avant = inventaire()
    manifestes = {nom: fichiers_avant[nom + '/simulation_manifest.json'] for nom, _, _ in PROFILS}
    fermes = {}
    commun = None
    for nom, niveau, duree in PROFILS:
        f, s, m, q = Q.charge_calcul(BASE / nom, exiger_courant=True)
        Q.valide_campagne(m, q, 'diamant_uwb_x18', niveau, duree)
        exige(Q.identite_moteur(m, q) == Q.MOTEUR_F2, 'Moteur nonF2')
        physique = dict(sources=m['sources_sha256'], environnement=m['environnement'],
                        materiaux=m['materiaux'], geometrie=q['geometrie'],
                        contrat=q['simulation_contract'], frequences=f.tolist())
        signature = json.dumps(physique, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if commun is None:
            commun = signature
        exige(signature == commun, 'Physique/contrat/geometrie/environnement/frequences differents')
        fermes[nom] = (f, s, m, q)
    comparaisons = {}
    for nom, a, b, temps in (('spatial', 'base_12ns', 'fin_12ns', False),
                            ('temporel', 'fin_12ns', 'fin_16ns', True)):
        fa, sa, *_ = fermes[a]
        fb, sb, *_ = fermes[b]
        independant = ecarts_numpy(fa, sa, fb, sb, temps)
        natif = Q.ecarts(fa, sa, fb, sb, temporel=temps)
        for cle in ('valeurs', 'seuils_acceptation', 'reussi'):
            exige(independant[cle] == natif[cle], 'Desaccord NumPy/Q : ' + nom + '/' + cle)
        comparaisons[nom] = dict(profils=[a, b], numpy=independant, Q=natif, accord_exact=True)
    Q.verifie_grilles_temporelles([BASE / 'fin_12ns', BASE / 'fin_16ns'])
    dt12 = fermes['fin_12ns'][2]['execution']['dt_s']
    dt16 = fermes['fin_16ns'][2]['execution']['dt_s']
    exige(np.asarray(dt12, dtype='<f8').tobytes() == np.asarray(dt16, dtype='<f8').tobytes(),
          'dt temporel nonidentique')
    diagnostics = []
    for nom, _, _ in PROFILS:
        f, s, m, q = fermes[nom]
        db = 20 * np.log10(np.maximum(abs(s), 1e-15))
        j = int(np.argmin(db))
        diagnostics.append(dict(profil=nom, manifeste_sha256=manifestes[nom],
            maximum_module=float(abs(s).max()), passivite=bool(abs(s).max() <= 1.005),
            minimum_S11_db=float(db[j]), frequence_minimum_hz=float(f[j]),
            maillage=m['maillage'], dt_s=m['execution']['dt_s'],
            FDTD_direct=not m.get('derive_sondes', False), indicateurs=Q.indicateurs(f, s)))
    fichiers_apres = inventaire()
    apres = {n: sha(SIM / n) for n in attendus}
    exige(avant == apres == attendus and fichiers_avant == fichiers_apres,
          'Preuve/source changee pendant lecture')
    reference = fermes['fin_16ns'][1]
    rapport = dict(schema='lecture_independante_grand_losange_F2_v1',
        utc=datetime.now(timezone.utc).isoformat(), script_sha256=sha(__file__),
        python=sys.version, numpy=np.__version__, threads_analyse=1,
        aucun_solveur=True, aucune_construction_maillage=True, aucune_selection_ecrite=True,
        gel_sha256=sha(GEL), sources18_avant=avant, sources18_apres=apres,
        cinq_manifestes_sha256=manifestes, tous_fichiers_cinq_profils_avant=fichiers_avant,
        tous_fichiers_cinq_profils_apres=fichiers_apres,
        cinq_profils_Q_valides=True, communs_physique_contrat_geometrie_env_frequences=True,
        diagnostics_profils=diagnostics, comparaisons_F2=comparaisons,
        temps_axes_NPZ_et_dt_octets_identiques=True, reference='fin_16ns',
        reference_passive=bool(abs(reference).max() <= 1.005),
        reference_maximum_module=float(abs(reference).max()),
        convergence_F2_grand_acquise=bool(comparaisons['spatial']['numpy']['reussi'] and
                                         comparaisons['temporel']['numpy']['reussi']),
        qualification_globale_effectuee=False,
        conclusion='Cinq profils integres ; echec spatialF2, controle temporel reussi. Antenne non qualifiee.',
        limites=['Les valeurs seules ne prouvent pas la cause scientifique du desaccord spatial.',
                 'Aucun profil Vivaldi, moteur, catalogue ou seuil modifie ; aucun calcul temporel lance.'])
    with sortie.open('x', encoding='utf-8', newline='\n') as flux:
        json.dump(rapport, flux, ensure_ascii=False, indent=2, allow_nan=False)
        flux.write('\n')
    print(json.dumps(dict(rapport=str(sortie), sha256=sha(sortie),
        spatial=comparaisons['spatial']['numpy']['valeurs'],
        temporel=comparaisons['temporel']['numpy']['valeurs'],
        frequence_ecart_spatial_max_hz=comparaisons['spatial']['numpy']['maximum_complexe_frequence_hz'],
        reference_maximum_module=rapport['reference_maximum_module'],
        fichiers_profils_inchanges=len(fichiers_avant), sources18_inchangees=True), ensure_ascii=False))


if __name__ == '__main__':
    main()
