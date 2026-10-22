"""Ajout de niveau et delegation controles ; aucun solveur n'est execute."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
import qualifie_pcbway as Q
import raffine_qualification_pcbway as R


class Complement(unittest.TestCase):
    def setUp(self):
        self.niveaux = deepcopy(Q.NIVEAUX)
        self.tmp = tempfile.TemporaryDirectory(prefix="mwt_raffinement_tests_")
        self.base = Path(self.tmp.name)/"campagne"

    def tearDown(self):
        Q.NIVEAUX.clear()
        Q.NIVEAUX.update(self.niveaux)
        self.tmp.cleanup()

    def test_enregistrement_copie_et_idempotence(self):
        faux = SimpleNamespace(NIVEAUX=deepcopy(self.niveaux))
        R.enregistre(faux)
        for nom, definition in self.niveaux.items():
            self.assertEqual(faux.NIVEAUX[nom], definition)
        for nom, definition in R.NIVEAUX_COMPLEMENTAIRES.items():
            self.assertEqual(faux.NIVEAUX[nom], definition)
            self.assertIsNot(faux.NIVEAUX[nom], definition)
        objet = faux.NIVEAUX["ultra_fin"]
        R.enregistre(faux)
        self.assertIs(faux.NIVEAUX["ultra_fin"], objet)
        objet["maille_min"] = 99
        self.assertEqual(R.NIVEAUX_COMPLEMENTAIRES["ultra_fin"]["maille_min"], .125)

    def test_collision_refusee_sans_modifier_niveaux(self):
        faux = SimpleNamespace(NIVEAUX={"base": {"maille_min": .25},
                                       "ultra_fin": {"maille_min": .15}})
        avant = deepcopy(faux.NIVEAUX)
        with self.assertRaisesRegex(ValueError, "collision"):
            R.enregistre(faux)
        self.assertEqual(faux.NIVEAUX, avant)

    def test_extension_conserve_ultra_et_refuse_collision_extreme(self):
        ultra = dict(mailles_par_lambda=22,mailles_par_lambda_air=16,maille_min=.125)
        faux = SimpleNamespace(NIVEAUX={**deepcopy(self.niveaux),"ultra_fin":ultra})
        R.enregistre(faux)
        self.assertIs(faux.NIVEAUX["ultra_fin"],ultra)
        self.assertEqual(faux.NIVEAUX["extreme_fin"],
                         dict(mailles_par_lambda=26,mailles_par_lambda_air=18,maille_min=.10))
        faux.NIVEAUX["extreme_fin"]["mailles_par_lambda"] = 25
        avant = deepcopy(faux.NIVEAUX)
        with self.assertRaisesRegex(ValueError,"collision"):
            R.enregistre(faux)
        self.assertEqual(faux.NIVEAUX,avant)

    def test_montage_reel_affine_sans_changer_seuils(self):
        R.enregistre(Q)
        m = Q.montage_campagne("ultra_fin", 12.)
        self.assertEqual((m.maillage.mailles_par_lambda,m.maillage.mailles_par_lambda_air,
                          m.maillage.maille_min,m.maillage.duree_ns), (22,16,.125,12.))
        self.assertEqual((m.acquisition.f_min,m.acquisition.f_max,m.acquisition.points),
                         (1e9,6.3e9,213))
        self.assertFalse(m.maillage.symetrie)
        extreme = Q.montage_campagne("extreme_fin",12.)
        self.assertEqual((extreme.maillage.mailles_par_lambda,
                          extreme.maillage.mailles_par_lambda_air,extreme.maillage.maille_min),
                         (26,18,.10))
        f = np.array([1e9,2e9])
        s = np.array([.4+.1j,.5-.1j])
        self.assertEqual(Q.ecarts(f,s,f,s)["seuils_acceptation"],
                         dict(maximum_complexe=.05,rms_complexe=.02,percentile95_db=1.))
        self.assertEqual(Q.ecarts(f,s,f,s,temporel=True)["seuils_acceptation"],
                         dict(maximum_complexe=.015,rms_complexe=.005,percentile95_db=.5))
        for nom, definition in self.niveaux.items():
            self.assertEqual(Q.NIVEAUX[nom],definition)

    def test_cout_delegue_sans_ecrire_ni_comparer(self):
        with patch.object(Q,"calcule",return_value="cout") as calcul, patch.object(Q,"comparer") as comparaison:
            self.assertEqual(R.calcule("diamant_uwb_x18","ultra_fin",12.,fils=4,
                                      cout=True,base=self.base), "cout")
            calcul.assert_called_once_with("diamant_uwb_x18","ultra_fin",12.,fils=4,
                                           cout=True,base=self.base.resolve())
            comparaison.assert_not_called()
        self.assertFalse(self.base.exists())

    def test_vrai_calcul_archive_octets_avant_delegation(self):
        controle = self.base/"journaux"/"controle_raffinement"/"diamant_uwb_x18"/"ultra_fin_12ns"
        def faux_calcul(*args,**kw):
            self.assertEqual((controle/Path(R.__file__).name).read_bytes(), Path(R.__file__).read_bytes())
            self.assertEqual((controle/Path(Q.__file__).name).read_bytes(), Path(Q.__file__).read_bytes())
            c = json.loads((controle/"controle.json").read_text(encoding="utf-8"))
            self.assertEqual(c["montage"]["maillage"]["mailles_par_lambda"],22)
            self.assertFalse((self.base/"diamant_uwb_x18").exists())
        with patch.object(Q,"calcule",side_effect=faux_calcul) as calcul:
            R.calcule("diamant_uwb_x18","ultra_fin",12.,base=self.base)
            R.calcule("diamant_uwb_x18","ultra_fin",12.,base=self.base)
            self.assertEqual(calcul.call_count,2)
        (controle/"raffine_qualification_pcbway.py").write_text("altere",encoding="utf-8")
        with patch.object(Q,"calcule") as calcul, self.assertRaises(FileExistsError):
            R.calcule("diamant_uwb_x18","ultra_fin",12.,base=self.base)
        calcul.assert_not_called()

    def test_arguments_invalides_refuses_avant_calcul(self):
        cas = [dict(antenne="../inconnu"),dict(niveau="fin"),dict(niveau=[]),
            *[dict(duree_ns=v) for v in (0,-1,float("nan"),float("inf"),True,"12")],
            *[dict(fils=v) for v in (0,-1,1.2,True,"4")],dict(cout=1),dict(base=" ")]
        for modif in cas:
            args = dict(antenne="diamant_uwb_x18",niveau="ultra_fin",duree_ns=12.,
                        fils=10,cout=True,base=self.base)
            args.update(modif)
            with self.subTest(modif=modif),patch.object(Q,"calcule") as calcul,self.assertRaises(ValueError):
                R.calcule(**args)
            calcul.assert_not_called()
        self.assertFalse(self.base.exists())

    def test_cli_refuse_comparaison_livraison_et_parametres_invalides(self):
        depart = ["--antenne","diamant_uwb_x18","--duree-ns","12"]
        for reste in (["--comparer"],["--livrer"],["--niveau","fin"],
                      ["--duree-ns","nan"],["--fils","0"],["--fils","1.2"]):
            with (self.subTest(reste=reste),patch.object(R,"calcule") as calcul,
                  contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as erreur):
                R.main(depart+reste)
            self.assertEqual(erreur.exception.code,2)
            calcul.assert_not_called()


if __name__ == "__main__":
    unittest.main()
