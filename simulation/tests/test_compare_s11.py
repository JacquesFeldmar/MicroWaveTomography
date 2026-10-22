"""Comparaison S11 aux plans declares : fixtures analytiques, aucun openEMS."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SIM))
import compare_s11 as C


class ComparaisonS11(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mwt_compare_s11_tests_")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.f = np.linspace(1e9,6.3e9,213)
        self.reference = .2*np.exp(-2j*np.pi*self.f*.3e-9)

    def ecrit(self,nom,s=None,f=None,reference=50):
        f = self.f if f is None else f
        s = self.reference if s is None else s
        p = self.base/nom
        lignes = ["! entree originale a conserver",f"# Hz S RI R {reference}"]
        lignes.extend(f"{x:.10f} {y.real:.16e} {y.imag:.16e} ! point" for x,y in zip(f,s))
        p.write_text("\n".join(lignes)+"\n",encoding="utf-8")
        return p

    def test_phase_connue_repetitions_csv_sha_et_rendu_reel(self):
        simulation = self.ecrit("simulation.s1p")
        a = .25*np.exp(-2j*np.pi*self.f*.3e-9+1j*.4)
        b = .25*np.exp(-2j*np.pi*self.f*.3e-9+1j*.6)
        m1,m2 = self.ecrit("reconnexion1.s1p",a),self.ecrit("reconnexion2.s1p",b)
        avant = {p:p.read_bytes() for p in (simulation,m1,m2)}
        sortie = self.base/"comparaison"
        r = C.comparer(simulation,[m1,m2],sortie,"SOL au SMA male du cable ; aucune extension de port")
        ecart = r["mesures"][0]["ecarts_simulation"]
        attendu = abs(.25*np.exp(1j*.4)-.2)
        self.assertAlmostEqual(ecart["maximum_complexe"],attendu,places=12)
        self.assertAlmostEqual(ecart["rms_complexe"],attendu,places=12)
        self.assertAlmostEqual(ecart["percentile95_ecart_db"],20*np.log10(1.25),places=10)
        self.assertAlmostEqual(ecart["percentile95_ecart_phase_principale_deg"],np.rad2deg(.4),places=10)
        self.assertAlmostEqual(r["dispersion"]["ecart_type_complexe_max"],abs(a[0]-b[0])/np.sqrt(2),places=12)
        self.assertFalse(r["conventions"]["recalage_phase"])
        self.assertFalse(r["conventions"]["recalage_retard"])
        self.assertNotIn("reussi",r)
        self.assertNotIn("seuils_acceptation",ecart)
        for p,octets in avant.items():
            self.assertEqual(p.read_bytes(),octets)
        for description in [r["simulation"],*r["mesures"]]:
            copie = sortie/description["copie"]
            self.assertEqual(C.sha256(copie.read_bytes()),description["sha256"])
        with (sortie/"courbes.csv").open(encoding="utf-8",newline="") as f:
            lignes = list(csv.DictReader(f))
        phases_sim = np.array([float(l["phase_deg"]) for l in lignes if l["id"] == "simulation"])
        phases_m1 = np.array([float(l["phase_deg"]) for l in lignes if l["id"] == "mesure_01"])
        np.testing.assert_allclose(phases_m1-phases_sim,np.rad2deg(.4),atol=1e-10)
        np.testing.assert_allclose(np.diff(phases_sim),-360*.3e-9*(self.f[1]-self.f[0]),atol=1e-10)
        manifeste = json.loads((sortie/"manifest_comparaison.json").read_text(encoding="utf-8"))
        for nom,sha in manifeste["fichiers_sha256"].items():
            self.assertEqual(hashlib.sha256((sortie/nom).read_bytes()).hexdigest(),sha)
        self.assertGreater((sortie/"comparaison_s11.png").stat().st_size,20000)
        self.assertTrue((sortie/"dispersion_frequentielle.csv").is_file())
        json.loads((sortie/"resultats.json").read_text(encoding="utf-8"))

    def test_decalage_frequence_minime_est_refuse_sans_creer_sortie(self):
        simulation = self.ecrit("simulation.s1p")
        mesure = self.ecrit("mesure.s1p",f=self.f+.5)
        sortie = self.base/"absent"
        with self.assertRaisesRegex(ValueError,"grille differente"):
            C.comparer(simulation,[mesure],sortie,"SOL SMA")
        self.assertFalse(sortie.exists())

    def test_grilles_non_uniforme_et_nulle_refusees(self):
        simulation = self.ecrit("simulation.s1p")
        for grille in (np.geomspace(1e9,6.3e9,213),np.zeros(213)):
            mesure = self.ecrit("mesure.s1p",f=grille)
            with self.assertRaises(ValueError):
                C.comparer(simulation,[mesure],self.base/"absent","SOL SMA")
        self.assertFalse((self.base/"absent").exists())

    def test_impedance_reference_autre_que_50_refusee(self):
        simulation = self.ecrit("simulation.s1p")
        mesure = self.ecrit("mesure.s1p",reference=75)
        with self.assertRaisesRegex(ValueError,"50"):
            C.comparer(simulation,[mesure],self.base/"absent","SOL SMA")

    def test_aucune_entree_plan_vide_et_chemin_duplique_refuses(self):
        simulation = self.ecrit("simulation.s1p")
        mesure = self.ecrit("mesure.s1p")
        with self.assertRaisesRegex(ValueError,"au moins"):
            C.comparer(simulation,[],self.base/"absent","SOL SMA")
        with self.assertRaisesRegex(ValueError,"plans"):
            C.comparer(simulation,[mesure],self.base/"absent","  ")
        with self.assertRaisesRegex(ValueError,"plusieurs fois"):
            C.comparer(simulation,[mesure,mesure],self.base/"absent","SOL SMA")
        self.assertFalse((self.base/"absent").exists())

    def test_dossier_non_vide_est_preserve(self):
        simulation = self.ecrit("simulation.s1p")
        mesure = self.ecrit("mesure.s1p")
        sortie = self.base/"a_conserver"
        sortie.mkdir()
        temoin = sortie/"temoin"
        temoin.write_bytes(b"intact")
        with self.assertRaises(FileExistsError):
            C.comparer(simulation,[mesure],sortie,"SOL SMA")
        self.assertEqual(temoin.read_bytes(),b"intact")

    def test_zero_phase_indefinie_et_circuit_ouvert(self):
        s = np.zeros(213,dtype=complex)
        self.assertTrue(np.all(np.isnan(C.phase_deg(s))))
        np.testing.assert_array_equal(C.impedance(s),np.full(213,50.))
        r = C.indicateurs(self.f,s)
        self.assertEqual(r["phase_indefinie_points"],213)
        self.assertEqual(r["moins_10_db"]["couverture"],1.)
        self.assertEqual(r["minimum_global"]["niveau_db"],-360.)
        self.assertIsNone(C.ecarts(s,s)["percentile95_ecart_db"])
        json.dumps(r,allow_nan=False)
        self.assertTrue(np.isnan(C.impedance(np.array([1+0j]))[0]))

    def test_dispersion_un_seul_fichier_non_estimee_et_bandes_disjointes(self):
        resume,frequentiel = C.dispersion([dict(s11=self.reference)])
        self.assertFalse(resume["disponible"])
        self.assertIsNone(frequentiel)
        s = np.full(213,.9+0j)
        s[20:40],s[100:150] = .1,.2
        r = C.indicateurs(self.f,s)
        self.assertEqual(len(r["moins_10_db"]["segments_hz"]),2)
        self.assertEqual(r["minimum_global"]["frequence_hz"],self.f[20])


if __name__ == "__main__":
    unittest.main()
