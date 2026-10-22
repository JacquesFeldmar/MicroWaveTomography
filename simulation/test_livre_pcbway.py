"""Delivery gates with temporary synthetic campaign fixtures; no solver run."""
import copy
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest

import export_gerber as G
import livre_pcbway as L


def ecrit(path, contenu):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(G.json_octets(contenu) if isinstance(contenu, dict) else contenu)
    return path


@pytest.fixture
def campagne(tmp_path, monkeypatch):
    """Mock only Q's already-tested numerical gates; retain actual G geometry."""
    base = tmp_path / "campagne"
    racine = tmp_path / "projet"
    sortie = tmp_path / "livraison" / "revision_r1"
    bilan = dict(schema="qualification_pcbway_r1", tous_reussis=True, antennes={})
    entrees, manifests = {}, {}
    for nom in L.Q.ANTENNES:
        carte = G.carte_antenne(nom)
        indicateurs = dict(bande_1p4_6=dict(
            moins_10_db=dict(couverture=.75), moins_6_db=dict(couverture=.95),
            moyenne_puissance_reflechie_db=-10.5, pire_db=-3.5))
        resultat = dict(reussi=True, spatial=dict(reussi=True), temporel=dict(reussi=True),
                        indicateurs=indicateurs, preuves_sha256={})
        for niveau in L.CALCULS:
            dossier = base / nom / niveau
            q = dict(geometrie=G.geometrie_canonique(carte),
                     simulation_contract=carte["simulation_contract"],
                     geometrie_sha256=hashlib.sha256(G.json_octets(G.geometrie_canonique(carte))).hexdigest(),
                     signature_physique="fixture-sans-solveur")
            m = dict(sources_sha256={"fixture.py": hashlib.sha256(b"fixture").hexdigest()})
            entrees[f"{nom}/{niveau}"] = q
            manifests[f"{nom}/{niveau}"] = m
            for f, contenu in {"qualification_entree.json": q, "simulation_manifest.json": m,
                               "geometrie.json": {"fixture": True},
                               "sources/fixture.py": b"fixture", "entree_openems.xml": b"<fixture/>",
                               "s11.s1p": b"fixture S11", "port_ut_1": b"fixture voltage",
                               "port_it_1": b"fixture current", "maillage.npz": b"fixture grid"}.items():
                p = ecrit(dossier / f, contenu)
                resultat["preuves_sha256"][p.relative_to(base).as_posix()] = L._sha(p)
        resultat["sorties_sha256"] = {}
        for f in L.SORTIES:
            p = ecrit(base / nom / "comparaison" / f, b"fixture " + f.encode())
            resultat["sorties_sha256"][p.relative_to(base).as_posix()] = L._sha(p)
        resultat["reference"] = str(base / nom / "fin_12ns")
        bilan["antennes"][nom] = resultat
        ecrit(base / nom / "comparaison" / "qualification.json", resultat)
    ecrit(base / "qualification_globale.json", bilan)
    for f in L.REFERENCES:
        ecrit(racine / "references" / f, b"test asset - not a manufacturer document")
    for f in L.GUIDES:
        ecrit(racine / "fabrication" / f, b"test guide")
    ecrit(racine / "PROTOCOLE_MESURE_PCBWAY.md", b"test protocol")
    ecrit(racine / "requirements_fabrication.txt", b"test requirements")
    ecrit(racine / "requirements_fdtd.txt", b"test scientific requirements")
    ecrit(racine / "qualifie_pcbway.py", b"# test tools placeholder\n")
    for carte in (G.carte_panneau_losanges(), G.carte_antenne("vivaldi_tomographie")):
        G.exporte(carte, racine / "fabrication" / carte["nom"])
    appels = []

    def charge(dossier, exiger_courant=False):
        assert exiger_courant is True
        cle = Path(dossier).relative_to(base).as_posix()
        appels.append(cle)
        return np.array([1e9, 6e9]), np.array([.1+0j, .2+0j]), manifests[cle], entrees[cle]

    recalcule = copy.deepcopy(bilan)

    def comparer(base, ecrire=True):
        assert ecrire is False
        return recalcule

    def verifie(zip_path, sortie, attendu=None, rendus=True):
        assert rendus is True
        ecrit(Path(sortie) / "controle_fixture.json", dict(ok=True))
        return None, True

    monkeypatch.setattr(L.Q, "charge_calcul", charge)
    monkeypatch.setattr(L.Q, "comparer", comparer)
    monkeypatch.setattr(L.V, "verifie", verifie)
    return dict(base=base, racine=racine, sortie=sortie, bilan=bilan,
                recalcule=recalcule, entrees=entrees, manifests=manifests, appels=appels)


