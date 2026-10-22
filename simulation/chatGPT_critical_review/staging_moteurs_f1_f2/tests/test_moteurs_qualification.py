"""Tests logiciels SYNTHETIQUES F1/F2 ; aucun moteur physique F2 ni Run.

Le stub F2 ne change aucune grille : il sert uniquement a exercer le routage,
la provenance et le vrai CalcPort de sondes synthetiques. Ce fichier ne doit
etre execute que par le runner dans sa copie temporaire marquee.
"""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
import fdtd as F
import fenetre_sondes as W
import qualifie_pcbway as Q
import qualification_adaptative as A

TAG = "maillage_controle_v2"
STUB = '''"""STUB LOGICIEL : API F1 et provenance F2 ; aucune physique F2."""
from pathlib import Path
import hashlib
import fdtd as F1
globals().update({n:v for n,v in vars(F1).items() if not n.startswith('__')})
NOM_MOTEUR = 'maillage_controle_v2'
NIVEAUX = {'base':dict(mailles_par_lambda=16,mailles_par_lambda_air=16,maille_min=.15),
           'fin':dict(mailles_par_lambda=24,mailles_par_lambda_air=16,maille_min=.10)}
def _sources():
    resultat = dict(F1._sources())
    resultat['fdtd_maille_controlee.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return resultat
def lance(*args, **kwargs):
    raise AssertionError('STUB F2 : aucun Run autorise')
'''


class Identites(unittest.TestCase):
    def test_absence_seule_est_F1_double_tag_seul_est_F2(self):
        self.assertEqual(Q.identite_moteur({}, {}), Q.MOTEUR_F1)
        self.assertEqual(Q.identite_moteur({'moteur':TAG}, {'moteur':TAG}), TAG)
        cas = [({}, {'moteur':TAG}), ({'moteur':TAG}, {}),
               ({'moteur':None}, {}), ({}, {'moteur':None}),
               ({'moteur':None}, {'moteur':None}),
               ({'moteur':'fdtd'}, {'moteur':'fdtd'}),
               ({'moteur':'inconnu'}, {'moteur':'inconnu'}),
               ({'moteur':TAG}, {'moteur':'inconnu'})]
        for m,q in cas:
            with self.subTest(m=m,q=q), self.assertRaisesRegex(ValueError,'tags moteur'):
                Q.identite_moteur(m,q)

    def test_nom_de_module_arbitraire_jamais_importe(self):
        with patch.object(importlib,'import_module',side_effect=AssertionError('import interdit')) as charge:
            for nom in ('../fdtd', 'os', '__import__', 'autre_moteur'):
                with self.subTest(nom=nom), self.assertRaises(ValueError):
                    Q.module_moteur(nom)
            charge.assert_not_called()


