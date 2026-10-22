"""Niveaux de calcul complementaires, sans comparaison ni livraison.

Ce module ajoute un niveau de maillage au controleur existant dans le seul
processus appelant. Il ne modifie ni son fichier source, ni ses seuils. Exemple :
  python raffine_qualification_pcbway.py --antenne diamant_uwb_x18 \
      --niveau ultra_fin --duree-ns 12 --fils 10 --cout

Avant un vrai calcul, les deux scripts de controle et leur configuration sont
copies sans ecrasement sous BASE/journaux/controle_raffinement. Les preuves FDTD
restent gerees par qualifie_pcbway.calcule dans un dossier distinct.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from numbers import Integral, Real
from pathlib import Path


NIVEAUX_COMPLEMENTAIRES = {
    "ultra_fin": dict(mailles_par_lambda=22, mailles_par_lambda_air=16,
                      maille_min=0.125),
    "extreme_fin": dict(mailles_par_lambda=26, mailles_par_lambda_air=18,
                        maille_min=0.10),
    "n30": dict(mailles_par_lambda=30, mailles_par_lambda_air=20,
                maille_min=1 / 12),
    "n34": dict(mailles_par_lambda=34, mailles_par_lambda_air=22,
                maille_min=1.0 / 14),
}


def enregistre(Q):
    """Ajoute des copies des niveaux, ou refuse toute collision differente.

    Aucune modification n'a lieu si une des definitions est incompatible.
    L'import du controleur n'est pas fait au niveau module : Q pourra donc
    importer cette constante sans dependance circulaire.
    """
    for nom, definition in NIVEAUX_COMPLEMENTAIRES.items():
        if nom in Q.NIVEAUX and Q.NIVEAUX[nom] != definition:
            raise ValueError(f"collision de niveau de qualification : {nom}")
    for nom, definition in NIVEAUX_COMPLEMENTAIRES.items():
        if nom not in Q.NIVEAUX:
            Q.NIVEAUX[nom] = definition.copy()


def _duree(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, Real):
        raise ValueError("duree_ns doit etre un nombre reel strictement positif")
    valeur = float(valeur)
    if not math.isfinite(valeur) or valeur <= 0:
        raise ValueError("duree_ns doit etre finie et strictement positive")
    return valeur


def _fils(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, Integral) or valeur <= 0:
        raise ValueError("fils doit etre un entier strictement positif")
    return int(valeur)


def _archive_controle(Q, antenne, niveau, duree_ns, fils, base):
    """Conserve les octets de controle avant Run, hors de son dossier FDTD."""
    script = Path(__file__).resolve()
    controleur = Path(Q.__file__).resolve()
    copies = {script.name: script.read_bytes(), controleur.name: controleur.read_bytes()}
    contexte = dict(schema="controle_raffinement_pcbway_v1", antenne=antenne,
        niveau=niveau, definition=NIVEAUX_COMPLEMENTAIRES[niveau].copy(),
        duree_ns=duree_ns, fils=fils, base=str(base),
        montage=asdict(Q.montage_campagne(niveau, duree_ns)),
        sources_physiques_sha256=Q.F._sources(),
        scripts_sha256={nom: hashlib.sha256(octets).hexdigest()
                        for nom, octets in copies.items()},
        finalite="calcul complementaire uniquement; aucune validation ni livraison")
    copies["controle.json"] = (json.dumps(contexte, ensure_ascii=False,
        sort_keys=True, indent=2)+"\n").encode("utf-8")
    dossier = base/"journaux"/"controle_raffinement"/antenne/f"{niveau}_{duree_ns:g}ns"
    if dossier.exists():
        if not dossier.is_dir() or any(not (dossier/nom).is_file() or
                (dossier/nom).read_bytes() != octets for nom, octets in copies.items()):
            raise FileExistsError(f"archive de controle differente ou incomplete : {dossier}")
        return dossier
    dossier.mkdir(parents=True, exist_ok=False)
    for nom, octets in copies.items():
        with (dossier/nom).open("xb") as fichier:
            fichier.write(octets)
    return dossier


def calcule(antenne, niveau, duree_ns, fils=10, cout=False, base=None):
    """Valide les arguments puis delegue exclusivement a Q.calcule."""
    if not isinstance(niveau, str) or niveau not in NIVEAUX_COMPLEMENTAIRES:
        raise ValueError("niveau complementaire inconnu")
    duree_ns = _duree(duree_ns)
    fils = _fils(fils)
    if not isinstance(cout, bool):
        raise ValueError("cout doit etre booleen")
    import qualifie_pcbway as Q
    if not isinstance(antenne, str) or antenne not in Q.ANTENNES:
        raise ValueError("antenne de production inconnue")
    if isinstance(base, str) and not base.strip():
        raise ValueError("base ne doit pas etre vide")
    try:
        base = Path(Q.BASE if base is None else base).expanduser().resolve()
    except TypeError as erreur:
        raise ValueError("base doit etre un chemin") from erreur
    if base.exists() and not base.is_dir():
        raise NotADirectoryError(base)
    enregistre(Q)
    if not cout:
        _archive_controle(Q, antenne, niveau, duree_ns, fils, base)
    return Q.calcule(antenne, niveau, duree_ns, fils=fils, cout=cout, base=base)


def _duree_cli(texte):
    try:
        return _duree(float(texte))
    except ValueError as erreur:
        raise argparse.ArgumentTypeError(str(erreur)) from erreur


def _fils_cli(texte):
    try:
        return _fils(int(texte))
    except ValueError as erreur:
        raise argparse.ArgumentTypeError(str(erreur)) from erreur


def main(argv=None):
    import qualifie_pcbway as Q
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--antenne", choices=Q.ANTENNES, required=True)
    p.add_argument("--niveau", choices=NIVEAUX_COMPLEMENTAIRES, default="ultra_fin")
    p.add_argument("--duree-ns", type=_duree_cli, required=True)
    p.add_argument("--fils", type=_fils_cli, default=10)
    p.add_argument("--cout", action="store_true")
    p.add_argument("--base", type=Path, default=Q.BASE)
    args = p.parse_args(argv)
    calcule(args.antenne, args.niveau, args.duree_ns, fils=args.fils,
            cout=args.cout, base=args.base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
