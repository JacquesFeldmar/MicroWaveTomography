"""Calcul supplementaire autonome, sans modifier les seize sources gelees.

Catalogue PLUS immuable ; Q.calcule est appele directement. Le calcul refuse
tout profil, prefixe ou archive deja present, meme vide. La queue PowerShell
possede exclusivement ses journaux externes et doit en refuser toute
collision AVANT Start-Process. Ce module conserve ses propres traces dans une
archive neuve. W reste externe, suivi de --verifier-seulement sur le prefixe.

Exemples :
  python -B raffine_qualification_plus_pcbway.py --antenne diamant_uwb_x18 --niveau n34 --duree-ns 12 --cout
  python -B raffine_qualification_plus_pcbway.py --antenne diamant_uwb_x18 --niveau n34 --duree-ns 8 --verifier-seulement

Ni --cout ni --verifier-seulement n'ecrivent de fichiers ou ne lancent de FDTD.
Les empreintes de la phase gelee sont volontairement strictes : un rejeu avec
des controleurs differents exige de restaurer les sources exactes archivees.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from numbers import Integral, Real
from pathlib import Path
import platform
import sys

sys.dont_write_bytecode = True
ICI = Path(__file__).resolve().parent
NIVEAUX_PLUS = {
    "n34": dict(mailles_par_lambda=34, mailles_par_lambda_air=22,
                maille_min=1.0 / 14.0),
}
SHA_R_FIGE = "533c2678aba6219073601fc0101682bc82ae52c5b221ce66bfecfac323f859fb"
SHA_INVENTAIRE_INITIAL = "7922f3a99f33c926cff2e31586af40ff681e144498768b6c5644201d62833791"


def enregistre(Q):
    """Prevalide PLUS avant R, puis ajoute des copies sans redefinir de niveau."""
    for nom, definition in NIVEAUX_PLUS.items():
        if nom in Q.NIVEAUX and Q.NIVEAUX[nom] != definition:
            raise ValueError("collision de niveau PLUS : "+nom)
    import raffine_qualification_pcbway as R
    R.enregistre(Q)  # Sa propre prevalidation refuse toute collision avant ajout.
    for nom, definition in NIVEAUX_PLUS.items():
        if nom not in Q.NIVEAUX:
            Q.NIVEAUX[nom] = definition.copy()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_octets(objet):
    return (json.dumps(objet, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False)+"\n").encode("utf-8")


def _duree(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, Real):
        raise ValueError("duree doit etre un nombre reel")
    valeur = float(valeur)
    texte = f"{valeur:g}"
    if (not math.isfinite(valeur) or valeur <= 0 or "e" in texte.lower() or
            float(texte) != valeur):
        raise ValueError("duree positive finie, representable exactement dans un nom de profil requise")
    return valeur


def _fils(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, Integral) or valeur <= 0:
        raise ValueError("fils doit etre un entier strictement positif")
    return int(valeur)


def _sources_figees(Q):
    """Verifie l'inventaire initial lui-meme, les neuf sources physiques et R."""
    chemin = Path(Q.BASE)/"journaux"/"controle_initial"/"pipeline_statut_initial.json"
    octets = chemin.read_bytes()  # Instantane termine et immuable, pas le statut actif.
    digest = hashlib.sha256(octets).hexdigest()
    if digest != SHA_INVENTAIRE_INITIAL:
        raise ValueError("empreinte de l'inventaire initial differente")
    inventaire = json.loads(octets)
    physiques = inventaire["sources_physiques_sha256"]
    controles = inventaire["scripts_orchestration_sha256"]
    attendues = {**physiques, **controles, "raffine_qualification_pcbway.py": SHA_R_FIGE}
    if len(physiques) != 9 or len(controles) != 6 or len(attendues) != 16:
        raise ValueError("inventaire des seize sources incomplet")
    racine = Path(Q.__file__).resolve().parent
    for nom, empreinte in attendues.items():
        p = (racine/nom).resolve()
        if not p.is_relative_to(racine) or not p.is_file() or _sha(p) != empreinte:
            raise ValueError("source gelee modifiee : "+nom)
    if Q.F._sources() != physiques:
        raise ValueError("catalogue des sources physiques different de l'initial")
    return dict(sources_16_sha256=attendues, inventaire_sha256=digest,
        inventaire_chemin=str(chemin.resolve()), inventaire_octets=octets,
        sources_physiques_initiales_sha256=physiques)


def _controle_sources_apres(Q, avant, propre_sha):
    if _sources_figees(Q) != avant or _sha(__file__) != propre_sha:
        raise ValueError("sources ou controleur PLUS modifies pendant l'operation")


def _configuration(Q, antenne, niveau, duree_ns):
    montage = Q.montage_campagne(niveau, duree_ns)
    carte = Q.G.carte_antenne(antenne)
    return dict(profil_relatif=f"{antenne}/{niveau}_{duree_ns:g}ns", duree_ns=duree_ns,
        montage=asdict(montage), signature_physique=Q.signature(carte, montage))


