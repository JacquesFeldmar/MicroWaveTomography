"""Tests de compatibilite John, contre le module donnees fourni par le lanceur.

Ces tests restent en staging tant que les files FDTD gelees sont actives.
"""
from pathlib import Path
import tempfile
import unittest
import warnings

import numpy as np

import donnees as D


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "from Maurice/plexiglas/textes/texte3_john/data"
NOMS = ("background", "plate_50cm", "plate_60cm", "plate_70cm", "independent_short")


class ImportCSVJohn(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mwt_csv_john_fixture_")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.f = np.array([1e9, 1.025e9, 1.05e9])
        self.s = np.array([.125-.25j, -.375+.0625j, -.5-.75j])

    def ecrit(self, entete="frequency_hz,s11_real,s11_imag", s=None, f=None):
        s = self.s if s is None else s
        f = self.f if f is None else f
        p = self.base / "lecture.csv"
        lignes = [] if entete is None else [entete]
        lignes.extend(f"{x:.17g},{z.real:.17g},{z.imag:.17g}" for x, z in zip(f, s))
        p.write_text("\n".join(lignes)+"\n", encoding="utf-8")
        return p

    def test_exports_reels_cinq_csv_s1p_et_numpy_exacts(self):
        for nom in NOMS:
            with self.subTest(nom=nom):
                fc, sc = D.lit_csv(DATA / (nom + ".csv"))
                fs, ss = D.lit_s1p(DATA / (nom + ".s1p"))
                attendu = np.loadtxt(DATA / (nom + ".csv"), delimiter=",", skiprows=1)
                np.testing.assert_array_equal(fc, fs)
                np.testing.assert_array_equal(sc, ss)
                np.testing.assert_array_equal(fc, attendu[:, 0])
                np.testing.assert_array_equal(sc.real, attendu[:, 1])
                np.testing.assert_array_equal(sc.imag, attendu[:, 2])
                self.assertEqual(len(fc), 201)
                np.testing.assert_array_equal(np.diff(fc), np.full(200, 25e6))

    def test_dossier_john_doublons_signales_pas_de_short_cible(self):
        with warnings.catch_warnings(record=True) as recus:
            warnings.simplefilter("always")
            f, fond, mesures = D.charge_dossier(DATA)
        self.assertEqual(set(mesures), {50., 60., 70.})
        self.assertEqual(len(recus), 4)
        np.testing.assert_array_equal(f, np.linspace(1e9, 6e9, 201))
        np.testing.assert_array_equal(fond, D.lit_s1p(DATA / "background.s1p")[1])
        for distance, s in mesures.items():
            np.testing.assert_array_equal(s, D.lit_s1p(DATA / f"plate_{distance:g}cm.s1p")[1])

    def test_complexes_signes_pas_echanges_ni_recalage(self):
        for entete in ("frequency_hz,s11_real,s11_imag", "\ufefffrequency_hz, S11_REAL , S11_IMAG "):
            with self.subTest(entete=entete):
                f, s = D.lit_csv(self.ecrit(entete))
                np.testing.assert_array_equal(f, self.f)
                np.testing.assert_array_equal(s, self.s)

    def test_formats_historiques_conserves(self):
        for entete in (None, "f,re,im", "freq,real,imag", "frequency_hz,reel,imaginaire", "frequence_hz,re,im"):
            with self.subTest(entete=entete):
                f, s = D.lit_csv(self.ecrit(entete))
                np.testing.assert_array_equal(f, self.f)
                np.testing.assert_array_equal(s, self.s)

    def test_entetes_ambigues_refusees(self):
        for composantes in ("s21_real,s21_imag", "s22_real,s22_imag", "s11_imag,s11_real",
                            "s11_real,im", "real,s11_imag", "s11_magnitude,s11_phase"):
            with self.subTest(composantes=composantes), self.assertRaises(ValueError):
                D.lit_csv(self.ecrit("frequency_hz," + composantes))

    def test_grille_john_non_uniforme_et_s11_non_fini_refuses(self):
        for s, f in ((self.s, self.f + [0, 1e5, 0]),
                     (np.array([self.s[0], complex(np.nan, 0), self.s[2]]), self.f)):
            with self.subTest(f=f, s=s), self.assertRaises(ValueError):
                D.lit_csv(self.ecrit(s=s, f=f))

    def test_doublon_john_contradictoire_refuse(self):
        self.ecrit().rename(self.base / "background.csv")
        s = self.s.copy()
        s[1] += .01j
        lignes = ["# Hz S RI R 50"]
        lignes.extend(f"{x:.17g} {z.real:.17g} {z.imag:.17g}" for x, z in zip(self.f, s))
        (self.base / "background.s1p").write_text("\n".join(lignes)+"\n", encoding="utf-8")
        self.ecrit().rename(self.base / "plate_50cm.csv")
        with self.assertRaisesRegex(ValueError, "contradictoires"):
            D.charge_dossier(self.base)


if __name__ == "__main__":
    unittest.main()
