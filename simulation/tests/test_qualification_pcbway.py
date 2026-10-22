"""Qualification S11 : criteres et provenance, sans execution du solveur.

Les archives de cette suite sont SYNTHETIQUES. CSXCAD et CalcPort sont reels,
mais aucun appel a Run n'est autorise. Elles ne qualifient aucune antenne.
"""
from copy import deepcopy
from dataclasses import asdict
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
import fdtd as F
import fenetre_sondes as W
import qualifie_pcbway as Q
from banc import Acquisition, Maillage, Montage


class Criteres(unittest.TestCase):
    def setUp(self):
        self.f = np.linspace(1e9, 6.3e9, 213)

    def test_identiques_passent_et_phase_est_diagnostique(self):
        s = np.full(213, .2 + .1j)
        for temporel in (False, True):
            r = Q.ecarts(self.f, s, self.f.copy(), s.copy(), temporel=temporel)
            self.assertTrue(r["reussi"])
            self.assertEqual(r["valeurs"]["maximum_complexe"], 0.)
        a = np.full(213, .2*np.exp(1j*np.deg2rad(175)))
        b = np.full(213, .2*np.exp(1j*np.deg2rad(-175)))
        r = Q.ecarts(self.f, a, self.f, b)
        self.assertAlmostEqual(r["valeurs"]["percentile95_phase_deg"], 10.)

    def test_limites_spatiale_et_temporelle_sont_distinctes(self):
        a, b = np.full(213, .2 + 0j), np.full(213, .211 + 0j)
        self.assertTrue(Q.ecarts(self.f, a, self.f, b)["reussi"])
        self.assertFalse(Q.ecarts(self.f, a, self.f, b, temporel=True)["reussi"])

    def test_rms_ne_se_confond_pas_avec_maximum(self):
        a, b = np.full(213, .5 + 0j), np.full(213, .53 + 0j)
        r = Q.ecarts(self.f, a, self.f, b)
        self.assertLess(r["valeurs"]["maximum_complexe"], .05)
        self.assertGreater(r["valeurs"]["rms_complexe"], .02)
        self.assertFalse(r["reussi"])

    def test_critere_db_est_effectivement_decisif(self):
        a = np.full(213, .101 + 0j)
        b = a * 10**(1.1/20)
        r = Q.ecarts(self.f, a, self.f, b)
        self.assertLess(r["valeurs"]["rms_complexe"], .02)
        self.assertAlmostEqual(r["valeurs"]["percentile95_db"], 1.1)
        self.assertFalse(r["reussi"])

    def test_delta_complexe_porte_aussi_sur_minima_profonds(self):
        a = np.full(213, .2 + 0j)
        b = a.copy()
        a[-1], b[-1] = -.04, .04
        r = Q.ecarts(self.f, a, self.f, b)
        self.assertAlmostEqual(r["valeurs"]["maximum_complexe"], .08)
        self.assertFalse(r["reussi"])

    def test_masque_db_vide_ne_qualifie_pas_silencieusement(self):
        r = Q.ecarts(self.f, np.full(213, .01), self.f, np.full(213, .01))
        self.assertIsNone(r["valeurs"]["percentile95_db"])
        self.assertFalse(r["reussi"])

    def test_grilles_differentes_refusees(self):
        with self.assertRaisesRegex(ValueError, "grilles"):
            Q.ecarts(self.f, np.ones(213), self.f + 1, np.ones(213))

    def test_indicateurs_segments_et_bande_utile(self):
        s = np.full(213, .9 + 0j)
        s[30:40], s[90:105] = .1, .2
        r = Q.indicateurs(self.f, s)
        self.assertEqual(len(r["moins_10_db"]["segments_hz"]), 2)
        utiles = (self.f >= 1.4e9) & (self.f <= 6e9)
        attendu = 10*np.log10(np.mean(np.abs(s[utiles])**2))
        self.assertAlmostEqual(r["bande_1p4_6"]["moyenne_puissance_reflechie_db"], attendu)
        self.assertTrue(r["passivite_numerique"])
        s[0] = 1.006
        self.assertFalse(Q.indicateurs(self.f, s)["passivite_numerique"])

    def test_indicateurs_zero_restent_serialisables(self):
        # Un coefficient exactement nul est mathematiquement possible ; il
        # ne doit pas transformer le rapport JSON en resultat non fini.
        Q.G.json_octets(Q.indicateurs(self.f, np.zeros(213, dtype=complex)))


