"""Relecture CalcPort reelle, signaux synthetiques; aucun solveur execute."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
import fdtd as F
import fenetre_sondes as W
import qualifie_pcbway as Q
from banc import Acquisition, Maillage, Montage


class Fenetres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='mwt_fenetre_sondes_tests_')
        cls.racine = Path(cls.tmp.name).resolve()
        cls.source = cls.racine/'synthese_12ns'
        cls.source.mkdir()
        cls.m = Montage(acquisition=Acquisition(f_min=1e9, f_max=6.3e9, points=17),
            maillage=Maillage(mailles_par_lambda=10, maille_min=.25, duree_ns=12))
        module = F.charge_antenne('diamant_uwb')
        cls.owner, csx, port, _ = F.construit(cls.m, module)
        cls.dt = F.resume_maillage(csx)['dt_cfl_vide_s']*.8
        cls.n = int(np.ceil(12e-9/cls.dt))+1
        cls.owner, csx, port, _ = F.construit(cls.m, module,
                                             n_pas=cls.n, dt_impose_s=cls.dt)
        u_t = np.arange(cls.n+1)*cls.dt
        i_t = (np.arange(cls.n+1)+.5)*cls.dt

        def signal(t):
            return np.exp(-((t-1e-9)/.2e-9)**2)*np.cos(2*np.pi*3.5e9*t)

        np.savetxt(cls.source/'port_ut_1', np.c_[u_t, signal(u_t)],
            fmt='%.14e', header='time voltage', comments='% ')
        np.savetxt(cls.source/'port_it_1', np.c_[i_t, .6/50*signal(i_t-.12e-9)],
            fmt='%.14e', header='time current', comments='% ')
        for nom in ('et','ht'):
            np.savetxt(cls.source/nom, np.c_[u_t, signal(u_t)], fmt='%.14e', comments='% ')
        # Les parseurs openEMS exigent le nom t/s dans la derniere ligne d'en-tete.
        for nom in ('port_ut_1','port_it_1'):
            p = cls.source/nom
            p.write_bytes(p.read_bytes().replace(b'% time ', b'% t/s ', 1))
        f = np.linspace(cls.m.acquisition.f_min, cls.m.acquisition.f_max, cls.m.acquisition.points)
        port.CalcPort(str(cls.source), f, ref_impedance=50)
        F.ecrit_s1p(str(cls.source/'s11.s1p'), f, port.uf_ref/port.uf_inc)
        cls.owner.Write2XML(str(cls.source/'entree_openems.xml'))
        np.savetxt(cls.source/'openEMS_stats.txt',
                   [F.resume_maillage(csx)['cellules'],cls.dt,cls.n,
                    cls.n*cls.dt,0.,0.],fmt='%.17e')
        np.savez_compressed(cls.source/'maillage.npz',
            **{a: np.asarray(csx.GetGrid().GetLines(a)) for a in 'xyz'})
        geometrie_fdtd = {nom:F._jsonable(getattr(module,nom)())
            for nom in ('cotes','contours_mm','vias_mm','trous_mm','materiau')
            if callable(getattr(module,nom,None))}
        W.ecrit_json(cls.source/'geometrie.json',geometrie_fdtd)
        for nom in F._sources():
            dest = cls.source/'sources'/nom
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SIM/nom, dest)
        carte = Q.G.carte_antenne('diamant_uwb')
        geometrie = Q.G.geometrie_canonique(carte)
        q = dict(schema='qualification_pcbway_r1', antenne=module.NOM, niveau='base',
            signature_physique=Q.signature(carte, cls.m),
            geometrie=geometrie,
            geometrie_sha256=hashlib.sha256(Q.G.json_octets(geometrie)).hexdigest(),
            simulation_contract=carte['simulation_contract'],
            montage=asdict(cls.m), synthetique_unittest=True)
        W.ecrit_json(cls.source/'qualification_entree.json', q)
        cls.manifeste = dict(schema_version=1, etat='termine', synthetique_unittest=True,
            antenne=module.NOM, montage=asdict(cls.m),
            maillage=F.resume_maillage(csx), materiaux=F._proprietes_matiere(csx)[3],
            execution=dict(dt_s=cls.dt, n_pas=cls.n, duree_demandee_s=12e-9,
                duree_prevue_s=(cls.n-1)*cls.dt, fin_energie_active=False),
            sources_sha256=F._sources(),
            sondes={nom: dict(echantillons=cls.n+1) for nom in ('port_ut_1','port_it_1')},
            fichiers_sha256={str(p.relative_to(cls.source)).replace('\\','/'): W.sha256(p)
                for p in cls.source.rglob('*') if p.is_file()})
        W.ecrit_json(cls.source/'simulation_manifest.json', cls.manifeste)

    @classmethod
    def tearDownClass(cls):
        # Chemin absolu explicitement alloue a cette classe de tests.
        if cls.racine.name.startswith('mwt_fenetre_sondes_tests_'):
            cls.tmp.cleanup()

    def test_complete_12_vers_12_reproduit_s11_arrondi(self):
        avant = {str(p.relative_to(self.source)): W.sha256(p)
                 for p in self.source.rglob('*') if p.is_file()}
        out = self.racine/'complete_12ns'
        m = W.derive(self.source, out, 12.)
        source = np.loadtxt(self.source/'s11.s1p', comments=('!','#'))
        derive = np.loadtxt(out/'s11.s1p', comments=('!','#'))
        np.testing.assert_array_equal(source, derive)
        self.assertTrue(m['derive_sondes'])
        self.assertFalse(m['calcul_fdtd_execute'])
        for nom in ('port_ut_1','port_it_1'):
            self.assertEqual((self.source/nom).read_bytes(), (out/nom).read_bytes())
        self.assertEqual(avant, {str(p.relative_to(self.source)): W.sha256(p)
                 for p in self.source.rglob('*') if p.is_file()})

    def test_prefixe_8ns_conserve_demi_pas_et_n_plus_un(self):
        out = self.racine/'prefixe_8ns'
        m = W.derive(self.source, out, 8.)
        n = int(np.ceil(8e-9/self.dt))+1
        self.assertEqual(m['execution']['n_pas'], n)
        for nom in ('port_ut_1','port_it_1'):
            parent = np.loadtxt(self.source/nom, comments='%')
            derive = np.loadtxt(out/nom, comments='%')
            np.testing.assert_array_equal(derive, parent[:n+1])
        self.assertEqual(m['maillage'], self.manifeste['maillage'])
        q = json.loads((out/'qualification_entree.json').read_text(encoding='utf-8'))
        attendu = replace(self.m, maillage=replace(self.m.maillage, duree_ns=8.))
        self.assertEqual(q['signature_physique'], Q.signature(Q.G.carte_antenne('diamant_uwb'), attendu))
        # Compatible avec le lecteur reel de qualification, empreintes incluses.
        Q.charge_calcul(out,exiger_courant=True)

    def test_refuse_ecrasement_et_source_alteree(self):
        out = self.racine/'a_conserver'
        out.mkdir()
        (out/'temoin').write_text('conserver', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            W.derive(self.source, out, 8.)
        with self.assertRaisesRegex(ValueError, 'disjoints'):
            W.derive(self.source, self.source/'derivee', 8.)
        with self.assertRaisesRegex(ValueError, 'plus longue'):
            W.derive(self.source, self.racine/'trop_long', 13.)

    def test_refuse_archive_alteree_et_pulse_tronque(self):
        copie = self.racine/'source_alt'
        shutil.copytree(self.source, copie)
        with (copie/'port_it_1').open('ab') as out:
            out.write(b'0 0\n')
        with self.assertRaisesRegex(ValueError, 'alteree'):
            W.derive(copie, self.racine/'refus_alt', 8.)
        with self.assertRaisesRegex(ValueError, 'pulse gaussien'):
            W.derive(self.source, self.racine/'refus_pulse', .1)

    def test_refuse_nombre_lignes_faux_meme_si_hash_actualise(self):
        copie = self.racine/'source_sans_derniere_ligne'
        shutil.copytree(self.source, copie)
        p = copie/'port_ut_1'
        lignes = p.read_bytes().splitlines(keepends=True)
        p.write_bytes(b''.join(lignes[:-1]))
        m = json.loads((copie/'simulation_manifest.json').read_text(encoding='utf-8'))
        m['fichiers_sha256']['port_ut_1'] = W.sha256(p)
        W.ecrit_json(copie/'simulation_manifest.json', m)
        with self.assertRaisesRegex(ValueError, 'nombre reel de lignes'):
            W.derive(copie, self.racine/'refus_n_lignes', 8.)


if __name__ == '__main__':
    unittest.main()
