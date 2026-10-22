"""Garde-fous du lanceur, avec moteur factice : aucun solveur n'est importe."""
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ICI = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('controleur_f2_en_test', ICI / 'calcule_maille_controlee.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


@dataclass
class MontageFactice:
    duree_ns: float


class ControleurTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.r = Path(self.temp.name)
        self.base = self.r / 'resultats/campagne_f2'
        self.physiques = [f'physique_{i}.py' for i in range(9)] + ['fdtd_maille_controlee.py']
        for n in (*C.CONTROLES, *self.physiques):
            (self.r / n).write_text('source originale\n', encoding='utf-8')
        self.sources = lambda: {n: hashlib.sha256((self.r / n).read_bytes()).hexdigest() for n in self.physiques}
        self.f2 = SimpleNamespace(NOM_MOTEUR=C.MOTEUR, _sources=self.sources)
        self.q = SimpleNamespace(ANTENNES=('diamant_uwb', 'diamant_uwb_x18', 'vivaldi_tomographie'),
            montage_campagne=Mock(side_effect=lambda n, t, moteur=None: MontageFactice(t)), calcule=Mock(),
            charge_calcul=Mock(), valide_campagne=Mock(), indicateurs=lambda f, s: dict(factice=True))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(C, 'RACINE', self.r))
        self.stack.enter_context(patch.dict(sys.modules, {'fdtd_maille_controlee': self.f2, 'qualifie_pcbway': self.q}))

    def lance(self, **kw):
        return C.calcul('diamant_uwb_x18', 'base', 12., base=self.base, **kw)

    def test_cout_sans_aucune_ecriture(self):
        self.lance(cout=True)
        self.assertFalse(self.base.exists())
        self.assertEqual(self.q.calcule.call_args.kwargs['moteur'], C.MOTEUR)
        self.assertTrue(self.q.calcule.call_args.kwargs['cout'])

    def test_refuse_dossier_partiel_meme_vide(self):
        p = self.base / 'diamant_uwb_x18/base_12ns'
        p.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            self.lance()
        self.q.calcule.assert_not_called()
        self.assertFalse((self.base / 'journaux').exists())

    def test_refuse_archive_controle_existante(self):
        (self.base / 'journaux/controle_maille/diamant_uwb_x18/base_12ns').mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            self.lance()
        self.q.calcule.assert_not_called()

    def test_refuse_imbriquer_dans_historique(self):
        with self.assertRaises(ValueError):
            C.calcul('diamant_uwb', 'base', 12., base=self.r / 'resultats/pcbway_r1/autre')
        self.q.calcule.assert_not_called()

    def test_refuse_inventaire_physique_incomplet(self):
        complet = self.sources()
        self.f2._sources = lambda: {n: h for n, h in complet.items() if n != 'fdtd_maille_controlee.py'}
        with self.assertRaises(ValueError):
            self.lance()
        self.q.calcule.assert_not_called()

    def test_source_changee_pendant_run_interdit_fin_validee(self):
        def change(*args, **kwargs):
            (self.r / 'donnees.py').write_text('change pendant run\n', encoding='utf-8')
        self.q.calcule.side_effect = change
        with self.assertRaises(ValueError):
            self.lance()
        self.q.charge_calcul.assert_not_called()
        a = self.base / 'journaux/controle_maille/diamant_uwb_x18/base_12ns'
        self.assertTrue((a / 'controle.json').is_file())
        self.assertFalse((a / 'fin_calcul.json').exists())

    def test_marqueur_manquant_ne_produit_pas_de_fin(self):
        self.q.charge_calcul.return_value = ([], [],
            dict(moteur=C.MOTEUR, sources_sha256=self.sources(), execution={}), {})
        with self.assertRaises(ValueError):
            self.lance()
        self.assertFalse((self.base / 'journaux/controle_maille/diamant_uwb_x18/base_12ns/fin_calcul.json').exists())

    def test_fin_uniquement_apres_controle_complete(self):
        self.q.charge_calcul.return_value = ([], [],
            dict(moteur=C.MOTEUR, sources_sha256=self.sources(), execution={'factice': True}), dict(moteur=C.MOTEUR))
        def faux_calcul(*args, **kwargs):
            p = self.base / 'diamant_uwb_x18/base_12ns'
            p.mkdir(parents=True)
            for n in ('simulation_manifest.json', 'qualification_entree.json'):
                (p / n).write_text('{}\n', encoding='utf-8')
        self.q.calcule.side_effect = faux_calcul
        resultat = self.lance()
        a = self.base / 'journaux/controle_maille/diamant_uwb_x18/base_12ns'
        trace = json.loads((a / 'fin_calcul.json').read_text(encoding='utf-8'))
        self.assertEqual(trace, resultat)
        self.assertTrue(trace['sources_et_controles_inchanges'])
        self.assertFalse(trace['qualification_globale_effectuee'])
        self.assertEqual(len(list(a.glob('*.py'))), len(C.CONTROLES))
        self.assertEqual(self.q.montage_campagne.call_args.kwargs['moteur'], C.MOTEUR)


if __name__ == '__main__':
    unittest.main()
