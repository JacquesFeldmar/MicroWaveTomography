"""Contre-verification numerique du grand losange, sans Run ni qualification.

Lecture seule par defaut. Python de l'environnement openems requis.
  python -B analyse_extreme_fin.py
  python -B analyse_extreme_fin.py --verification-precedente
  python -B analyse_extreme_fin.py --sortie controle_final

--sortie designe un sous-dossier NEUF de ce repertoire, jamais un profil de
calcul. Il recoit rapport, provenance, journal et copie exacte de l'analyseur.
Codes : 0 criteres respectes ; 2 criteres non respectes ; 3 preuves manquantes
ou calcul encore en cours ; 1 erreur d'integrite/configuration. Aucun resultat
ne remplace une selection ou une qualification officielle du projet.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import traceback

sys.dont_write_bytecode = True
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
ICI = Path(__file__).resolve().parent
SIMULATION = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SIMULATION))

import numpy as np
import qualifie_pcbway as Q
import raffine_qualification_pcbway as R

# Seuils declares dans le controleur Q gele ; calcul des metriques independant.
SEUILS = {
    "spatial": dict(maximum_complexe=.05, rms_complexe=.02, percentile95_db=1.),
    "temporel": dict(maximum_complexe=.015, rms_complexe=.005, percentile95_db=.5),
}
PROFILS = [("base_8ns", "base", 8.), ("fin_8ns", "fin", 8.),
    ("fin_12ns", "fin", 12.), ("tres_fin_8ns", "tres_fin", 8.),
    ("tres_fin_12ns", "tres_fin", 12.), ("ultra_fin_8ns", "ultra_fin", 8.),
    ("ultra_fin_12ns", "ultra_fin", 12.), ("extreme_fin_8ns", "extreme_fin", 8.),
    ("extreme_fin_12ns", "extreme_fin", 12.)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance():
    return dict(utc=datetime.now(timezone.utc).isoformat(),
        commande=sys.argv, python=platform.python_version(), numpy=np.__version__,
        threads=dict(OMP_NUM_THREADS=os.environ["OMP_NUM_THREADS"],
                     OPENBLAS_NUM_THREADS=os.environ["OPENBLAS_NUM_THREADS"]),
        scripts_sha256={p.name: sha(p) for p in
            (Path(__file__), Path(Q.__file__), Path(R.__file__))})


def manquants(racine, profils):
    resultat = []
    for nom, _, _ in profils:
        p = racine/nom
        if not (p/"simulation_manifest.json").is_file():
            resultat.append(dict(profil=nom, motif="manifeste absent"))
            continue
        m = json.loads((p/"simulation_manifest.json").read_text(encoding="utf-8"))
        if m["etat"] == "echec":
            raise ValueError(f"calcul en echec : {nom}")
        if m["etat"] != "termine":
            resultat.append(dict(profil=nom, motif="calcul non termine", etat=m["etat"]))
            continue
        fichiers = [n for n in ("qualification_entree.json", "s11.s1p",
            "s11_indicateurs.json", "maillage.npz") if not (p/n).is_file()]
        if fichiers:
            resultat.append(dict(profil=nom, motif="preuves finales absentes", fichiers=fichiers))
    return resultat


def ecarts_independants(a, b, type_):
    fa, sa = a[:2]
    fb, sb = b[:2]
    if not np.array_equal(fa, fb):
        raise ValueError("grilles frequentielles differentes")
    delta = np.abs(sa-sb)
    garde = (np.abs(sa) >= .1) & (np.abs(sb) >= .1)
    db = np.abs(20*np.log10(np.maximum(np.abs(sa), 1e-15)/
                             np.maximum(np.abs(sb), 1e-15)))
    phase = np.abs(np.angle(sa*np.conj(sb), deg=True))
    valeurs = dict(maximum_complexe=float(delta.max()),
        rms_complexe=float(np.sqrt(np.mean(delta**2))),
        percentile95_db=float(np.percentile(db[garde], 95, method="linear")) if garde.any() else None,
        percentile95_phase_deg=float(np.percentile(phase[garde], 95, method="linear")) if garde.any() else None)
    seuils = SEUILS[type_].copy()
    return dict(valeurs=valeurs, seuils_acceptation=seuils,
        reussi=all(valeurs[k] is not None and valeurs[k] <= limite for k, limite in seuils.items()),
        points_masque_db=int(garde.sum()),
        masque_db="deux modules >= -20 dB ; max/RMS sur tous les points")


def bandes(f, s, seuil):
    sous = 20*np.log10(np.maximum(np.abs(s), 1e-18)) < seuil
    ids = np.flatnonzero(sous)
    groupes = np.split(ids, np.flatnonzero(np.diff(ids) > 1)+1)
    return dict(seuil_db=seuil,
        segments_hz=[[float(f[g[0]]), float(f[g[-1]])] for g in groupes if len(g)],
        couverture=float(sous.mean()), points_sous_seuil=int(sous.sum()), points_total=len(f))


def indicateurs_independants(f, s):
    utile = (f >= 1.4e9) & (f <= 6e9)
    maximum = float(np.abs(s).max())
    return dict(bande_hz=[float(f[0]), float(f[-1])], points=len(f),
        maximum_module=maximum, passivite_numerique=maximum <= 1.005,
        moins_10_db=bandes(f, s, -10.), moins_6_db=bandes(f, s, -6.),
        bande_1p4_6=dict(moins_10_db=bandes(f[utile], s[utile], -10.),
            moins_6_db=bandes(f[utile], s[utile], -6.),
            moyenne_puissance_reflechie_db=float(10*np.log10(max(float(
                np.mean(np.abs(s[utile])**2)), 1e-36))),
            pire_db=float(20*np.log10(max(float(np.abs(s[utile]).max()), 1e-18)))))


def grille_identique(racine, noms, donnees):
    a, b = (donnees[n][2] for n in noms)
    if a["maillage"] != b["maillage"]:
        raise ValueError("resumes de grille differents dans la paire temporelle")
    if float(a["execution"]["dt_s"]).hex() != float(b["execution"]["dt_s"]).hex():
        raise ValueError("pas temporels differents")
    with np.load(racine/noms[0]/"maillage.npz", allow_pickle=False) as ma, \
         np.load(racine/noms[1]/"maillage.npz", allow_pickle=False) as mb:
        for axe in "xyz":
            x, y = ma[axe], mb[axe]
            if (x.dtype.str != "<f8" or y.dtype.str != "<f8" or x.ndim != 1 or
                    x.shape != y.shape or x.tobytes() != y.tobytes()):
                raise ValueError("coordonnees temporelles differentes sur "+axe)
            digest = hashlib.sha256(x.tobytes()).hexdigest()
            if digest != a["maillage"]["axes"][axe]["sha256"]:
                raise ValueError("empreinte des coordonnees incoherente sur "+axe)
    return dict(coordonnees_bit_a_bit_identiques=True, dt_bit_a_bit_identique=True,
                dt_s=a["execution"]["dt_s"])


def analyse(base, precedente=False):
    R.enregistre(Q)  # Uniquement dans la memoire de ce processus.
    racine = Path(base).resolve()/"diamant_uwb_x18"
    profils = PROFILS[:7] if precedente else PROFILS
    rapport = dict(qualification_officielle=False, racine=str(racine),
        mode="verification_precedente" if precedente else "extreme_fin",
        profils_attendus=[p[0] for p in profils], provenance=provenance())
    manque = manquants(racine, profils)
    if manque:
        rapport.update(etat="preconditions_non_remplies", manquants=manque,
                       controles_numeriques_reussis=False)
        return rapport, 3
    donnees = {}
    for nom, niveau, duree in profils:
        donnees[nom] = Q.charge_calcul(racine/nom, exiger_courant=True)
        Q.valide_campagne(*donnees[nom][2:], "diamant_uwb_x18", niveau, duree)
    premier = donnees[profils[0][0]]
    for nom, d in donnees.items():
        if (d[3]["geometrie_sha256"] != premier[3]["geometrie_sha256"] or
            Q.G.json_octets(d[3]["simulation_contract"]) !=
                Q.G.json_octets(premier[3]["simulation_contract"]) or
            d[2]["sources_sha256"] != premier[2]["sources_sha256"] or
            d[2]["environnement"] != premier[2]["environnement"]):
            raise ValueError("geometrie/contrat/sources/environnement differents : "+nom)
    spatial = ["tres_fin_12ns", "ultra_fin_12ns"] if precedente else ["ultra_fin_12ns", "extreme_fin_12ns"]
    temporel = ["ultra_fin_8ns", "ultra_fin_12ns"] if precedente else ["extreme_fin_8ns", "extreme_fin_12ns"]
    rapport["grille_temporelle"] = grille_identique(racine, temporel, donnees)
    for type_, noms in (("spatial", spatial), ("temporel", temporel)):
        rapport[type_] = dict(profils=noms, **ecarts_independants(
            donnees[noms[0]], donnees[noms[1]], type_))
    reference = donnees[temporel[-1]]
    rapport.update(etat="analyse_terminee", reference=temporel[-1],
        verifications_communes=dict(nombre_profils=len(donnees),
            geometrie_sha256=premier[3]["geometrie_sha256"],
            sources_physiques_sha256=premier[2]["sources_sha256"],
            environnement_archive=premier[2]["environnement"],
            contrat=premier[3]["simulation_contract"]),
        preuves={nom: {f: sha(racine/nom/f) for f in
            ("simulation_manifest.json", "qualification_entree.json", "s11.s1p", "maillage.npz")}
            for nom in donnees},
        passivite_par_profil={nom: dict(maximum_module=float(np.abs(d[1]).max()),
            passivite_numerique=bool(np.abs(d[1]).max() <= 1.005)) for nom, d in donnees.items()},
        indicateurs_reference=indicateurs_independants(*reference[:2]))
    rapport["controles_numeriques_reussis"] = bool(rapport["spatial"]["reussi"] and
        rapport["temporel"]["reussi"] and rapport["indicateurs_reference"]["passivite_numerique"])
    return rapport, 0 if rapport["controles_numeriques_reussis"] else 2


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", type=Path, default=SIMULATION/"resultats"/"pcbway_r1")
    p.add_argument("--verification-precedente", action="store_true")
    p.add_argument("--sortie", type=Path)
    args = p.parse_args(argv)
    sortie = None
    trace = ""
    try:
        if args.sortie is not None:
            candidate = (ICI/args.sortie).resolve()
            if candidate == ICI or not candidate.is_relative_to(ICI) or candidate.exists():
                raise ValueError("--sortie doit viser un sous-dossier neuf de "+str(ICI))
            sortie = candidate
        rapport, code = analyse(args.base, args.verification_precedente)
    except Exception as erreur:
        trace = traceback.format_exc()
        rapport = dict(qualification_officielle=False, etat="erreur_integrite_configuration",
            controles_numeriques_reussis=False, erreur=str(erreur), provenance=provenance())
        code = 1
    texte = json.dumps(rapport, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    print(texte, end="")
    if sortie is not None:
        sortie.mkdir(parents=True, exist_ok=False)
        (sortie/"rapport.json").write_text(texte, encoding="utf-8")
        (sortie/"provenance.json").write_text(json.dumps(rapport["provenance"],
            ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        (sortie/"execution.txt").write_text("Code de sortie : "+str(code)+"\n"+
            "Aucun FDTD, aucune selection ou qualification officielle ecrite.\n"+trace,
            encoding="utf-8")
        (sortie/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    return code


if __name__ == "__main__":
    raise SystemExit(main())
