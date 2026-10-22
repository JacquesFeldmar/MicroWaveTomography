"""Integration du controleur copie : imports, CLI et archives synthetiques.

Aucun solveur n'est lance. Les fixtures utilisent les vrais CSXCAD/CalcPort.
Ce fichier est copie par le runner dans un arbre temporaire independant.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
sys.path.insert(0, str(SIM / "tests"))
import qualifie_pcbway as Q
import qualification_adaptative as A
import raffine_qualification_pcbway as R
import livre_pcbway as L
import fenetre_sondes as W
import test_qualification_pcbway as T


class IntegrationQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="mwt_q_cli_synthetique_")
        cls.base = Path(cls.temp.name) / "campagne"
        # Trois geometries reelles mais sondes purement synthetiques ; pas Run.
        for nom in Q.ANTENNES:
            fixture = SimpleNamespace(base=cls.base, nom=nom)
            for niveau, duree in (("base", 8.), ("fin", 12.)):
                T.ArchivesQualification.cree_archive.__func__(fixture, niveau, duree)
            with contextlib.redirect_stdout(io.StringIO()):
                W.derive(cls.base/nom/"fin_12ns", cls.base/nom/"fin_8ns", 8.)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", "-X", "utf8", str(SIM/"qualifie_pcbway.py"), *args],
                              cwd=SIM, capture_output=True, text=True, encoding="utf-8")

    def test_imports_partagent_controleur_et_catalogue_sans_execution(self):
        self.assertIs(A.Q, Q)
        self.assertIs(L.Q, Q)
        self.assertEqual(Q.__name__, "qualifie_pcbway")
        self.assertEqual(Q.NIVEAUX["base"], dict(mailles_par_lambda=10, mailles_par_lambda_air=10, maille_min=.25))
        self.assertEqual(Q.NIVEAUX["fin"], dict(mailles_par_lambda=14, mailles_par_lambda_air=12, maille_min=.20))
        self.assertEqual(Q.NIVEAUX["tres_fin"], dict(mailles_par_lambda=18, mailles_par_lambda_air=14, maille_min=.15))
        for nom, definition in R.NIVEAUX_COMPLEMENTAIRES.items():
            self.assertEqual(Q.NIVEAUX[nom], definition)
            self.assertIsNot(Q.NIVEAUX[nom], definition)
            self.assertEqual(A.profil(nom+"_12ns"), (nom, 12.))
        self.assertFalse(Q.BASE.exists())

    def test_cli_aide_reconnait_niveaux_et_options_historiques(self):
        r = self.cli("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for option in ("--antenne", "--niveau", "--duree-ns", "--fils", "--cout", "--comparer", "--base"):
            self.assertIn(option, r.stdout)
        self.assertIn("ultra_fin", r.stdout)
        self.assertIn("extreme_fin", r.stdout)
        self.assertFalse(Q.BASE.exists())

    def test_cli_sans_option_B_et_sans_variable_necrit_aucun_cache(self):
        self.assertEqual(list(SIM.rglob("__pycache__")), [])
        env = os.environ.copy()
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        env.pop("PYTHONPYCACHEPREFIX", None)
        r = subprocess.run([sys.executable,"-X","utf8",str(SIM/"qualifie_pcbway.py"),"--help"],
                           cwd=SIM,env=env,capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ultra_fin",r.stdout)
        self.assertEqual(list(SIM.rglob("__pycache__")), [])

    def test_main_conserve_arguments_et_defauts_sans_calcul(self):
        for reste, attendu in (([], ("base", 8., 10, False)),
                               (["--niveau", "ultra_fin", "--cout"], ("ultra_fin", 8., 10, True)),
                               (["--niveau", "extreme_fin", "--duree-ns", "16", "--fils", "3"],
                                ("extreme_fin", 16., 3, False))):
            with self.subTest(reste=reste), patch.object(Q, "calcule") as calcul:
                self.assertEqual(Q.main(["--antenne", "diamant_uwb", *reste]), 0)
                calcul.assert_called_once_with("diamant_uwb", *attendu, Q.BASE)

    def test_route_import_selon_presence_selection_et_propage_erreur(self):
        with tempfile.TemporaryDirectory(prefix="mwt_q_route_") as tmp:
            base = Path(tmp)
            with patch.object(Q, "ANTENNES", ()), patch.object(A, "comparer") as adaptatif:
                self.assertEqual(Q.comparer(base, ecrire=False),
                                 dict(schema="qualification_pcbway_r1", antennes={}, tous_reussis=True))
                adaptatif.assert_not_called()
            (base/A.FICHIER_SELECTION).write_text("{}", encoding="utf-8")
            temoin = {"temoin": True}
            with patch.object(A, "comparer", return_value=temoin) as adaptatif:
                self.assertIs(Q.comparer(base, ecrire=False), temoin)
                adaptatif.assert_called_once_with(base, ecrire=False)
            with patch.object(A, "comparer", side_effect=ValueError("selection invalide")):
                with self.assertRaisesRegex(ValueError, "selection invalide"):
                    Q.comparer(base)

    def test_cli_comparaison_reelle_sans_et_avec_selection(self):
        # Sans selection, la commande historique conserve exactement sa voie.
        self.assertFalse((self.base/A.FICHIER_SELECTION).exists())
        r = self.cli("--comparer", "--base", str(self.base))
        self.assertEqual(r.returncode, 0, r.stderr)
        initial = json.loads(r.stdout)
        self.assertTrue(initial["tous_reussis"])
        self.assertNotIn("selection", initial)
        with contextlib.redirect_stdout(io.StringIO()):
            importe = Q.comparer(self.base, ecrire=False)
        self.assertEqual(json.loads(Q.G.json_octets(importe)), initial)
        # Selection valide temporaire : toutes les antennes gardent ici le
        # protocole standard. Les prolongements sont couverts par la suite AP.
        Q.sauve(self.base/A.FICHIER_SELECTION, dict(schema=A.SCHEMA_SELECTION, antennes={}))
        try:
            r = self.cli("--comparer", "--base", str(self.base))
            self.assertEqual(r.returncode, 0, r.stderr)
            adapte = json.loads(r.stdout)
            self.assertTrue(adapte["tous_reussis"])
            self.assertEqual(adapte["selection"], dict(schema=A.SCHEMA_SELECTION, antennes={}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(json.loads(Q.G.json_octets(Q.comparer(self.base, ecrire=False))), adapte)
            for nom in Q.ANTENNES:
                self.assertEqual(adapte["antennes"][nom]["calculs_utilises"],
                                 ["base_8ns", "fin_8ns", "fin_12ns"])
        finally:
            (self.base/A.FICHIER_SELECTION).unlink()

    def test_subprocess_main_charge_une_seule_instance_canonique(self):
        # Une sonde locale intercepte uniquement l'appel de routage pour
        # verifier l'identite de Q vue par AP dans le vrai processus CLI.
        code = '''
import json,runpy,sys
from pathlib import Path
import qualifie_pcbway as Q
import qualification_adaptative as A
assert A.Q is Q
def comparer(base, ecrire=True):
    assert A.Q is Q and Q.NIVEAUX is A.Q.NIVEAUX
    assert sys.modules["qualifie_pcbway"] is Q
    print(json.dumps({"tous_reussis":True,"module":Q.__name__,"ultra":A.profil("ultra_fin_12ns")[0]}))
    return {"tous_reussis":True}
A.comparer=comparer
sys.argv=[str(Path(Q.__file__)),"--comparer","--base",sys.argv[1]]
runpy.run_path(Q.__file__,run_name="__main__")
'''
        with tempfile.TemporaryDirectory(prefix="mwt_q_identite_") as tmp:
            (Path(tmp)/A.FICHIER_SELECTION).write_text("{}", encoding="utf-8")
            r = subprocess.run([sys.executable,"-B","-X","utf8","-c",code,tmp],
                               cwd=SIM,capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout),dict(tous_reussis=True,module="qualifie_pcbway",ultra="ultra_fin"))


if __name__ == "__main__":
    unittest.main()
