"""Garde-fous numeriques de reprise, avec CSXCAD reel mais sans Run FDTD.

    python -B -X utf8 -m unittest discover -s simulation/tests -p test_fdtd_reprise.py -v
"""
from dataclasses import replace
import pathlib
import sys
import tempfile
import unittest

import numpy as np

SIM = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
import fdtd as F
from banc import Acquisition, C, Maillage, Montage
from materiaux import modele_debye


class Materiaux(unittest.TestCase):
    def test_reference_exacte_et_passivite_large_bande(self):
        modele = modele_debye(4.6, .011, 1e9)
        ref = modele.reponse_complexe(1e9)
        self.assertAlmostEqual(ref.real, 4.6, places=12)
        self.assertAlmostEqual(-ref.imag/ref.real, .011, places=12)
        eps = modele.reponse_complexe(np.geomspace(1e6, 1e11, 200))
        self.assertTrue(np.all(eps.real > 1))
        self.assertTrue(np.all(eps.imag < 0))
        self.assertTrue(all(p > 0 for p in modele.delta_epsilon))
        self.assertGreaterEqual(min(modele.relaxation_s), 1/(2*np.pi*1e11)*(1-1e-12))


class Maillages(unittest.TestCase):
    def setUp(self):
        self.m = Montage(acquisition=Acquisition(f_min=1e9, f_max=6.3e9, points=213),
            maillage=Maillage(mailles_par_lambda=10, maille_min=.2, duree_ns=8))
        self.owners = []

    def construit(self, nom='diamant_uwb', m=None, **kw):
        objet = F.construit(m or self.m, F.charge_antenne(nom), **kw)
        self.owners.append(objet)  # le FDTD possede la structure C++
        return objet[1]

    def test_fond_et_toutes_cibles_identiques_faces_exactes(self):
        distances = [50., 60., 70.]
        fond = self.construit('vivaldi_tomographie', distances_communes_cm=distances)
        for x in distances:
            cible = self.construit('vivaldi_tomographie', x_cm=x,
                                  distances_communes_cm=distances)
            for axe in 'xyz':
                np.testing.assert_array_equal(fond.GetGrid().GetLines(axe),
                                              cible.GetGrid().GetLines(axe))
        for axe in 'xy':
            lignes = np.asarray(fond.GetGrid().GetLines(axe))
            for face in [-self.m.plaque.cote/2, self.m.plaque.cote/2]:
                self.assertIn(face, lignes)
        lignes = np.asarray(fond.GetGrid().GetLines('z'))
        for x in distances:
            self.assertIn(x*10, lignes)
            self.assertIn(x*10+self.m.plaque.epaisseur, lignes)

    def test_resolution_finale_substrat_et_gradation(self):
        for nom in ('diamant_uwb', 'diamant_uwb_x18', 'vivaldi_tomographie'):
            csx = self.construit(nom)
            _, dielectriques, _, definitions = F._proprietes_matiere(csx)
            self.assertEqual(definitions[0]['type'], 'debye_passif_13_poles')
            for boite, eps in dielectriques:
                limite = C/self.m.acquisition.f_max*1e3/np.sqrt(eps)/10
                for i, axe in enumerate('xyz'):
                    l = np.asarray(csx.GetGrid().GetLines(axe))
                    d, milieu = np.diff(l), (l[:-1]+l[1:])/2
                    selection = (milieu >= boite[0, i]) & (milieu <= boite[1, i])
                    self.assertLessEqual(d[selection].max(), limite*(1+1e-7))
                    ratios = np.maximum(d[1:]/d[:-1], d[:-1]/d[1:])
                    self.assertLessEqual(ratios.max(), 1.5*(1+1e-7))

    def test_parametres_substrat_et_port_actifs(self):
        base = self.construit('vivaldi_tomographie')
        fin = self.construit('vivaldi_tomographie', m=replace(self.m,
              maillage=replace(self.m.maillage, mailles_par_lambda=16, maille_min=.15)))
        self.assertGreater(F.resume_maillage(fin)['cellules'],
                           F.resume_maillage(base)['cellules'])
        self.assertLess(F.resume_maillage(fin)['dt_cfl_vide_s'],
                        F.resume_maillage(base)['dt_cfl_vide_s'])
        for d in F.resume_maillage(fin)['axes'].values():
            self.assertLessEqual(d['maximum_mm'], C/6.3e9*1e3/10*(1+1e-7))

    def test_materiau_inchange_quand_bande_acquisition_change(self):
        csx_a = self.construit()
        csx_b = self.construit(m=replace(self.m,
            acquisition=Acquisition(f_min=2e9, f_max=8e9, points=201)))
        self.assertEqual(F._proprietes_matiere(csx_a)[3],
                         F._proprietes_matiere(csx_b)[3])

    def test_cout_grille_reelle_et_absence_symetrie_fictive(self):
        csx = self.construit()
        cellules, pas, minutes = F.estime_cout(self.m,
                                    antenne_mod=F.charge_antenne('diamant_uwb'))
        self.assertEqual(cellules, F.resume_maillage(csx)['cellules'])
        self.assertEqual(pas, F._durations(self.m, csx)['n_pas'])
        self.assertGreater(minutes, 0)
        with self.assertRaisesRegex(ValueError, 'symetrie'):
            self.construit(m=replace(self.m, maillage=replace(self.m.maillage, symetrie=True)))

    def test_pas_de_troncature_silencieuse_ni_ecrasement(self):
        with self.assertRaisesRegex(ValueError, 'n_pas_max'):
            self.construit(m=replace(self.m, maillage=replace(self.m.maillage, n_pas_max=10)))
        # TemporaryDirectory fournit un chemin absolu explicitement reserve
        # a ce test; aucun dossier du projet n'est nettoye.
        with tempfile.TemporaryDirectory(prefix='mwt_fdtd_read_only_') as dossier:
            temoin = pathlib.Path(dossier)/'preuve_existante.txt'
            temoin.write_text('a conserver', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                F.lance(self.m, F.charge_antenne('diamant_uwb'), dossier=dossier)
            self.assertEqual(temoin.read_text(encoding='utf-8'), 'a conserver')


if __name__ == '__main__':
    unittest.main()