def _plan(Q, antenne, niveau, duree_ns, prefixe_ns, base):
    calcul = _configuration(Q, antenne, niveau, duree_ns)
    prefixe = _configuration(Q, antenne, niveau, prefixe_ns)
    archive = base/"journaux"/"controle_raffinement_plus"/antenne/f"{niveau}_{duree_ns:g}ns"
    return dict(calcul=calcul, prefixe=prefixe), archive


def _refuse_cibles_existantes(base, profils, archive):
    for chemin in (base/profils["calcul"]["profil_relatif"],
                   base/profils["prefixe"]["profil_relatif"], archive):
        if chemin.exists() or chemin.is_symlink():
            raise FileExistsError("cible deja presente, aucune reutilisation : "+str(chemin))


def _versions(Q):
    import os
    import scipy
    import openEMS
    import CSXCAD
    return dict(python=platform.python_version(), executable=sys.executable,
        numpy=Q.np.__version__, scipy=scipy.__version__, openems=openEMS.__version__,
        csxcad=CSXCAD.__version__, systeme=platform.platform(),
        environnement_threads={n: os.environ.get(n) for n in
            ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")})


def _archive_avant(Q, antenne, niveau, duree_ns, fils, prefixe_ns, base,
                   profils, archive, sources, propre_sha):
    import raffine_qualification_pcbway as R
    fichiers = {Path(__file__).name: Path(__file__).read_bytes(),
        Path(Q.__file__).name: Path(Q.__file__).read_bytes(),
        Path(R.__file__).name: Path(R.__file__).read_bytes(),
        "inventaire_sources_initial.json": sources["inventaire_octets"]}
    catalogues = dict(Q_effectif={n: d.copy() for n, d in Q.NIVEAUX.items()},
        R_declares={n: d.copy() for n, d in R.NIVEAUX_COMPLEMENTAIRES.items()},
        PLUS_declares={n: d.copy() for n, d in NIVEAUX_PLUS.items()})
    fichiers["catalogues.json"] = _json_octets(catalogues)
    commande = [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
        "--antenne", antenne, "--niveau", niveau, "--duree-ns", f"{duree_ns:g}",
        "--prefixe-ns", f"{prefixe_ns:g}", "--fils", str(fils), "--base", str(base)]
    contexte = dict(schema="controle_raffinement_plus_pcbway_v1",
        utc=datetime.now(timezone.utc).isoformat(), qualification_officielle=False,
        antenne=antenne, niveau=niveau, duree_ns=duree_ns, prefixe_ns=prefixe_ns,
        fils=fils, base=str(base), profils=profils,
        sources_16_sha256=sources["sources_16_sha256"],
        sources_physiques_initiales_sha256=sources["sources_physiques_initiales_sha256"],
        inventaire_source=dict(chemin=sources["inventaire_chemin"], sha256=sources["inventaire_sha256"]),
        scripts_sha256={n: hashlib.sha256(v).hexdigest() for n, v in fichiers.items() if n.endswith(".py")},
        controleur_plus_sha256=propre_sha,
        catalogues_sha256=hashlib.sha256(fichiers["catalogues.json"]).hexdigest(),
        commande_reproduction=commande, orig_argv=list(sys.orig_argv),
        argv_processus=list(sys.argv), versions=_versions(Q),
        contrat_journaux="La queue PS refuse tous ses logs externes avant Start-Process ; PLUS ne les controle pas car ils existent deja a l'entree Python.",
        contrat_execution="Calcul unique frais ; W externe puis verifier-seulement du prefixe ; aucune comparaison ou selection officielle.")
    fichiers["controle.json"] = _json_octets(contexte)
    # mkdir exclusif reserve la cible entre deux instances PLUS concurrentes.
    archive.mkdir(parents=True, exist_ok=False)
    for nom, octets in fichiers.items():
        with (archive/nom).open("xb") as f:
            f.write(octets)
    empreintes = {n: hashlib.sha256(v).hexdigest() for n, v in fichiers.items()}
    with (archive/"archive_sha256.json").open("xb") as f:
        f.write(_json_octets(empreintes))
    return dict(fichiers_sha256=empreintes, index_sha256=_sha(archive/"archive_sha256.json"))


def _controle_archive(archive, empreintes):
    if _sha(archive/"archive_sha256.json") != empreintes["index_sha256"]:
        raise ValueError("index de l'archive PLUS modifie")
    for nom, digest in empreintes["fichiers_sha256"].items():
        if _sha(archive/nom) != digest:
            raise ValueError("archive PLUS modifiee : "+nom)


def _trace(archive, evenement, **details):
    with (archive/"execution_interne.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
            evenement=evenement, **details), ensure_ascii=False)+"\n")