@pytest.fixture
def campagne_adaptative(campagne, monkeypatch):
    """A longer selected window with the failed initial trial still archived."""
    c = campagne
    petit = "diamant_uwb"
    selection = dict(schema="selection_qualification_pcbway_v1", antennes={
        petit: dict(spatial=["base_16ns", "fin_16ns"],
                    temporel=["fin_12ns", "fin_16ns"], reference="fin_16ns",
                    preliminaires=[
                        dict(type="spatial", calculs=["base_8ns", "fin_8ns"],
                             motif="premiere comparaison spatiale conservee"),
                        dict(type="temporel", calculs=["fin_8ns", "fin_12ns"],
                             motif="premiere fenetre 8 ns insuffisante")])})
    for niveau in ("base_16ns", "fin_16ns"):
        original = c["base"] / petit / "base_8ns"
        dossier = c["base"] / petit / niveau
        for f in original.rglob("*"):
            if f.is_file():
                destination = ecrit(dossier / f.relative_to(original), f.read_bytes())
                c["bilan"]["antennes"][petit]["preuves_sha256"][destination.relative_to(c["base"]).as_posix()] = L._sha(destination)
        c["entrees"][f"{petit}/{niveau}"] = copy.deepcopy(c["entrees"][f"{petit}/base_8ns"])
        c["manifests"][f"{petit}/{niveau}"] = copy.deepcopy(c["manifests"][f"{petit}/base_8ns"])
    for nom, resultat in c["bilan"]["antennes"].items():
        spec = (selection["antennes"][petit] if nom == petit else dict(
            spatial=["base_8ns", "fin_8ns"], temporel=["fin_8ns", "fin_12ns"],
            reference="fin_12ns", preliminaires=[]))
        resultat["selection_effective"] = copy.deepcopy(spec)
        resultat["calculs_utilises"] = (list(L.CALCULS) + ["base_16ns", "fin_16ns"]
                                          if nom == petit else list(L.CALCULS))
        resultat["reference"] = str(c["base"] / nom / spec["reference"])
        resultat["essais_preliminaires"] = [dict(
            **essai, ecarts=dict(reussi=essai["type"] == "spatial",
                valeurs=dict(maximum_complexe=.02134, rms_complexe=.00534)))
            for essai in spec["preliminaires"]]
        ecrit(c["base"] / nom / "comparaison/qualification.json", resultat)
    config = ecrit(c["base"] / "selection_qualification.json", selection)
    c["bilan"]["configuration_sha256"] = {config.name: L._sha(config)}
    c["bilan"]["selection"] = selection
    ecrit(c["base"] / "qualification_globale.json", c["bilan"])
    c["recalcule"].clear()
    c["recalcule"].update(copy.deepcopy(c["bilan"]))
    ecrit(c["racine"] / "qualification_adaptative.py", b"# test adaptive selection helper\n")
    return c


def prepare(c):
    return L.livre(c["base"], c["sortie"], racine=c["racine"])


def test_livraison_neuve_copie_exacte_et_archive_complete(campagne):
    c = campagne
    sortie = prepare(c)
    assert len(c["appels"]) == 9
    assert L.verifie_livraison(sortie)
    manifeste = json.loads((sortie / L.MANIFESTE).read_text(encoding="utf-8"))
    assert len(manifeste["articles"]) == 2
    assert L.MANIFESTE not in manifeste["fichiers_sha256"]
    for nom in ("panneau_losanges", "vivaldi_tomographie"):
        source = c["racine"] / "fabrication" / nom / (nom + "_pcbway.zip")
        assert (sortie / "uploads" / source.name).read_bytes() == source.read_bytes()
        with zipfile.ZipFile(source) as z:
            assert (sortie / "uploads" / (nom + "_lisez_moi.txt")).read_bytes() == z.read(nom + "_lisez_moi.txt")
    with zipfile.ZipFile(sortie / "preuves_calculs.zip") as z:
        assert len([n for n in z.namelist() if n.endswith("entree_openems.xml")]) == 9
        assert len([n for n in z.namelist() if n.endswith("port_ut_1")]) == 9
        assert len([n for n in z.namelist() if n.endswith("sources/fixture.py")]) == 9
        assert all(not Path(n).is_absolute() and "\\" not in n and ".." not in n.split("/") for n in z.namelist())
    texte = (sortie / "README.md").read_text(encoding="utf-8")
    assert "75.00 %" in texte and "95.00 %" in texte
    assert "2 different designs" in texte