@unittest.skipUnless(importlib.util.find_spec("openEMS"), "environnement openems requis, sans Run")
class ArchivesQualification(unittest.TestCase):
    """Archives completes, isolees et marquees synthetiques pour les regressions."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="mwt_qualification_tests_")
        cls.racine = Path(cls.temp.name).resolve()
        cls.base = cls.racine/"campagne"
        cls.nom = "diamant_uwb"
        cls.cree_archive("base", 8.)
        cls.cree_archive("fin", 12.)
        # Meme extracteur que pour la livraison, meme prefixe causal U/I.
        with contextlib.redirect_stdout(io.StringIO()):
            W.derive(cls.base/cls.nom/"fin_12ns", cls.base/cls.nom/"fin_8ns", 8.)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def cree_archive(cls, niveau, duree_ns):
        import openEMS
        import CSXCAD
        import scipy
        dossier = cls.base/cls.nom/f"{niveau}_{duree_ns:g}ns"
        dossier.mkdir(parents=True)
        montage = Montage(acquisition=Acquisition(f_min=1e9, f_max=6.3e9, points=213),
            maillage=Maillage(**Q.NIVEAUX[niveau], duree_ns=duree_ns,
                              symetrie=False, n_pas_max=1000000))
        module = F.charge_antenne(cls.nom)
        owner, csx, port, _ = F.construit(montage, module, dossier=str(dossier))
        dt = F.resume_maillage(csx)["dt_cfl_vide_s"]*.8
        nombre = int(np.ceil(duree_ns*1e-9/dt))+1
        owner, csx, port, _ = F.construit(montage, module, dossier=str(dossier),
                                         n_pas=nombre, dt_impose_s=dt)
        u_t = np.arange(nombre+1)*dt
        i_t = (np.arange(nombre+1)+.5)*dt

        def pulse(t):
            return np.exp(-((t-1e-9)/.2e-9)**2)*np.cos(2*np.pi*3.5e9*t)

        sondes = {}
        for nom, temps, signal in (("port_ut_1", u_t, pulse(u_t)),
                                    ("port_it_1", i_t, .6/50*pulse(i_t))):
            np.savetxt(dossier/nom, np.c_[temps, signal], fmt="%.14e",
                       header="t/s signal", comments="% ")
            sondes[nom] = dict(echantillons=nombre+1, dt_effectif_s=float(np.median(np.diff(temps))),
                debut_s=float(temps[0]), fin_s=float(temps[-1]), sha256=W.sha256(dossier/nom))
        for nom in ("et", "ht"):
            np.savetxt(dossier/nom, np.c_[u_t, pulse(u_t)], fmt="%.14e", comments="% ")
        f = np.linspace(1e9, 6.3e9, 213)
        port.CalcPort(str(dossier), f, ref_impedance=50)
        F.ecrit_s1p(str(dossier/"s11.s1p"), f, port.uf_ref/port.uf_inc,
                   commentaire="SYNTHETIQUE UNITTEST, aucun solveur execute")
        owner.Write2XML(str(dossier/"entree_openems.xml"))
        np.savez_compressed(dossier/"maillage.npz",
            **{a: np.asarray(csx.GetGrid().GetLines(a)) for a in "xyz"})
        np.savetxt(dossier/"openEMS_stats.txt", [F.resume_maillage(csx)["cellules"],dt,nombre,nombre*dt,0.,0.], fmt="%.17e")
        geometrie = {nom: F._jsonable(getattr(module, nom)()) for nom in
            ("cotes", "contours_mm", "vias_mm", "trous_mm", "materiau")
            if callable(getattr(module, nom, None))}
        W.ecrit_json(dossier/"geometrie.json", geometrie)
        sources = F._sources()
        for nom in sources:
            dest = dossier/"sources"/nom
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SIM/nom, dest)
        carte = Q.G.carte_antenne(cls.nom)
        canonique = Q.G.geometrie_canonique(carte)
        q = dict(schema="qualification_pcbway_r1", antenne=cls.nom, niveau=niveau,
            signature_physique=Q.signature(carte, montage), geometrie=canonique,
            geometrie_sha256=hashlib.sha256(Q.G.json_octets(canonique)).hexdigest(),
            simulation_contract=carte["simulation_contract"], montage=asdict(montage),
            synthetique_unittest=True)
        environnement = dict(python=platform.python_version(), numpy=np.__version__,
            scipy=scipy.__version__, csxcad=getattr(CSXCAD,"__version__","inconnu"),
            dtype_maillage="float64 little-endian", openems=getattr(openEMS,"__version__","inconnu"))
        execution = F._durations(montage, csx, n_pas=nombre, duree_ns=duree_ns, dt_s=dt)
        execution.update(dt_calibre_operateur=True)
        m = dict(schema_version=1, etat="termine", antenne=cls.nom, cible_cm=None,
            distances_communes_cm=[], x_domaine_cm=None, montage=asdict(montage),
            maillage=F.resume_maillage(csx), execution=execution,
            materiaux=F._proprietes_matiere(csx)[3], environnement=environnement,
            sources_sha256=sources, entree_xml_sha256=W.sha256(dossier/"entree_openems.xml"),
            geometrie_sha256=W.sha256(dossier/"geometrie.json"), sondes=sondes,
            fichiers_sha256={str(p.relative_to(dossier)).replace("\\", "/"):W.sha256(p)
                             for p in dossier.rglob("*") if p.is_file()},
            synthetique_unittest=True)
        W.ecrit_json(dossier/"simulation_manifest.json", m)
        W.ecrit_json(dossier/"qualification_entree.json", q)

    def copie(self, nom):
        dest = self.racine/self._testMethodName/nom
        shutil.copytree(self.base/self.nom/nom, dest)
        return dest

    def modifie_json(self, dossier, fichier, fonction):
        p = dossier/fichier
        objet = json.loads(p.read_text(encoding="utf-8"))
        fonction(objet)
        W.ecrit_json(p, objet)

    def test_archives_completes_et_fenetre_sont_lisibles(self):
        for niveau, ns in (("base",8.), ("fin",8.), ("fin",12.)):
            dossier = self.base/self.nom/f"{niveau}_{ns:g}ns"
            f,s,m,q = Q.charge_calcul(dossier, exiger_courant=True)
            Q.valide_campagne(m,q,self.nom,niveau,ns)
            self.assertEqual(len(f),213)
            self.assertTrue(np.all(np.isfinite(s)))
        court = json.loads((self.base/self.nom/"fin_8ns"/"simulation_manifest.json").read_text())
        self.assertTrue(court["derive_sondes"])
        self.assertFalse(court["calcul_fdtd_execute"])

    def test_duree_ne_se_deduit_pas_du_nom_du_dossier(self):
        _,_,m,q = Q.charge_calcul(self.base/self.nom/"fin_8ns")
        with self.assertRaises(ValueError):
            Q.valide_campagne(m,q,self.nom,"fin",12.)

    def test_niveau_ne_se_deduit_pas_du_nom_du_dossier(self):
        _,_,m,q = Q.charge_calcul(self.base/self.nom/"base_8ns")
        with self.assertRaises(ValueError):
            Q.valide_campagne(m,q,self.nom,"fin",8.)

    def test_integrite_s11_et_suppression_entree_sha(self):
        dossier = self.copie("base_8ns")
        with (dossier/"s11.s1p").open("ab") as f:
            f.write(b"! alteration de preuve\n")
        with self.assertRaises(ValueError):
            Q.charge_calcul(dossier)
        self.modifie_json(dossier,"simulation_manifest.json",lambda m:m["fichiers_sha256"].pop("s11.s1p"))
        with self.assertRaises(ValueError):
            Q.charge_calcul(dossier)

    def test_sources_archivees_alterees_refusees(self):
        dossier = self.copie("fin_12ns")
        p = dossier/"sources"/"fdtd.py"
        with p.open("ab") as f:
            f.write(b"\n# alteration unittest\n")
        # Meme si la liste generale est actualisee, le SHA des sources fait foi.
        self.modifie_json(dossier,"simulation_manifest.json",
            lambda m:m["fichiers_sha256"].update({"sources/fdtd.py":W.sha256(p)}))
        with self.assertRaises(ValueError):
            Q.charge_calcul(dossier)

    def test_montage_q_et_signature_incoherents_refuses(self):
        dossier = self.copie("fin_12ns")
        self.modifie_json(dossier,"qualification_entree.json",
            lambda q:q["montage"]["maillage"].update(duree_ns=8.))
        with self.assertRaises(ValueError):
            Q.charge_calcul(dossier)

    def test_geometrie_courante_differente_est_refusee(self):
        dossier = self.base/self.nom/"base_8ns"
        carte = deepcopy(Q.G.carte_antenne(self.nom))
        carte["F_Cu"][0][0] = (carte["F_Cu"][0][0][0]+.1, carte["F_Cu"][0][0][1])
        with patch.object(Q.G,"carte_antenne",return_value=carte), self.assertRaises(ValueError):
            Q.charge_calcul(dossier, exiger_courant=True)

    def test_source_moteur_courante_differente_est_refusee(self):
        sources = dict(F._sources())
        sources["fdtd.py"] = "0"*64
        with patch.object(F,"_sources",return_value=sources), self.assertRaises(ValueError):
            Q.charge_calcul(self.base/self.nom/"fin_12ns", exiger_courant=True)

    def test_chemin_sha_hors_archive_est_refuse(self):
        dossier = self.copie("base_8ns")
        dehors = dossier.parent/"hors_archive.txt"
        dehors.write_text("preuve exterieure",encoding="utf-8")
        self.modifie_json(dossier,"simulation_manifest.json",
            lambda m:m["fichiers_sha256"].update({"../hors_archive.txt":W.sha256(dehors)}))
        with self.assertRaises(ValueError):
            Q.charge_calcul(dossier)

    def test_cache_n_ignore_pas_un_s11_altere(self):
        base = self.racine/self._testMethodName/"cache"
        dossier = base/self.nom/"base_8ns"
        shutil.copytree(self.base/self.nom/"base_8ns",dossier)
        with (dossier/"s11.s1p").open("ab") as f:
            f.write(b"! alteration cache\n")
        with patch.object(F,"lance",side_effect=AssertionError("Run interdit")) as lance, self.assertRaises((ValueError,FileExistsError)):
            Q.calcule(self.nom,"base",8.,base=base)
        lance.assert_not_called()

    def test_comparer_refuse_un_autre_environnement(self):
        base = self.racine/self._testMethodName/"campagne"
        shutil.copytree(self.base,base)
        self.modifie_json(base/self.nom/"fin_12ns","simulation_manifest.json",
            lambda m:m["environnement"].update(numpy="version_differente"))
        with patch.object(Q,"ANTENNES",(self.nom,)), self.assertRaises(ValueError):
            Q.comparer(base)

    def test_comparer_selectionne_fin12_et_relecture_est_sans_ecriture(self):
        base = self.racine/self._testMethodName/"campagne"
        shutil.copytree(self.base,base)
        with patch.object(Q,"ANTENNES",(self.nom,)), contextlib.redirect_stdout(io.StringIO()):
            resultat = Q.comparer(base)
        self.assertTrue(resultat["tous_reussis"])
        r = resultat["antennes"][self.nom]
        self.assertEqual(Path(r["reference"]), base/self.nom/"fin_12ns")
        self.assertTrue(r["spatial"]["reussi"])
        self.assertTrue(r["temporel"]["reussi"])
        self.assertEqual(len(r["sorties_sha256"]), 3)
        avant = {str(p.relative_to(base)):W.sha256(p) for p in base.rglob("*") if p.is_file()}
        with patch.object(Q,"ANTENNES",(self.nom,)):
            relu = Q.comparer(base,ecrire=False)
        self.assertTrue(relu["tous_reussis"])
        self.assertEqual(avant,{str(p.relative_to(base)):W.sha256(p) for p in base.rglob("*") if p.is_file()})

    def test_relecture_refuse_csv_livre_altere(self):
        base = self.racine/self._testMethodName/"campagne"
        shutil.copytree(self.base,base)
        with patch.object(Q,"ANTENNES",(self.nom,)), contextlib.redirect_stdout(io.StringIO()):
            Q.comparer(base)
        csv = base/self.nom/"comparaison"/"reference_simulation.csv"
        valeurs = np.loadtxt(csv,delimiter=",",comments="#")
        valeurs[0,1] += .01
        np.savetxt(csv,valeurs,delimiter=",")
        avant = W.sha256(csv)
        with patch.object(Q,"ANTENNES",(self.nom,)), self.assertRaises(ValueError):
            Q.comparer(base,ecrire=False)
        self.assertEqual(W.sha256(csv),avant)


if __name__ == "__main__":
    unittest.main()
