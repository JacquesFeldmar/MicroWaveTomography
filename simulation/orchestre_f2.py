"""Deux files F2, sans import de solveur ; preparer puis executer explicitement.

Tous les calculs/extractions sont des sous-processus Python directs. Le code
natif de chaque processus est conserve, independamment du verdict numerique.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
SIM = Path(__file__).resolve().parent  # version destinee a simulation/orchestre_f2.py
MOTEUR = "maillage_controle_v2"
ANTENNES = ("diamant_uwb", "diamant_uwb_x18", "vivaldi_tomographie")
CONTROLES = {"qualifie_pcbway.py", "qualification_adaptative.py", "fenetre_sondes.py",
             "raffine_qualification_pcbway.py", "export_gerber.py", "donnees.py",
             "traitement.py", "calcule_maille_controlee.py"}
PHYSIQUES = {"fdtd.py", "fdtd_maille_controlee.py", "banc.py", "materiaux.py", "connectique.py",
             *(f"antennes/{n}/geometrie.py" for n in (*ANTENNES, "dipole_reference", "uwb_surveyor"))}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for bloc in iter(lambda:f.read(1024*1024), b""):
            h.update(bloc)
    return h.hexdigest()


def octets(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n").encode("utf-8")


def lit(p):
    def unique(paires):
        obj = {}
        for k,v in paires:
            if k in obj:
                raise ValueError("cle JSON dupliquee : "+k)
            obj[k] = v
        return obj
    return json.loads(Path(p).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def neuf(p, contenu):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("xb") as f:
        f.write(contenu if isinstance(contenu, bytes) else octets(contenu))


def atomique(p, obj):
    p = Path(p)
    t = p.with_name(p.name+"."+uuid.uuid4().hex+".tmp")
    neuf(t,obj)
    for i in range(41):
        try:
            os.replace(t,p)
            return
        except PermissionError:
            if i == 40:
                raise
            time.sleep(.05)


def chemin(base, nom):
    if not isinstance(nom,str) or "\\" in nom:
        raise ValueError("chemin relatif POSIX requis")
    n = PurePosixPath(nom)
    if n.is_absolute() or ".." in n.parts or str(n) != nom or ":" in nom:
        raise ValueError("chemin de preuve invalide : "+nom)
    p = (Path(base)/nom).resolve()
    if not p.is_relative_to(Path(base).resolve()):
        raise ValueError("chemin hors racine")
    return p


def gel_charge(p, racine):
    g = lit(p)
    if set(g) != {"schema", "sources_physiques_sha256", "controles_sha256", "pilote_valide"} or g["schema"] != "gel_campagne_pcbway_f2_v1":
        raise ValueError("schema de gel explicite F2 requis")
    for cle, noms in (("sources_physiques_sha256",PHYSIQUES),("controles_sha256",CONTROLES)):
        valeurs = g[cle]
        if not isinstance(valeurs,dict) or set(valeurs) != noms:
            raise ValueError("inventaire exact requis : "+cle)
        for nom,h in valeurs.items():
            if not isinstance(h,str) or not re.fullmatch("[0-9a-f]{64}",h) or sha(chemin(racine,nom)) != h:
                raise ValueError("source gelee absente/alteree : "+nom)
    preuve = g["pilote_valide"]
    if not isinstance(preuve,dict) or set(preuve) != {"preuve", "sha256"}:
        raise ValueError("preuve de pilote valide obligatoire")
    fichier = chemin(racine, preuve["preuve"])
    if sha(fichier) != preuve["sha256"]:
        raise ValueError("preuve du pilote absente ou alteree")
    p = lit(fichier)
    if (p.get("schema") != "fin_pilote_natif_maille_controlee_v2" or
            p.get("moteur") != MOTEUR or
            any(p.get(k) is not True for k in ("pilote_natif_termine",
                "sondes_reelles_NrTS_plus_1_verifiees",
                "rejeu_deplace_S11_octets_identiques", "sources_et_controles_inchanges")) or
            p.get("qualification_globale_effectuee") is not False or
            any(p.get(k) != g[k] for k in ("sources_physiques_sha256", "controles_sha256"))):
        raise ValueError("pilote non valide ou sources differentes de la campagne")
    return g


def selection():
    return dict(schema="selection_qualification_pcbway_v1", antennes={n:dict(
        spatial=["base_12ns","fin_12ns"], temporel=["fin_12ns","fin_16ns"], reference="fin_16ns",
        preliminaires=[dict(type="spatial", calculs=["base_8ns","fin_8ns"],
                           motif="Essai initial spatial a 8 ns conserve sans presumer sa reussite"),
                       dict(type="temporel", calculs=["fin_8ns","fin_12ns"],
                           motif="Essai initial temporel 8 vers 12 ns conserve sans presumer sa reussite")])
        for n in ANTENNES})


def plan():
    def une(n):
        return [dict(type=t, antenne=n, niveau=niv, duree_ns=d, profil=f"{niv}_{d}ns",
                     source_profil=parent) for t,niv,d,parent in (
            ("calcul","base",12,None),("prefixe","base",8,"base_12ns"),
            ("calcul","fin",16,None),("prefixe","fin",8,"fin_16ns"),
            ("prefixe","fin",12,"fin_16ns"))]
    return dict(losanges=une(ANTENNES[0])+une(ANTENNES[1]), vivaldi=une(ANTENNES[2]))


def commande(e, racine, base, python, fils):
    prefixe=[str(python),"-B","-X","utf8"]
    if e["type"] == "calcul":
        return prefixe+[str(racine/"calcule_maille_controlee.py"),"--antenne",e["antenne"],
            "--niveau",e["niveau"],"--duree-ns",str(e["duree_ns"]),"--fils",str(fils),"--base",str(base)]
    return prefixe+[str(racine/"fenetre_sondes.py"),"--source",str(base/e["antenne"]/e["source_profil"]),
        "--sortie",str(base/e["antenne"]/e["profil"]),"--duree-ns",str(e["duree_ns"])]


def base_sure(racine, base):
    racine,base = Path(racine).resolve(),Path(base).resolve()
    f1=racine/"resultats/pcbway_r1"
    if base == racine or base == f1 or base.is_relative_to(f1) or f1.is_relative_to(base):
        raise ValueError("BASE F1 ou racine parente interdite")
    return racine,base


def prepare(racine, base, gel, python, fils=10):
    racine,base=base_sure(racine,base)
    gel=Path(gel).resolve();python=Path(python).resolve()
    if base.exists():
        raise FileExistsError("BASE doit etre entierement neuve, meme vide : "+str(base))
    if not python.is_file() or fils not in (1,2,4,10):
        raise ValueError("Python existant et fils 1/2/4/10 requis")
    g=gel_charge(gel,racine)
    queues=plan()
    for nom,etapes in queues.items():
        for i,e in enumerate(etapes,1):
            e["commande"]=commande(e,racine,base,python,fils)
            e["journal"]=f"journaux/{nom}/{i:02d}_{e['antenne']}_{e['profil']}"
    cfg=selection()
    # Aucun sous-processus n'est cree avant archivage complet.
    base.mkdir(parents=True,exist_ok=False)
    neuf(base/"selection_qualification.json",cfg)
    neuf(base/"controle_orchestration/gel_attendu.json",gel.read_bytes())
    neuf(base/"controle_orchestration/preuve_pilote.json",
         chemin(racine,g["pilote_valide"]["preuve"]).read_bytes())
    for n,h in {**g["sources_physiques_sha256"],**g["controles_sha256"]}.items():
        contenu=chemin(racine,n).read_bytes()
        if hashlib.sha256(contenu).hexdigest() != h:
            raise ValueError("source changee pendant preparation : "+n)
        neuf(base/"controle_orchestration/sources"/n,contenu)
    neuf(base/"controle_orchestration/orchestre_f2.py",Path(__file__).read_bytes())
    for n,etapes in queues.items():
        neuf(base/f"controle_orchestration/queue_{n}.json",etapes)
        (base/"journaux"/n).mkdir(parents=True,exist_ok=False)
    (base/"journaux/analyse").mkdir()
    contexte=dict(schema="orchestration_f2_v1", racine_sources=str(racine), base=str(base),
        python=str(python),fils=fils,moteur=MOTEUR,gel_original=str(gel),gel_sha256=sha(gel),
        orchestrateur_original=str(Path(__file__).resolve()),orchestrateur_sha256=sha(__file__),
        selection_sha256=sha(base/"selection_qualification.json"),utc_preparation=utc(),queues=queues)
    neuf(base/"controle_orchestration/contexte.json",contexte)
    # Les 18 sources, le gel, les deux queues et la selection sont couverts.
    inventaire={p.relative_to(base).as_posix():sha(p) for p in base.rglob("*") if p.is_file()}
    neuf(base/"controle_orchestration/archive_sha256.json",inventaire)
    etat=dict(schema="etat_orchestration_f2_v1",etat="prepare",tous_reussis=False,
        echec_technique=False,echec_numerique=False,queues={},analyse=None,utc=utc(),
        archive_index_sha256=sha(base/"controle_orchestration/archive_sha256.json"))
    neuf(base/"etat_orchestration.json",etat)
    return contexte


def controle(base, contexte):
    r=Path(contexte["racine_sources"])
    if sha(base/"controle_orchestration/archive_sha256.json") != contexte["_archive_index_sha256"]:
        raise ValueError("index des archives modifie")
    gel_charge(base/"controle_orchestration/gel_attendu.json",r)
    if sha(contexte["gel_original"]) != contexte["gel_sha256"] or sha(contexte["orchestrateur_original"]) != contexte["orchestrateur_sha256"]:
        raise ValueError("gel ou orchestrateur original modifie")
    if sha(base/"selection_qualification.json") != contexte["selection_sha256"]:
        raise ValueError("selection originale modifiee")
    for n,h in lit(base/"controle_orchestration/archive_sha256.json").items():
        if sha(chemin(base,n)) != h:
            raise ValueError("archive de preparation modifiee : "+n)


def profil_verifie(base,e,g):
    p=base/e["antenne"]/e["profil"]
    m,q=lit(p/"simulation_manifest.json"),lit(p/"qualification_entree.json")
    if (m.get("etat") != "termine" or m.get("moteur") != MOTEUR or q.get("moteur") != MOTEUR or
            m.get("antenne") != e["antenne"] or q.get("antenne") != e["antenne"] or
            q.get("niveau") != e["niveau"] or m.get("sources_sha256") != g["sources_physiques_sha256"]):
        raise ValueError("profil incomplet ou melange F1/F2 : "+str(p))
    for obj in (m,q):
        if obj["montage"]["maillage"]["duree_ns"] != e["duree_ns"]:
            raise ValueError("duree du profil incoherente")
    if e["type"] == "prefixe" and (m.get("derive_sondes") is not True or q.get("derive_sondes") is not True):
        raise ValueError("prefixe non derive par W")
    if not (p/"s11.s1p").is_file():
        raise ValueError("S11 manquant")


def bilan_verifie(base,cfg):
    b=lit(base/"qualification_globale.json")
    if (b.get("schema") != "qualification_pcbway_r1" or b.get("moteur") != MOTEUR or
            b.get("selection") != cfg or b.get("configuration_sha256") !=
            {"selection_qualification.json":sha(base/"selection_qualification.json")} or
            set(b.get("antennes",{})) != set(ANTENNES) or type(b.get("tous_reussis")) is not bool):
        raise ValueError("bilan AP absent/incoherent, pas un verdict numerique exploitable")
    verdicts=[]
    for n in ANTENNES:
        r=b["antennes"][n];spec=cfg["antennes"][n]
        profils={e["profil"] for q in plan().values() for e in q if e["antenne"]==n}
        if (r.get("selection_effective") != spec or set(r.get("calculs_utilises",[])) != profils or
                len(r.get("calculs_utilises",[])) != 5 or Path(r["reference"]).resolve() != base/n/"fin_16ns" or
                type(r.get("reussi")) is not bool):
            raise ValueError("selection/preuves AP incoherentes")
        for cle in ("spatial","temporel"):
            if type(r[cle].get("reussi")) is not bool:
                raise ValueError("verdict de convergence invalide")
        if r["reussi"] and not (r["spatial"]["reussi"] and r["temporel"]["reussi"]):
            raise ValueError("reussite AP contradictoire")
        preuves=r.get("preuves_sha256",{});sorties=r.get("sorties_sha256",{})
        requis={f"{n}/{p}/{f}" for p in profils for f in ("simulation_manifest.json","qualification_entree.json","s11.s1p")}
        attendues={f"{n}/comparaison/{f}" for f in ("reference_simulation.s1p","reference_simulation.csv","comparaison_convergence.png")}
        if not requis <= set(preuves) or set(sorties) != attendues:
            raise ValueError("inventaire des preuves AP incomplet")
        for fichier,h in {**preuves,**sorties}.items():
            if sha(chemin(base,fichier)) != h:
                raise ValueError("preuve AP alteree")
        verdicts.append(r["reussi"])
    if b["tous_reussis"] != all(verdicts):
        raise ValueError("verdict global AP contradictoire")
    return b


def processus(cmd,stdout,stderr):
    # Binary pipes preserve exact UTF-8 bytes; child Python is forced to UTF-8.
    env=os.environ.copy()
    env.update(PYTHONUTF8="1",PYTHONIOENCODING="utf-8",PYTHONUNBUFFERED="1",
               OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",NUMEXPR_NUM_THREADS="1")
    with Path(stdout).open("xb") as out,Path(stderr).open("xb") as err:
        return subprocess.run(cmd,stdout=out,stderr=err,env=env,check=False).returncode


def execute(base):
    base=Path(base).resolve()
    contexte=lit(base/"controle_orchestration/contexte.json")
    initial=lit(base/"etat_orchestration.json")
    # Etat mutable lu une seule fois avant les threads : Windows peut refuser
    # une lecture pendant os.replace. Le sceau attendu reste ensuite en RAM.
    contexte["_archive_index_sha256"]=initial["archive_index_sha256"]
    if Path(contexte["base"]) != base or initial["etat"] != "prepare":
        raise ValueError("campagne preparee neuve uniquement, pas de reprise/adoption automatique")
    base_sure(contexte["racine_sources"],base)
    controle(base,contexte)
    # Aucun profil, journal ou fichier inconnu ne preexiste a l'execution.
    attendus=set(lit(base/"controle_orchestration/archive_sha256.json"))|{
        "controle_orchestration/archive_sha256.json","etat_orchestration.json"}
    if {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()} != attendus:
        raise FileExistsError("fichier inattendu avant execution")
    repertoires={"journaux","journaux/losanges","journaux/vivaldi","journaux/analyse"}
    for n in attendus:
        repertoires.update(str(p) for p in PurePosixPath(n).parents if str(p) != ".")
    if {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_dir()} != repertoires:
        raise FileExistsError("dossier inattendu avant execution, meme vide")
    if any((base/n).exists() for n in ANTENNES):
        raise FileExistsError("dossier antenne/profil deja present, meme vide")
    verrou=base/"orchestration.lock"
    neuf(verrou,dict(pid=os.getpid(),utc=utc()))
    etat=initial;etat.update(etat="en_cours",utc=utc())
    mutex=threading.Lock();arret=threading.Event()
    def publie():
        etat["utc"]=utc();atomique(base/"etat_orchestration.json",etat)
    with mutex:
        publie()
    g=lit(base/"controle_orchestration/gel_attendu.json")
    def queue(n,etapes):
        resultat=dict(etat="en_cours",etapes=[],retour_natif=None)
        with mutex:
            etat["queues"][n]=resultat;publie()
        try:
            for e in etapes:
                if arret.is_set():
                    with mutex:
                        resultat["etat"]="arretee_avant_etape"
                    break
                controle(base,contexte)
                if (base/e["antenne"]/e["profil"]).exists():
                    raise FileExistsError("profil deja present")
                trace=dict(profil=e["antenne"]+"/"+e["profil"],type=e["type"],debut_utc=utc(),
                           commande=e["commande"],retour_natif=None)
                with mutex:
                    resultat["etapes"].append(trace);publie()
                print("DEBUT "+trace["profil"],flush=True)
                rc=processus(e["commande"],base/(e["journal"]+".stdout.log"),base/(e["journal"]+".stderr.log"))
                with mutex:
                    trace.update(retour_natif=rc,fin_utc=utc());resultat["retour_natif"]=rc;publie()
                print("FIN "+trace["profil"]+" code="+str(rc),flush=True)
                if rc != 0:
                    with mutex:
                        resultat["etat"]="echec_processus"
                    arret.set();break
                controle(base,contexte)
                profil_verifie(base,e,g)
            else:
                with mutex:
                    resultat["etat"]="terminee"
        except Exception as exc:
            with mutex:
                resultat.update(etat="echec_controle",erreur=f"{type(exc).__name__}: {exc}")
            arret.set()
        with mutex:
            publie()
        return resultat
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futurs=[pool.submit(queue,n,e) for n,e in contexte["queues"].items()]
            # Attendre les deux voies ; ne jamais tuer le calcul du pair.
            resultats=[f.result() for f in futurs]
        if any(r["etat"] != "terminee" for r in resultats):
            etat.update(etat="echec_execution",echec_technique=True,tous_reussis=False)
            rc=next((r["retour_natif"] for r in resultats if r["etat"]=="echec_processus"),1)
            etat["retour_orchestrateur"]=rc;publie();return rc
        controle(base,contexte)
        if (base/"qualification_globale.json").exists():
            raise FileExistsError("bilan AP deja present avant analyse")
        cmd=[contexte["python"],"-B","-X","utf8",str(Path(contexte["racine_sources"])/"qualification_adaptative.py"),"--base",str(base)]
        etat.update(etat="analyse",analyse=dict(commande=cmd,debut_utc=utc(),retour_natif=None));publie()
        rc=processus(cmd,base/"journaux/analyse/AP.stdout.log",base/"journaux/analyse/AP.stderr.log")
        etat["analyse"].update(retour_natif=rc,fin_utc=utc());publie()
        controle(base,contexte)
        b=bilan_verifie(base,selection())
        if rc == 0 and b["tous_reussis"]:
            etat.update(etat="qualifie",tous_reussis=True)
        elif rc == 2 and not b["tous_reussis"]:
            etat.update(etat="non_convergence",echec_numerique=True,tous_reussis=False)
        else:
            raise ValueError("ExitCode AP et bilan numerique incompatibles")
        etat["retour_orchestrateur"]=rc;publie();return rc
    except Exception as exc:
        etat.update(etat="echec_analyse" if etat.get("analyse") else "echec_execution",
                    echec_technique=True,tous_reussis=False,erreur=f"{type(exc).__name__}: {exc}")
        rc=(etat.get("analyse") or {}).get("retour_natif")
        rc=rc if isinstance(rc,int) and rc != 0 else 1
        etat["retour_orchestrateur"]=rc;publie();return rc
    finally:
        # Le verrou est une preuve conservee ; un second lancement est refuse.
        neuf(base/"fin_orchestration.json",dict(utc=utc(),etat=etat["etat"],
            retour_orchestrateur=etat.get("retour_orchestrateur"),tous_reussis=etat["tous_reussis"]))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preparer",action="store_true")
    modes.add_argument("--executer",action="store_true")
    p.add_argument("--racine-sources",type=Path,default=SIM)
    p.add_argument("--base",type=Path)
    p.add_argument("--gel",type=Path)
    p.add_argument("--python-openems",type=Path,default=Path(r"C:\Users\jfeld\anaconda3\envs\openems\python.exe"))
    p.add_argument("--fils",type=int,choices=(1,2,4,10),default=10)
    a=p.parse_args(argv)
    base=a.base or a.racine_sources/"resultats/pcbway_maille_controlee_v2"
    if a.preparer:
        if a.gel is None:
            p.error("--preparer exige --gel fourni apres integration, sans auto-gel")
        c=prepare(a.racine_sources,base,a.gel,a.python_openems,a.fils)
        print(json.dumps(dict(etat="prepare",base=c["base"],tous_reussis=False),ensure_ascii=False));return 0
    return execute(base)


if __name__ == "__main__":
    raise SystemExit(main())