def test_preuves_orchestration_et_codes_finaux_livres_octet_par_octet(campagne):
    c = campagne
    traces = {
        "controle_orchestration/gel_attendu.json": b'{"fixture":"gel18"}\n',
        "controle_orchestration/queue_vivaldi.json": b'{"fixture":"queue"}\n',
        "controle_orchestration/sources/fdtd_maille_controlee.py": b'# fixture moteur archive\n',
        "etat_orchestration.json": b'{"etat":"qualifie","tous_reussis":true}\n',
        "fin_orchestration.json": b'{"retour_orchestrateur":0,"tous_reussis":true}\n',
        "orchestration.lock": b'{"pid":1234,"fixture":true}\n',
    }
    for nom, contenu in traces.items():
        ecrit(c["base"] / nom, contenu)
    sortie = prepare(c)
    manifeste = json.loads((sortie / L.MANIFESTE).read_text(encoding="utf-8"))
    for nom, contenu in traces.items():
        relatif = "documentation/campagne/" + nom
        assert (sortie / relatif).read_bytes() == contenu
        assert manifeste["fichiers_sha256"][relatif] == hashlib.sha256(contenu).hexdigest()
    assert L.verifie_livraison(sortie)


def test_qualification_absente_ne_cree_pas_de_livraison(tmp_path):
    with pytest.raises(ValueError, match="absent"):
        L.livre(tmp_path / "absente", tmp_path / "livraison")
    assert not (tmp_path / "livraison").exists()


@pytest.mark.parametrize("valeur", [False, 1, "true", None])
def test_convergence_non_strictement_vraie_refusee(campagne, valeur):
    c = campagne
    c["bilan"]["tous_reussis"] = valeur
    ecrit(c["base"] / "qualification_globale.json", c["bilan"])
    with pytest.raises(ValueError, match="convergence non reussie"):
        prepare(c)
    assert not c["sortie"].exists()


def test_refuse_ecrasement_meme_dossier_vide(campagne):
    c = campagne
    c["sortie"].mkdir(parents=True)
    with pytest.raises(FileExistsError):
        prepare(c)
    assert not list(c["sortie"].iterdir())


def test_recalcul_des_criteres_refuse_qualification_mensongere(campagne):
    c = campagne
    c["recalcule"]["tous_reussis"] = False
    with pytest.raises(ValueError, match="recalcul"):
        prepare(c)
    assert not c["sortie"].exists()


@pytest.mark.parametrize("fichier", ["port_ut_1", "geometrie.json", "sources/fixture.py"])
def test_preuves_sha256_revalidees(campagne, fichier):
    c = campagne
    ecrit(c["base"] / "diamant_uwb" / "base_8ns" / fichier, b"modified")
    with pytest.raises(ValueError, match="preuve SHA-256 alteree"):
        prepare(c)
    assert not c["sortie"].exists()


def test_refuse_omission_dans_inventaire_preuves(campagne):
    c = campagne
    c["bilan"]["antennes"]["diamant_uwb"]["preuves_sha256"].pop("diamant_uwb/base_8ns/port_ut_1")
    ecrit(c["base"] / "qualification_globale.json", c["bilan"])
    with pytest.raises(ValueError, match="inventaire des preuves"):
        prepare(c)


@pytest.mark.parametrize("fichier", L.SORTIES)
def test_refuse_courbes_alterees(campagne, fichier):
    c = campagne
    ecrit(c["base"] / "diamant_uwb" / "comparaison" / fichier, b"modified curve")
    with pytest.raises(ValueError, match="courbe de qualification alteree"):
        prepare(c)
    assert not c["sortie"].exists()


@pytest.mark.parametrize("champ", ["geometrie", "simulation_contract"])
def test_refuse_geometrie_ou_contrat_anciens(campagne, champ):
    c = campagne
    c["entrees"]["diamant_uwb/fin_12ns"][champ] = {"ancienne_revision": True}
    with pytest.raises(ValueError, match="geometrie/contrat"):
        prepare(c)


def test_refus_zip_gerber_non_conforme(campagne, monkeypatch):
    monkeypatch.setattr(L.V, "verifie", lambda *a, **kw: (None, False))
    with pytest.raises(ValueError, match="ZIP de fabrication non conforme"):
        prepare(campagne)
    assert not campagne["sortie"].exists()


