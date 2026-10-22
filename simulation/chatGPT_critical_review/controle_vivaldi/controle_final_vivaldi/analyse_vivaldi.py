"""Controle Vivaldi independant, sans Run ni qualification officielle.

Par defaut : preconditions seulement, sans ecriture ni Q.charge_calcul.
APRES sortie 0 de la queue 20307, prefixe tres_fin_12ns compris :
  python -B analyse_vivaldi.py --queue-sortie-zero-confirmee --sortie controle_final_vivaldi

--sortie doit etre un sous-dossier neuf de ce repertoire. Sans cette option,
aucun fichier n'est ecrit. Codes : 0 criteres respectes ; 2 criteres non
respectes ; 3 preconditions manquantes ; 1 erreur d'integrite/configuration.
Les metriques et lecteurs partages sont reutilises depuis analyse_extreme_fin.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
ICI = Path(__file__).resolve().parent
SIMULATION = Path(__file__).resolve().parents[2]
UTILS_PATH = SIMULATION/"chatGPT_critical_review"/"controle_extreme_fin"/"analyse_extreme_fin.py"
_spec = importlib.util.spec_from_file_location("controle_vivaldi_utils", UTILS_PATH)
U = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(U)
Q, np = U.Q, U.np

PROFILS = [("base_8ns", "base", 8.), ("fin_8ns", "fin", 8.),
    ("fin_12ns", "fin", 12.), ("tres_fin_12ns", "tres_fin", 12.),
    ("tres_fin_16ns", "tres_fin", 16.)]


def provenance():
    p = U.provenance()
    p["scripts_sha256"][Path(__file__).name] = U.sha(__file__)
    p["dependance_numerique"] = str(UTILS_PATH)
    return p


def analyse(base, queue_sortie_zero_confirmee=False):
    racine = Path(base).resolve()/"vivaldi_tomographie"
    rapport = dict(qualification_officielle=False, mode="vivaldi", racine=str(racine),
        profils_attendus=[n for n, _, _ in PROFILS], provenance=provenance(),
        sortie_zero_queue_confirmee_par_coordinateur=bool(queue_sortie_zero_confirmee))
    manque = U.manquants(racine, PROFILS)
    if not queue_sortie_zero_confirmee:
        manque.append(dict(profil="coordination", motif="sortie zero de la queue 20307 non confirmee"))
    if manque:
        rapport.update(etat="preconditions_non_remplies", manquants=manque,
                       controles_numeriques_reussis=False)
        return rapport, 3
    donnees = {}
    for nom, niveau, duree in PROFILS:
        donnees[nom] = Q.charge_calcul(racine/nom, exiger_courant=True)
        Q.valide_campagne(*donnees[nom][2:], "vivaldi_tomographie", niveau, duree)
    premier = donnees[PROFILS[0][0]]
    for nom, d in donnees.items():
        if (not np.array_equal(d[0], premier[0]) or
            d[3]["geometrie_sha256"] != premier[3]["geometrie_sha256"] or
            Q.G.json_octets(d[3]["simulation_contract"]) !=
                Q.G.json_octets(premier[3]["simulation_contract"]) or
            d[2]["sources_sha256"] != premier[2]["sources_sha256"] or
            d[2]["environnement"] != premier[2]["environnement"]):
            raise ValueError("frequences/geometrie/contrat/sources/environnement differents : "+nom)
    spatial = ["fin_12ns", "tres_fin_12ns"]
    temporel = ["tres_fin_12ns", "tres_fin_16ns"]
    rapport["grille_temporelle"] = U.grille_identique(racine, temporel, donnees)
    for type_, noms in (("spatial", spatial), ("temporel", temporel)):
        rapport[type_] = dict(profils=noms, **U.ecarts_independants(
            donnees[noms[0]], donnees[noms[1]], type_))
    indicateurs = {nom: U.indicateurs_independants(*d[:2]) for nom, d in donnees.items()}
    rapport.update(etat="analyse_terminee", reference=temporel[-1],
        verifications_communes=dict(nombre_profils=len(donnees),
            geometrie_sha256=premier[3]["geometrie_sha256"],
            sources_physiques_sha256=premier[2]["sources_sha256"],
            environnement_archive=premier[2]["environnement"],
            contrat=premier[3]["simulation_contract"]),
        preuves={nom: {f: U.sha(racine/nom/f) for f in
            ("simulation_manifest.json", "qualification_entree.json", "s11.s1p", "maillage.npz")}
            for nom in donnees},
        passivite_par_profil={nom: {k: v[k] for k in ("maximum_module", "passivite_numerique")}
                             for nom, v in indicateurs.items()},
        indicateurs_reference=indicateurs[temporel[-1]])
    rapport["controles_numeriques_reussis"] = bool(rapport["spatial"]["reussi"] and
        rapport["temporel"]["reussi"] and rapport["indicateurs_reference"]["passivite_numerique"])
    return rapport, 0 if rapport["controles_numeriques_reussis"] else 2


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", type=Path, default=SIMULATION/"resultats"/"pcbway_r1")
    p.add_argument("--queue-sortie-zero-confirmee", action="store_true")
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
        rapport, code = analyse(args.base, args.queue_sortie_zero_confirmee)
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
