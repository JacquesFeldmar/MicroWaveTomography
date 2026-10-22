"""Pilote operateur F2 reel puis extraction et rejeu apres deplacement.

Ce diagnostic court ne qualifie aucune antenne pour fabrication.
Les sources doivent avoir ete integrees et gelees dans integration_appliquee.json.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]
sys.path.insert(0, str(SIM))
BASE = SIM / 'resultats/validation_maille_controle_v2'
TAG = 'maillage_controle_v2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def neuf(path, objet):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(objet, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def main():
    import numpy as np
    import fdtd_maille_controlee as F
    import qualifie_pcbway as Q
    import fenetre_sondes as W

    integration = json.loads((HERE / 'integration_appliquee.json').read_text(encoding='utf-8'))
    physiques = integration['sources_physiques_sha256']
    controles = integration['controles_sha256']
    assert len(physiques) == 10 and len(controles) == 8

    def verifie():
        if F._sources() != physiques:
            raise ValueError('Inventaire physique different de celui integre')
        for nom, empreinte in {**physiques, **controles}.items():
            if sha(SIM / nom) != empreinte:
                raise ValueError('Source modifiee depuis integration : ' + nom)

    verifie()
    if BASE.exists():
        raise FileExistsError('Le diagnostic pilote exige une base entierement neuve')
    parent = BASE / 'diamant_uwb/base_3.5ns'
    prefixe = BASE / 'diamant_uwb/base_2ns'
    preuves = BASE / 'journaux'
    preuves.mkdir(parents=True)
    for nom in controles:
        shutil.copyfile(SIM / nom, preuves / nom)
    shutil.copyfile(__file__, preuves / Path(__file__).name)
    neuf(preuves / 'entree_pilote.json', dict(
        schema='pilote_natif_maille_controlee_v2',
        utc=datetime.now(timezone.utc).isoformat(), moteur=TAG,
        antenne='diamant_uwb', niveau='base', duree_ns=3.5,
        prefixe_ns=2., sources_physiques_sha256=physiques,
        controles_sha256=controles, pilote_sha256=sha(__file__),
        finalite='operateur, archivage et rejeu ; aucune qualification de convergence'))
    print('DEBUT PILOTE F2 NATIF 3.5ns', flush=True)
    Q.calcule('diamant_uwb', 'base', 3.5, fils=10, base=BASE, moteur=TAG)
    verifie()
    f, s, m, q = Q.charge_calcul(parent, exiger_courant=True)
    Q.valide_campagne(m, q, 'diamant_uwb', 'base', 3.5)
    if m.get('moteur') != TAG or q.get('moteur') != TAG:
        raise ValueError('Marqueurs F2 absents du pilote')
    stats = np.loadtxt(parent / 'openEMS_stats.txt', comments='%')
    n, dt = m['execution']['n_pas'], m['execution']['dt_s']
    if int(stats[2]) != n or not np.isclose(stats[1], dt, rtol=2e-7, atol=1e-18):
        raise ValueError('Statistiques natives incompatibles avec le pilote')
    for nom, decalage in (('port_ut_1', 0.), ('port_it_1', .5)):
        u = np.loadtxt(parent / nom, comments='%')
        if (len(u) != n+1 or not np.all(np.isfinite(u)) or
                np.max(np.abs(u[:, 0]/dt-(np.arange(n+1)+decalage))) > 2e-6):
            raise ValueError('Echantillonnage reel incompatible : ' + nom)

    derive = W.derive(parent, prefixe, 2.)
    fp, sp, mp, qp = Q.charge_calcul(prefixe, exiger_courant=True)
    Q.valide_campagne(mp, qp, 'diamant_uwb', 'base', 2.)
    Q.verifie_grilles_temporelles([parent, prefixe])
    if not derive.get('derive_sondes') or derive.get('calcul_fdtd_execute') is not False:
        raise ValueError('Le prefixe doit etre explicitement sans nouveau Run')
    verifie()

    # Deplacer une copie complete et refaire CalcPort avec ses dix sources.
    temporaire = Path(tempfile.mkdtemp(prefix='rejeu_pilote_f2_deplace_'))
    deplace = temporaire / 'diamant_uwb'
    shutil.copytree(parent.parent, deplace)
    nouveau = deplace / 'rejeu_base_2ns'
    relu = W.derive(deplace / parent.name, nouveau, 2.)
    fr, sr, mr, qr = Q.charge_calcul(nouveau, exiger_courant=True)
    Q.valide_campagne(mr, qr, 'diamant_uwb', 'base', 2.)
    if not np.array_equal(fp, fr) or not np.array_equal(sp, sr):
        raise ValueError('Le rejeu deplace ne reproduit pas le S11 du prefixe')
    verifie()
    preuve = dict(schema='fin_pilote_natif_maille_controlee_v2',
        utc=datetime.now(timezone.utc).isoformat(), moteur=TAG,
        pilote_natif_termine=True, sondes_reelles_NrTS_plus_1_verifiees=True,
        stats_iterations=n, dt_operateur_s=dt,
        maillage=m['maillage'], execution=m['execution'],
        materiaux=m['materiaux'],
        parent_manifeste_sha256=sha(parent / 'simulation_manifest.json'),
        prefixe_manifeste_sha256=sha(prefixe / 'simulation_manifest.json'),
        prefixe_calcport=derive['relecture_calcport'],
        rejeu_deplace_calcport=relu['relecture_calcport'],
        rejeu_deplace_S11_octets_identiques=True,
        temporaire_conserve=str(temporaire),
        sources_physiques_sha256=physiques, controles_sha256=controles,
        sources_et_controles_inchanges=True,
        qualification_globale_effectuee=False,
        limite='diagnostic court operateur/extraction ; aucune convergence acquise')
    neuf(preuves / 'fin_pilote.json', preuve)
    print(json.dumps(preuve, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