def test_panel_refuse_cuivre_non_identique_aux_composants_translates():
    carte = copy.deepcopy(G.carte_panneau_losanges())
    x, y = carte["F_Cu"][0][0]
    carte["F_Cu"][0][0] = (x + .1, y)
    with pytest.raises(ValueError, match="composants translates"):
        L._verifie_panneau(carte)


def test_comparaisons_recursives_exclues_de_l_archive(campagne):
    c = campagne
    ecrit(c["base"] / "diamant_uwb/base_8ns/comparaison/recursive.zip", b"excluded")
    sortie = prepare(c)
    with zipfile.ZipFile(sortie / "preuves_calculs.zip") as z:
        assert not any("comparaison" in n for n in z.namelist())


def test_refuse_fichier_livre_modifie(campagne):
    sortie = prepare(campagne)
    ecrit(sortie / "simulations/diamant_uwb/reference_simulation.s1p", b"modified")
    with pytest.raises(ValueError, match="fichier livre altere"):
        L.verifie_livraison(sortie)


def test_aucune_publication_si_entree_change_pendant_copie(campagne, monkeypatch):
    original = L._copie_verifiee
    def change(source, destination, sha):
        if Path(source).name == "requirements_fdtd.txt":
            ecrit(source, b"edited while packing")
        return original(source, destination, sha)
    monkeypatch.setattr(L, "_copie_verifiee", change)
    with pytest.raises(ValueError, match="modifie pendant"):
        prepare(campagne)
    assert not campagne["sortie"].exists()


def test_integration_verificateur_gerber_reel_sur_zip_altere(campagne, monkeypatch):
    c = campagne
    zip_path = c["racine"] / "fabrication/panneau_losanges/panneau_losanges_pcbway.zip"
    with zipfile.ZipFile(zip_path) as z:
        fichiers = {n: z.read(n) for n in z.namelist() if not n.endswith(".GTL")}
    with zipfile.ZipFile(zip_path, "w") as z:
        for n, b in fichiers.items():
            z.writestr(n, b)
    import verifie_gerber
    # The fixture patched L.V (the same module); restore its actual function
    # from the saved implementation below, rather than faking Gerber analysis.
    monkeypatch.setattr(L.V, "verifie", VERIFIE_REEL)
    with pytest.raises(ValueError, match="ZIP de fabrication non conforme"):
        prepare(c)
    assert not c["sortie"].exists()


def test_cli_expose_base_et_destination_exactes(tmp_path, monkeypatch, capsys):
    appels = []
    def faux_livre(base, sortie):
        appels.append((base, sortie))
        return sortie
    monkeypatch.setattr(L, "livre", faux_livre)
    base, sortie = tmp_path / "preuves", tmp_path / "livraison"
    assert L.principal(["--base", str(base), "--sortie", str(sortie)]) == 0
    assert appels == [(base, sortie)]
    assert str(sortie) in capsys.readouterr().out


