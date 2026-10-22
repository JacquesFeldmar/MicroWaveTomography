"""Cloture stdlib des preuves, archives de controle et 18 copies sources."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent
SIM = ICI.parents[1]
BASE = SIM / "resultats/pcbway_maille_controlee_v2"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def charge(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def ecrit(nom, contenu):
    with (ICI / nom).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(contenu, f, ensure_ascii=True, indent=2); f.write("\n")


def main():
    avant = charge(ICI / "avant.json")
    rapport = charge(ICI / "rapport_croise.json")
    execution = charge(ICI / "execution.json")
    assert execution["code_execution_controle"] == 0
    assert rapport["controle_integrite_et_reproduction_reussi"] is True
    assert rapport["qualification_globale_reussie"] is False
    assert execution["stdout_sha256"] == sha(ICI / "execution.stdout.txt")
    assert execution["stderr_sha256"] == sha(ICI / "execution.stderr.txt")
    assert rapport["script_sha256"] == sha(ICI / "controle_croise.py")
    for nom, attendu in avant["sources_18_sha256"].items():
        assert sha(SIM / nom) == attendu
        assert sha(BASE / "controle_orchestration/sources" / nom) == attendu
    index = charge(BASE / "controle_orchestration/archive_sha256.json")
    for nom, attendu in index.items():
        p = (BASE / nom).resolve()
        assert p.is_relative_to(BASE) and sha(p) == attendu
    for nom, attendu in avant["fichiers_profils_sha256"].items():
        assert sha(BASE / nom) == attendu
    gel = SIM / "chatGPT_critical_review/integration_finale_f2/gel_campagne_F2.json"
    assert (BASE / "controle_orchestration/gel_attendu.json").read_bytes() == gel.read_bytes()
    physique = charge(gel)["sources_physiques_sha256"]
    controles = charge(gel)["controles_sha256"]
    preuves_calculs = []
    for nom in ("diamant_uwb", "diamant_uwb_x18", "vivaldi_tomographie"):
        for profil in ("base_12ns", "fin_16ns"):
            p = BASE / "journaux/controle_maille" / nom / profil
            entree = charge(p / "controle.json")
            fin = charge(p / "fin_calcul.json")
            assert entree["sources_physiques_sha256"] == physique
            assert entree["controles_sha256"] == controles
            assert fin["etat"] == "calcul_termine_et_verifie" and fin["sources_et_controles_inchanges"] is True
            assert fin["controle_entree_sha256"] == sha(p / "controle.json")
            assert fin["manifeste_sha256"] == sha(BASE / nom / profil / "simulation_manifest.json")
            assert fin["qualification_entree_sha256"] == sha(BASE / nom / profil / "qualification_entree.json")
            for source, attendu in controles.items():
                assert sha(p / source) == attendu
            preuves_calculs.append(dict(antenne=nom, profil=profil,
                controle_sha256=sha(p / "controle.json"), fin_sha256=sha(p / "fin_calcul.json"),
                sources10_et_controles8_declares_exacts=True, copies8_controles_octets_exacts=True))
    etat = charge(BASE / "etat_orchestration.json")
    fin = charge(BASE / "fin_orchestration.json")
    assert etat["etat"] == fin["etat"] == "non_convergence"
    assert etat["analyse"]["retour_natif"] == fin["retour_orchestrateur"] == 2
    journaux_sha = {p.relative_to(BASE).as_posix():sha(p)
        for p in sorted((BASE / "journaux").glob("*/*.log"))}
    for nom, attendu in avant["entrees_et_sorties_sha256"].items():
        assert sha(SIM / nom) == attendu
    ecrit("complement_cloture.json", dict(schema="complement_cloture_F2_v1", utc=datetime.now(timezone.utc).isoformat(),
        reussi_integrite=True, qualification_globale_reussie=False,
        archive_orchestration=dict(index_sha256=sha(BASE / "controle_orchestration/archive_sha256.json"),
            fichiers_indexes_relus=len(index), tous_SHA_exacts=True,
            copies18sources_octets_exacts=True, gel_attendu_byteexact=True),
        preuves_six_calculs=preuves_calculs, journaux_sha256=journaux_sha,
        sources18_et420fichiers_toujours_inchanges=True,
        code_controle=0, code_AP_numerique=2, code_orchestrateur_numerique=2,
        etat="non_convergence", aucun_Run=True, aucune_ecriture_projet=True))
    ecrit("revue_orchestration_independante.json", dict(
        relecteur="/root/reprise_fabrication/revue_cloture_orchestrateur_f2",
        nature="Retour de contrelecture independante en lecture seule, sans import projet, solveur ni test.",
        constats=dict(calculs6_code0=True, prefixes9_code0=True, deux_queues_terminees_code0=True,
            AP_code2_numerique=True, echec_technique=False, trois_spatiaux_FALSE_trois_temporels_TRUE=True,
            fin_UTC=fin["utc"], six_fin_calcul_sources_controles_inchanges=True),
        nuance="Avertissements openEMS sur nombre de pas/excitation et arret avant critere energetique conserves ; aucun traceback ni arret fatal vu par le relecteur. Les codes0 ne valent pas qualification numerique.",
        portee_sources="Le relecteur a compare les18SHA declares au gel ; la relecture des octets copies est faite par cloture_preuves.py et consignee dans complement_cloture.json."))
    lignes = ["CONTRELECTURE GLOBALE F2 CLOSE - NON QUALIFIEE", "",
        "Les15 profils sont termines et integres :420 fichiers et18 sources exacts avant/apres.",
        "Q charge les calculs avec exiger_courant=True et valide chaque campagne.",
        "AP ecrire=False reproduit exactement le bilan existant, sans modifier ses sorties.",
        "Les trois controles spatiaux echouent ; les trois controles temporels reussissent.",
        "Les trois references sont passives. Cette passivite ne corrige aucun echec spatial.", ""]
    for nom, r in rapport["verdicts_antennes"].items():
        for type_ecart in ("spatial", "temporel"):
            v = r[type_ecart]["valeurs"]
            lignes.append(f"{nom} {type_ecart} : max={v['maximum_complexe']!r}, RMS={v['rms_complexe']!r}, P95dB={v['percentile95_db']!r}, PASS={r[type_ecart]['reussi']}.")
    lignes += ["", "Vivaldi est recalcule par un parseur S1P RI et NumPy independants de Q.ecarts.",
        "Les valeurs, seuils et verdicts sont exactement reproduits ; masques183points spatial et192points temporel.",
        "Six paires temporelles (finales et preliminaires) ont axes NPZ et dt bitidentiques.",
        "Six Run et neuf prefixes sont clos code0 ; AP/orchestrateur code2 correspond au refus numerique attendu.",
        "Le controle present termine code0 parce que les constats sont reproduits ; qualification_globale_reussie=false.",
        "Aucun solveur, nouvelle grille, ecriture AP, PDF ou livraison. Aucune cause PEC physique n'est pretendue demontree.", ""]
    with (ICI / "note_resultats.txt").open("x", encoding="utf-8") as f:
        f.write("\n".join(lignes))
    fichiers = {p.relative_to(ICI).as_posix():sha(p) for p in sorted(ICI.rglob("*"))
        if p.is_file() and p.name != "index_sha256.json"}
    ecrit("index_sha256.json", dict(schema="index_contrelecture_globale_F2_v1",
        nombre_fichiers=len(fichiers), sha256=fichiers, exclusion="index_sha256.json uniquement"))
    for nom, attendu in fichiers.items(): assert sha(ICI / nom) == attendu
    print(json.dumps(dict(reussi_integrite=True, qualification_globale_reussie=False,
        fichiers_preuve=len(fichiers), rapport_sha256=sha(ICI / "rapport_croise.json"),
        index_sha256=sha(ICI / "index_sha256.json")), indent=2))


if __name__ == "__main__":
    main()
