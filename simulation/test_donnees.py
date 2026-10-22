"""Regressions d'import. Executer avec python -B -X utf8 -m unittest test_donnees."""
from pathlib import Path
import tempfile
import unittest
import warnings

import numpy as np

import donnees as D


class ImportS11(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.f = np.linspace(1e9, 6e9, 201)
        self.s = .2 * np.exp(-1j * self.f / 1e9)

    def ecrit(self, nom, s=None, f=None, options="# Hz S RI R 50", commentaires=False):
        f = self.f if f is None else f
        s = self.s if s is None else s
        chemin = self.base / nom
        sep = "," if chemin.suffix == ".csv" else " "
        lignes = ["frequency_hz,re,im" if sep == "," else options]
        for x, y in zip(f, s):
            suffixe = " ! commentaire ignore" if commentaires else ""
            lignes.append(sep.join(f"{z:.12g}" for z in (x, y.real, y.imag)) + suffixe)
        chemin.write_text("\n".join(lignes), encoding="utf-8")
        return chemin

    def test_s1p_unites_et_commentaires(self):
        for unite, facteur in (("Hz", 1), ("kHz", 1e3), ("MHz", 1e6), ("GHz", 1e9)):
            f, s = D.lit(self.ecrit("lecture.s1p", f=self.f / facteur,
                                   options=f"# {unite} S RI R 50", commentaires=True))
            np.testing.assert_allclose(f, self.f, rtol=0, atol=1)
            np.testing.assert_allclose(s, self.s, rtol=1e-10)

    def test_csv_en_tete_commentaires_et_bom(self):
        chemin = self.ecrit("lecture.csv", commentaires=True)
        chemin.write_text("\ufeff# commentaire\n" + chemin.read_text(encoding="utf-8"), encoding="utf-8")
        f, s = D.lit(chemin)
        np.testing.assert_allclose(f, self.f)
        np.testing.assert_allclose(s, self.s)

    def test_formats_touchstone_refuses(self):
        for options in ("# Hz Z RI R 50", "# Hz S DB R 50", "# Hz S MA R 50", "# Hz S RI R 75", "# banana S RI R 50", "", "# Hz S RI"):
            with self.subTest(options=options), self.assertRaises(ValueError):
                D.lit(self.ecrit("invalide.s1p", options=options))

    def test_deux_entetes_contradictoires(self):
        chemin = self.ecrit("invalide.s1p")
        chemin.write_text(chemin.read_text() + "\n# GHz S RI R 50\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "contradictoires"):
            D.lit(chemin)

    def test_grilles_invalides(self):
        grilles = [self.f[::-1], np.geomspace(1e9, 6e9, 201),
                   np.r_[self.f[:100], self.f[99:-1]], np.r_[self.f[:-1], np.inf],
                   np.r_[self.f[:-1], np.nan], self.f[:2]]
        for f in grilles:
            with self.subTest(f=f[:3]), self.assertRaises(ValueError):
                D.lit(self.ecrit("invalide.csv", f=f))

    def test_s11_non_fini_ou_colonnes_en_trop(self):
        for valeur in (complex(np.nan, 0), complex(0, np.inf)):
            s = self.s.copy()
            s[3] = valeur
            with self.assertRaises(ValueError):
                D.lit(self.ecrit("invalide.csv", s=s))
        chemin = self.base / "invalide.csv"
        chemin.write_text("1,2,3,4\n2,2,3,4\n3,2,3,4\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            D.lit(chemin)

    def test_noms_natifs_anciens_et_decimaux(self):
        for ancien in (False, True):
            for fichier in self.base.iterdir():
                fichier.unlink()
            self.ecrit("antenne_seule.s1p" if ancien else "background.s1p")
            self.ecrit("plaque_50.5cm.csv" if ancien else "plate_50.5cm.csv", s=self.s * .9)
            # Un SHORT sur une grille differente n'appartient pas a la serie plaque.
            self.ecrit("independent_short.s1p", f=self.f + 2e6)
            f, fond, mesures = D.charge_dossier(self.base)
            self.assertEqual(set(mesures), {50.5})
            np.testing.assert_allclose(f, self.f)
            np.testing.assert_allclose(fond, self.s)

    def test_doublons_identiques_signales_et_divergents_refuses(self):
        self.ecrit("background.csv")
        self.ecrit("background.s1p")
        self.ecrit("plate_50cm.csv", s=self.s * .9)
        self.ecrit("plate_50cm.s1p", s=self.s * .9)
        with warnings.catch_warnings(record=True) as recus:
            warnings.simplefilter("always")
            self.assertEqual(len(D.charge_dossier(self.base)[2]), 1)
        self.assertEqual(len(recus), 2)
        self.ecrit("plate_50cm.s1p", s=self.s * .8)
        with warnings.catch_warnings(), self.assertRaisesRegex(ValueError, "contradictoires"):
            warnings.simplefilter("ignore")
            D.charge_dossier(self.base)

    def test_grilles_deux_fichiers_tolerance_absolue(self):
        self.ecrit("background.s1p")
        self.ecrit("plate_50cm.s1p", f=self.f + .5)
        D.charge_dossier(self.base)
        self.ecrit("plate_50cm.s1p", f=self.f + 100.)
        with self.assertRaisesRegex(ValueError, "grille de frequences differente"):
            D.charge_dossier(self.base)

    def test_trous_de_grille_et_aucune_interpolation(self):
        for extension in ("csv", "s1p"):
            with self.subTest(extension=extension), self.assertRaises(ValueError):
                D.lit(self.ecrit(f"invalide.{extension}", f=np.delete(self.f, 40), s=np.delete(self.s, 40)))


if __name__ == "__main__":
    unittest.main()
