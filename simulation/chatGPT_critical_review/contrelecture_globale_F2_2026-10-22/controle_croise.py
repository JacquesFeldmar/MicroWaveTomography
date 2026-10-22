"""Lecture seule des 15 profils F2 clos et calcul NumPy Vivaldi independant."""
import os
for cle in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[cle] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["MPLBACKEND"] = "Agg"
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[1]
BASE = SIM / "resultats/pcbway_maille_controlee_v2"
os.environ["CSXCAD_INSTALL_PATH"] = str(SIM.parent / "outils/openEMS")
sys.path.insert(0, str(SIM))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def charge(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def ecrit_neuf(nom, contenu):
    with (ICI / nom).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(contenu, f, ensure_ascii=True, indent=2, allow_nan=False)
        f.write("\n")


def main():
    if (ICI / "avant.json").exists() or (ICI / "rapport_croise.json").exists():
        raise FileExistsError("Les preuves doivent etre neuves")
    import numpy as np
    import qualifie_pcbway as Q
    import qualification_adaptative as AP
    import fdtd_maille_controlee as F2
    assert Path(Q.__file__).resolve() == SIM / "qualifie_pcbway.py"
    assert Path(AP.__file__).resolve() == SIM / "qualification_adaptative.py"
    gel_path = SIM / "chatGPT_critical_review/integration_finale_f2/gel_campagne_F2.json"
    gel = charge(gel_path)
    attendues = {**gel["sources_physiques_sha256"], **gel["controles_sha256"]}
    assert len(gel["sources_physiques_sha256"]) == 10 and len(attendues) == 18
    sources_avant = {n: sha(SIM / n) for n in attendues}
    assert sources_avant == attendues
    global_path = BASE / "qualification_globale.json"
    enregistre = charge(global_path)
    assert enregistre["moteur"] == Q.MOTEUR_F2
    profils = {n: AP.calculs_utilises(enregistre, n) for n in Q.ANTENNES}
    assert sum(map(len, profils.values())) == 15 and all(len(v) == 5 for v in profils.values())
    dossiers = [BASE / n / p for n, noms in profils.items() for p in noms]
    fichiers_avant = {p.relative_to(BASE).as_posix(): sha(p)
        for d in dossiers for p in sorted(d.rglob("*")) if p.is_file()}
    manifestes_avant = {d.relative_to(BASE).as_posix(): sha(d / "simulation_manifest.json") for d in dossiers}
    inputs = [global_path, BASE / "selection_qualification.json", BASE / "etat_orchestration.json",
              BASE / "fin_orchestration.json", gel_path]
    inputs += sorted(p for n in Q.ANTENNES for p in (BASE / n / "comparaison").glob("*") if p.is_file())
    inputs_avant = {str(p.relative_to(SIM)): sha(p) for p in inputs}
    ecrit_neuf("avant.json", dict(utc=datetime.now(timezone.utc).isoformat(),
        sources_18_sha256=sources_avant, manifestes_15_sha256=manifestes_avant,
        fichiers_profils_sha256=fichiers_avant, entrees_et_sorties_sha256=inputs_avant))

    donnees, validations, temps = {}, [], []
    with patch.object(F2, "lance", side_effect=AssertionError("Run interdit")), \
         patch.object(F2, "construit", side_effect=AssertionError("Nouvelle grille interdite")), \
         patch.object(F2, "_sauve_manifeste", side_effect=AssertionError("Ecriture interdite")), \
         patch.object(Q, "sauve", side_effect=AssertionError("Ecriture Q interdite")), \
         patch.object(Q, "figures", side_effect=AssertionError("Figure Q interdite")):
        for nom, noms in profils.items():
            donnees[nom] = {}
            communs = None
            for profil in noms:
                d = BASE / nom / profil
                f, s, m, q = Q.charge_calcul(d, exiger_courant=True)
                niveau, duree = AP.profil(profil)
                Q.valide_campagne(m, q, nom, niveau, duree)
                assert m["moteur"] == q["moteur"] == Q.MOTEUR_F2
                assert m["sources_sha256"] == gel["sources_physiques_sha256"]
                assert m["etat"] == "termine" and len(f) == 213
                assert np.array_equal(f, np.linspace(1e9, 6.3e9, 213))
                courant = dict(geometrie_sha256=q["geometrie_sha256"],
                    geometrie_fdtd_sha256=sha(d / "geometrie.json"),
                    contrat=q["simulation_contract"], sources=m["sources_sha256"], environnement=m["environnement"],
                    frequence_sha256=hashlib.sha256(f.tobytes()).hexdigest())
                if communs is None: communs = courant
                assert canon(courant) == canon(communs)
                donnees[nom][profil] = (f, s, m, q)
                validations.append(dict(antenne=nom, profil=profil, charge_exiger_courant=True,
                    valide_campagne=True, moteur=m["moteur"], etat=m["etat"],
                    derive_sondes=bool(m.get("derive_sondes")), n_pas=m["execution"]["n_pas"],
                    dt_s=m["execution"]["dt_s"], geometrie_sha256=q["geometrie_sha256"],
                    geometrie_fdtd_sha256=courant["geometrie_fdtd_sha256"],
                    maximum_module=float(np.max(np.abs(s))),
                    passivite_numerique=bool(np.max(np.abs(s)) <= 1.005)))
            spec = enregistre["antennes"][nom]["selection_effective"]
            paires = [spec["temporel"]] + [e["calculs"] for e in spec["preliminaires"] if e["type"] == "temporel"]
            for a, b in paires:
                x, y = donnees[nom][a][2], donnees[nom][b][2]
                assert struct.pack("!d", x["execution"]["dt_s"]) == struct.pack("!d", y["execution"]["dt_s"])
                axes_sha = {}
                with np.load(BASE / nom / a / "maillage.npz", allow_pickle=False) as aa, \
                     np.load(BASE / nom / b / "maillage.npz", allow_pickle=False) as bb:
                    for axe in "xyz":
                        u, v = aa[axe], bb[axe]
                        assert u.dtype.str == v.dtype.str == "<f8" and u.shape == v.shape
                        assert u.tobytes() == v.tobytes()
                        axes_sha[axe] = hashlib.sha256(u.tobytes()).hexdigest()
                temps.append(dict(antenne=nom, calculs=[a, b], dt_bitidentique=True,
                    dt_hex=struct.pack("!d", x["execution"]["dt_s"]).hex(), axes_bitidentiques=True, axes_sha256=axes_sha))
        recalcule = AP.comparer(BASE, ecrire=False)
        assert canon(recalcule) == canon(enregistre)

    # Parseur S1P et metriques NumPy independants : aucun Q.ecarts ou lit_s1p ici.
    def lit_ri(path):
        texte = path.read_text(encoding="ascii")
        entetes = [l.strip().upper().split() for l in texte.splitlines() if l.strip().startswith("#")]
        assert entetes == [["#", "HZ", "S", "RI", "R", "50"]]
        lignes = [l.split("!", 1)[0] for l in texte.splitlines() if l.strip() and not l.lstrip().startswith(("!", "#"))]
        tab = np.loadtxt(io.StringIO("\n".join(lignes)), dtype=np.float64)
        assert tab.shape == (213, 3) and np.all(np.isfinite(tab))
        assert np.array_equal(tab[:, 0], np.linspace(1e9, 6.3e9, 213))
        return tab[:, 0], tab[:, 1] + 1j * tab[:, 2]

    def metriques(sa, sb, temporel):
        delta = np.abs(sa - sb)
        masque = (np.abs(sa) >= .1) & (np.abs(sb) >= .1)
        db = np.abs(20 * np.log10(np.maximum(np.abs(sa), 1e-15) / np.maximum(np.abs(sb), 1e-15)))
        phase = np.abs(np.angle(sa * np.conj(sb), deg=True))
        valeurs = dict(maximum_complexe=float(np.max(delta)), rms_complexe=float(np.sqrt(np.mean(delta ** 2))),
            percentile95_db=float(np.percentile(db[masque], 95)), percentile95_phase_deg=float(np.percentile(phase[masque], 95)))
        seuils = dict(maximum_complexe=.015 if temporel else .05, rms_complexe=.005 if temporel else .02,
            percentile95_db=.5 if temporel else 1.)
        return dict(valeurs=valeurs, seuils_acceptation=seuils,
            reussi=bool(all(valeurs[k] <= v for k, v in seuils.items())),
            points_masque=int(masque.sum()), points_complexes=len(sa))

    nom = "vivaldi_tomographie"
    courbes = {p: lit_ri(BASE / nom / p / "s11.s1p") for p in profils[nom]}
    controles_v = {}
    for type_ecart in ("spatial", "temporel"):
        paire = enregistre["antennes"][nom]["selection_effective"][type_ecart]
        a, b = [courbes[p] for p in paire]
        assert np.array_equal(a[0], b[0])
        mesure = metriques(a[1], b[1], type_ecart == "temporel")
        attendu = enregistre["antennes"][nom][type_ecart]
        assert mesure["valeurs"] == attendu["valeurs"]
        assert mesure["seuils_acceptation"] == attendu["seuils_acceptation"]
        assert mesure["reussi"] is attendu["reussi"]
        controles_v[type_ecart] = dict(calculs=paire, **mesure)
    f, s = courbes["fin_16ns"]
    refmax = float(np.max(np.abs(s)))
    assert refmax == enregistre["antennes"][nom]["indicateurs"]["maximum_module"]
    utile = (f >= 1.4e9) & (f <= 6e9)
    dbutile = 20 * np.log10(np.maximum(np.abs(s[utile]), 1e-18))
    indices = dict(maximum_module=refmax, passivite_numerique=bool(refmax <= 1.005),
        points=213, points_bande_1p4_6=int(utile.sum()), points_moins10=int((dbutile < -10).sum()),
        points_moins6=int((dbutile < -6).sum()),
        moyenne_puissance_reflechie_db=float(10 * np.log10(np.mean(np.abs(s[utile]) ** 2))),
        pire_db=float(dbutile.max()))
    attendu = enregistre["antennes"][nom]["indicateurs"]["bande_1p4_6"]
    assert indices["points_moins10"] == attendu["moins_10_db"]["points_sous_seuil"]
    assert indices["points_moins6"] == attendu["moins_6_db"]["points_sous_seuil"]
    assert indices["moyenne_puissance_reflechie_db"] == attendu["moyenne_puissance_reflechie_db"]
    assert indices["pire_db"] == attendu["pire_db"]

    etat = charge(BASE / "etat_orchestration.json")
    fin = charge(BASE / "fin_orchestration.json")
    etapes = [e for q in etat["queues"].values() for e in q["etapes"]]
    assert len(etapes) == 15 and sum(e["type"] == "calcul" for e in etapes) == 6
    assert sum(e["type"] == "prefixe" for e in etapes) == 9 and all(e["retour_natif"] == 0 for e in etapes)
    assert etat["etat"] == fin["etat"] == "non_convergence"
    assert etat["echec_numerique"] is True and etat["echec_technique"] is False
    assert etat["analyse"]["retour_natif"] == etat["retour_orchestrateur"] == fin["retour_orchestrateur"] == 2
    assert etat["tous_reussis"] is fin["tous_reussis"] is recalcule["tous_reussis"] is False
    stdout_ap = charge(BASE / "journaux/analyse/AP.stdout.log")
    assert canon(stdout_ap) == canon(enregistre)
    assert (BASE / "journaux/analyse/AP.stderr.log").stat().st_size == 0

    fichiers_apres = {p.relative_to(BASE).as_posix(): sha(p)
        for d in dossiers for p in sorted(d.rglob("*")) if p.is_file()}
    sources_apres = {n: sha(SIM / n) for n in attendues}
    inputs_apres = {str(p.relative_to(SIM)): sha(p) for p in inputs}
    assert fichiers_avant == fichiers_apres and sources_avant == sources_apres and inputs_avant == inputs_apres
    for r in recalcule["antennes"].values():
        assert r["spatial"]["reussi"] is False and r["temporel"]["reussi"] is True and r["reussi"] is False
        assert r["indicateurs"]["passivite_numerique"] is True
    bilan = dict(schema="contrelecture_globale_F2_close_v1", utc=datetime.now(timezone.utc).isoformat(),
        controle_integrite_et_reproduction_reussi=True, qualification_globale_reussie=False,
        verdict="REFUS_NUMERIQUE : trois echecs spatiaux ; trois controles temporels reussis ; references passives",
        aucun_Run=True, aucune_nouvelle_grille=True, aucune_ecriture_AP=True, aucun_PDF_ou_livraison=True,
        script_sha256=sha(__file__), gel_sources_sha256=sha(gel_path),
        sources_18_avant=sources_avant, sources_18_apres=sources_apres,
        manifestes_15_sha256=manifestes_avant, fichiers_profils_nombre=len(fichiers_avant), fichiers_profils_inchanges=True,
        entrees_sorties_avant=inputs_avant, entrees_sorties_apres=inputs_apres,
        AP_ecrire_false_reproduit_bilan_exact=True,
        profils_valides=validations, paires_temporelles_bitidentiques=temps,
        verdicts_antennes={n:{k:r[k] for k in ("spatial", "temporel", "reussi", "indicateurs", "selection_effective")}
            for n, r in recalcule["antennes"].items()},
        vivaldi_numpy_independant=dict(parseur="S1P Hz RI 50ohms strict, NumPy direct sans Q.ecarts ni lit_s1p",
            ecarts=controles_v, indicateurs_reference=indices,
            passivite_cinq_profils={p:bool(np.max(np.abs(v[1])) <= 1.005) for p,v in courbes.items()},
            maxima_cinq_profils={p:float(np.max(np.abs(v[1]))) for p,v in courbes.items()}),
        orchestration=dict(etat=etat["etat"], calculs=6, prefixes=9, codes_etapes_tous_zero=True,
            code_AP=2, code_orchestrateur=2, echec_numerique=True, echec_technique=False, fin=fin,
            stdout_AP_identique_bilan=True, stderr_AP_vide=True),
        limites=["La relecture et les codes0 valident l'integrite technique, pas la convergence spatiale.",
            "Aucun nouveau calcul ni diagnostic causal de l'operateur PEC n'est execute.",
            "Le controle lui-meme termine code0 si les constats sont reproduits ; le verdict de qualification reste false."])
    ecrit_neuf("rapport_croise.json", bilan)
    print(json.dumps(dict(controle_reproduit=True, qualification_globale_reussie=False,
        fichiers_profils=len(fichiers_avant), manifestes=15, sources=18,
        vivaldi_numpy=bilan["vivaldi_numpy_independant"], rapport_sha256=sha(ICI / "rapport_croise.json")), indent=2), flush=True)


if __name__ == "__main__":
    main()