def _verifie_calcul(Q, antenne, niveau, duree_ns, base):
    attendu = _configuration(Q, antenne, niveau, duree_ns)
    dossier = base/attendu["profil_relatif"]
    _, _, manifeste, entree = Q.charge_calcul(dossier, exiger_courant=True)
    Q.valide_campagne(manifeste, entree, antenne, niveau, duree_ns)
    if entree["signature_physique"] != attendu["signature_physique"]:
        raise ValueError("signature du profil differente du plan PLUS")
    return dict(profil=attendu["profil_relatif"], signature_physique=entree["signature_physique"],
        manifeste_sha256=_sha(dossier/"simulation_manifest.json"),
        qualification_entree_sha256=_sha(dossier/"qualification_entree.json"),
        derive_sondes=bool(manifeste.get("derive_sondes", False)),
        execution=manifeste["execution"], qualification_officielle=False)


def calcule(antenne, niveau, duree_ns, fils=10, cout=False, base=None,
            verifier_seulement=False, prefixe_ns=None):
    if not isinstance(niveau, str) or niveau not in NIVEAUX_PLUS:
        raise ValueError("niveau PLUS inconnu")
    duree_ns, fils = _duree(duree_ns), _fils(fils)
    if not isinstance(cout, bool) or not isinstance(verifier_seulement, bool) or (cout and verifier_seulement):
        raise ValueError("cout et verifier_seulement doivent etre booleens et exclusifs")
    if prefixe_ns is not None and (cout or verifier_seulement):
        raise ValueError("prefixe_ns est reserve au mode calcul")
    if not cout and not verifier_seulement:
        cible = Decimal(str(duree_ns))
        prefixe_ns = _duree(float(cible-Decimal("4")) if prefixe_ns is None else prefixe_ns)
        depart = Decimal(str(prefixe_ns))
        if depart >= cible or cible-depart < Decimal("4"):
            raise ValueError("prefixe positif et prolongement minimal de 4 ns requis")
    import qualifie_pcbway as Q
    if not isinstance(antenne, str) or antenne not in Q.ANTENNES:
        raise ValueError("antenne de production inconnue")
    if isinstance(base, str) and not base.strip():
        raise ValueError("base vide")
    try:
        base = Path(Q.BASE if base is None else base).expanduser().resolve()
    except TypeError as erreur:
        raise ValueError("base doit etre un chemin") from erreur
    if base.exists() and not base.is_dir():
        raise NotADirectoryError(base)
    enregistre(Q)
    sources, propre_sha = _sources_figees(Q), _sha(__file__)
    if cout:
        try:
            return Q.calcule(antenne, niveau, duree_ns, fils=fils, cout=True, base=base)
        finally:
            _controle_sources_apres(Q, sources, propre_sha)
    if verifier_seulement:
        try:
            return dict(operation="verification_seule", **_verifie_calcul(Q, antenne, niveau, duree_ns, base))
        finally:
            _controle_sources_apres(Q, sources, propre_sha)
    profils, archive = _plan(Q, antenne, niveau, duree_ns, prefixe_ns, base)
    _refuse_cibles_existantes(base, profils, archive)
    empreintes = _archive_avant(Q, antenne, niveau, duree_ns, fils, prefixe_ns,
        base, profils, archive, sources, propre_sha)
    _controle_sources_apres(Q, sources, propre_sha)
    _controle_archive(archive, empreintes)
    _trace(archive, "avant_calcul", profils=profils)
    try:
        # Les deux autres chemins restent frais apres la reservation atomique.
        for cle in ("calcul", "prefixe"):
            if (base/profils[cle]["profil_relatif"]).exists():
                raise FileExistsError("profil apparu apres la reservation PLUS")
        Q.calcule(antenne, niveau, duree_ns, fils=fils, cout=False, base=base)
        _controle_sources_apres(Q, sources, propre_sha)
        validation = _verifie_calcul(Q, antenne, niveau, duree_ns, base)
        with (archive/"validation_apres_calcul.json").open("xb") as f:
            f.write(_json_octets(validation))
        _trace(archive, "calcul_termine_valide", validation=validation)
        return dict(operation="calcul_termine_valide", **validation)
    except BaseException as erreur:
        _trace(archive, "echec", erreur=repr(erreur))
        raise
    finally:
        _controle_sources_apres(Q, sources, propre_sha)
        _controle_archive(archive, empreintes)


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
    p.add_argument("--niveau", choices=NIVEAUX_PLUS, default="n34")
    p.add_argument("--duree-ns", type=_duree_cli, required=True)
    p.add_argument("--prefixe-ns", type=_duree_cli)
    p.add_argument("--fils", type=_fils_cli, default=10)
    p.add_argument("--base", type=Path, default=Q.BASE)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--cout", action="store_true")
    modes.add_argument("--verifier-seulement", action="store_true")
    args = p.parse_args(argv)
    resultat = calcule(args.antenne, args.niveau, args.duree_ns, fils=args.fils,
        cout=args.cout, base=args.base, verifier_seulement=args.verifier_seulement,
        prefixe_ns=args.prefixe_ns)
    if resultat is not None:
        print(json.dumps(resultat, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