def test_copie_outil_mesure_et_liens_documentation(campagne):
    c = campagne
    ecrit(c["racine"] / "compare_s11.py", b"# test measurement tool\n")
    ecrit(c["racine"] / "compare_s11_usage.md", b"[protocole](PROTOCOLE_MESURE_PCBWAY.md)\n")
    ecrit(c["racine"] / "PROTOCOLE_MESURE_PCBWAY.md", b"[mode](compare_s11_usage.md)\n")
    ecrit(c["racine"] / "fabrication/README.md",
          b"[plan](../references/cinch_catalogue.pdf)\n[zip](panneau_losanges/panneau_losanges_pcbway.zip)\n")
    documents = {
        "compare_s11_usage.md": ("documentation/compare_s11_usage.md", "../README.md"),
        "PROTOCOLE_MESURE_PCBWAY.md": ("documentation/PROTOCOLE_MESURE_PCBWAY.md", "../README.md"),
        "fabrication/README.md": ("documentation/fabrication/README.md", "../../README.md"),
    }
    originaux = {nom: (c["racine"] / nom).read_bytes() for nom in documents}
    sortie = prepare(c)
    assert (sortie / "sources_outils/compare_s11.py").is_file()
    assert not (sortie / "sources_outils/compare_s11_usage.md").exists()
    assert (sortie / "documentation/compare_s11_usage.md").is_file()
    assert "](PROTOCOLE_MESURE_PCBWAY.md)" in (sortie / "documentation/compare_s11_usage.md").read_text()
    assert "](compare_s11_usage.md)" in (sortie / "documentation/PROTOCOLE_MESURE_PCBWAY.md").read_text()
    assert (sortie / "sources_outils/requirements_fdtd.txt").is_file()
    guide = (sortie / "documentation/fabrication/README.md").read_text()
    assert "](../../references/cinch_catalogue.pdf)" in guide
    assert "](../../uploads/panneau_losanges_pcbway.zip)" in guide
    readme = (sortie / "README.md").read_text(encoding="utf-8")
    assert "](documentation/compare_s11_usage.md)" in readme
    assert "--simulation simulations/vivaldi_tomographie/reference_simulation.s1p" in readme
    assert "--sortie ../comparaison_V01" in readme
    manifeste = json.loads((sortie / L.MANIFESTE).read_text(encoding="utf-8"))
    for nom, (relatif, lien) in documents.items():
        assert (c["racine"] / nom).read_bytes() == originaux[nom]
        copie = sortie / relatif
        contenu = copie.read_bytes()
        texte = contenu.decode("utf-8")
        assert "Contexte de cette copie livrée" in texte
        assert "les tests et les outils USB" in texte
        assert f"]({lien})" in texte
        assert (copie.parent / lien).resolve() == (sortie / "README.md").resolve()
        assert manifeste["fichiers_sha256"][relatif] == hashlib.sha256(contenu).hexdigest()
        assert contenu != originaux[nom]
    assert L.verifie_livraison(sortie)


def test_livraison_adaptative_reference16_et_preliminaires_conserves(campagne_adaptative):
    c = campagne_adaptative
    import qualification_adaptative as A
    selection, effectives, sha, _ = A.lire_selection(c["base"])
    assert selection == c["bilan"]["selection"]
    assert effectives["diamant_uwb"]["reference"] == "fin_16ns"
    assert sha == c["bilan"]["configuration_sha256"]["selection_qualification.json"]
    assert L._profils_calculs(c["bilan"], "diamant_uwb") == A.calculs_utilises(c["bilan"], "diamant_uwb")
    sortie = prepare(c)
    assert len(c["appels"]) == 11
    assert L.verifie_livraison(sortie)
    manifeste = json.loads((sortie / L.MANIFESTE).read_text(encoding="utf-8"))
    assert len(manifeste["calculs"]) == 11
    assert "diamant_uwb/fin_16ns" in manifeste["calculs"]
    assert "sources_outils/qualification_adaptative.py" in manifeste["fichiers_sha256"]
    assert "sources_outils/qualifie_pcbway.py" in manifeste["fichiers_sha256"]
    assert (sortie / "sources_outils/qualification_adaptative.py").read_bytes() == (
        c["racine"] / "qualification_adaptative.py").read_bytes()
    with zipfile.ZipFile(sortie / "preuves_calculs.zip") as z:
        assert len([n for n in z.namelist() if n.endswith("entree_openems.xml")]) == 11
        assert "diamant_uwb/fin_8ns/port_ut_1" in z.namelist()
        assert "diamant_uwb/fin_16ns/port_ut_1" in z.namelist()
        assert z.read("selection_qualification.json") == (c["base"] / "selection_qualification.json").read_bytes()
        index = json.loads(z.read("index_preuves_sha256.json"))
        assert index["selection_qualification.json"] == c["bilan"]["configuration_sha256"]["selection_qualification.json"]
    readme = (sortie / "README.md").read_text(encoding="utf-8")
    assert "les 11 dossiers" in readme
    assert "| diamant_uwb | fin_16ns | base_16ns / fin_16ns | fin_12ns / fin_16ns |" in readme
    assert "premiere fenetre 8 ns insuffisante" in readme
    assert "comparaison insuffisante" in readme
    assert "La reference est fin_12ns" not in readme


def test_configuration_adaptative_sha_raw_alteree_refusee(campagne_adaptative):
    c = campagne_adaptative
    path = c["base"] / "selection_qualification.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="configuration SHA-256 alteree"):
        prepare(c)
    assert not c["sortie"].exists()


def test_configuration_adaptative_snapshot_different_refuse(campagne_adaptative):
    c = campagne_adaptative
    c["bilan"]["selection"]["antennes"]["diamant_uwb"]["reference"] = "fin_12ns"
    ecrit(c["base"] / "qualification_globale.json", c["bilan"])
    with pytest.raises(ValueError, match="instantane de selection"):
        prepare(c)


