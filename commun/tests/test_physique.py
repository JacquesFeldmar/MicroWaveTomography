"""Reprise selective des controles Maurice, sans acquisition instrumentale.

Le fichier original archive fournit le temoin de non-regression numerique.
Les tests de retard et d'amplitude verifient aussi des invariants analytiques
independants de ce temoin.
"""
import hashlib
import importlib.util
import inspect
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from commun import physique as P


class ProfilDistance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = ROOT / "simulation/chatGPT_critical_review/revue_commun_maurice_2026-10-18/physique.py.orig"
        contenu = archive.read_bytes()
        attendu = "f63f66012c72190b2da5f37a124381bd5209c995072207a9bfa15e7cfe7659d4"
        if hashlib.sha256(contenu).hexdigest() != attendu:
            raise AssertionError("Le temoin original de non-regression a change.")
        cls.ancien = types.ModuleType("physique_originale_archivee")
        exec(compile(contenu.decode("utf-8"), str(archive), "exec"), cls.ancien.__dict__)

    def test_profils_valides_identiques_au_temoin_original(self):
        for n in (3, 101, 201, 213, 401):
            f = np.linspace(1.4e9, 6.3e9, n)
            s = (.2+.1j)*np.exp(-4j*np.pi*f*.65/P.c)
            for zoom in (1, 8, 16):
                for fenetre in ("hann", "blackman-harris", "aucune"):
                    for listes in (False, True):
                        with self.subTest(n=n, zoom=zoom, fenetre=fenetre, listes=listes):
                            ff, ss = (f.tolist(), s.tolist()) if listes else (f, s)
                            attendu = self.ancien.profil_distance(ff, ss, zoom, fenetre)
                            obtenu = P.profil_distance(ff, ss, zoom, fenetre)
                            for a, b in zip(attendu, obtenu):
                                np.testing.assert_array_equal(a, b)

    def test_exports_john_profils_valides_identiques(self):
        dossier = ROOT / "from Maurice/plexiglas/textes/texte3_john/data"
        for nom in ("background", "plate_50cm", "plate_60cm", "plate_70cm", "independent_short"):
            valeurs = np.loadtxt(dossier / (nom+".csv"), delimiter=",", skiprows=1)
            f, s = valeurs[:, 0], valeurs[:, 1]+1j*valeurs[:, 2]
            for zoom in (1, 8, 16):
                for fenetre in ("hann", "blackman-harris", "aucune"):
                    with self.subTest(nom=nom, zoom=zoom, fenetre=fenetre):
                        attendu = self.ancien.profil_distance(f, s, zoom, fenetre)
                        obtenu = P.profil_distance(f, s, zoom, fenetre)
                        for a, b in zip(attendu, obtenu):
                            np.testing.assert_array_equal(a, b)

    def test_retards_connus_independants_du_zoom(self):
        for n, zoom in ((201, 16), (401, 8)):
            f = np.linspace(1e9, 6e9, n)
            for distance_m in (0, .5, .6, .7, 1.5):
                s = -.08*np.exp(-4j*np.pi*f*distance_m/P.c)
                d, amplitude, pas = P.profil_distance(f, s, zoom)
                with self.subTest(n=n, zoom=zoom, distance_m=distance_m):
                    self.assertLessEqual(abs(d[np.argmax(amplitude)]-1000*distance_m), pas/2)

    def test_hann_conserve_gain_coherent_et_unites_mm(self):
        n = 201
        f = np.linspace(1e9, 6e9, n)
        for zoom in (1, 8, 16):
            d, amplitude, pas = P.profil_distance(f, np.full(n, .2+.1j), zoom)
            # Somme analytique de la Hann symetrique = (N-1)/2.
            self.assertAlmostEqual(amplitude[0], abs(.2+.1j)*(n-1)/(2*n), places=15)
            self.assertAlmostEqual(pas, P.c/(2*zoom*n*25e6)*1e3, places=12)
            self.assertEqual(d[0], 0.)
            self.assertEqual(len(d), n*zoom//2)

    def test_donnees_invalides_refusees_avant_ifft(self):
        cas = (
            ([1e9, 2e9, 4e9], [1, 1, 1]),
            ([3e9, 2e9, 1e9], [1, 1, 1]),
            ([1e9, 1e9, 2e9], [1, 1, 1]),
            ([1e9, np.nan, 3e9], [1, 1, 1]),
            ([1e9, 2e9, np.inf], [1, 1, 1]),
            ([1e9, 2e9, 3e9], [1, np.nan, 1]),
            ([1e9, 2e9, 3e9], [1, complex(0, np.inf), 1]),
            ([1e9, 2e9, 3e9, 4e9], [1, 1, 1]),
            ([[1e9, 2e9], [3e9, 4e9]], [1, 1, 1, 1]),
            ([1e9, 2e9, 3e9], [[1, 1, 1]]),
            ([1e9], [1]),
            (1e9, [1]),
        )
        for f, s in cas:
            with self.subTest(f=f, s=s), self.assertRaises(ValueError):
                P.profil_distance(f, s)

    def test_zoom_invalide_refuse_et_entier_numpy_accepte(self):
        f, s = [1e9, 2e9, 3e9], [1, 1, 1]
        for zoom in (0, -1, 1.5):
            with self.subTest(zoom=zoom), self.assertRaises(ValueError):
                P.profil_distance(f, s, zoom)
        obtenu = P.profil_distance(f, s, np.int64(8))
        attendu = self.ancien.profil_distance(f, s, np.int64(8))
        for a, b in zip(obtenu, attendu):
            np.testing.assert_array_equal(a, b)

    def test_api_et_cote_plaque_preservees(self):
        for nom in ("milieu", "indice", "profil_distance", "resolution_mm", "cote_plaque_mm"):
            self.assertEqual(inspect.signature(getattr(P, nom)), inspect.signature(getattr(self.ancien, nom)))
        self.assertEqual(P.c, self.ancien.c)
        self.assertEqual(P.eps0, self.ancien.eps0)
        self.assertEqual(P.MILIEUX, self.ancien.MILIEUX)
        for distance, f_min in ((100, 1e9), (500, 1.4e9), (700, 1e9)):
            self.assertEqual(P.cote_plaque_mm(distance, f_min), self.ancien.cote_plaque_mm(distance, f_min))
        self.assertEqual(P.cote_plaque_mm(500, 1e9), 547.5330656681841)

    def test_consommateur_cartilage_import_et_simulation_sans_vna(self):
        from commun import instrument
        with patch.object(instrument, "ouvrir_reel", side_effect=AssertionError("Acces VNA interdit")) as ouvrir:
            spec = importlib.util.spec_from_file_location("noyau_revue_commun_test", ROOT / "cartilage/noyau.py")
            noyau = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(noyau)
            f = np.linspace(1.4e9, 6.3e9, 201)
            vna = noyau.VNASimule(f, ["vide"])
            s11, _ = vna.get_s11_s21()
            noyau.profil_distance(s11.f, s11.s[:, 0, 0])
            self.assertIs(noyau.profil_distance, P.profil_distance)
            self.assertEqual(noyau.cote_plaque_mm(500, 1e9), 547.5330656681841)
            ouvrir.assert_not_called()


if __name__ == "__main__":
    unittest.main()
