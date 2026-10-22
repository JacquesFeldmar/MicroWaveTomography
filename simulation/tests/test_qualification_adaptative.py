"""Selection de convergence prolongee : aucune execution FDTD.

Les archives sont synthetiques, avec les vrais CSXCAD/CalcPort. Une reponse
tardive est injectee dans les sondes pour faire echouer 8->12 ns, tandis que
12->16 ns et le raffinement a 16 ns passent. Ce n'est pas un resultat d'antenne.
"""
from copy import deepcopy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SIM))
import fdtd as F
import fenetre_sondes as W
import qualifie_pcbway as Q
import qualification_adaptative as A


def selection_adaptee():
    return dict(spatial=["base_16ns","fin_16ns"],temporel=["fin_12ns","fin_16ns"],
        reference="fin_16ns",preliminaires=[
            dict(type="spatial",calculs=["base_8ns","fin_8ns"],motif="Premier essai spatial a 8 ns"),
            dict(type="temporel",calculs=["fin_8ns","fin_12ns"],motif="Fenetre 8 ns insuffisante")])


class Selection(unittest.TestCase):
    def test_profils_stricts_sans_traversal(self):
        self.assertEqual(A.profil("tres_fin_16ns"),("tres_fin",16.))
        self.assertEqual(A.profil("fin_0.5ns"),("fin",.5))
        for nom in ("../fin_16ns",r"x\fin_16ns","/fin_16ns","fin_-1ns","fin_0ns",
                    "fin_nanns","fin_infns","fin_1e2ns","fin_016ns","inconnu_16ns",None):
            with self.subTest(nom=nom),self.assertRaises(ValueError):
                A.profil(nom)

    def test_selection_standard_et_adaptee_connectees(self):
        self.assertEqual(A._selection_effective(A.selection_standard()),A.selection_standard())
        self.assertEqual(A._selection_effective(selection_adaptee()),selection_adaptee())

    def test_paires_invalides_et_seuil_injecte_refuses(self):
        cas = []
        s = selection_adaptee();s["spatial"]=["base_8ns","fin_16ns"];cas.append(s)
        s = selection_adaptee();s["spatial"]=["fin_16ns","base_16ns"];cas.append(s)
        s = selection_adaptee();s["spatial"]=["base_8ns","fin_8ns"];cas.append(s)
        s = selection_adaptee();s["temporel"]=["fin_16ns","fin_12ns"];cas.append(s)
        s = selection_adaptee();s["temporel"]=["base_12ns","fin_16ns"];cas.append(s)
        s = selection_adaptee();s["reference"]="fin_12ns";cas.append(s)
        s = selection_adaptee();s["seuils_acceptation"]={"maximum_complexe":1};cas.append(s)
        for spec in cas:
            with self.subTest(spec=spec),self.assertRaises(ValueError):
                A._selection_effective(spec)

    def test_prolongement_minimal4ns_exact_et_pas_quasi_nul(self):
        for paire in (["fin_11.999ns","fin_12ns"],["fin_16ns","fin_19.999ns"],
                      ["fin_12ns","fin_12.0001ns"]):
            with self.subTest(paire=paire),self.assertRaisesRegex(ValueError,"4 ns"):
                A._paire("temporel",paire)
        # 18.9 - 14.9 est legerement inferieur a 4 en float binaire.
        A._paire("temporel",["fin_14.9ns","fin_18.9ns"])
        A._paire("temporel",["fin_16ns","fin_20ns"])

    def test_reference_ne_peut_preceder_les_preliminaires(self):
        spec=selection_adaptee()
        spec["preliminaires"].append(dict(type="temporel",calculs=["fin_16ns","fin_20ns"],
            motif="Essai ulterieur a conserver"))
        with self.assertRaisesRegex(ValueError,"reference"):
            A._selection_effective(spec)
        spec=selection_adaptee()
        spec.update(spatial=["base_9ns","fin_9ns"],temporel=["fin_5ns","fin_9ns"],reference="fin_9ns")
        with self.assertRaisesRegex(ValueError,"reference"):
            A._selection_effective(spec)
        spec.update(spatial=["base_1ns","fin_1ns"],temporel=["fin_0.5ns","fin_1ns"],reference="fin_1ns")
        with self.assertRaises(ValueError):
            A._selection_effective(spec)

    def test_adaptation12ns_exige_niveau_effectivement_plus_fin(self):
        spec=selection_adaptee()
        spec.update(spatial=["base_12ns","fin_12ns"],temporel=["fin_8ns","fin_12ns"],reference="fin_12ns")
        with self.assertRaisesRegex(ValueError,"niveau fin"):
            A._selection_effective(spec)
        spec.update(spatial=["fin_12ns","tres_fin_12ns"],
            temporel=["tres_fin_8ns","tres_fin_12ns"],reference="tres_fin_12ns")
        self.assertEqual(A._selection_effective(spec),spec)

    def test_adaptation_ne_peut_cacher_historique_initial(self):
        for prelim in ([],selection_adaptee()["preliminaires"][:1]):
            spec=selection_adaptee();spec["preliminaires"]=prelim
            with self.assertRaisesRegex(ValueError,"essais initiaux"):
                A._selection_effective(spec)
        spec=selection_adaptee();spec["preliminaires"][1]["motif"]=" "
        with self.assertRaises(ValueError):
            A._selection_effective(spec)

    def test_helper_profils_avec_historique_et_fallback(self):
        spec=selection_adaptee()
        profils=A._profils_selection(spec)
        self.assertEqual(profils,["base_8ns","fin_8ns","fin_12ns","base_16ns","fin_16ns"])
        bilan={"antennes":{"a":{"calculs_utilises":profils,"reference":"a/fin_16ns"}}}
        self.assertEqual(A.calculs_utilises(bilan,"a"),profils)
        bilan["antennes"]["a"].pop("calculs_utilises")
        self.assertEqual(A.calculs_utilises(bilan,"a"),["base_8ns","fin_8ns","fin_12ns"])
        bilan["antennes"]["a"]["calculs_utilises"]=["fin_16ns","fin_16ns"]
        with self.assertRaises(ValueError):
            A.calculs_utilises(bilan,"a")

    def test_config_defauts_snapshot_sha_et_cles_dupliquees(self):
        with tempfile.TemporaryDirectory(prefix="mwt_selection_tests_") as dossier:
            p=Path(dossier)/A.FICHIER_SELECTION
            cfg=dict(schema=A.SCHEMA_SELECTION,antennes={"diamant_uwb":selection_adaptee()})
            Q.sauve(p,cfg)
            raw=p.read_bytes()
            snapshot,effectives,sha,octets=A.lire_selection(dossier)
            self.assertEqual(snapshot,cfg)
            self.assertEqual(octets,raw)
            self.assertEqual(sha,W.sha256(p))
            self.assertEqual(effectives["diamant_uwb_x18"],A.selection_standard())
            p.write_text('{"schema":"selection_qualification_pcbway_v1","antennes":{},"antennes":{}}',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"dupliquee"):
                A.lire_selection(dossier)

    def test_proposition20_conserve_historique_et_declare_palier16(self):
        source=A.proposer_selection("diamant_uwb",16.,12.,"8 ns insuffisantes")
        resultat=A.proposer_selection("vivaldi_tomographie",20.,16.,"Sensibilite a mesurer",source)
        self.assertEqual(resultat["antennes"]["diamant_uwb"],source["antennes"]["diamant_uwb"])
        v=resultat["antennes"]["vivaldi_tomographie"]
        self.assertEqual(v["spatial"],["base_20ns","fin_20ns"])
        self.assertEqual(v["temporel"],["fin_16ns","fin_20ns"])
        self.assertEqual(v["reference"],"fin_20ns")
        self.assertEqual([e["calculs"] for e in v["preliminaires"]],
            [["base_8ns","fin_8ns"],["fin_8ns","fin_12ns"],["fin_12ns","fin_16ns"]])
        self.assertNotIn("reussi",v)
        prolonge=A.proposer_selection("diamant_uwb",20.,16.,"Nouveau controle",source)
        p=prolonge["antennes"]["diamant_uwb"]["preliminaires"]
        self.assertIn(["base_16ns","fin_16ns"],[e["calculs"] for e in p])
        self.assertIn(["fin_12ns","fin_16ns"],[e["calculs"] for e in p])

    def test_creation_neuve_et_protection_campagne_active(self):
        cfg=A.proposer_selection("diamant_uwb",16.,12.,"Controle necessaire")
        with tempfile.TemporaryDirectory(prefix="mwt_selection_creation_") as dossier:
            root=Path(dossier)
            actif=root/"base"
            manifeste=actif/"antenne"/"profil"/"simulation_manifest.json"
            Q.sauve(manifeste,{"etat":"calcul_en_cours"})
            with patch.object(Q,"BASE",actif):
                with self.assertRaisesRegex(ValueError,"campagne en cours"):
                    A.creer_selection(actif/A.FICHIER_SELECTION,cfg)
                cible=root/"brouillon.json"
                sha=A.creer_selection(cible,cfg)
                self.assertEqual(sha,W.sha256(cible))
                avant=cible.read_bytes()
                with self.assertRaises(FileExistsError):
                    A.creer_selection(cible,cfg)
                self.assertEqual(cible.read_bytes(),avant)
            self.assertFalse((actif/A.FICHIER_SELECTION).exists())

    def test_cli_creation_et_validation_structurelles(self):
        with tempfile.TemporaryDirectory(prefix="mwt_selection_cli_") as dossier:
            cible=Path(dossier)/"brouillon.json"
            script=SIM/"qualification_adaptative.py"
            r=subprocess.run([sys.executable,"-B","-X","utf8",str(script),
                "--creer-selection",str(cible),"--adapter","vivaldi_tomographie",
                "--duree-ns","20","--depuis-ns","16","--motif","Controle temporel a evaluer"],
                capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue(json.loads(r.stdout)["validation_structurelle_uniquement"])
            avant=cible.read_bytes()
            r=subprocess.run([sys.executable,"-B","-X","utf8",str(script),
                "--valider-selection",str(cible)],capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("fin_20ns",json.loads(r.stdout)["calculs_utilises"]["vivaldi_tomographie"])
            self.assertEqual(cible.read_bytes(),avant)


@unittest.skipUnless(importlib.util.find_spec("openEMS"),"environnement openems requis, sans Run")
class CampagneAdaptee(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reutilisation du constructeur d'archives completes de la suite Q.
        # Aucun mock minimal ne remplace les grilles, sources ou CalcPort.
        import test_qualification_pcbway as fixtures
        cls.temp=tempfile.TemporaryDirectory(prefix="mwt_adaptative_tests_")
        cls.racine=Path(cls.temp.name).resolve()
        cls.base=cls.racine/"campagne"
        cls.nom="diamant_uwb"
        for niveau,duree in (("base",8.),("fin",12.),("base",16.),("fin",16.)):
            fixtures.ArchivesQualification.cree_archive.__func__(cls,niveau,duree)
            if duree >= 12.:
                cls.ajoute_reponse_tardive(cls.base/cls.nom/f"{niveau}_{duree:g}ns")
        W.derive(cls.base/cls.nom/"fin_12ns",cls.base/cls.nom/"fin_8ns",8.)
        Q.sauve(cls.base/A.FICHIER_SELECTION,dict(schema=A.SCHEMA_SELECTION,
            antennes={cls.nom:selection_adaptee()}))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def ajoute_reponse_tardive(cls,dossier):
        m=json.loads((dossier/"simulation_manifest.json").read_text(encoding="utf-8"))
        courant=np.loadtxt(dossier/"port_it_1",comments="%")
        t=courant[:,0]
        courant[:,1] += .04/50*np.exp(-((t-9e-9)/.2e-9)**2)*np.cos(2*np.pi*3.5e9*t)
        np.savetxt(dossier/"port_it_1",courant,fmt="%.14e",header="t/s signal",comments="% ")
        montage=W.montage_depuis_dict(m["montage"])
        module=F.charge_antenne(cls.nom)
        owner,csx,port,_=F.construit(montage,module,dossier=str(dossier),
            n_pas=m["execution"]["n_pas"],dt_impose_s=m["execution"]["dt_s"])
        f=np.linspace(1e9,6.3e9,213)
        port.CalcPort(str(dossier),f,ref_impedance=50)
        F.ecrit_s1p(str(dossier/"s11.s1p"),f,port.uf_ref/port.uf_inc,
            commentaire="SYNTHETIQUE UNITTEST, reponse tardive connue, aucun Run")
        m["sondes"]["port_it_1"]["sha256"]=W.sha256(dossier/"port_it_1")
        m["fichiers_sha256"]={p.relative_to(dossier).as_posix():W.sha256(p)
            for p in dossier.rglob("*") if p.is_file() and p.name != "simulation_manifest.json"}
        W.ecrit_json(dossier/"simulation_manifest.json",m)

    def copie(self):
        base=self.racine/self._testMethodName/"campagne"
        shutil.copytree(self.base,base)
        return base

    def execute(self,base,ecrire=True):
        with patch.object(Q,"ANTENNES",(self.nom,)),contextlib.redirect_stdout(io.StringIO()):
            return A.comparer(base,ecrire=ecrire)

    def modifie(self,p,fonction):
        objet=json.loads(p.read_text(encoding="utf-8"))
        fonction(objet)
        Q.sauve(p,objet)

    def test_extension_reussie_conserve_echec_preliminaire_et_toutes_preuves(self):
        base=self.copie()
        with patch.object(Q,"figures",wraps=Q.figures) as figure:
            bilan=self.execute(base)
        r=bilan["antennes"][self.nom]
        self.assertTrue(bilan["tous_reussis"])
        self.assertTrue(r["spatial"]["reussi"])
        self.assertTrue(r["temporel"]["reussi"])
        self.assertTrue(r["essais_preliminaires"][0]["ecarts"]["reussi"])
        self.assertFalse(r["essais_preliminaires"][1]["ecarts"]["reussi"])
        self.assertGreater(r["essais_preliminaires"][1]["ecarts"]["valeurs"]["maximum_complexe"],.015)
        self.assertEqual(r["temporel"]["seuils_acceptation"],r["essais_preliminaires"][1]["ecarts"]["seuils_acceptation"])
        profils=["base_8ns","fin_8ns","fin_12ns","base_16ns","fin_16ns"]
        self.assertEqual(r["calculs_utilises"],profils)
        self.assertEqual([x[0] for x in figure.call_args.args[1]],profils)
        self.assertEqual(Path(r["reference"]),base/self.nom/"fin_16ns")
        self.assertEqual({p.split('/')[1] for p in r["preuves_sha256"]},set(profils))
        self.assertEqual(bilan["configuration_sha256"],{A.FICHIER_SELECTION:W.sha256(base/A.FICHIER_SELECTION)})
        self.assertEqual(A.calculs_utilises(bilan,self.nom),profils)
        f,s,_,_=Q.charge_calcul(base/self.nom/"fin_16ns")
        fc,sc=Q.lit_s1p(str(base/self.nom/"comparaison"/"reference_simulation.s1p"))
        np.testing.assert_array_equal(f,fc)
        np.testing.assert_allclose(s,sc,atol=2e-13,rtol=2e-12)
        avant={p.relative_to(base).as_posix():W.sha256(p) for p in base.rglob("*") if p.is_file()}
        self.assertEqual(self.execute(base,ecrire=False),bilan)
        self.assertEqual(avant,{p.relative_to(base).as_posix():W.sha256(p) for p in base.rglob("*") if p.is_file()})

    def test_relecture_refuse_csv_png_et_configuration_alteres(self):
        base=self.copie()
        self.execute(base)
        csv=base/self.nom/"comparaison"/"reference_simulation.csv"
        original=csv.read_bytes()
        d=np.loadtxt(csv,delimiter=",",comments="#");d[0,1]+=.01
        np.savetxt(csv,d,delimiter=",")
        with self.assertRaises(ValueError):
            self.execute(base,ecrire=False)
        csv.write_bytes(original)
        png=base/self.nom/"comparaison"/"comparaison_convergence.png"
        image=png.read_bytes();png.write_bytes(image+b"alteration")
        with self.assertRaises(ValueError):
            self.execute(base,ecrire=False)
        png.write_bytes(image)
        config=base/A.FICHIER_SELECTION
        config.write_bytes(config.read_bytes()+b"\n")
        with self.assertRaisesRegex(ValueError,"configuration"):
            self.execute(base,ecrire=False)

    def test_relecture_apres_deplacement_garde_octets_et_sha(self):
        base=self.copie()
        bilan=self.execute(base)
        deplace=base.parent/"preuves_extraites"/"autre_base"
        shutil.copytree(base,deplace)
        avant={p.relative_to(deplace).as_posix():W.sha256(p) for p in deplace.rglob("*") if p.is_file()}
        relu=self.execute(deplace,ecrire=False)
        self.assertTrue(relu["tous_reussis"])
        self.assertEqual(relu["antennes"][self.nom]["reference"],str(deplace/self.nom/"fin_16ns"))
        self.assertEqual(avant,{p.relative_to(deplace).as_posix():W.sha256(p) for p in deplace.rglob("*") if p.is_file()})
        sauvegarde=json.loads((deplace/"qualification_globale.json").read_text(encoding="utf-8"))
        self.assertEqual(sauvegarde["antennes"][self.nom]["reference"],bilan["antennes"][self.nom]["reference"])

    def test_portabilite_ne_neutralise_ni_mauvais_profil_ni_autres_champs(self):
        base=self.copie()
        self.execute(base)
        individuel=base/self.nom/"comparaison"/"qualification.json"
        original=individuel.read_bytes()
        self.modifie(individuel,lambda r:r.update(reference="ancien_chemin/fin_12ns"))
        with self.assertRaisesRegex(ValueError,"profil de reference"):
            self.execute(base,ecrire=False)
        individuel.write_bytes(original)
        self.modifie(individuel,lambda r:r["hypothese_plan"].update(reference="autre_metadonnee"))
        with self.assertRaises(ValueError):
            self.execute(base,ecrire=False)
        individuel.write_bytes(original)
        global_=base/"qualification_globale.json"
        self.modifie(global_,lambda b:b["antennes"][self.nom].update(reference="autre_chemin/fin_12ns"))
        with self.assertRaisesRegex(ValueError,"profil de reference"):
            self.execute(base,ecrire=False)

    def test_preliminaire_altere_ne_peut_etre_ignore(self):
        base=self.copie()
        p=base/self.nom/"fin_8ns"/"s11.s1p"
        p.write_bytes(p.read_bytes()+b"! alteration du preliminaire\n")
        with self.assertRaises(ValueError):
            self.execute(base)

    def test_sources_environnement_et_maillage_restent_communs(self):
        base=self.copie()
        p=base/self.nom/"base_8ns"/"simulation_manifest.json"
        self.modifie(p,lambda m:m["environnement"].update(numpy="autre_version"))
        with self.assertRaisesRegex(ValueError,"sources/environnement"):
            self.execute(base)
        shutil.copy2(self.base/self.nom/"base_8ns"/"simulation_manifest.json",p)
        p=base/self.nom/"fin_16ns"/"simulation_manifest.json"
        self.modifie(p,lambda m:m["maillage"]["axes"]["x"].update(sha256="different"))
        with self.assertRaisesRegex(ValueError,"maillage"):
            self.execute(base)


if __name__ == "__main__":
    unittest.main()
