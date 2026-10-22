"""Preuve preparatoire sur trois calculs acheves, lecture seule.

Le succes de ces executions physiques ne signifie pas que la file globale
initiale soit sortie 0 : sa comparaison a echoue. Cette preuve n'atteste donc
aucune sortie 0 globale ni aucune qualification. Aucun CLI final n'est ajoute.
"""
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyse_vivaldi as V


def preuve():
    base = V.SIMULATION/"resultats"/"pcbway_r1"
    racine = base/"vivaldi_tomographie"
    profils = [("base_8ns", "base", 8.), ("fin_8ns", "fin", 8.), ("fin_12ns", "fin", 12.)]
    fige = json.loads((base/"journaux/controle_initial/pipeline_statut_initial.json").read_text(encoding="utf-8"))
    sources = {**fige["sources_physiques_sha256"], **fige["scripts_orchestration_sha256"],
        "raffine_qualification_pcbway.py": "533c2678aba6219073601fc0101682bc82ae52c5b221ce66bfecfac323f859fb"}
    avant_sources = {n: V.U.sha(V.SIMULATION/n) for n in sources}
    if len(sources) != 16 or avant_sources != sources:
        raise ValueError("les seize sources ne correspondent pas au gel attendu")
    def inventaire():
        return {str(p): V.U.sha(p) for n, _, _ in profils
                for p in (racine/n).rglob("*") if p.is_file()}
    avant = inventaire()
    d = {}
    for nom, niveau, duree in profils:
        d[nom] = V.Q.charge_calcul(racine/nom, exiger_courant=True)
        V.Q.valide_campagne(*d[nom][2:], "vivaldi_tomographie", niveau, duree)
    spatial = V.U.ecarts_independants(d["base_8ns"], d["fin_8ns"], "spatial")
    temporel = V.U.ecarts_independants(d["fin_8ns"], d["fin_12ns"], "temporel")
    attendus = dict(spatial=[.0942647817337662, .04179304240011919, 2.5985376033433263],
                    temporel=[.03172385741729312, .008299422325135537, .5811223209935332])
    for nom, ecart in (("spatial", spatial), ("temporel", temporel)):
        chiffres = [ecart["valeurs"][k] for k in ("maximum_complexe", "rms_complexe", "percentile95_db")]
        if chiffres != attendus[nom] or ecart["reussi"]:
            raise ValueError("les valeurs historiques attendues ne sont pas exactement retrouvees")
    with patch.object(V.Q, "charge_calcul", side_effect=AssertionError("chargement final interdit")) as charge:
        pending, code = V.analyse(base)
        if code != 3 or charge.call_count != 0:
            raise ValueError("la garde de preconditions finales ne fonctionne pas")
    apres_sources = {n: V.U.sha(V.SIMULATION/n) for n in sources}
    apres = inventaire()
    if avant_sources != apres_sources or avant != apres:
        raise ValueError("un fichier d'entree a change pendant la preuve")
    return dict(qualification_officielle=False,
        portee="trois executions physiques terminees ; aucune affirmation de sortie 0 de la file globale initiale",
        spatial=spatial, temporel=temporel, valeurs_exactes_attendues_retrouvees=True,
        preconditions_finales=dict(code_sortie=code, nombre_Q_charge_calcul=charge.call_count,
                                  manquants=pending["manquants"]),
        controle_lecture_seule=dict(nombre_fichiers_profils=len(avant),
            profils_sha256_avant_apres_identiques=True, sources_16_avant_apres_identiques=True),
        sources_16_sha256_avant=avant_sources, sources_16_sha256_apres=apres_sources,
        fichiers_profils_sha256_avant=avant, fichiers_profils_sha256_apres=apres,
        provenance=V.provenance(), script_preuve_sha256=V.U.sha(__file__))


if __name__ == "__main__":
    print(json.dumps(preuve(), ensure_ascii=False, indent=2, allow_nan=False))
