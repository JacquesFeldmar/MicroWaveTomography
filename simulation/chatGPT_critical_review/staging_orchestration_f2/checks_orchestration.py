"""Sous-processus factices ; aucun import ou Run openEMS."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("orchestration_f2_staging",HERE/"orchestre_f2.py")
O=importlib.util.module_from_spec(spec);spec.loader.exec_module(O)

STUB=r'''
import argparse,hashlib,json,os,sys,time
from pathlib import Path
R=Path(__file__).resolve().parent
def lire(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def ecrit(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o),encoding="utf-8")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
cfg=lire(R/"comportement.json")
p=argparse.ArgumentParser();p.add_argument("--base",type=Path);p.add_argument("--antenne");p.add_argument("--niveau");p.add_argument("--duree-ns",type=int);p.add_argument("--fils");p.add_argument("--source",type=Path);p.add_argument("--sortie",type=Path)
a=p.parse_args();genre=Path(__file__).name
def event(type_,nom):
 with (R/"trace.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(dict(type=type_,nom=nom,t=time.time(),pid=os.getpid()))+"\n")
if genre=="qualification_adaptative.py":
 event("analyse","AP");b=a.base
 assert lire(b/"etat_orchestration.json")["tous_reussis"] is False
 rc=cfg.get("ap_rc",0)
 print("analyse UTF-8 : échec ou réussite",flush=True)
 if rc==1 or cfg.get("ap_sans_bilan"):sys.exit(rc)
 s=lire(b/"selection_qualification.json");ants={}
 for nom,spec in s["antennes"].items():
  profils=["base_8ns","fin_8ns","base_12ns","fin_12ns","fin_16ns"]
  preuves={f"{nom}/{pr}/{f}":sha(b/nom/pr/f) for pr in profils for f in ("simulation_manifest.json","qualification_entree.json","s11.s1p")}
  sorties={}
  for f in ("reference_simulation.s1p","reference_simulation.csv","comparaison_convergence.png"):
   q=b/nom/"comparaison"/f;q.parent.mkdir(exist_ok=True);q.write_bytes(b"fixture sans solveur");sorties[q.relative_to(b).as_posix()]=sha(q)
  ants[nom]=dict(selection_effective=spec,calculs_utilises=profils,reference=str(b/nom/"fin_16ns"),reussi=(rc==0),spatial=dict(reussi=(rc==0)),temporel=dict(reussi=True),preuves_sha256=preuves,sorties_sha256=sorties)
 ecrit(b/"qualification_globale.json",dict(schema="qualification_pcbway_r1",moteur="maillage_controle_v2",selection=s,configuration_sha256={"selection_qualification.json":sha(b/"selection_qualification.json")},antennes=ants,tous_reussis=(rc==0)))
 sys.exit(rc)
if genre=="calcule_maille_controlee.py":
 ant,niveau,d=a.antenne,a.niveau,a.duree_ns;b=a.base;sortie=b/ant/f"{niveau}_{d}ns";derive=False
else:
 sortie=a.sortie;ant=sortie.parent.name;niveau=sortie.name.split("_")[0];d=a.duree_ns;b=sortie.parents[1];derive=True
nom=ant+"/"+sortie.name;event("debut",nom)
print("début UTF-8 "+nom,flush=True);print("diagnostic é",file=sys.stderr,flush=True)
time.sleep(.22 if ant=="vivaldi_tomographie" else .05)
rc=cfg.get("calcul_rc",0) if ant==cfg.get("echec_ant") and not derive else 0
if rc:event("fin",nom);sys.exit(rc)
sortie.mkdir(parents=True,exist_ok=False)
tag="fdtd" if ant==cfg.get("mixte_ant") else "maillage_controle_v2"
montage=dict(maillage=dict(duree_ns=d))
m=dict(etat="termine",moteur=tag,antenne=ant,montage=montage,sources_sha256=lire(R/"gel.json")["sources_physiques_sha256"])
q=dict(moteur=tag,antenne=ant,niveau=niveau,montage=montage)
if derive:m["derive_sondes"]=q["derive_sondes"]=True
ecrit(sortie/"simulation_manifest.json",m);ecrit(sortie/"qualification_entree.json",q);(sortie/"s11.s1p").write_text("# Hz S RI R 50\n",encoding="utf-8")
if cfg.get("muter") and ant=="diamant_uwb" and not derive:
 with (R/"fdtd_maille_controlee.py").open("a") as f:f.write("\n# mutation de test\n")
event("fin",nom)
'''


class Orchestration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="mwt_orchestrateur_stub_")
        self.addCleanup(self.tmp.cleanup)
        self.r=Path(self.tmp.name)/"simulation";self.r.mkdir()
        for n in O.PHYSIQUES|O.CONTROLES:
            p=self.r/n;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(STUB if n in {"calcule_maille_controlee.py","fenetre_sondes.py","qualification_adaptative.py"} else "# source stub\n",encoding="utf-8")
        self.g=self.r/"gel.json"
        gel=dict(schema="gel_campagne_pcbway_f2_v1",
            sources_physiques_sha256={n:O.sha(self.r/n) for n in O.PHYSIQUES},
            controles_sha256={n:O.sha(self.r/n) for n in O.CONTROLES})
        pilote=self.r/"resultats/validation_maille_controle_v2/journaux/fin_pilote.json"
        O.neuf(pilote,dict(schema="fin_pilote_natif_maille_controlee_v2",moteur=O.MOTEUR,
            pilote_natif_termine=True,sondes_reelles_NrTS_plus_1_verifiees=True,
            rejeu_deplace_S11_octets_identiques=True,sources_et_controles_inchanges=True,
            qualification_globale_effectuee=False,
            sources_physiques_sha256=gel["sources_physiques_sha256"],
            controles_sha256=gel["controles_sha256"]))
        gel["pilote_valide"]=dict(preuve=pilote.relative_to(self.r).as_posix(),sha256=O.sha(pilote))
        O.neuf(self.g,gel)
        self.b=Path(self.tmp.name)/"campagne_f2"
        self.cfg()

    def cfg(self,**kw):
        (self.r/"comportement.json").write_text(json.dumps(kw),encoding="utf-8")

    def prepare(self):
        return O.prepare(self.r,self.b,self.g,sys.executable)

    def etat(self):return O.lit(self.b/"etat_orchestration.json")
    def events(self):
        p=self.r/"trace.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def test_plan_15_profils_succes_deux_files_et_journaux_utf8(self):
        self.prepare()
        self.assertFalse(self.etat()["tous_reussis"])
        self.assertEqual(O.execute(self.b),0)
        etat=self.etat();self.assertEqual(etat["etat"],"qualifie");self.assertTrue(etat["tous_reussis"])
        events=self.events();actifs=set();maximum=0
        for e in events:
            if e["type"]=="debut":actifs.add(e["pid"]);maximum=max(maximum,len(actifs))
            elif e["type"]=="fin":actifs.remove(e["pid"])
        self.assertEqual(maximum,2);self.assertFalse(actifs)
        for n,etapes in O.plan().items():
            attendu=[e["antenne"]+"/"+e["profil"] for e in etapes]
            retenus=[e["nom"] for e in events if e["type"]=="debut" and e["nom"] in attendu]
            self.assertEqual(retenus,attendu)
        self.assertEqual(len([e for e in events if e["type"]=="fin"]),15)
        self.assertEqual(events[-1]["type"],"analyse")
        self.assertIn("début UTF-8",next((self.b/"journaux/losanges").glob("*.stdout.log")).read_text(encoding="utf-8"))
        self.assertIn("diagnostic é",next((self.b/"journaux/vivaldi").glob("*.stderr.log")).read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):O.execute(self.b)

    def test_echec_numerique_code2_distinct_du_runtime1(self):
        for rc,nom in ((2,"non_convergence"),(1,"echec_analyse")):
            with self.subTest(rc=rc):
                self.b=Path(self.tmp.name)/f"campagne_{rc}";self.cfg(ap_rc=rc);self.prepare()
                self.assertEqual(O.execute(self.b),rc)
                e=self.etat();self.assertEqual(e["etat"],nom);self.assertFalse(e["tous_reussis"])
                self.assertEqual(e["echec_numerique"],rc==2);self.assertEqual(e["echec_technique"],rc==1)
                self.assertEqual(e["analyse"]["retour_natif"],rc)

    def test_sortie2_sans_bilan_pas_un_verdict_numerique(self):
        self.cfg(ap_rc=2,ap_sans_bilan=True);self.prepare();self.assertEqual(O.execute(self.b),2)
        self.assertEqual(self.etat()["etat"],"echec_analyse")
        self.assertTrue(self.etat()["echec_technique"]);self.assertFalse(self.etat()["echec_numerique"])

    def test_worker_exit2_conserve_attend_pair_sans_analyse(self):
        self.cfg(echec_ant="diamant_uwb",calcul_rc=2);self.prepare()
        self.assertEqual(O.execute(self.b),2)
        e=self.etat();self.assertTrue(e["echec_technique"]);self.assertFalse(e["tous_reussis"])
        self.assertIsNone(e["analyse"])
        self.assertTrue(any(x["type"]=="fin" and x["nom"]=="vivaldi_tomographie/base_12ns" for x in self.events()))
        self.assertFalse(any(x["type"]=="analyse" for x in self.events()))

    def test_gel_mutation_pendant_calcul_interdit_suite_et_analyse(self):
        self.cfg(muter=True);self.prepare();self.assertEqual(O.execute(self.b),1)
        self.assertTrue(self.etat()["echec_technique"])
        self.assertFalse(any(x["type"]=="analyse" for x in self.events()))

    def test_profil_mixte_f1_refuse_meme_code_zero(self):
        self.cfg(mixte_ant="vivaldi_tomographie");self.prepare();self.assertEqual(O.execute(self.b),1)
        self.assertIn("F1/F2",json.dumps(self.etat()))
        self.assertFalse(any(x["type"]=="analyse" for x in self.events()))

    def test_preflight_refuse_existant_et_preserve_f1(self):
        f1=self.r/"resultats/pcbway_r1";f1.mkdir(parents=True);temoin=f1/"intact.txt";temoin.write_bytes(b"F1 intact")
        with self.assertRaises(ValueError):O.prepare(self.r,f1/"autre",self.g,sys.executable)
        self.b.mkdir()
        with self.assertRaises(FileExistsError):self.prepare()
        self.assertEqual(temoin.read_bytes(),b"F1 intact")

    def test_refus_selection_archive_ou_dossier_inattendu_avant_processus(self):
        self.prepare()
        p=self.b/"selection_qualification.json";original=p.read_bytes();p.write_bytes(original+b"\n")
        with patch.object(O,"processus",side_effect=AssertionError("aucun processus")),self.assertRaises(ValueError):O.execute(self.b)
        p.write_bytes(original)
        dossier=self.b/"journaux/inconnu";dossier.mkdir()
        with self.assertRaises(FileExistsError):O.execute(self.b)
        dossier.rmdir()
        p=self.b/"controle_orchestration/queue_losanges.json";p.write_bytes(p.read_bytes()+b"\n")
        with self.assertRaises(ValueError):O.execute(self.b)

    def test_pilote_altere_ou_sources_differentes_refuses_avant_preparation(self):
        g=O.lit(self.g);p=self.r/g["pilote_valide"]["preuve"]
        origin=p.read_bytes();p.write_bytes(origin+b"\n")
        with self.assertRaisesRegex(ValueError,"pilote"):
            self.prepare()
        self.assertFalse(self.b.exists())
        donnees=json.loads(origin);donnees["sources_et_controles_inchanges"]=False
        p.write_bytes(O.octets(donnees));g["pilote_valide"]["sha256"]=O.sha(p)
        self.g.write_bytes(O.octets(g))
        with self.assertRaisesRegex(ValueError,"pilote"):
            self.prepare()
        self.assertFalse(self.b.exists())


if __name__=="__main__":unittest.main(verbosity=2)
