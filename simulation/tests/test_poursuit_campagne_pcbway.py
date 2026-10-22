"""Ordonnancement et reprise testes avec des workers factices : aucun Run."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SIM))
import poursuit_campagne_pcbway as P


class ProcessusFactice:
    def __init__(self, poll=None, pid=123456):
        self.pid = pid
        self._poll = poll or (lambda:None)
        self.terminate = Mock()
        self.kill = Mock()
        self.close = Mock()

    def poll(self):
        return self._poll()


class EcritureStatut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mwt_statut_atomique_tests_')
        self.statut = Path(self.tmp.name).resolve()/'pipeline_pcbway_statut.json'
        self.statut.write_text('{"version":0}',encoding='utf-8')
        self.temps,self.pauses,self.appels = [0.],[],[]

    def tearDown(self):
        self.tmp.cleanup()

    def attend(self,duree):
        self.pauses.append(duree)
        self.temps[0] += duree

    @staticmethod
    def erreur_windows():
        exc = PermissionError(13,'lecture Windows sans FILE_SHARE_DELETE')
        exc.winerror = 5
        return exc

    def test_verrou_transitoire_garde_json_lisible_puis_remplace(self):
        nouveau = {'version':1,'etat':'terminé','liste':[1,2,3]}
        def remplace(source,cible):
            self.appels.append(1)
            # Les lectures ne voient jamais un JSON tronque, ancien ou nouveau.
            self.assertEqual(json.loads(cible.read_text(encoding='utf-8')),{'version':0})
            self.assertEqual(json.loads(source.read_text(encoding='utf-8')),nouveau)
            if len(self.appels) < 3:
                raise self.erreur_windows()
            source.replace(cible)
        P.ecrit_statut_atomique(self.statut,nouveau,remplacer=remplace,
            attendre=self.attend,horloge=lambda:self.temps[0])
        self.assertEqual(len(self.appels),3)
        self.assertEqual(self.pauses,[.05,.05])
        self.assertEqual(json.loads(self.statut.read_text(encoding='utf-8')),nouveau)
        self.assertFalse(self.statut.with_name(self.statut.name+'.tmp').exists())

    def test_verrou_permanent_propage_erreur_et_preserve_les_deux_json(self):
        nouveau = {'version':1,'etat':'en cours'}
        def remplace(source,cible):
            self.appels.append(1)
            raise self.erreur_windows()
        with self.assertRaises(PermissionError) as erreur:
            P.ecrit_statut_atomique(self.statut,nouveau,remplacer=remplace,
                attendre=self.attend,horloge=lambda:self.temps[0])
        self.assertLessEqual(len(self.appels),41)
        self.assertAlmostEqual(sum(self.pauses),2.,places=10)
        self.assertEqual(json.loads(self.statut.read_text(encoding='utf-8')),{'version':0})
        tmp = self.statut.with_name(self.statut.name+'.tmp')
        self.assertEqual(json.loads(tmp.read_text(encoding='utf-8')),nouveau)
        self.assertIn(str(tmp),' '.join(erreur.exception.__notes__))

    def test_autre_erreur_pas_masquee_ni_reessayee(self):
        remplace = Mock(side_effect=FileNotFoundError('incident different'))
        with self.assertRaises(FileNotFoundError):
            P.ecrit_statut_atomique(self.statut,{'version':1},remplacer=remplace,
                attendre=self.attend,horloge=lambda:self.temps[0])
        remplace.assert_called_once()
        self.assertFalse(self.pauses)

    def test_trace_pipeline_utilise_le_remplacement_resilient(self):
        pipeline = P.Pipeline(base=self.statut.parent,versions={})
        original = Path.replace
        nombre = [0]
        def remplace(source,cible):
            nombre[0] += 1
            if nombre[0] < 3:
                raise self.erreur_windows()
            return original(source,cible)
        with patch.object(Path,'replace',remplace),patch.object(P.time,'sleep'):
            pipeline.trace('controle_transitoire')
        statut = json.loads(self.statut.read_text(encoding='utf-8'))
        self.assertEqual(statut['schema'],'poursuite_pcbway_v1')
        self.assertEqual(nombre[0],3)
        traces = self.statut.parent/'journaux'/'pipeline_trace.jsonl'
        self.assertEqual(len(traces.read_text(encoding='utf-8').splitlines()),1)


class Poursuite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mwt_pipeline_tests_')
        self.base = Path(self.tmp.name).resolve()
        self.sources = P.F._sources()
        self.f = np.linspace(1e9,6.3e9,213)
        self.s = np.full(213,.2+.1j)
        self.jobs = {t.cle:t for v in P.plan_deux_voies() for t in v}
        self.patcher = patch.object(P.Q,'charge_calcul',side_effect=self.charge)
        self.charge_mock = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def ecrit(self,p,obj):
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(obj),encoding='utf-8')

    def seed(self,t,etat='calcul_en_cours',ferme=False):
        p = t.dossier(self.base)
        mnt = asdict(P.Q.montage_campagne(t.niveau,t.duree_ns))
        dt = 1e-12
        n = int(np.ceil(t.duree_ns*1e-9/dt))+1
        m = dict(etat=etat,antenne=t.antenne,montage=mnt,environnement={},
            sources_sha256=self.sources,debut_utc=datetime.now(timezone.utc).isoformat(),
            execution=dict(dt_s=dt,n_pas=n,fin_energie_active=False,
                           duree_demandee_s=t.duree_ns*1e-9),
            sondes={nom:dict(echantillons=n+1,dt_effectif_s=dt,
                     debut_s=d*dt,fin_s=(n+d)*dt)
                    for nom,d in [('port_ut_1',0),('port_it_1',.5)]})
        self.ecrit(p/'simulation_manifest.json',m)
        if ferme:
            self.ecrit(p/'qualification_entree.json',dict(antenne=t.antenne,niveau=t.niveau,montage=mnt))
            self.ecrit(p/'s11_indicateurs.json',P.Q.indicateurs(self.f,self.s))
        return m

    def charge(self,dossier,exiger_courant=False):
        self.assertTrue(exiger_courant)
        p = Path(dossier)
        return (self.f,self.s,
            json.loads((p/'simulation_manifest.json').read_text(encoding='utf-8')),
            json.loads((p/'qualification_entree.json').read_text(encoding='utf-8')))

    def record(self,t,pid=123456):
        return dict(pid=pid,executable=sys.executable,cwd=str(t.dossier(self.base)),
            commande='fixture',creation_utc=datetime.now(timezone.utc).isoformat(),
            arguments=[sys.executable,str(SIM/'qualifie_pcbway.py'),
                '--antenne',t.antenne,'--niveau',t.niveau,'--duree-ns',str(t.duree_ns),
                '--fils','10','--base',str(self.base)])

    def pipeline(self,**kw):
        return P.Pipeline(base=self.base,versions={},**kw)

    def test_adopte_sans_lancement_et_attend_trois_preuves(self):
        t = P.Travail('diamant_uwb','fin',12)
        self.seed(t)
        nombre = [0]
        def attend(event,seconds):
            nombre[0] += 1
            # termine seul ne suffit pas; seulement au 2e tour les deux JSON
            # ecrits apres F.lance deviennent lisibles.
            self.seed(t,'termine',ferme=nombre[0] >= 2)
        proc = ProcessusFactice(lambda: 0 if nombre[0] >= 2 else None)
        popen = Mock()
        pipeline = self.pipeline(adopter=True,popen=popen,attend=attend,
            inventaire=lambda:[self.record(t)],observe=lambda record:proc)
        pipeline.assure(t)
        self.assertEqual(nombre[0],2)
        popen.assert_not_called()
        proc.close.assert_called_once()
        proc.terminate.assert_not_called()
        proc.kill.assert_not_called()

    def test_preuves_completes_ne_liberent_pas_worker_avant_exit(self):
        t = P.Travail('vivaldi_tomographie','base',8)
        self.seed(t)
        nombre = [0]
        def attend(event,seconds):
            nombre[0] += 1
            self.seed(t,'termine',ferme=True)
        proc = ProcessusFactice(lambda:0 if nombre[0] >= 2 else None)
        pipeline = self.pipeline(adopter=True,attend=attend,
            inventaire=lambda:[self.record(t)],observe=lambda r:proc,popen=Mock())
        pipeline.assure(t)
        self.assertEqual(nombre[0],2)

    def test_cache_valide_reutilise_sans_processus(self):
        t = P.Travail('diamant_uwb','base',8)
        self.seed(t,'termine',ferme=True)
        popen = Mock()
        pipeline = self.pipeline(popen=popen)
        pipeline.assure(t)
        popen.assert_not_called()
        self.charge_mock.assert_called_once_with(t.dossier(self.base),exiger_courant=True)
        self.ecrit(t.dossier(self.base)/'s11_indicateurs.json',{})
        with self.assertRaisesRegex(ValueError,'indicateurs'):
            pipeline.assure(t)

    def test_indicateurs_tolerent_quantification_touchstone_pas_alteration(self):
        f = np.linspace(1e9,6.3e9,213)
        phase = np.linspace(-2,2,213)
        s = (.25+.06*np.cos(phase))*np.exp(1j*phase)
        avant = P.Q.indicateurs(f,s)
        chemin = self.base/'reference_arrondie.s1p'
        P.F.ecrit_s1p(str(chemin),f,s)
        data = np.loadtxt(chemin,comments=('!','#'))
        relu = data[:,1]+1j*data[:,2]
        apres = P.Q.indicateurs(data[:,0],relu)
        self.assertNotEqual(P.Q.G.json_octets(avant),P.Q.G.json_octets(apres))
        self.assertTrue(P.indicateurs_equivalents(avant,apres))
        self.assertFalse(P.indicateurs_equivalents(avant,P.Q.indicateurs(f,relu*(1+1e-6))))
        self.assertFalse(P.indicateurs_equivalents({'compte':3},{'compte':4}))
        self.assertFalse(P.indicateurs_equivalents({'compte':3},{'compte':3.0}))
        self.assertFalse(P.indicateurs_equivalents({'ok':True},{'ok':1}))
        self.assertFalse(P.indicateurs_equivalents({'segments':[[1.,2.]]},{'segments':[[1.,2.],[3.,4.]]}))
        self.assertFalse(P.indicateurs_equivalents({'x':None},{'x':0.}))
        self.assertFalse(P.indicateurs_equivalents({'x':1.},{'y':1.}))

    def test_adoption_explicite_pid_et_sources_exiges(self):
        t = P.Travail('diamant_uwb','fin',12)
        self.seed(t)
        with self.assertRaisesRegex(FileExistsError,'adopter'):
            self.pipeline(popen=Mock()).assure(t)
        with self.assertRaisesRegex(RuntimeError,'exactement un worker'):
            self.pipeline(adopter=True,popen=Mock(),inventaire=lambda:[]).assure(t)
        m = self.seed(t)
        m['sources_sha256'] = {'faux':'sha'}
        self.ecrit(t.dossier(self.base)/'simulation_manifest.json',m)
        with self.assertRaisesRegex(ValueError,'configuration/sources'):
            self.pipeline(adopter=True,popen=Mock()).assure(t)

    def test_cwd_autre_projet_refuse_et_dossier_partiel_refuse(self):
        t = P.Travail('diamant_uwb_x18','base',8)
        self.seed(t)
        record = self.record(t)
        record['cwd'] = str(self.base/'autre_projet')
        with self.assertRaisesRegex(RuntimeError,'exactement un worker'):
            self.pipeline(adopter=True,inventaire=lambda:[record]).assure(t)
        partiel = P.Travail('diamant_uwb_x18','fin',12)
        self.ecrit(partiel.dossier(self.base)/'fragment.json',{})
        with self.assertRaisesRegex(FileExistsError,'partiel'):
            self.pipeline(adopter=True,popen=Mock()).assure(partiel)

    def test_watchdog_inactivite_et_limite_globale_sans_kill(self):
        for global_timeout in (False,True):
            with self.subTest(global_timeout=global_timeout):
                t = P.Travail('vivaldi_tomographie','base',8)
                self.seed(t)
                temps = [0.]
                proc = ProcessusFactice()
                def attend(event,seconds):
                    temps[0] += seconds
                popen = Mock()
                pipeline = self.pipeline(adopter=True,popen=popen,horloge=lambda:temps[0],
                    attend=attend,inactivite_s=10,limite_s=5 if global_timeout else 100,
                    inventaire=lambda:[self.record(t)],observe=lambda r:proc)
                self.assertFalse(pipeline._voie(1,[t,P.Travail('vivaldi_tomographie','fin',12)]))
                self.assertTrue(pipeline.stop.is_set())
                self.assertIn('globale' if global_timeout else 'progression',pipeline.etat['erreurs'][0])
                popen.assert_not_called()
                proc.terminate.assert_not_called()
                proc.kill.assert_not_called()

    def test_exit_nonzero_refuse_meme_si_preuves_existent(self):
        t = P.Travail('diamant_uwb_x18','base',8)
        def cree(commande,**kw):
            self.seed(t,'termine',ferme=True)
            self.assertFalse(t.dossier(self.base).is_relative_to(Path(kw['stdout'].name).parent))
            return ProcessusFactice(lambda:7)
        with self.assertRaisesRegex(RuntimeError,'code 7'):
            self.pipeline(popen=cree).assure(t)

    def test_worker_echec_stoppe_nouveaux_lancements(self):
        t = P.Travail('diamant_uwb','fin',12)
        self.seed(t,'echec')
        popen = Mock()
        pipeline = self.pipeline(adopter=True,popen=popen)
        self.assertFalse(pipeline._voie(1,[t]))
        with self.assertRaises(P.ArretCoordonne):
            pipeline.assure(P.Travail('diamant_uwb_x18','base',8))
        popen.assert_not_called()

    def test_verrou_os_empeche_double_pipeline_et_reprise_normale(self):
        a,b = self.pipeline(adopter=True),self.pipeline(adopter=True)
        a.acquiert_verrou()
        try:
            with self.assertRaises(FileExistsError):
                b.acquiert_verrou()
        finally:
            a.libere_verrou()
        b.acquiert_verrou()
        b.libere_verrou()

    def test_deux_voies_et_commandes_derivees_comparaison_apres_neuf(self):
        actif,max_actif = [0],[0]
        commands = []
        lock = threading.Lock()
        def cree(commande,**kw):
            if '--antenne' in commande:
                ant = commande[commande.index('--antenne')+1]
                niv = commande[commande.index('--niveau')+1]
                duree = float(commande[commande.index('--duree-ns')+1])
                self.assertEqual(commande[commande.index('--fils')+1],'10')
                t = P.Travail(ant,niv,duree)
            else:
                target = Path(commande[commande.index('--sortie')+1])
                t = P.Travail(target.parent.name,'fin',8,12)
                self.assertTrue((target.parent/'fin_12ns'/'qualification_entree.json').exists())
            self.assertFalse(t.dossier(self.base).exists())
            self.assertTrue(Path(kw['stdout'].name).parent == self.base/'journaux')
            self.assertEqual(kw['cwd'],str(SIM))
            self.seed(t)
            with lock:
                actif[0] += 1
                max_actif[0] = max(max_actif[0],actif[0])
                commands.append((t,commande))
            tours = [0]
            def poll():
                tours[0] += 1
                if tours[0] < 2:
                    return None
                self.seed(t,'termine',ferme=True)
                with lock:
                    actif[0] -= 1
                return 0
            return ProcessusFactice(poll)
        def compare(base):
            self.assertEqual(actif[0],0)
            self.assertEqual(len(commands),9)
            for voie in P.plan_deux_voies():
                for t in voie:
                    self.assertTrue((t.dossier(base)/'s11_indicateurs.json').exists())
            return {'tous_reussis':False}
        pipeline = self.pipeline(popen=cree,intervalle_s=.01)
        with patch.object(P.Q,'comparer',side_effect=compare) as comparer:
            self.assertEqual(pipeline.execute(),2)
            self.assertFalse(pipeline.etat['erreurs'],pipeline.etat['erreurs'])
            comparer.assert_called_once_with(self.base)
        self.assertEqual(max_actif[0],2)
        self.assertEqual(len([t for t,c in commands if t.derive_de_ns]),3)
        self.assertFalse(pipeline.etat['criteres_reussis'])

    def test_delais_non_finis_refuses(self):
        for v in (float('inf'),float('nan'),0,-1):
            with self.assertRaises(ValueError):
                self.pipeline(limite_s=v)


if __name__ == '__main__':
    unittest.main()
