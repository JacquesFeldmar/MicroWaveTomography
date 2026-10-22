"""Vérifie la conservation du retard physique lors du changement de bande."""
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'progs'))
from ifft_sous_bande import selectionner
from commun import physique


class SousBandeTests(unittest.TestCase):
    def test_echo_connu_sur_deux_bandes(self):
        f = np.linspace(1e9, 6e9, 201)
        # Écho à 83 cm ; phase constante non nulle, amplitude variable positive.
        y = (.02 + .005 * np.cos(2*np.pi*(f-f[0])/(f[-1]-f[0])))
        y = y * np.exp(.7j - 4j*np.pi*f*.83/physique.c)
        fs, ys = selectionner(f, y, 1e9, 4e9)
        self.assertEqual(len(fs), 121)
        np.testing.assert_array_equal(ys, y[:121])
        for ff, yy in ((f, y), (fs, ys)):
            d, h, pas = physique.profil_distance(ff, yy, zoom=16, fenetre='hann')
            self.assertAlmostEqual(d[np.argmax(h)], 830, delta=pas)

    def test_grilles_invalides(self):
        f = np.linspace(1e9, 6e9, 201)
        for debut, fin in ((4e9, 1e9), (0, 4e9), (1e9, 7e9), (1e9, 1.01e9)):
            with self.assertRaises(ValueError):
                selectionner(f, np.ones(201), debut, fin)
        f[10] += 1e6
        with self.assertRaises(ValueError):
            selectionner(f, np.ones(201), 1e9, 4e9)


if __name__ == '__main__':
    unittest.main()