class ArchivesMoteurs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (SIM/'_staging_moteurs_f1_f2.txt').is_file():
            raise RuntimeError('Ces tests exigent la copie TEMP du runner')
        cls.stub_path = SIM/'fdtd_maille_controlee.py'
        if cls.stub_path.exists():
            raise RuntimeError('Le stub ne doit jamais ecraser un moteur existant')
        cls.stub_path.write_text(STUB,encoding='utf8',newline='\n')
        importlib.invalidate_caches()
        cls.F2 = importlib.import_module('fdtd_maille_controlee')
        cls.temp = tempfile.TemporaryDirectory(prefix='mwt_engines_synthetiques_')
        cls.racine = Path(cls.temp.name)
        cls.base = cls.racine/'archives_F1'
        cls.nom = 'diamant_uwb'
        import test_qualification_pcbway as fixtures
        fixtures.ArchivesQualification.cree_archive.__func__(cls,'base',8.)
        fixtures.ArchivesQualification.cree_archive.__func__(cls,'fin',12.)
        base_f1=cls.base
        cls.base=cls.racine/'archives_F2_stub'
        with patch.object(Q,'NIVEAUX',cls.F2.NIVEAUX):
            fixtures.ArchivesQualification.cree_archive.__func__(cls,'base',8.)
            fixtures.ArchivesQualification.cree_archive.__func__(cls,'fin',12.)
        cls.base_f2=cls.base
        cls.base=base_f1

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        sys.modules.pop('fdtd_maille_controlee',None)
        cls.stub_path.unlink()

    def copie(self,profil='base_8ns',F2=True):
        base=self.racine/self._testMethodName
        cible=base/self.nom/profil
        shutil.copytree((self.base_f2 if F2 else self.base)/self.nom/profil,cible)
        if F2:
            shutil.copy2(self.stub_path,cible/'sources/fdtd_maille_controlee.py')
            q=json.loads((cible/'qualification_entree.json').read_text(encoding='utf8'))
            q['moteur']=TAG;W.ecrit_json(cible/'qualification_entree.json',q)
            m=json.loads((cible/'simulation_manifest.json').read_text(encoding='utf8'))
            m['moteur']=TAG;m['sources_sha256']=self.F2._sources()
            self.actualise(cible,m)
        return base,cible

    @staticmethod
    def actualise(cible,m):
        m['fichiers_sha256']={p.relative_to(cible).as_posix():W.sha256(p)
            for p in cible.rglob('*') if p.is_file() and p.name!='simulation_manifest.json'}
        W.ecrit_json(cible/'simulation_manifest.json',m)

    def test_F1_et_F2_source10_integralement_relus(self):
        _,_,m,q=Q.charge_calcul(self.base/self.nom/'base_8ns',exiger_courant=True)
        self.assertEqual(len(m['sources_sha256']),9)
        _,c=self.copie();_,_,m,q=Q.charge_calcul(c,exiger_courant=True)
        self.assertEqual(Q.identite_moteur(m,q),TAG)
        self.assertEqual(len(m['sources_sha256']),10)

    def test_F1_sans_tags_refuse_fichier_F2_meme_non_declare(self):
        _,c=self.copie(F2=False)
        shutil.copy2(self.stub_path,c/'sources/fdtd_maille_controlee.py')
        with self.assertRaisesRegex(ValueError,'source F2 presente'):
            Q.charge_calcul(c)

    def test_F2_source_absente_ou_inventaire_incomplet_refuse(self):
        _,c=self.copie();m=json.loads((c/'simulation_manifest.json').read_text(encoding='utf8'))
        (c/'sources/fdtd_maille_controlee.py').unlink()
        with self.assertRaisesRegex(ValueError,'F2 absente'):
            Q.charge_calcul(c)
        shutil.copy2(self.stub_path,c/'sources/fdtd_maille_controlee.py')
        m['sources_sha256'].pop('materiaux.py')
        self.actualise(c,m)
        with self.assertRaisesRegex(ValueError,'inventaire complet'):
            Q.charge_calcul(c)

    def test_F2_source_tamper_meme_si_archives_SHA_recalcules_refuse(self):
        _,c=self.copie();p=c/'sources/fdtd_maille_controlee.py'
        p.write_bytes(p.read_bytes()+b'\n# modification locale\n')
        m=json.loads((c/'simulation_manifest.json').read_text(encoding='utf8'))
        m['sources_sha256']['fdtd_maille_controlee.py']=W.sha256(p);self.actualise(c,m)
        with self.assertRaisesRegex(ValueError,'sources physiques/moteur'):
            Q.charge_calcul(c,exiger_courant=False)

    def test_catalogue_F2_doit_conserver_les_neuf_originaux(self):
        _,c=self.copie()
        faux=dict(self.F2._sources());faux.pop('materiaux.py')
        with patch.object(self.F2,'_sources',return_value=faux), self.assertRaisesRegex(ValueError,'neuf sources F1'):
            Q.charge_calcul(c)

    def test_F2_ne_peut_etendre_silencieusement_inventaire_a_onze(self):
        _,c=self.copie()
        trop=dict(F._sources());trop['autre/geometrie.py']='0'*64
        with patch.object(F,'_sources',return_value=trop),self.assertRaisesRegex(ValueError,'exactement neuf'):
            Q.charge_calcul(c)

    def test_montage_F2_utilise_son_catalogue_distinct(self):
        ancien=Q.montage_campagne('base',8.)
        nouveau=Q.montage_campagne('base',8.,moteur=TAG)
        self.assertEqual(ancien.maillage.mailles_par_lambda,10)
        self.assertEqual(nouveau.maillage.mailles_par_lambda,16)
        self.assertEqual(nouveau.maillage.maille_min,.15)
        with self.assertRaisesRegex(ValueError,'niveau/duree'):
            Q.montage_campagne('n30',8.,moteur=TAG)

    def test_catalogue_F2_absent_ou_nonmonotone_refuse(self):
        for catalogue in (None,{}, {'base':self.F2.NIVEAUX['base']},
                {'base':self.F2.NIVEAUX['fin'],'fin':self.F2.NIVEAUX['base']}):
            with self.subTest(catalogue=catalogue),patch.object(self.F2,'NIVEAUX',catalogue),self.assertRaises(ValueError):
                Q.montage_campagne('base',8.,moteur=TAG)

    def test_valide_campagne_F2_refuse_montage_F1_cache_sous_tag(self):
        _,c=self.copie();_,_,m,q=Q.charge_calcul(c,exiger_courant=True)
        Q.valide_campagne(m,q,self.nom,'base',8.)
        m['montage']=asdict(Q.montage_campagne('base',8.))
        q['montage']=deepcopy(m['montage'])
        with self.assertRaisesRegex(ValueError,'configuration differente'):
            Q.valide_campagne(m,q,self.nom,'base',8.)

    def test_main_transmet_moteur_explicite_sans_executer(self):
        with patch.object(Q,'calcule') as calcul:
            Q.main(['--antenne',self.nom,'--moteur',TAG,'--cout'])
        calcul.assert_called_once_with(self.nom,'base',8.,10,True,Q.BASE,moteur=TAG)

    def test_cache_F1_refuse_F2_et_inverse_avant_tout_lance(self):
        base,c=self.copie()
        with patch.object(F,'lance',side_effect=AssertionError('Run interdit')) as a, \
             patch.object(self.F2,'lance',side_effect=AssertionError('Run interdit')) as b:
            # Collision volontaire de Montage : seule l'identite du moteur
            # doit empecher la reutilisation, pas une difference numerique.
            with patch.dict(Q.NIVEAUX,{'base':dict(self.F2.NIVEAUX['base'])}):
                archive=json.loads((c/'qualification_entree.json').read_text(encoding='utf8'))
                self.assertEqual(Q.signature(Q.G.carte_antenne(self.nom),Q.montage_campagne('base',8.)),archive['signature_physique'])
                with self.assertRaisesRegex(FileExistsError,'moteur different'):
                    Q.calcule(self.nom,'base',8.,base=base)
            with patch.dict(self.F2.NIVEAUX,{'base':dict(Q.NIVEAUX['base'])}):
                archive=json.loads((self.base/self.nom/'base_8ns/qualification_entree.json').read_text(encoding='utf8'))
                self.assertEqual(Q.signature(Q.G.carte_antenne(self.nom),Q.montage_campagne('base',8.,moteur=TAG)),archive['signature_physique'])
                with self.assertRaisesRegex(FileExistsError,'moteur different'):
                    Q.calcule(self.nom,'base',8.,base=self.base,moteur=TAG)
            a.assert_not_called();b.assert_not_called()

    def test_nouvel_appel_F2_route_lance_et_qualification_tag(self):
        base=self.racine/self._testMethodName
        def sans_run(montage,module,**kw):
            d=Path(kw['dossier']);d.mkdir(parents=True)
            W.ecrit_json(d/'simulation_manifest.json',{'moteur':TAG,'synthetique_unittest':True})
            return np.linspace(1e9,6.3e9,213),np.full(213,.2+0j)
        with patch.object(self.F2,'lance',side_effect=sans_run) as lance,redirect_stdout(io.StringIO()):
            Q.calcule(self.nom,'base',8.,base=base,moteur=TAG)
        self.assertEqual(lance.call_count,1)
        q=json.loads((base/self.nom/'base_8ns/qualification_entree.json').read_text(encoding='utf8'))
        self.assertEqual(q['moteur'],TAG)
        self.assertEqual(q['montage']['maillage']['mailles_par_lambda'],16)

    def test_cout_F2_route_estime_sans_lance(self):
        with patch.object(self.F2,'estime_cout',return_value=(1,2,3.)) as cout, \
             patch.object(self.F2,'lance',side_effect=AssertionError('Run interdit')) as lance, \
             redirect_stdout(io.StringIO()):
            Q.calcule(self.nom,'base',8.,cout=True,moteur=TAG)
        cout.assert_called_once();lance.assert_not_called()

    def test_W_prefixe_F2_vrai_CalcPort_preserve_sources_et_tag(self):
        _,c=self.copie('fin_12ns')
        out=c.parent/'base_prefixe8'
        m=W.derive(c,out,8.)
        q=json.loads((out/'qualification_entree.json').read_text(encoding='utf8'))
        params=json.loads((out/'parametres_extraction.json').read_text(encoding='utf8'))
        self.assertEqual(m['moteur'],TAG);self.assertEqual(q['moteur'],TAG)
        self.assertEqual(params['moteur'],TAG)
        self.assertEqual(m['sources_sha256'],self.F2._sources())
        self.assertEqual((c/'maillage.npz').read_bytes(),(out/'maillage.npz').read_bytes())
        Q.charge_calcul(out,exiger_courant=True)
        relu=json.loads((out/'relecture_calcport.json').read_text(encoding='utf8'))
        self.assertTrue(relu['maillage_archive_identique'])
        self.assertTrue(relu['materiaux_archives_identiques'])

    def test_W_refuse_tags_avant_toute_ecriture(self):
        _,c=self.copie('fin_12ns')
        q=json.loads((c/'qualification_entree.json').read_text(encoding='utf8'));q.pop('moteur')
        W.ecrit_json(c/'qualification_entree.json',q)
        out=c.parent/'refus'
        with self.assertRaisesRegex(ValueError,'tags moteur'):
            W.derive(c,out,8.)
        self.assertFalse(out.exists())


