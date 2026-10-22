"""Lancement F2 avec controles archives, apres validation de son maillage.

Ce fichier est en staging : ne l'installer a la racine qu'avec Q/W/F2 valides.
Un appel de calcul exige des dossiers neufs ; le mode cout n'ecrit rien.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
RACINE = Path(__file__).resolve().parent
MOTEUR = 'maillage_controle_v2'
BASE = RACINE / 'resultats/pcbway_maille_controlee_v2'
CONTROLES = ('qualifie_pcbway.py', 'qualification_adaptative.py',
             'fenetre_sondes.py', 'raffine_qualification_pcbway.py',
             'export_gerber.py', 'donnees.py', 'traitement.py',
             'calcule_maille_controlee.py')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def neuf(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def calcul(antenne, niveau, duree_ns, fils=10, base=BASE, cout=False):
    import fdtd_maille_controlee as F2
    import qualifie_pcbway as Q
    if antenne not in Q.ANTENNES or niveau not in ('base', 'fin'):
        raise ValueError('Antenne ou niveau F2 inconnu')
    if not isfinite(duree_ns) or float(duree_ns) not in (8., 12., 16.):
        raise ValueError('Duree de campagne F2 : 8, 12 ou 16 ns')
    if type(fils) is not int or fils not in (1, 2, 4, 10):
        raise ValueError('Fils : 1, 2, 4 ou 10')
    if F2.NOM_MOTEUR != MOTEUR:
        raise ValueError('Identifiant moteur F2 inattendu')
    base = Path(base).resolve()
    historique = (RACINE / 'resultats/pcbway_r1').resolve()
    if base.is_relative_to(historique) or historique.is_relative_to(base):
        raise ValueError('La campagne F2 doit etre distincte de la campagne historique')
    profil = f'{niveau}_{duree_ns:g}ns'
    dossier = base / antenne / profil
    archive = base / 'journaux/controle_maille' / antenne / profil
    if cout:
        return Q.calcule(antenne, niveau, duree_ns, fils=fils, cout=True,
                         base=base, moteur=MOTEUR)
    # Aucun fichier de controle ni calcul ne doit etre ecrase, meme vide.
    if dossier.exists() or archive.exists():
        raise FileExistsError('Dossier de calcul ou archive de controle deja present')
    physiques = F2._sources()
    if len(physiques) != 10 or 'fdtd_maille_controlee.py' not in physiques:
        raise ValueError('Les dix sources physiques F2 sont requises')
    controles = {n: sha(RACINE / n) for n in CONTROLES}
    if any(sha(RACINE / n) != h for n, h in physiques.items()):
        raise ValueError('Inventaire physique F2 different des fichiers courants')
    archive.mkdir(parents=True, exist_ok=False)
    for n in CONTROLES:
        shutil.copyfile(RACINE / n, archive / n)
    entree = dict(schema='controle_avant_calcul_maille_v2',
        utc=datetime.now(timezone.utc).isoformat(), moteur=MOTEUR, antenne=antenne,
        niveau=niveau, duree_ns=duree_ns, fils=fils,
        montage=asdict(Q.montage_campagne(niveau, duree_ns, moteur=MOTEUR)),
        sources_physiques_sha256=physiques, controles_sha256=controles,
        qualification_globale_effectuee=False)
    neuf(archive / 'controle.json', entree)

    def verifie_sources():
        if F2._sources() != physiques:
            raise ValueError('Inventaire physique change depuis lancement')
        if any(sha(RACINE / n) != h for n, h in {**physiques, **controles}.items()):
            raise ValueError('Source ou controle change pendant calcul')

    verifie_sources()
    Q.calcule(antenne, niveau, duree_ns, fils=fils, base=base, moteur=MOTEUR)
    verifie_sources()
    f, s, m, q = Q.charge_calcul(dossier, exiger_courant=True)
    Q.valide_campagne(m, q, antenne, niveau, duree_ns)
    if m.get('moteur') != MOTEUR or q.get('moteur') != MOTEUR:
        raise ValueError('Les deux marqueurs F2 sont requis')
    if m['sources_sha256'] != physiques:
        raise ValueError('Sources du calcul differentes de celles archivees avant Run')
    result = dict(schema='fin_calcul_maille_v2', utc=datetime.now(timezone.utc).isoformat(),
        moteur=MOTEUR, profil=profil, antenne=antenne, etat='calcul_termine_et_verifie',
        controle_entree_sha256=sha(archive / 'controle.json'),
        manifeste_sha256=sha(dossier / 'simulation_manifest.json'),
        qualification_entree_sha256=sha(dossier / 'qualification_entree.json'),
        execution=m['execution'], indicateurs=Q.indicateurs(f, s),
        sources_et_controles_inchanges=True, qualification_globale_effectuee=False)
    neuf(archive / 'fin_calcul.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--antenne', required=True, choices=('diamant_uwb', 'diamant_uwb_x18', 'vivaldi_tomographie'))
    p.add_argument('--niveau', required=True, choices=('base', 'fin'))
    p.add_argument('--duree-ns', type=float, required=True)
    p.add_argument('--fils', type=int, choices=(1, 2, 4, 10), default=10)
    p.add_argument('--base', type=Path, default=BASE)
    p.add_argument('--cout', action='store_true')
    a = p.parse_args(argv)
    calcul(a.antenne, a.niveau, a.duree_ns, a.fils, a.base, a.cout)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
