"""Contrats temporels F2 avec faux Run local ; aucun solveur natif importe."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
ICI=Path(__file__).resolve().parent
SIM=ICI.parents[1]
sys.path.insert(0,str(SIM))
from banc import Acquisition,Montage
spec=importlib.util.spec_from_file_location('F2_garde_locale',ICI/'modifies/fdtd_maille_controlee.py')
F=importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
DT=1e-13
N=10


class Grille:
    def GetLines(self,axe):return np.array([0.,1.,2.])


class CSX:
    def GetGrid(self):return Grille()


class Port:
    def __init__(self):self.appels=0
    def CalcPort(self,*args,**kwargs):
        self.appels+=1
        self.uf_inc=np.ones(2,dtype=complex)
        self.uf_ref=np.array([.2+.1j,.3-.1j])


class FauxRun:
    def __init__(self,cas):self.cas=cas
    def Write2XML(self,chemin):Path(chemin).write_text('<faux_Run_test/>',encoding='utf-8')
    def Run(self,dossier,**kwargs):
        p=Path(dossier)
        stats=np.array([8.,DT,N,DT*N,.01,8000.])
        if self.cas=='stats_iterations':stats[2]=N-1
        if self.cas=='stats_dt':stats[1]=DT*1.001
        if self.cas=='stats_nan':stats[1]=np.nan
        np.savetxt(p/'openEMS_stats.txt',stats,fmt='%.16e')
        for nom,decalage in (('port_ut_1',0.),('port_it_1',.5)):
            nombre=N+1
            if self.cas=='n_moins_1':nombre=N
            if self.cas=='n_moins_3':nombre=N-2
            temps=(np.arange(nombre)+decalage)*DT
            if self.cas=='sonde_dt':temps*=1.001
            if self.cas=='U_origine' and nom=='port_ut_1':temps+=DT
            if self.cas=='I_demi_pas' and nom=='port_it_1':temps-=DT/2
            if self.cas=='increment_interieur':temps[4]+=DT/100
            if self.cas=='indices_hors_tolerance':temps+=2.1e-6*DT
            donnees=np.c_[temps,np.sin(np.arange(nombre))]
            if self.cas=='sonde_nan':donnees[3,1]=np.nan
            if self.cas=='arrondi_texte':
                donnees[2:-1:2,0]+=(2e-6*DT)/4
            np.savetxt(p/nom,donnees,fmt='%.12e')


class GardeSondes(unittest.TestCase):
    def execute(self,cas,accepte=False):
        # mkdir neuf hors profils reels ; pas de suppression recursive.
        dossier=Path(tempfile.mkdtemp(prefix='stub_garde_F2_'))/'calcul_factice'
        port=Port();faux=FauxRun(cas)
        montage=Montage(acquisition=Acquisition(f_min=1e9,f_max=2e9,points=2))
        antenne=types.SimpleNamespace(NOM='antenne_factice_pour_garde')
        def construit(*args,**kwargs):return faux,CSX(),port,str(dossier)
        execution=dict(dt_s=DT,n_pas=N,duree_prevue_s=(N-1)*DT)
        modules={n:types.SimpleNamespace(__version__='stub_sans_solveur') for n in ('openEMS','CSXCAD','scipy')}
        with patch.object(F,'construit',construit),patch.object(F,'_durations',return_value=execution),\
             patch.object(F,'resume_maillage',return_value={'cellules':8}),\
             patch.object(F,'politique_maillage',return_value={'type':'fixture_garde_sondes'}),\
             patch.object(F,'_sources',return_value={}),\
             patch.object(F,'_proprietes_matiere',return_value=({},[],[],[])),\
             patch.dict(sys.modules,modules):
            if accepte:
                F.lance(montage,antenne,dossier=str(dossier),dt_impose_s=DT,calibration_info={})
            else:
                with self.assertRaises(RuntimeError):
                    F.lance(montage,antenne,dossier=str(dossier),dt_impose_s=DT,calibration_info={})
        m=json.loads((dossier/'simulation_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(m['moteur'],'maillage_controle_v2')
        self.assertEqual(m['etat'],'termine' if accepte else 'echec')
        self.assertEqual(port.appels,1 if accepte else 0)
        self.assertEqual((dossier/'s11.s1p').exists(),accepte)

    def test_bon_NrTS_plus_un_et_demi_pas(self):self.execute('bon',accepte=True)
    def test_arrondi_textuel_admissible(self):self.execute('arrondi_texte',accepte=True)
    def test_sondes_N_moins_un_et_N_moins_trois_refusees(self):
        for cas in ('n_moins_1','n_moins_3'):
            with self.subTest(cas=cas):self.execute(cas)
    def test_stats_iterations_incompletes_refusees(self):self.execute('stats_iterations')
    def test_dt_stats_et_sondes_refuses(self):
        for cas in ('stats_dt','sonde_dt'):
            with self.subTest(cas=cas):self.execute(cas)
    def test_non_finis_stats_et_sondes_refuses(self):
        for cas in ('stats_nan','sonde_nan'):
            with self.subTest(cas=cas):self.execute(cas)
    def test_origines_U_et_I_refusees(self):
        for cas in ('U_origine','I_demi_pas'):
            with self.subTest(cas=cas):self.execute(cas)
    def test_increment_interieur_irregulier_refuse(self):self.execute('increment_interieur')
    def test_tolerance_indices_Q_a_dt_un_dixieme_ps(self):self.execute('indices_hors_tolerance')


if __name__=='__main__':unittest.main(verbosity=2)
