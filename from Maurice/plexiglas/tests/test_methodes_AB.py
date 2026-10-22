"""Validation indépendante des modèles B et non-régression du traitement A."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"progs"))
from ajustement_B import ajuster_echos, ajuster_plaque, information, C
from mesure_cible import arguments, obtenir_mesure, variance_moyenne
from commun import physique


class MethodesTests(unittest.TestCase):
    def setUp(self):
        self.f = np.linspace(1e9, 6e9, 201)

    def test_deux_trajets_dont_un_parasite_plus_fort(self):
        # Génération indépendante en fréquence absolue, distances en mètres.
        y = (.03+.01j)*np.exp(-4j*np.pi*self.f*.203/C)
        y += (.003-.005j)*np.exp(-4j*np.pi*self.f*.785/C)
        fit = ajuster_echos(self.f, y, variance=np.full(201, 1e-8))
        np.testing.assert_allclose(fit["distances_cm"], [20.3, 78.5], atol=1e-5)
        self.assertLess(fit["erreur_rms_relative"], 1e-8)
        self.assertEqual(fit["rang_fim"], 6)

    def test_plaque_epaisseur_amplitude_et_retard_inconnus_avec_bruit(self):
        n, e, alpha, d = 1.61, .015, .7, .43
        r = (1-n)/(1+n)
        arriere = (1-r*r)*(-r)*np.exp(-4j*np.pi*self.f*n*e/C)
        y = (.1+.05j)*np.exp(-4j*np.pi*self.f*d/C)*(r+alpha*arriere)
        rng = np.random.default_rng(142)
        v = np.full(201, 1e-10)
        y += np.sqrt(v/2)*(rng.normal(size=201)+1j*rng.normal(size=201))
        fit = ajuster_plaque(self.f, y, n, variance=v, ponderation="bruit")
        self.assertAlmostEqual(fit["epaisseur_mm"], 15., delta=.03)
        self.assertAlmostEqual(fit["alpha"], .7, delta=.003)
        self.assertAlmostEqual(fit["distances_cm"][0], 43., delta=.01)
        self.assertTrue(fit["crlb_interpretable_sous_modele"])
        self.assertTrue(.5 < fit["chi2_reduit"] < 1.5)

    def test_modele_incomplet_signale(self):
        y = .01*np.exp(-4j*np.pi*self.f*.3/C)+.01*np.exp(-4j*np.pi*self.f*.9/C)
        fit = ajuster_echos(self.f, y, nombre=1, variance=np.full(201, 1e-10))
        self.assertGreater(fit["erreur_rms_relative"], .6)
        self.assertFalse(fit["crlb_interpretable_sous_modele"])

    def test_fim_singuliere_ne_donne_pas_de_fausse_precision(self):
        j = np.column_stack([np.ones(201), np.ones(201)])
        _, covariance, rang, _ = information(j, np.ones(201))
        self.assertEqual(rang, 1)
        self.assertIsNone(covariance)

    def test_fim_retard_avec_gain_inconnu(self):
        g = .02+.01j
        a = np.exp(-4j*np.pi*(self.f-self.f.mean())*.43/C)
        j = np.column_stack([a, 1j*a, g*a*(-4j*np.pi*(self.f-self.f.mean())/(100*C))])
        v = 1e-8
        _, covariance, rang, _ = information(j, np.full(201, v))
        theorique = 1/(2*abs(g)**2/v*(4*np.pi/(100*C))**2*np.sum((self.f-self.f.mean())**2))
        self.assertAlmostEqual(covariance[2, 2]/theorique, 1., places=10)
        self.assertEqual(rang, 3)

    def test_variance_des_moyennes_cible_et_fond(self):
        with tempfile.TemporaryDirectory() as tmp:
            sf = np.array([np.ones(201), -np.ones(201)], complex)
            fond = Path(tmp)/"fond.npz"
            np.savez(fond, freqs=self.f, fond=sf.mean(axis=0), sweeps_calibres=sf)
            cible = np.array([2*np.ones(201), -2*np.ones(201)], complex)
            data = dict(freqs=self.f, fond=sf.mean(axis=0), sweeps_calibres=cible, fichier_fond=str(fond))
            np.testing.assert_allclose(variance_moyenne(data), 5.)

    def test_relecture_ne_contacte_pas_le_vna_et_a_conserve_le_profil(self):
        y = .01*np.exp(-4j*np.pi*self.f*.731/C)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"cible.npz"
            d, p, pas = physique.profil_distance(self.f, y)
            np.savez(path, freqs=self.f, residu=y, distance_mm=d, profil=p, pas_mm=pas)
            args = arguments("test").parse_args(["--mesure", str(path)])
            with patch("mesure_cible.litevna.acquisition", side_effect=AssertionError("Accès matériel")):
                _, z = obtenir_mesure(args)
            dd, pp, _ = physique.profil_distance(z["freqs"], z["residu"])
            np.testing.assert_array_equal(dd, z["distance_mm"])
            np.testing.assert_array_equal(pp, z["profil"])

    def test_bornes_et_variances_invalides(self):
        y = np.ones(201, complex)
        with self.assertRaises(ValueError):
            ajuster_echos(self.f, y, bornes=(0, 700))
        with self.assertRaises(ValueError):
            ajuster_echos(self.f, y, variance=np.zeros(201))
        with self.assertRaises(ValueError):
            ajuster_echos(self.f, y, ponderation="bruit")
        with self.assertRaises(ValueError):
            ajuster_plaque(self.f, y, indice=1.)

    def test_acquisition_commune_sauvegarde_avant_traitement(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            cal = dict(freqs=self.f, e00=np.zeros(201, complex),
                       e11=np.zeros(201, complex), e10e01=np.ones(201, complex))
            np.savez(racine/"sol.npz", **cal)
            np.savez(racine/"fond.npz", freqs=self.f, fond=np.zeros(201, complex),
                     correction_mode="brut", sigma_complexe=np.ones(201)*.001,
                     sweeps_calibres=np.zeros((3, 201), complex),
                     **{"sol_"+k: v for k, v in cal.items()})
            args = arguments("test").parse_args([
                "--start-ghz", "1", "--stop-ghz", "6", "--points", "201", "--nombre", "2",
                "--fond", str(racine/"fond.npz"), "--sol", str(racine/"sol.npz"), "--sortie", tmp])
            s = np.full((2, 201), .1+.2j)
            with patch("mesure_cible.litevna.acquisition", return_value=(
                    s, np.array([0., 1.]), np.zeros((2, 201*32), np.uint8), {}, "FAUX")):
                chemin, data = obtenir_mesure(args)
            self.assertTrue(chemin.is_file())
            with np.load(chemin, allow_pickle=False) as z:
                np.testing.assert_allclose(z["residu"], .1+.2j)
                np.testing.assert_allclose(z["variance_moyenne_fond"], 1e-6/3)
                self.assertNotIn("profil", z.files)
                self.assertIn("paquets_usb", z.files)
                self.assertIn("sol_e10e01", z.files)


if __name__ == "__main__":
    unittest.main()
