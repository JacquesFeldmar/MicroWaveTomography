"""Poursuit les calculs PCBWay sur exactement deux voies de sous-processus.

Ne livre aucun dossier de fabrication et ne prononce aucun avis de commande.
Les workers deja actifs ne sont jamais dupliques ni tues. Leur adoption exige
--adopter-en-cours. Journaux, verrou et statut restent hors des calculs.

  python -B -X utf8 poursuit_campagne_pcbway.py --adopter-en-cours
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
import numpy as np

import fdtd as F
import qualifie_pcbway as Q

RACINE = Path(__file__).resolve().parent


def ecrit_statut_atomique(destination,etat,*,remplacer=None,attendre=None,
                          horloge=None,delai_max_s=2.,pause_s=.05):
    """Publie un JSON complet malgre un verrou de lecture Windows bref.

    Certains lecteurs Windows ouvrent le statut sans FILE_SHARE_DELETE et
    refusent momentanement os.replace. On garde le temporaire complet et
    retente au plus deux secondes, sans supprimer la destination. Une erreur
    permanente reste une erreur; son temporaire est conserve pour diagnostic.
    Les fonctions injectables permettent de tester sans attendre reellement.
    """
    if not all(math.isfinite(v) and v > 0 for v in (delai_max_s,pause_s)):
        raise ValueError('delai et pause de remplacement doivent etre positifs et finis')
    destination = Path(destination)
    temporaire = destination.with_name(destination.name+'.tmp')
    temporaire.write_text(json.dumps(etat,ensure_ascii=False,indent=2,allow_nan=False),
                           encoding='utf-8')
    remplacer = remplacer or (lambda source,cible:source.replace(cible))
    attendre = attendre or time.sleep
    horloge = horloge or time.monotonic
    expiration = horloge()+delai_max_s
    # Borne en nombre aussi : un faux clock immobile ne cree pas de boucle.
    maximum = int(math.ceil(delai_max_s/pause_s))+1
    for tentative in range(maximum):
        try:
            remplacer(temporaire,destination)
            return
        except PermissionError as exc:
            if os.name != 'nt' and getattr(exc,'winerror',None) not in (5,32,33):
                raise
            restant = expiration-horloge()
            if restant <= 0 or tentative == maximum-1:
                exc.add_note('statut non publie; JSON temporaire conserve : '+str(temporaire))
                raise
            attendre(min(pause_s,restant))


def indicateurs_equivalents(stockes,recalcules):
    """Structure/classifications exactes, nombres reels avec arrondi S1P.

    Q.calcule evalue les indicateurs avant l'ecriture du Touchstone a douze
    decimales de mantisse. Leur relecture fait varier les derniers chiffres
    des dB/moyennes. La tolerance ne s'applique jamais aux comptes, booleens,
    nombres de segments ou cles : une classification differente est refusee.
    """
    if isinstance(stockes,dict) or isinstance(recalcules,dict):
        return (isinstance(stockes,dict) and isinstance(recalcules,dict) and
            stockes.keys() == recalcules.keys() and
            all(indicateurs_equivalents(stockes[k],recalcules[k]) for k in stockes))
    # Les tuples Python des bornes sont des listes dans le JSON sauvegarde.
    if isinstance(stockes,(list,tuple)) or isinstance(recalcules,(list,tuple)):
        return (isinstance(stockes,(list,tuple)) and isinstance(recalcules,(list,tuple)) and
            len(stockes) == len(recalcules) and
            all(indicateurs_equivalents(a,b) for a,b in zip(stockes,recalcules)))
    if stockes is None or recalcules is None:
        return stockes is None and recalcules is None
    if isinstance(stockes,(bool,np.bool_)) or isinstance(recalcules,(bool,np.bool_)):
        return (isinstance(stockes,(bool,np.bool_)) and
                isinstance(recalcules,(bool,np.bool_)) and bool(stockes) == bool(recalcules))
    if isinstance(stockes,(int,np.integer)) or isinstance(recalcules,(int,np.integer)):
        return (isinstance(stockes,(int,np.integer)) and
                isinstance(recalcules,(int,np.integer)) and int(stockes) == int(recalcules))
    if isinstance(stockes,(float,np.floating)) or isinstance(recalcules,(float,np.floating)):
        return (isinstance(stockes,(float,np.floating)) and
                isinstance(recalcules,(float,np.floating)) and
                math.isfinite(stockes) and math.isfinite(recalcules) and
                math.isclose(stockes,recalcules,rel_tol=2e-11,abs_tol=2e-12))
    return type(stockes) is type(recalcules) and stockes == recalcules


class ArretCoordonne(RuntimeError):
    """Arret des nouveaux lancements; les workers existants restent actifs."""


@dataclass(frozen=True)
class Travail:
    antenne: str
    niveau: str
    duree_ns: float
    derive_de_ns: float | None = None

    @property
    def cle(self):
        return f'{self.antenne}/{self.niveau}_{self.duree_ns:g}ns'

    def dossier(self, base):
        return Path(base)/self.cle


def plan_deux_voies():
    def antenne(nom):
        return (Travail(nom,'base',8), Travail(nom,'fin',12), Travail(nom,'fin',8,12))
    return (antenne('diamant_uwb')+antenne('diamant_uwb_x18'),
            antenne('vivaldi_tomographie'))


def versions_courantes():
    import scipy
    import openEMS
    import CSXCAD
    return dict(python=platform.python_version(), numpy=np.__version__,
        scipy=scipy.__version__, openems=openEMS.__version__, csxcad=CSXCAD.__version__)


def pid_actif(pid):
    """Lecture seule : ne jamais appeler os.kill(pid,0) sous Windows."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        h = kernel.OpenProcess(0x1000,False,pid)  # QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() != 87  # inconnu/acces refuse = prudent
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(h,ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(h)
    try:
        os.kill(pid,0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def arguments_windows(commande):
    if os.name != 'nt':
        return shlex.split(commande)
    from ctypes import wintypes
    shell = ctypes.WinDLL('shell32',use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    nombre = ctypes.c_int()
    pointeur = shell.CommandLineToArgvW(commande,ctypes.byref(nombre))
    if not pointeur:
        raise OSError('CommandLineToArgvW a echoue')
    try:
        return [pointeur[i] for i in range(nombre.value)]
    finally:
        kernel.LocalFree(pointeur)


def inventaire_workers():
    """Inventaire en lecture seule, avec repertoire courant et date creation."""
    import psutil
    data = []
    for processus in psutil.process_iter(['pid','exe','cmdline','create_time','cwd']):
        try:
            i = processus.info
            if not any(Path(a).name == 'qualifie_pcbway.py' for a in (i['cmdline'] or [])):
                continue
            data.append(dict(pid=i['pid'],executable=i['exe'],arguments=i['cmdline'],
                commande=subprocess.list2cmdline(i['cmdline']),cwd=i['cwd'],
                creation_utc=datetime.fromtimestamp(i['create_time'],timezone.utc).isoformat()))
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            continue
    return data


class ProcessusAdopte:
    """Handle Windows de lecture garde jusqu'a la sortie du meme processus."""
    def __init__(self, record):
        from ctypes import wintypes
        self.pid, self.record = record['pid'],record
        self.kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetExitCodeProcess.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.OpenProcess(0x1000,False,self.pid)
        if not self.handle:
            raise OSError('impossible d observer le PID adopte '+str(self.pid))
        # Controle de creation sur le HANDLE, pas seulement le PID inventorie.
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
        naissance,fin,noyau,user = (wintypes.FILETIME() for _ in range(4))
        if not self.kernel.GetProcessTimes(self.handle,*map(ctypes.byref,(naissance,fin,noyau,user))):
            self.close()
            raise OSError('lecture de creation du PID adopte impossible')
        ticks = naissance.dwHighDateTime*2**32+naissance.dwLowDateTime
        creation_s = (ticks-116444736000000000)/1e7
        attendu_s = datetime.fromisoformat(record['creation_utc']).timestamp()
        if abs(creation_s-attendu_s) > .002:
            self.close()
            raise RuntimeError('PID recycle entre inventaire et observation')

    def poll(self):
        from ctypes import wintypes
        code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle,ctypes.byref(code)):
            raise OSError('lecture du statut du processus adopte impossible')
        return None if code.value == 259 else int(code.value)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class Pipeline:
    def __init__(self, base=Q.BASE, adopter=False, fils=10, inactivite_s=600,
                 limite_s=21600, intervalle_s=5, *, popen=None, horloge=None,
                 attend=None, versions=None, inventaire=None, observe=None):
        if (fils < 1 or not all(np.isfinite(x) and x > 0
                for x in (inactivite_s,limite_s,intervalle_s))):
            raise ValueError('fils et delais doivent etre positifs')
        self.base = Path(base).resolve()
        self.adopter, self.fils = adopter, fils
        self.inactivite_s, self.limite_s, self.intervalle_s = inactivite_s, limite_s, intervalle_s
        self.popen = popen or subprocess.Popen
        self.horloge = horloge or time.monotonic
        self.attend = attend or (lambda event,seconds: event.wait(seconds))
        self.versions = versions_courantes() if versions is None else versions
        self.inventaire = inventaire or inventaire_workers
        self.observe = observe or ProcessusAdopte
        self.sources = F._sources()
        self.scripts = {p.name:F._sha256(p) for p in (
            Path(__file__),RACINE/'qualifie_pcbway.py',RACINE/'fenetre_sondes.py',
            RACINE/'export_gerber.py',RACINE/'donnees.py',RACINE/'traitement.py')}
        self.stop = threading.Event()
        self.etat_lock = threading.RLock()
        self.lancement_lock = threading.Lock()
        self.debut = self.horloge()
        self.jeton = uuid.uuid4().hex
        self.verrou = self.base/'pipeline_pcbway.lock'
        self.verrou_acquis = False
        self.verrou_stream = None
        self.etat = dict(schema='poursuite_pcbway_v1', execution=self.jeton,
            pid=os.getpid(), etat='initialise', debut_utc=self.utc(),
            perimetre='calculs et comparaison uniquement; aucune livraison ni avis de commande',
            adopter_en_cours=adopter, fils_par_worker=fils, voies=2,
            inactivite_max_s=inactivite_s, duree_globale_max_s=limite_s,
            sources_physiques_sha256=self.sources, travaux={}, erreurs=[])
        self.etat['scripts_orchestration_sha256'] = self.scripts

    @staticmethod
    def utc():
        return datetime.now(timezone.utc).isoformat()

    def trace(self, evenement, travail=None, **details):
        with self.etat_lock:
            self.base.mkdir(parents=True,exist_ok=True)
            journaux = self.base/'journaux'
            journaux.mkdir(exist_ok=True)
            ligne = dict(utc=self.utc(),evenement=evenement,**details)
            if travail is not None:
                ligne['travail'] = travail.cle
                self.etat['travaux'][travail.cle] = dict(
                    self.etat['travaux'].get(travail.cle,{}),
                    etat=evenement,derniere_maj_utc=ligne['utc'],**details)
            self.etat['derniere_maj_utc'] = ligne['utc']
            self.etat['temps_ecoule_s'] = self.horloge()-self.debut
            with (journaux/'pipeline_trace.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(ligne,ensure_ascii=False,allow_nan=False)+'\n')
            ecrit_statut_atomique(self.base/'pipeline_pcbway_statut.json',self.etat)

    def acquiert_verrou(self):
        self.base.mkdir(parents=True,exist_ok=True)
        stream = self.verrou.open('a+b')
        try:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            stream.seek(0)
            texte = stream.read().decode('utf-8')
            ancien = json.loads(texte) if texte else {}
            if ancien and ancien.get('etat') != 'libere' and not self.adopter:
                raise FileExistsError('verrou abandonne : reprise explicite --adopter-en-cours requise')
            stream.seek(0)
            stream.truncate()
            stream.write(json.dumps(dict(pid=os.getpid(),jeton=self.jeton,
                etat='actif',debut_utc=self.utc())).encode('utf-8'))
            stream.flush()
            self.verrou_stream,self.verrou_acquis = stream,True
        except (OSError,ValueError):
            stream.close()
            raise FileExistsError('verrou exclusif de pipeline indisponible : '+str(self.verrou))

    def libere_verrou(self):
        if self.verrou_stream is not None:
            s = self.verrou_stream
            s.seek(0)
            s.truncate()
            s.write(json.dumps(dict(pid=os.getpid(),jeton=self.jeton,
                etat='libere',fin_utc=self.utc())).encode('utf-8'))
            s.flush()
            if os.name == 'nt':
                import msvcrt
                s.seek(0)
                msvcrt.locking(s.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(s.fileno(),fcntl.LOCK_UN)
            s.close()
            self.verrou_stream = None
        self.verrou_acquis = False

    def _verifie_sources(self):
        if F._sources() != self.sources:
            raise ValueError('sources physiques ou moteur modifies pendant le pipeline')
        if any(F._sha256(RACINE/nom) != sha for nom,sha in self.scripts.items()):
            raise ValueError('scripts de campagne modifies pendant le pipeline')

    def _trouve_adopte(self, travail, m):
        correspondants = []
        for record in self.inventaire():
            args = record.get('arguments',[])
            indices = [i for i,a in enumerate(args) if Path(a).name == 'qualifie_pcbway.py']
            if len(indices) != 1 or Path(record['executable']).resolve() != Path(sys.executable).resolve():
                continue
            options = args[indices[0]+1:]
            def option(nom,defaut=None):
                return options[options.index(nom)+1] if nom in options else defaut
            try:
                script = Path(args[indices[0]])
                cwd = Path(record.get('cwd','')).resolve()
                if script.is_absolute():
                    script_bon = script.resolve() == RACINE/'qualifie_pcbway.py'
                else:
                    # Les deux workers initiaux ont ete lances du workspace
                    # avec simulation/qualifie_pcbway.py et chdir maintenant
                    # dans leur calcul. Le CWD effectif doit nous appartenir.
                    script_bon = script in (Path('simulation')/'qualifie_pcbway.py',Path('qualifie_pcbway.py'))
                base_arg = option('--base')
                bon = (option('--antenne') == travail.antenne and
                    option('--niveau','base') == travail.niveau and
                    float(option('--duree-ns',8)) == travail.duree_ns and
                    int(option('--fils',10)) == self.fils and
                    (base_arg is None or Path(base_arg).is_absolute()) and
                    Path(base_arg or Q.BASE).resolve() == self.base and script_bon and
                    cwd in (RACINE.parent,RACINE,travail.dossier(self.base)))
            except (ValueError,IndexError):
                bon = False
            if not bon:
                continue
            creation = datetime.fromisoformat(record['creation_utc'].replace('Z','+00:00'))
            if m and m.get('debut_utc'):
                debut = datetime.fromisoformat(m['debut_utc'].replace('Z','+00:00'))
                if not -2 <= (debut-creation).total_seconds() <= 600:
                    raise ValueError('creation PID incompatible avec le manifeste : '+travail.cle)
            correspondants.append(record)
        if len(correspondants) != 1:
            raise RuntimeError('adoption exige exactement un worker vivant correspondant : '+travail.cle)
        record = correspondants[0]
        self.trace('identite_worker_adopte_verifiee',travail,**record)
        return self.observe(record)

    def _valide_entete(self, m, travail):
        if m.get('etat') == 'echec':
            raise RuntimeError(f'calcul en echec {travail.cle}: '+m.get('erreur','sans detail'))
        attendu = asdict(Q.montage_campagne(travail.niveau,travail.duree_ns))
        if (m.get('antenne') != travail.antenne or
                Q.G.json_octets(m.get('montage')) != Q.G.json_octets(attendu) or
                m.get('sources_sha256') != self.sources):
            raise ValueError('configuration/sources du worker incompatibles : '+travail.cle)
        if any(m.get('environnement',{}).get(k) != v for k,v in self.versions.items()):
            raise ValueError('environnement du worker incompatible : '+travail.cle)
        if m.get('etat') not in ('prepare','calcul_en_cours','termine','derivation_en_cours'):
            raise ValueError('etat du worker non adoptable : '+str(m.get('etat')))

    def _lecture_manifeste(self, travail):
        p = travail.dossier(self.base)/'simulation_manifest.json'
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except (json.JSONDecodeError,PermissionError):
            return None  # remplacement/ecriture en cours : retenter sans lancer

    def _est_clos(self, travail, m):
        p = travail.dossier(self.base)
        if not m or m.get('etat') != 'termine':
            return False
        for nom in ('qualification_entree.json','s11_indicateurs.json'):
            try:
                json.loads((p/nom).read_text(encoding='utf-8'))
            except (FileNotFoundError,json.JSONDecodeError,PermissionError):
                return False
        return True

    def _valide_termine(self, travail):
        self._verifie_sources()
        f,s,m,q = Q.charge_calcul(travail.dossier(self.base),exiger_courant=True)
        self._valide_entete(m,travail)
        Q.valide_campagne(m,q,travail.antenne,travail.niveau,travail.duree_ns)
        p = travail.dossier(self.base)/'s11_indicateurs.json'
        indicateurs = json.loads(p.read_text(encoding='utf-8'))
        if not indicateurs_equivalents(indicateurs,Q.indicateurs(f,s)):
            raise ValueError('indicateurs differents des sondes qualifiees : '+travail.cle)
        return m

    def _progression(self, travail, journal=None):
        p = travail.dossier(self.base)
        fichiers = [p/n for n in ('port_ut_1','port_it_1','openEMS_run_stats.txt',
                    'simulation_manifest.json','qualification_entree.json','s11_indicateurs.json')]
        if journal:
            fichiers.append(journal)
        signature = []
        for f in fichiers:
            try:
                s = f.stat()
                signature.append((str(f),s.st_size,s.st_mtime_ns))
            except OSError:
                pass
        dernier_t = None
        try:
            with (p/'port_ut_1').open('rb') as f:
                f.seek(0,2)
                f.seek(max(0,f.tell()-2048))
                for ligne in reversed(f.read().splitlines()):
                    if not ligne.startswith(b'%') and len(ligne.split()) == 2:
                        dernier_t = float(ligne.split()[0])
                        break
        except (OSError,ValueError):
            pass
        return tuple(signature),dernier_t

    def _verifie_delais(self, travail, dernier_progres):
        maintenant = self.horloge()
        if maintenant-self.debut >= self.limite_s:
            raise TimeoutError('limite globale de campagne atteinte; workers non tues')
        if maintenant-dernier_progres >= self.inactivite_s:
            raise TimeoutError('aucune progression depuis le delai autorise : '+travail.cle)

    def _surveille(self, travail, processus=None, journal=None):
        signature,_ = self._progression(travail,journal)
        dernier_progres = self.horloge()
        while True:
            if self.stop.is_set():
                self.trace('worker_laisse_actif',travail,pid=getattr(processus,'pid',None))
                raise ArretCoordonne('nouveaux lancements suspendus; worker non tue')
            self._verifie_sources()
            m = self._lecture_manifeste(travail)
            if m:
                self._valide_entete(m,travail)
            retour = processus.poll() if processus is not None else None
            if retour is not None:
                if retour:
                    raise RuntimeError(f'worker termine avec code {retour} : {travail.cle}')
                # Le worker peut avoir clos les preuves ENTRE la lecture
                # precedente et poll(). Ne pas juger sur cet ancien snapshot.
                m = self._lecture_manifeste(travail)
                if m:
                    self._valide_entete(m,travail)
                if self._est_clos(travail,m):
                    self._valide_termine(travail)
                    self.trace('termine_valide',travail,pid=getattr(processus,'pid',None))
                    return
                raise RuntimeError('worker sorti sans dossier complet lisible : '+travail.cle)
            courant,t = self._progression(travail,journal)
            if courant != signature:
                dernier_progres,signature = self.horloge(),courant
                dt = m.get('execution',{}).get('dt_s') if m else None
                self.trace('progression',travail,dernier_t_s=t,
                    dernier_pas=int(round(t/dt)) if t is not None and dt else None,
                    pid=getattr(processus,'pid',None))
            self._verifie_delais(travail,dernier_progres)
            self.attend(self.stop,self.intervalle_s)

    def _commande(self, travail):
        if travail.derive_de_ns is not None:
            source = Travail(travail.antenne,travail.niveau,travail.derive_de_ns)
            self._valide_termine(source)
            return [sys.executable,'-u','-B','-X','utf8',str(RACINE/'fenetre_sondes.py'),
                '--source',str(source.dossier(self.base)),
                '--sortie',str(travail.dossier(self.base)),'--duree-ns',f'{travail.duree_ns:g}']
        return [sys.executable,'-u','-B','-X','utf8',str(RACINE/'qualifie_pcbway.py'),
            '--antenne',travail.antenne,'--niveau',travail.niveau,
            '--duree-ns',f'{travail.duree_ns:g}','--fils',str(self.fils),'--base',str(self.base)]

    def assure(self, travail):
        if self.stop.is_set():
            raise ArretCoordonne('aucun nouveau lancement apres un echec')
        self._verifie_sources()
        p = travail.dossier(self.base)
        m = self._lecture_manifeste(travail)
        if m:
            self._valide_entete(m,travail)
            if self._est_clos(travail,m):
                self._valide_termine(travail)
                self.trace('cache_valide_reutilise',travail)
                return
            if not self.adopter:
                raise FileExistsError('worker existant : ajouter explicitement --adopter-en-cours')
            processus = self._trouve_adopte(travail,m)
            self.trace('worker_adopte_sans_lancement',travail,pid=processus.pid)
            try:
                self._surveille(travail,processus)
            finally:
                processus.close()
            return
        if p.exists() and any(p.iterdir()):
            raise FileExistsError('dossier partiel sans manifeste adoptable : '+str(p))
        commande = self._commande(travail)
        # Pas de creation du dossier de calcul : F.lance exige un dossier vide.
        journaux = self.base/'journaux'
        journaux.mkdir(parents=True,exist_ok=True)
        nom = travail.cle.replace('/','_')+'_'+self.jeton[:10]+'.log'
        journal = journaux/nom
        with self.lancement_lock:
            if self.stop.is_set():
                raise ArretCoordonne('lancement annule apres echec de l autre voie')
            self._verifie_delais(travail,self.horloge())
            self.trace('lancement',travail,commande=commande,journal=str(journal))
            with journal.open('xb') as out:
                processus = self.popen(commande,stdout=out,stderr=subprocess.STDOUT,
                    cwd=str(RACINE),creationflags=(subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
            self.trace('worker_cree',travail,pid=processus.pid,journal=str(journal))
        # Le handle du journal est duplique chez le child : fermer notre copie
        # ne tue ni n'interrompt le worker, meme si le pipeline doit s'arreter.
        self._surveille(travail,processus,journal)

    def _echec(self, message, travail=None):
        with self.lancement_lock:
            self.stop.set()
        with self.etat_lock:
            self.etat['erreurs'].append(message)
            self.etat['etat'] = 'arret_sur_echec'
        self.trace('echec',travail,erreur=message,workers_existants_non_tues=True)

    def _voie(self, numero, travaux):
        for travail in travaux:
            if self.stop.is_set():
                self.trace('non_lance_apres_arret',travail,voie=numero)
                return False
            try:
                self.assure(travail)
            except ArretCoordonne:
                return False
            except Exception as exc:
                self._echec(f'{type(exc).__name__}: {exc}',travail)
                return False
        return True

    def execute(self):
        self.acquiert_verrou()
        try:
            self.etat['etat'] = 'en_cours'
            self.trace('pipeline_demarre',plan=[[t.cle for t in v] for v in plan_deux_voies()])
            try:
                with ThreadPoolExecutor(max_workers=2,thread_name_prefix='pcbway_voie') as pool:
                    futures = [pool.submit(self._voie,i+1,v) for i,v in enumerate(plan_deux_voies())]
                    try:
                        succes = all([f.result() for f in futures])
                    except KeyboardInterrupt:
                        self._echec('interruption du pipeline; workers existants non tues')
                        succes = False
            except KeyboardInterrupt:
                self._echec('interruption du pipeline; workers existants non tues')
                return 2
            if not succes or self.stop.is_set():
                return 2
            for voie in plan_deux_voies():
                for travail in voie:
                    self._valide_termine(travail)
            self._verifie_delais(Travail('comparaison','globale',0),self.horloge())
            self.trace('neuf_dossiers_lisibles_comparaison')
            bilan = Q.comparer(self.base)
            self.etat.update(etat='comparaison_terminee',
                criteres_reussis=bool(bilan['tous_reussis']), fin_utc=self.utc())
            self.trace('comparaison_terminee',criteres_reussis=bool(bilan['tous_reussis']))
            return 0 if bilan['tous_reussis'] else 2
        except Exception as exc:
            self._echec(f'{type(exc).__name__}: {exc}')
            return 2
        finally:
            self.libere_verrou()


def principal():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=Q.BASE)
    p.add_argument('--adopter-en-cours',action='store_true')
    p.add_argument('--fils',type=int,default=10)
    p.add_argument('--inactivite-minutes',type=float,default=10)
    p.add_argument('--limite-heures',type=float,default=6)
    args = p.parse_args()
    pipeline = Pipeline(args.base,args.adopter_en_cours,args.fils,
        args.inactivite_minutes*60,args.limite_heures*3600)
    try:
        return pipeline.execute()
    except (FileExistsError,ValueError) as exc:
        print(f'Pipeline non lance : {exc}',file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(principal())