def test_configuration_adaptative_chemin_non_sur_refuse(campagne_adaptative):
    c = campagne_adaptative
    sha = next(iter(c["bilan"]["configuration_sha256"].values()))
    c["bilan"]["configuration_sha256"] = {"../selection_qualification.json": sha}
    ecrit(c["base"] / "qualification_globale.json", c["bilan"])
    with pytest.raises(ValueError, match="chemin relatif interdit"):
        prepare(c)


def test_configuration_adaptative_obligatoire(campagne_adaptative):
    c = campagne_adaptative
    c["bilan"].pop("configuration_sha256")
    ecrit(c["base"] / "qualification_globale.json", c["bilan"])
    with pytest.raises(ValueError, match="configuration de selection adaptative absente"):
        prepare(c)


def test_module_adaptatif_obligatoire_dans_outils_livres(campagne_adaptative):
    c = campagne_adaptative
    (c["racine"] / "qualification_adaptative.py").unlink()
    with pytest.raises(ValueError, match="qualification_adaptative.py"):
        prepare(c)
    assert not c["sortie"].exists()


def test_selection_bom_acceptee_et_raw_sha_conserve(campagne_adaptative):
    c = campagne_adaptative
    chemin = c["base"] / "selection_qualification.json"
    chemin.write_bytes(b"\xef\xbb\xbf" + chemin.read_bytes())
    nouveau_sha = L._sha(chemin)
    c["bilan"]["configuration_sha256"][chemin.name] = nouveau_sha
    c["recalcule"]["configuration_sha256"][chemin.name] = nouveau_sha
    ecrit(c["base"] / "qualification_globale.json", c["bilan"])
    import qualification_adaptative as A
    assert A.lire_selection(c["base"])[2] == nouveau_sha
    sortie = prepare(c)
    with zipfile.ZipFile(sortie / "preuves_calculs.zip") as z:
        assert z.read(chemin.name) == chemin.read_bytes()
        assert json.loads(z.read("index_preuves_sha256.json"))[chemin.name] == nouveau_sha


def test_selection_combinee_petit16_grand_tres_fin12_archive13(campagne_adaptative):
    c = campagne_adaptative
    grand = "diamant_uwb_x18"
    spec = dict(
        spatial=["fin_12ns", "tres_fin_12ns"],
        temporel=["tres_fin_8ns", "tres_fin_12ns"], reference="tres_fin_12ns",
        preliminaires=[
            dict(type="spatial", calculs=["base_8ns", "fin_8ns"],
                 motif="premiere comparaison insuffisante, raffinement spatial au niveau tres_fin"),
            dict(type="temporel", calculs=["fin_8ns", "fin_12ns"],
                 motif="premiere comparaison temporelle conservee")])
    resultat = c["bilan"]["antennes"][grand]
    for profil in ("tres_fin_8ns", "tres_fin_12ns"):
        original = c["base"] / grand / "base_8ns"
        dossier = c["base"] / grand / profil
        for f in original.rglob("*"):
            if f.is_file():
                copie = ecrit(dossier / f.relative_to(original), f.read_bytes())
                resultat["preuves_sha256"][copie.relative_to(c["base"]).as_posix()] = L._sha(copie)
        c["entrees"][f"{grand}/{profil}"] = copy.deepcopy(c["entrees"][f"{grand}/base_8ns"])
        c["manifests"][f"{grand}/{profil}"] = copy.deepcopy(c["manifests"][f"{grand}/base_8ns"])
    resultat["calculs_utilises"] = list(L.CALCULS) + ["tres_fin_8ns", "tres_fin_12ns"]
    resultat["selection_effective"] = copy.deepcopy(spec)
    resultat["reference"] = str(c["base"] / grand / spec["reference"])
    resultat["essais_preliminaires"] = [dict(
        **essai, ecarts=dict(reussi=essai["type"] == "temporel", valeurs=dict(
            maximum_complexe=.05552, rms_complexe=.03841, percentile95_db=2.19667)))
        for essai in spec["preliminaires"]]
    c["bilan"]["selection"]["antennes"][grand] = spec
    ecrit(c["base"] / grand / "comparaison/qualification.json", resultat)
    config = ecrit(c["base"] / "selection_qualification.json", c["bilan"]["selection"])
    c["bilan"]["configuration_sha256"][config.name] = L._sha(config)
    ecrit(c["base"] / "qualification_globale.json", c["bilan"])
    c["recalcule"].clear()
    c["recalcule"].update(copy.deepcopy(c["bilan"]))
    import qualification_adaptative as A
    _, effectives, _, _ = A.lire_selection(c["base"])
    assert effectives[grand]["reference"] == "tres_fin_12ns"
    sortie = prepare(c)
    assert len(c["appels"]) == 13
    assert L.verifie_livraison(sortie)
    manifeste = json.loads((sortie / L.MANIFESTE).read_text(encoding="utf-8"))
    assert len(manifeste["calculs"]) == 13
    with zipfile.ZipFile(sortie / "preuves_calculs.zip") as z:
        assert len([n for n in z.namelist() if n.endswith("entree_openems.xml")]) == 13
        assert f"{grand}/tres_fin_8ns/port_ut_1" in z.namelist()
        assert f"{grand}/tres_fin_12ns/port_ut_1" in z.namelist()
        assert f"{grand}/base_8ns/port_ut_1" in z.namelist()
    texte = (sortie / "README.md").read_text(encoding="utf-8")
    assert "les 13 dossiers" in texte
    assert "| diamant_uwb | fin_16ns | base_16ns / fin_16ns | fin_12ns / fin_16ns |" in texte
    assert "| diamant_uwb_x18 | tres_fin_12ns | fin_12ns / tres_fin_12ns | tres_fin_8ns / tres_fin_12ns |" in texte
    assert "| vivaldi_tomographie | fin_12ns |" in texte
    ligne_echec = next(l for l in texte.splitlines() if l.startswith("- diamant_uwb_x18, spatial"))
    assert "comparaison insuffisante" in ligne_echec and "raffinement spatial" in ligne_echec
    assert "16ns" not in ligne_echec and "prolongation" not in ligne_echec


