"""Regressions de la commande publique, sans lancer openEMS."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from banc import C
from donnees import charge_dossier
import run


def ecrit_s1p(chemin, freqs, s11, commentaire=""):
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    lignes = [f"! {commentaire}", "# Hz S RI R 50"]
    lignes.extend(f"{f:.9f} {s.real:.12g} {s.imag:.12g}" for f, s in zip(freqs, s11))
    chemin.write_text("\n".join(lignes), encoding="ascii")


class CommandePublique(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.f = np.linspace(1e9, 6e9, 201)
        self.fond = np.full(201, .3, dtype=complex)
        self.plaques = {x: self.fond + .05 * np.exp(-4j * np.pi * self.f * x / 100 / C) for x in (50.5, 60.)}
        antenne = SimpleNamespace(NOM="antenne_test", DESCRIPTION="antenne de test")
        self.F = SimpleNamespace(charge_antenne=Mock(return_value=antenne),
                                 estime_cout=Mock(return_value=(1000, 3000, .1)),
                                 serie=Mock(return_value=(self.f, self.fond, self.plaques)),
                                 lance=Mock(return_value=(self.f, np.full(201, .9))),
                                 ecrit_s1p=ecrit_s1p)

    def commande(self, *args):
        sortie = io.StringIO()
        with patch.dict(sys.modules, {"fdtd": self.F}), patch.object(sys, "argv", ["run.py", "--sortie", str(self.base), *args]), patch.object(run, "_sortie") as figures, patch.object(run.fig, "figure_s11", return_value="s11.png"), contextlib.redirect_stdout(sortie):
            run.principal()
        return sortie.getvalue(), figures

    def test_serie_commune_et_reimport_natif(self):
        _, figures = self.commande("--mode", "fdtd", "--distances", "50.5", "60",
                                   "--mailles-substrat", "24", "--maille-min", ".3",
                                   "--duree-ns", "45", "--n-pas-max", "80000")
        self.F.serie.assert_called_once()
        self.F.lance.assert_not_called()
        montage = self.F.serie.call_args.args[0]
        self.assertFalse(montage.maillage.symetrie)
        self.assertEqual(montage.maillage.mailles_par_lambda, 24)
        self.assertEqual(montage.maillage.maille_min, .3)
        self.assertEqual(montage.maillage.n_pas_max, 80000)
        self.assertEqual(self.F.serie.call_args.kwargs["duree_ns"], 45)
        self.assertEqual(len(self.F.estime_cout.call_args_list), 3)  # fond inclus
        self.assertTrue(all(c.kwargs["distances_communes_cm"] == [50.5, 60.] for c in self.F.estime_cout.call_args_list))
        f, fond, plaques = charge_dossier(self.base / "antenne_test")
        np.testing.assert_allclose(f, self.f)
        np.testing.assert_allclose(fond, self.fond)
        for x, s in plaques.items():
            np.testing.assert_allclose(s, self.plaques[x])
        self.assertFalse(figures.call_args.args[-1])  # reference historique opt-in

    def test_aucune_bande_est_un_compte_rendu_valide(self):
        texte, _ = self.commande("--mode", "fdtd-antenne")
        self.assertIn("aucun point", texte)
        self.assertIn("0.0 %", texte)
        self.F.serie.assert_not_called()
        self.F.lance.assert_called_once()
        self.assertTrue(Path(self.F.lance.call_args.kwargs["dossier"]).is_absolute())

    def test_estimation_n_execute_ni_serie_ni_lance(self):
        self.commande("--mode", "fdtd", "--cout")
        self.F.serie.assert_not_called()
        self.F.lance.assert_not_called()

    def test_mesures_refuse_grille_non_uniforme_avant_figure(self):
        self.base.mkdir(exist_ok=True)
        f = np.geomspace(1e9, 6e9, 201)
        ecrit_s1p(self.base / "background.s1p", f, self.fond)
        ecrit_s1p(self.base / "plate_50cm.s1p", f, self.fond)
        with self.assertRaisesRegex(ValueError, "non uniforme"):
            self.commande("--mode", "mesures", "--donnees", str(self.base))


if __name__ == "__main__":
    unittest.main()