class CampagnesMoteurs(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='mwt_campagne_engines_synthetique_')
        self.base=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def exerce(self,types,adaptee=False,preliminaire_inexact=False,sans_selection=False):
        spec=A.selection_standard()
        if adaptee:
            from test_qualification_adaptative import selection_adaptee
            spec=selection_adaptee()
        if not sans_selection:
            Q.sauve(self.base/A.FICHIER_SELECTION,dict(schema=A.SCHEMA_SELECTION,antennes={n:spec for n in Q.ANTENNES}))
        for n in Q.ANTENNES:
            for p in A._profils_selection(spec):
                d=self.base/n/p;d.mkdir(parents=True)
                x=np.array([0.,1.,2.])
                if preliminaire_inexact and p in ('fin_12ns','fin_16ns'):
                    x[1]=np.nextafter(x[1],np.inf)
                np.savez_compressed(d/'maillage.npz',x=x,y=np.array([0.,1.]),z=np.array([0.,1.]))
        def charge(p,exiger_courant=False):
            m=dict(maillage={'resume':'identique'},execution={'dt_s':1e-12},sources_sha256={'fixture':'empreinte'},environnement={'fixture':True})
            q=dict(geometrie_sha256='g',simulation_contract={})
            if types[p.parent.name]==TAG:m['moteur']=TAG;q['moteur']=TAG
            return np.linspace(1e9,6.3e9,213),np.full(213,.2+0j),m,q
        with ExitStack() as stack:
            original=Q.module_moteur
            fixture_catalogue={'base':dict(mailles_par_lambda=16,mailles_par_lambda_air=16,maille_min=.15),
                               'fin':dict(mailles_par_lambda=24,mailles_par_lambda_air=16,maille_min=.1)}
            stack.enter_context(patch.object(Q,'module_moteur',side_effect=lambda n=None:
                SimpleNamespace(NIVEAUX=fixture_catalogue) if n==TAG else original(n)))
            stack.enter_context(patch.object(Q,'charge_calcul',side_effect=charge))
            stack.enter_context(patch.object(Q,'valide_campagne'))
            stack.enter_context(patch.object(Q,'extinction',return_value={}))
            reference=stack.enter_context(patch.object(A,'_reference'))
            figures=stack.enter_context(patch.object(Q,'figures',side_effect=lambda nom,courbes,sortie:
                (sortie/'comparaison_convergence.png').write_bytes(b'PNG SYNTHETIQUE TEST')))
            with redirect_stdout(io.StringIO()):
                try:return (Q.comparer(self.base) if sans_selection else A.comparer(self.base)),reference.call_count
                except ValueError:
                    self.assertEqual(reference.call_count,0)
                    figures.assert_not_called()
                    raise

    def test_trois_F1_bilan_reste_sans_tag(self):
        r,c=self.exerce({n:Q.MOTEUR_F1 for n in Q.ANTENNES})
        self.assertTrue(r['tous_reussis']);self.assertNotIn('moteur',r);self.assertEqual(c,3)

    def test_trois_F2_bilan_tag_unique(self):
        r,c=self.exerce({n:TAG for n in Q.ANTENNES})
        self.assertTrue(r['tous_reussis']);self.assertEqual(r['moteur'],TAG);self.assertEqual(c,3)

    def test_mix_entre_antennes_refuse_avant_sorties(self):
        types={n:Q.MOTEUR_F1 for n in Q.ANTENNES};types[Q.ANTENNES[-1]]=TAG
        with self.assertRaisesRegex(ValueError,'melange de moteurs'):
            self.exerce(types)
        self.assertFalse((self.base/'qualification_globale.json').exists())

    def test_Q_sans_selection_mix_refuse_avant_sorties(self):
        types={n:Q.MOTEUR_F1 for n in Q.ANTENNES};types[Q.ANTENNES[-1]]=TAG
        with self.assertRaisesRegex(ValueError,'melange de moteurs'):
            self.exerce(types,sans_selection=True)
        self.assertFalse((self.base/'qualification_globale.json').exists())

    def test_Q_sans_selection_axes_temporels_reels_controlés(self):
        with self.assertRaisesRegex(ValueError,'bit a bit'):
            self.exerce({n:Q.MOTEUR_F1 for n in Q.ANTENNES},sans_selection=True,preliminaire_inexact=True)

    def test_Q_sans_selection_trois_F2_bilan_tag_unique(self):
        r,_=self.exerce({n:TAG for n in Q.ANTENNES},sans_selection=True)
        self.assertTrue(r['tous_reussis']);self.assertEqual(r['moteur'],TAG)

    def test_paire_temporelle_preliminaire_axes_differents_refusee(self):
        with self.assertRaisesRegex(ValueError,'bit a bit'):
            self.exerce({n:Q.MOTEUR_F1 for n in Q.ANTENNES},adaptee=True,preliminaire_inexact=True)

    def test_axes_zeros_signes_distincts_et_dtype_refuses(self):
        a,b=self.base/'a',self.base/'b';a.mkdir();b.mkdir()
        chemins={'a':a,'b':b}
        for bad in (np.array([-0.,1.]),np.array([0.,1.],dtype=np.float32)):
            with self.subTest(dtype=str(bad.dtype)):
                np.savez(a/'maillage.npz',x=np.array([0.,1.]),y=np.array([0.,1.]),z=np.array([0.,1.]))
                np.savez(b/'maillage.npz',x=bad,y=np.array([0.,1.]),z=np.array([0.,1.]))
                with self.assertRaisesRegex(ValueError,'bit a bit'):
                    A._grilles_temporelles(['a','b'],chemins)


if __name__=='__main__':
    unittest.main()