def test_selection_combinee_17_profils_9_preliminaires_ultra_fin(campagne_adaptative, monkeypatch):
    """Synthetic full delivery: no solver and no persistent Q-level registration."""
    import qualification_adaptative as A
    import raffine_qualification_pcbway as R

    c = campagne_adaptative
    petit, grand, vivaldi = L.Q.ANTENNES
    catalogue = L.Q.NIVEAUX
    catalogue_initial = copy.deepcopy(catalogue)
    with monkeypatch.context() as contexte:
        contexte.setattr(L.Q, "NIVEAUX", copy.deepcopy(catalogue))
        R.enregistre(L.Q)
        selection = copy.deepcopy(c["bilan"]["selection"])
        selection["antennes"][petit]["preliminaires"].append(dict(
            type="temporel", calculs=["base_8ns", "base_16ns"],
            motif="fixture : diagnostic temporel supplementaire insuffisant"))
        selection["antennes"][grand] = dict(
            spatial=["tres_fin_12ns", "ultra_fin_12ns"],
            temporel=["ultra_fin_8ns", "ultra_fin_12ns"], reference="ultra_fin_12ns",
            preliminaires=[
                dict(type="spatial", calculs=["base_8ns", "fin_8ns"],
                     motif="fixture : premier raffinement spatial insuffisant"),
                dict(type="temporel", calculs=["fin_8ns", "fin_12ns"],
                     motif="fixture : premier diagnostic temporel conserve"),
                dict(type="spatial", calculs=["fin_12ns", "tres_fin_12ns"],
                     motif="fixture : second raffinement spatial insuffisant"),
                dict(type="temporel", calculs=["tres_fin_8ns", "tres_fin_12ns"],
                     motif="fixture : diagnostic temporel tres_fin conserve")])
        selection["antennes"][vivaldi] = dict(
            spatial=["fin_12ns", "tres_fin_12ns"],
            temporel=["tres_fin_12ns", "tres_fin_16ns"], reference="tres_fin_16ns",
            preliminaires=[
                dict(type="spatial", calculs=["base_8ns", "fin_8ns"],
                     motif="fixture : premiere comparaison spatiale conservee"),
                dict(type="temporel", calculs=["fin_8ns", "fin_12ns"],
                     motif="fixture : premiere fenetre temporelle insuffisante")])
        profils_attendus = {
            petit: list(L.CALCULS) + ["base_16ns", "fin_16ns"],
            grand: list(L.CALCULS) + ["tres_fin_8ns", "tres_fin_12ns", "ultra_fin_8ns", "ultra_fin_12ns"],
            vivaldi: list(L.CALCULS) + ["tres_fin_12ns", "tres_fin_16ns"],
        }
        for nom, profils in profils_attendus.items():
            resultat = c["bilan"]["antennes"][nom]
            original = c["base"] / nom / "base_8ns"
            for profil in profils:
                dossier = c["base"] / nom / profil
                if dossier.exists():
                    continue
                for f in original.rglob("*"):
                    if f.is_file():
                        copie = ecrit(dossier / f.relative_to(original), f.read_bytes())
                        resultat["preuves_sha256"][copie.relative_to(c["base"]).as_posix()] = L._sha(copie)
                c["entrees"][f"{nom}/{profil}"] = copy.deepcopy(c["entrees"][f"{nom}/base_8ns"])
                c["manifests"][f"{nom}/{profil}"] = copy.deepcopy(c["manifests"][f"{nom}/base_8ns"])
            spec = selection["antennes"][nom]
            resultat["calculs_utilises"] = profils
            resultat["selection_effective"] = copy.deepcopy(spec)
            resultat["reference"] = str(c["base"] / nom / spec["reference"])
            resultat["essais_preliminaires"] = [dict(
                **essai, ecarts=dict(reussi=(nom == petit and essai["type"] == "spatial") or
                    (nom == grand and essai["type"] == "temporel"),
                    valeurs=dict(maximum_complexe=.05552, rms_complexe=.03841)))
                for essai in spec["preliminaires"]]
            ecrit(c["base"] / nom / "comparaison/qualification.json", resultat)
        config = ecrit(c["base"] / "selection_qualification.json", selection)
        c["bilan"]["selection"] = selection
        c["bilan"]["configuration_sha256"] = {config.name: L._sha(config)}
        ecrit(c["base"] / "qualification_globale.json", c["bilan"])
        c["recalcule"].clear()
        c["recalcule"].update(copy.deepcopy(c["bilan"]))
        source_r = ecrit(c["racine"] / Path(R.__file__).name, Path(R.__file__).read_bytes())
        preuve_r = ecrit(c["base"] / "journaux/controle_raffinement" / grand /
                         "ultra_fin_12ns" / source_r.name, source_r.read_bytes())
        _, effectives, _, _ = A.lire_selection(c["base"])
        assert effectives[grand]["reference"] == "ultra_fin_12ns"
        assert sum(len(s["preliminaires"]) for s in effectives.values()) == 9
        sortie = prepare(c)
        assert len(c["appels"]) == 17
        assert L.verifie_livraison(sortie)
        manifeste = json.loads((sortie / L.MANIFESTE).read_text(encoding="utf-8"))
        assert set(manifeste["calculs"]) == {
            f"{nom}/{profil}" for nom, profils in profils_attendus.items() for profil in profils}
        for relatif in ("sources_outils/" + source_r.name,
                        "documentation/campagne/" + preuve_r.relative_to(c["base"]).as_posix()):
            assert (sortie / relatif).read_bytes() == source_r.read_bytes()
            assert manifeste["fichiers_sha256"][relatif] == L._sha(source_r)
        with zipfile.ZipFile(sortie / "preuves_calculs.zip") as z:
            assert len([n for n in z.namelist() if n.endswith("entree_openems.xml")]) == 17
            assert len([n for n in z.namelist() if n.endswith("sources/fixture.py")]) == 17
            assert z.read(config.name) == config.read_bytes()
            for nom, profils in profils_attendus.items():
                assert all(f"{nom}/{profil}/port_ut_1" in z.namelist() for profil in profils)
        texte = (sortie / "README.md").read_text(encoding="utf-8")
        assert "les 17 dossiers" in texte
        assert "| diamant_uwb_x18 | ultra_fin_12ns | tres_fin_12ns / ultra_fin_12ns | ultra_fin_8ns / ultra_fin_12ns |" in texte
        assert "| vivaldi_tomographie | tres_fin_16ns | fin_12ns / tres_fin_12ns | tres_fin_12ns / tres_fin_16ns |" in texte
        assert len([l for l in texte.splitlines() if l.startswith("- ")]) == 9
        assert "base_8ns / base_16ns ; comparaison insuffisante" in texte
        assert "fin_12ns / tres_fin_12ns ; comparaison insuffisante" in texte
    assert L.Q.NIVEAUX is catalogue
    assert L.Q.NIVEAUX == catalogue_initial


VERIFIE_REEL = L.V.verifie
