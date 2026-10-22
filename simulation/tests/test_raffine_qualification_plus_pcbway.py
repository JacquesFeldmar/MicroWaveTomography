"""Garde du nouveau niveau n34 avec archives temporaires, sans aucun solveur.

Les donnees chargees sont synthetiques : les signatures et les montages sont
reels, mais Q.calcule et Q.charge_calcul sont remplaces explicitement. Aucun
fichier physique ou controleur gele n'est modifie par ces tests.
"""
from copy import deepcopy
from dataclasses import asdict
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


sys.dont_write_bytecode = True
SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
import qualifie_pcbway as Q
import raffine_qualification_pcbway as R
import raffine_qualification_plus_pcbway as PLUS


class RaffinementPlus(unittest.TestCase):
    def setUp(self):
        self.catalogue_initial = deepcopy(Q.NIVEAUX)
        self.temp = tempfile.TemporaryDirectory(prefix="mwt_raffinement_plus_tests_")
        self.racine = Path(self.temp.name).resolve()
        self.base = self.racine/"campagne"
        self.antenne = "diamant_uwb_x18"
        self.physique = Q.F._sources()
        octets = b'{"sources":"SYNTHETIQUE UNITTEST, aucun calcul FDTD"}\n'
        self.fige = dict(
            sources_16_sha256={f"fixture_source_{i}.py": hashlib.sha256(str(i).encode()).hexdigest()
                               for i in range(16)},
            inventaire_sha256=hashlib.sha256(octets).hexdigest(),
            inventaire_chemin=str(self.racine/"inventaire_synthetique.json"),
            inventaire_octets=octets,
            sources_physiques_initiales_sha256=self.physique,
        )
        self.sources_figees_reelles = PLUS._sources_figees
        self.sources_patch = patch.object(PLUS, "_sources_figees", return_value=deepcopy(self.fige))
        self.sources = self.sources_patch.start()
        self.solveur_patch = patch.object(Q.F, "lance",
            side_effect=AssertionError("FDTD interdit dans les tests du controleur PLUS"))
        self.solveur_interdit = self.solveur_patch.start()
        self.f = Q.np.linspace(1e9, 6.3e9, 213)
        self.s = Q.np.full(213, .2+.1j)

    def tearDown(self):
        self.solveur_patch.stop()
        self.sources_patch.stop()
        Q.NIVEAUX.clear()
        Q.NIVEAUX.update(self.catalogue_initial)
        self.temp.cleanup()

    def profil(self, duree):
        return self.base/self.antenne/f"n34_{duree:g}ns"

    def archive(self, duree):
        return self.base/"journaux"/"controle_raffinement_plus"/self.antenne/f"n34_{duree:g}ns"

    @staticmethod
    def ecrit_json(path, valeur):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Q.G.json_octets(valeur))

    def cree_profil(self, duree, derive=False):
        """Entrees synthetiques compatibles avec le vrai valide_campagne."""
        PLUS.enregistre(Q)
        p = self.profil(duree)
        p.mkdir(parents=True, exist_ok=False)
        montage = Q.montage_campagne("n34", duree)
        carte = Q.G.carte_antenne(self.antenne)
        geometrie = Q.G.geometrie_canonique(carte)
        dt = 1e-12
        n = int(Q.np.ceil(duree*1e-9/dt))+1
        manifeste = dict(etat="termine", antenne=self.antenne, montage=asdict(montage),
            sources_sha256=self.physique, derive_sondes=derive,
            execution=dict(dt_s=dt, n_pas=n, fin_energie_active=False,
                           duree_demandee_s=duree*1e-9),
            sondes={nom: dict(echantillons=n+1, dt_effectif_s=dt,
                    debut_s=decalage*dt, fin_s=(n+decalage)*dt)
                    for nom, decalage in (("port_ut_1", 0.), ("port_it_1", .5))},
            synthetique_unittest=True)
        qualification = dict(antenne=self.antenne, niveau="n34", montage=asdict(montage),
            signature_physique=Q.signature(carte, montage), geometrie=geometrie,
            geometrie_sha256=hashlib.sha256(Q.G.json_octets(geometrie)).hexdigest(),
            simulation_contract=carte["simulation_contract"], derive_sondes=derive,
            synthetique_unittest=True)
        self.ecrit_json(p/"simulation_manifest.json", manifeste)
        self.ecrit_json(p/"qualification_entree.json", qualification)
        self.ecrit_json(p/"s11_indicateurs.json", Q.indicateurs(self.f, self.s))
        Q.F.ecrit_s1p(str(p/"s11.s1p"), self.f, self.s,
                     commentaire="SYNTHETIQUE UNITTEST, aucun FDTD")
        return manifeste, qualification

    def charge_fixture(self, dossier, exiger_courant=False):
        self.assertTrue(exiger_courant, "les preuves doivent etre confrontees aux sources courantes")
        p = Path(dossier)
        return (self.f, self.s,
            json.loads((p/"simulation_manifest.json").read_text(encoding="utf-8")),
            json.loads((p/"qualification_entree.json").read_text(encoding="utf-8")))

    def appelle(self, **arguments):
        options = dict(antenne=self.antenne, niveau="n34", duree_ns=12., base=self.base)
        options.update(arguments)
        return PLUS.calcule(**options)

    def test_catalogue_n34_exact_copie_et_idempotent(self):
        faux = SimpleNamespace(NIVEAUX=deepcopy(self.catalogue_initial))
        avant = deepcopy(faux.NIVEAUX)
        PLUS.enregistre(faux)
        attendu = dict(mailles_par_lambda=34, mailles_par_lambda_air=22, maille_min=1.0/14.0)
        self.assertEqual(PLUS.NIVEAUX_PLUS, {"n34": attendu})
        self.assertEqual(faux.NIVEAUX["n34"], attendu)
        self.assertIsNot(faux.NIVEAUX["n34"], PLUS.NIVEAUX_PLUS["n34"])
        for nom, definition in avant.items():
            self.assertEqual(faux.NIVEAUX[nom], definition)
        for nom, definition in R.NIVEAUX_COMPLEMENTAIRES.items():
            self.assertEqual(faux.NIVEAUX[nom], definition)
            self.assertIsNot(faux.NIVEAUX[nom], definition)
        objet = faux.NIVEAUX["n34"]
        PLUS.enregistre(faux)
        self.assertIs(faux.NIVEAUX["n34"], objet)
        objet["maille_min"] = 1.
        self.assertEqual(PLUS.NIVEAUX_PLUS["n34"]["maille_min"], 1.0/14.0)

    def test_collision_plus_refusee_avant_ajout_des_niveaux_R(self):
        faux = SimpleNamespace(NIVEAUX={"base": {"maille_min": .25},
                                       "n34": {"maille_min": .1}})
        avant = deepcopy(faux.NIVEAUX)
        with patch.object(R, "enregistre", wraps=R.enregistre) as ajoute_R:
            with self.assertRaisesRegex(ValueError, "collision"):
                PLUS.enregistre(faux)
        ajoute_R.assert_not_called()
        self.assertEqual(faux.NIVEAUX, avant)

    def test_collision_R_ne_laisse_pas_n34_partiellement_ajoute(self):
        faux = SimpleNamespace(NIVEAUX={"ultra_fin": {"maille_min": 99.}})
        avant = deepcopy(faux.NIVEAUX)
        with self.assertRaisesRegex(ValueError, "collision"):
            PLUS.enregistre(faux)
        self.assertEqual(faux.NIVEAUX, avant)

    def test_inventaire_initial_altere_refuse_avant_acces_aux_sources(self):
        inventaire = self.base/"journaux"/"controle_initial"/"pipeline_statut_initial.json"
        inventaire.parent.mkdir(parents=True)
        inventaire.write_bytes(b"{}")
        # BASE suffit volontairement : acceder a __file__ ou F avant de
        # verifier le checkpoint serait une regression de cette garde.
        faux = SimpleNamespace(BASE=self.base)
        with self.assertRaisesRegex(ValueError, "empreinte de l'inventaire initial"):
            self.sources_figees_reelles(faux)
        self.sources.assert_not_called()

    def test_profil_prefixe_et_archive_existants_refuses_meme_vides(self):
        for cible in (self.profil(12), self.profil(8), self.archive(12)):
            with self.subTest(cible=cible):
                cible.mkdir(parents=True)
                with patch.object(Q, "calcule") as calcul:
                    with self.assertRaises(FileExistsError):
                        self.appelle()
                calcul.assert_not_called()
                cible.rmdir()
        self.assertFalse(self.profil(12).exists())
        self.assertFalse(self.profil(8).exists())

    def test_cout_sans_ecriture_ni_validation_ni_comparaison(self):
        with (patch.object(Q, "calcule") as calcul,
              patch.object(Q, "charge_calcul") as charge,
              patch.object(Q, "comparer") as compare):
            self.appelle(cout=True, fils=4)
        calcul.assert_called_once_with(self.antenne, "n34", 12., fils=4,
                                       cout=True, base=self.base)
        charge.assert_not_called()
        compare.assert_not_called()
        self.assertFalse(self.base.exists())

    def test_archive_exacte_et_plan_signe_avant_delegation_puis_validation(self):
        archive = self.archive(12)
        scripts = [Path(module.__file__) for module in (PLUS, Q, R)]
        def faux_calcul(*args, **kwargs):
            self.assertFalse(self.profil(12).exists())
            self.assertFalse(self.profil(8).exists(), "PLUS doit reserver le prefixe sans le produire")
            for script in scripts:
                self.assertEqual((archive/script.name).read_bytes(), script.read_bytes())
            self.assertEqual((archive/"inventaire_sources_initial.json").read_bytes(),
                             self.fige["inventaire_octets"])
            catalogues = json.loads((archive/"catalogues.json").read_text(encoding="utf-8"))
            self.assertEqual(catalogues, dict(Q_effectif=Q.NIVEAUX,
                R_declares=R.NIVEAUX_COMPLEMENTAIRES, PLUS_declares=PLUS.NIVEAUX_PLUS))
            contexte = json.loads((archive/"controle.json").read_text(encoding="utf-8"))
            self.assertFalse(contexte["qualification_officielle"])
            self.assertEqual(contexte["sources_16_sha256"], self.fige["sources_16_sha256"])
            self.assertEqual(contexte["catalogues_sha256"],
                             hashlib.sha256((archive/"catalogues.json").read_bytes()).hexdigest())
            self.assertEqual(contexte["base"], str(self.base))
            self.assertNotIn("commande_effective", contexte)
            self.assertEqual(contexte["orig_argv"], list(sys.orig_argv))
            self.assertEqual(contexte["argv_processus"], list(sys.argv))
            self.assertEqual(contexte["commande_reproduction"], [
                sys.executable, "-B", "-X", "utf8", str(Path(PLUS.__file__).resolve()),
                "--antenne", self.antenne, "--niveau", "n34", "--duree-ns", "12",
                "--prefixe-ns", "8", "--fils", "10", "--base", str(self.base)])
            carte = Q.G.carte_antenne(self.antenne)
            for cle, duree in (("calcul", 12.), ("prefixe", 8.)):
                attendu = Q.montage_campagne("n34", duree)
                definition = dict(
                    profil_relatif=f"{self.antenne}/n34_{duree:g}ns", duree_ns=duree,
                    montage=asdict(attendu), signature_physique=Q.signature(carte, attendu))
                self.assertEqual(contexte["profils"][cle],
                                 json.loads(Q.G.json_octets(definition)))
            index = json.loads((archive/"archive_sha256.json").read_text(encoding="utf-8"))
            self.assertEqual(set(index), {p.name for p in scripts} |
                {"inventaire_sources_initial.json", "catalogues.json", "controle.json"})
            for nom, digest in index.items():
                self.assertEqual(hashlib.sha256((archive/nom).read_bytes()).hexdigest(), digest)
            trace = [json.loads(ligne) for ligne in
                     (archive/"execution_interne.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([ligne["evenement"] for ligne in trace], ["avant_calcul"])
            self.cree_profil(12.)

        with (patch.object(Q, "calcule", side_effect=faux_calcul) as calcul,
              patch.object(Q, "charge_calcul", side_effect=self.charge_fixture) as charge,
              patch.object(Q, "valide_campagne", wraps=Q.valide_campagne) as valide,
              patch.object(Q, "comparer") as comparer):
            resultat = self.appelle()
        calcul.assert_called_once_with(self.antenne, "n34", 12., fils=10, cout=False, base=self.base)
        charge.assert_called_once_with(self.profil(12), exiger_courant=True)
        self.assertEqual(valide.call_count, 1)
        self.assertEqual(valide.call_args.args[2:], (self.antenne, "n34", 12.))
        comparer.assert_not_called()
        self.assertEqual(resultat["operation"], "calcul_termine_valide")
        self.assertFalse(resultat["qualification_officielle"])
        validation = json.loads((archive/"validation_apres_calcul.json").read_text(encoding="utf-8"))
        for cle, fichier in (("manifeste_sha256", "simulation_manifest.json"),
                             ("qualification_entree_sha256", "qualification_entree.json")):
            self.assertEqual(validation[cle], hashlib.sha256((self.profil(12)/fichier).read_bytes()).hexdigest())
        self.assertFalse(self.profil(8).exists(), "le prefixe appartient a l'etape W externe")

    def test_durees_decimales_prefixe_implicite_et_ecart_exact_quatre_acceptes(self):
        for duree, prefixe, explicite in ((4.1, .1, False), (18.9, 14.9, True)):
            with self.subTest(duree=duree, prefixe=prefixe, explicite=explicite):
                def faux_calcul(*args, **kwargs):
                    controle = json.loads((self.archive(duree)/"controle.json").read_text(encoding="utf-8"))
                    self.assertEqual(controle["prefixe_ns"], prefixe)
                    attendu = controle["profils"]["prefixe"]
                    self.assertEqual(attendu["duree_ns"], prefixe)
                    self.assertEqual(attendu["profil_relatif"],
                                     f"{self.antenne}/n34_{prefixe:g}ns")
                    self.assertEqual(attendu["signature_physique"], Q.signature(
                        Q.G.carte_antenne(self.antenne), Q.montage_campagne("n34", prefixe)))
                    self.assertFalse(self.profil(prefixe).exists())
                    self.cree_profil(duree)
                arguments = dict(duree_ns=duree)
                if explicite:
                    arguments["prefixe_ns"] = prefixe
                with (patch.object(Q, "calcule", side_effect=faux_calcul) as calcul,
                      patch.object(Q, "charge_calcul", side_effect=self.charge_fixture) as charge):
                    resultat = self.appelle(**arguments)
                calcul.assert_called_once_with(self.antenne, "n34", duree,
                                               fils=10, cout=False, base=self.base)
                charge.assert_called_once_with(self.profil(duree), exiger_courant=True)
                self.assertEqual(resultat["operation"], "calcul_termine_valide")
                self.assertFalse(self.profil(prefixe).exists())

    def test_prolongement_decimal_juste_inferieur_a_quatre_refuse(self):
        for duree, prefixe in ((18.9, 14.9001), (18.8999, 14.9)):
            with (self.subTest(duree=duree, prefixe=prefixe),
                  patch.object(Q, "calcule") as calcul,
                  patch.object(Q, "charge_calcul") as charge):
                with self.assertRaisesRegex(ValueError, "4 ns"):
                    self.appelle(duree_ns=duree, prefixe_ns=prefixe)
            calcul.assert_not_called()
            charge.assert_not_called()
        self.sources.assert_not_called()
        self.assertFalse(self.base.exists())

    def test_postvalidation_refuse_niveau_different_du_profil_attendu(self):
        def faux_calcul(*args, **kwargs):
            _, entree = self.cree_profil(12.)
            entree["niveau"] = "fin"
            self.ecrit_json(self.profil(12)/"qualification_entree.json", entree)
        with (patch.object(Q, "calcule", side_effect=faux_calcul) as calcul,
              patch.object(Q, "charge_calcul", side_effect=self.charge_fixture) as charge):
            with self.assertRaisesRegex(ValueError, "configuration"):
                self.appelle()
        calcul.assert_called_once()
        charge.assert_called_once_with(self.profil(12), exiger_courant=True)
        self.assertFalse((self.archive(12)/"validation_apres_calcul.json").exists())
        journal = (self.archive(12)/"execution_interne.jsonl").read_text(encoding="utf-8")
        self.assertEqual(json.loads(journal.splitlines()[-1])["evenement"], "echec")

    def test_changement_sources_simule_apres_calcul_refuse_sans_physique_modifiee(self):
        change = deepcopy(self.fige)
        change["sources_16_sha256"]["fixture_source_0.py"] = "0"*64
        termine = [False]
        def sources_fictives(controleur):
            self.assertIs(controleur, Q)
            return deepcopy(change if termine[0] else self.fige)
        self.sources.side_effect = sources_fictives
        def faux_calcul(*args, **kwargs):
            self.cree_profil(12.)
            termine[0] = True
        with (patch.object(Q, "calcule", side_effect=faux_calcul),
              patch.object(Q, "charge_calcul", side_effect=self.charge_fixture)):
            with self.assertRaisesRegex(ValueError, "modifi"):
                self.appelle()
        self.assertFalse((self.archive(12)/"validation_apres_calcul.json").exists())
        self.assertFalse(self.profil(8).exists())

    def test_verification_seule_du_prefixe_huit_ns_sans_run_archive_ni_ecriture(self):
        self.cree_profil(8., derive=True)
        # L'archive du calcul long est normalement deja presente apres W.
        self.archive(12).mkdir(parents=True)
        (self.archive(12)/"archive_parent_fixture.txt").write_bytes(b"ARCHIVE LONGUE SYNTHETIQUE\n")
        avant = {p.relative_to(self.base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.base.rglob("*") if p.is_file()}
        repertoires_avant = {p.relative_to(self.base).as_posix() for p in self.base.rglob("*") if p.is_dir()}
        with (patch.object(Q, "calcule") as calcul,
              patch.object(Q, "charge_calcul", side_effect=self.charge_fixture) as charge,
              patch.object(Q, "comparer") as comparer):
            resultat = self.appelle(duree_ns=8., verifier_seulement=True)
        calcul.assert_not_called()
        comparer.assert_not_called()
        charge.assert_called_once_with(self.profil(8), exiger_courant=True)
        self.assertEqual(resultat["operation"], "verification_seule")
        self.assertTrue(resultat["derive_sondes"])
        self.assertFalse(resultat["qualification_officielle"])
        self.assertFalse(self.archive(8).exists())
        apres = {p.relative_to(self.base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.base.rglob("*") if p.is_file()}
        self.assertEqual(avant, apres)
        self.assertEqual(repertoires_avant,
                         {p.relative_to(self.base).as_posix() for p in self.base.rglob("*") if p.is_dir()})

    def test_arguments_et_modes_invalides_refuses_avant_delegation(self):
        cas = [dict(antenne="../autre"), dict(niveau="n30"), dict(niveau=[]),
            *[dict(duree_ns=v) for v in (0., -1., float("nan"), float("inf"), True, "12")],
            *[dict(fils=v) for v in (0, -1, 2.5, True, "10")],
            *[dict(prefixe_ns=v) for v in (0., -1., 12., 13., float("nan"), True, "8")],
            dict(cout=1), dict(verifier_seulement=1), dict(base=" "),
            dict(cout=True, verifier_seulement=True),
            dict(cout=True, prefixe_ns=8.), dict(verifier_seulement=True, prefixe_ns=8.)]
        for modification in cas:
            with (self.subTest(modification=modification),
                  patch.object(Q, "calcule") as calcul,
                  patch.object(Q, "charge_calcul") as charge):
                with self.assertRaises(ValueError):
                    self.appelle(**modification)
            calcul.assert_not_called()
            charge.assert_not_called()
        self.assertFalse(self.base.exists())

    def test_cli_refuse_modes_concurrents_et_actions_hors_perimetre(self):
        depart = ["--antenne", self.antenne, "--duree-ns", "12"]
        for extra in (["--cout", "--verifier-seulement"], ["--comparer"], ["--livrer"],
                      ["--niveau", "n30"], ["--duree-ns", "nan"], ["--fils", "0"]):
            with (self.subTest(extra=extra), patch.object(PLUS, "calcule") as calcul,
                  contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as arret):
                PLUS.main(depart+extra)
            self.assertEqual(arret.exception.code, 2)
            calcul.assert_not_called()
        self.assertFalse(self.base.exists())


if __name__ == "__main__":
    unittest.main()
