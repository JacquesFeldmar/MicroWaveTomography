"""Campagne S11 des trois antennes de production et controle de convergence.

Chaque calcul utilise un dossier neuf et conserve XML, grille, sondes et
sources. Les cartes sont separees du panneau AVANT la mesure/simulation.
Exemples (Python openems) :
  python qualifie_pcbway.py --antenne diamant_uwb --niveau base --duree-ns 8
  python qualifie_pcbway.py --antenne diamant_uwb --niveau fin --duree-ns 8
  python qualifie_pcbway.py --antenne diamant_uwb --niveau fin --duree-ns 12
  python qualifie_pcbway.py --comparer
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
# L'entree CLI delegue au controleur canonique : AP et L importent ainsi
# exactement le meme module et le meme catalogue, sans alias sys.modules.
if __name__ == "__main__":
    from qualifie_pcbway import main
    raise SystemExit(main())
import numpy as np

from banc import Acquisition, Maillage, Montage
import fdtd as F
import export_gerber as G
from donnees import lit_s1p
from traitement import bandes_adaptees

RACINE = Path(__file__).resolve().parent
ANTENNES = ("diamant_uwb", "diamant_uwb_x18", "vivaldi_tomographie")
NIVEAUX = {
    "base": dict(mailles_par_lambda=10, mailles_par_lambda_air=10, maille_min=0.25),
    "fin": dict(mailles_par_lambda=14, mailles_par_lambda_air=12, maille_min=0.20),
    "tres_fin": dict(mailles_par_lambda=18, mailles_par_lambda_air=14, maille_min=0.15),
}
import raffine_qualification_pcbway as R
R.enregistre(sys.modules[__name__])
BASE = RACINE / "resultats" / "pcbway_r1"


def sauve(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(G.json_octets(obj))


def signature(carte, montage):
    physique = dict(geometrie=G.geometrie_canonique(carte),
        contrat=carte["simulation_contract"], montage=asdict(montage))
    return hashlib.sha256(G.json_octets(physique)).hexdigest()


def montage_campagne(niveau, duree_ns):
    if niveau not in NIVEAUX or not np.isfinite(duree_ns) or duree_ns <= 0:
        raise ValueError("niveau/duree de campagne invalide")
    return Montage(acquisition=Acquisition(f_min=1e9, f_max=6.3e9, points=213),
        maillage=Maillage(**NIVEAUX[niveau], duree_ns=float(duree_ns), symetrie=False,
                          n_pas_max=1000000))


def calcule(antenne, niveau, duree_ns, fils=10, cout=False, base=BASE):
    module = F.charge_antenne(antenne)
    carte = G.carte_antenne(antenne)
    montage = montage_campagne(niveau, duree_ns)
    dossier = Path(base)/antenne/f"{niveau}_{duree_ns:g}ns"
    empreinte = signature(carte, montage)
    if cout:
        cellules, pas, minutes = F.estime_cout(montage, antenne_mod=module, duree_ns=duree_ns)
        print(json.dumps(dict(antenne=antenne, niveau=niveau, duree_ns=duree_ns,
            cellules=cellules, pas_estimes=pas, minutes_indicatives=minutes,
            note="dt operateur et vitesse mesures au lancement"), ensure_ascii=False), flush=True)
        return
    preuve = dossier/"qualification_entree.json"
    if (dossier/"simulation_manifest.json").exists():
        _, _, actuel, precedent = charge_calcul(dossier, exiger_courant=True)
        valide_campagne(actuel, precedent, antenne, niveau, duree_ns)
        if precedent.get("signature_physique") != empreinte:
            raise FileExistsError(f"Configuration differente : {dossier}")
        import platform
        import scipy
        import openEMS
        import CSXCAD
        versions = dict(python=platform.python_version(), numpy=np.__version__,
            scipy=scipy.__version__, openems=openEMS.__version__, csxcad=CSXCAD.__version__)
        if any(actuel["environnement"].get(k) != v for k,v in versions.items()):
            raise ValueError("environnement modifie; calcul archive non reutilise automatiquement")
        print(f"Calcul conserve, integre et reutilise : {dossier}", flush=True)
        return
    # lance refuse un dossier non vide : la preuve d'entree sera ecrite ensuite.
    print(f"DEBUT {antenne} {niveau} {duree_ns:g} ns", flush=True)
    entrees = dict(schema="qualification_pcbway_r1", antenne=antenne, niveau=niveau,
        signature_physique=empreinte, geometrie=G.geometrie_canonique(carte),
        geometrie_sha256=hashlib.sha256(G.json_octets(G.geometrie_canonique(carte))).hexdigest(),
        simulation_contract=carte["simulation_contract"], montage=asdict(montage),
        debut_utc=datetime.now(timezone.utc).isoformat())
    try:
        f, s = F.lance(montage, module, dossier=str(dossier), duree_ns=duree_ns,
                       fils=fils, verbose=0)
    finally:
        if dossier.is_dir():
            sauve(preuve, entrees)
    sauve(dossier/"s11_indicateurs.json", indicateurs(f, s))
    print(f"TERMINE {antenne} {niveau} {duree_ns:g} ns", flush=True)


def indicateurs(f, s):
    db = 20*np.log10(np.maximum(np.abs(s), 1e-18))
    utiles = (f >= 1.4e9) & (f <= 6e9)
    return dict(bande_hz=[float(f[0]), float(f[-1])], points=len(f),
        maximum_module=float(np.max(np.abs(s))),
        passivite_numerique=bool(np.max(np.abs(s)) <= 1.005),
        moins_10_db=bandes_adaptees(f, s, -10), moins_6_db=bandes_adaptees(f, s, -6),
        bande_1p4_6=dict(moins_10_db=bandes_adaptees(f[utiles], s[utiles], -10),
            moins_6_db=bandes_adaptees(f[utiles], s[utiles], -6),
            moyenne_puissance_reflechie_db=float(10*np.log10(max(float(np.mean(np.abs(s[utiles])**2)),1e-36))),
            pire_db=float(db[utiles].max())))


def ecarts(fa, sa, fb, sb, temporel=False):
    if fa.shape != fb.shape or not np.array_equal(fa, fb):
        raise ValueError("grilles frequentielles differentes")
    delta = np.abs(sa-sb)
    garde = (np.abs(sa) >= .1) & (np.abs(sb) >= .1)
    db = np.abs(20*np.log10(np.maximum(np.abs(sa),1e-15)/np.maximum(np.abs(sb),1e-15)))
    phase = np.abs(np.angle(sa*np.conj(sb), deg=True))
    limites = dict(maximum_complexe=.015 if temporel else .05,
                   rms_complexe=.005 if temporel else .02,
                   percentile95_db=.5 if temporel else 1.0)
    valeurs = dict(maximum_complexe=float(delta.max()), rms_complexe=float(np.sqrt(np.mean(delta**2))),
        percentile95_db=float(np.percentile(db[garde],95)) if garde.any() else None,
        percentile95_phase_deg=float(np.percentile(phase[garde],95)) if garde.any() else None)
    ok = all(valeurs[k] is not None and valeurs[k] <= v for k,v in limites.items())
    return dict(valeurs=valeurs, seuils_acceptation=limites, reussi=ok,
        masque_db="percentile95 lorsque les deux |S11| sont >= -20 dB; tous points pour delta complexe")


def _verifie_fichiers(dossier, inventaire):
    dossier = Path(dossier).resolve()
    if not inventaire:
        raise ValueError("inventaire SHA-256 vide")
    for nom, sha in inventaire.items():
        chemin = (dossier/nom).resolve()
        if (not chemin.is_relative_to(dossier) or not chemin.is_file() or
                hashlib.sha256(chemin.read_bytes()).hexdigest() != sha):
            raise ValueError(f"empreinte du calcul alteree : {chemin}")


def charge_calcul(dossier, exiger_courant=False):
    dossier = Path(dossier).resolve()
    m = json.loads((dossier/"simulation_manifest.json").read_text(encoding="utf-8"))
    q = json.loads((dossier/"qualification_entree.json").read_text(encoding="utf-8"))
    if m["etat"] != "termine":
        raise ValueError(f"calcul non termine : {dossier}")
    _verifie_fichiers(dossier, m["fichiers_sha256"])
    _verifie_fichiers(dossier/"sources", m["sources_sha256"])
    critiques = {"s11.s1p","maillage.npz","geometrie.json","port_ut_1","port_it_1"}
    critiques.add("origine_entree_openems.xml" if m.get("derive_sondes") else "entree_openems.xml")
    critiques.update("sources/"+nom for nom in m["sources_sha256"])
    if not critiques.issubset(m["fichiers_sha256"]):
        raise ValueError("fichiers critiques non couverts par les empreintes")
    if G.json_octets(q["montage"]) != G.json_octets(m["montage"]):
        raise ValueError("montage de qualification different du calcul")
    physique = dict(geometrie=q["geometrie"], contrat=q["simulation_contract"], montage=q["montage"])
    if hashlib.sha256(G.json_octets(physique)).hexdigest() != q["signature_physique"]:
        raise ValueError("signature physique de qualification incoherente")
    if hashlib.sha256(G.json_octets(q["geometrie"])).hexdigest() != q["geometrie_sha256"]:
        raise ValueError("geometrie de qualification incoherente")
    if q["antenne"] != m["antenne"]:
        raise ValueError("identites antenne differentes")
    if exiger_courant:
        carte = G.carte_antenne(m["antenne"])
        if (G.json_octets(G.geometrie_canonique(carte)) != G.json_octets(q["geometrie"]) or
                G.json_octets(carte["simulation_contract"]) != G.json_octets(q["simulation_contract"])):
            raise ValueError("geometrie/contrat courants differents de la simulation")
        if m["sources_sha256"] != F._sources():
            raise ValueError("sources physiques/moteur modifiees depuis le calcul")
        module = F.charge_antenne(m["antenne"])
        geometrie_fdtd = {nom:F._jsonable(getattr(module,nom)())
            for nom in ("cotes","contours_mm","vias_mm","trous_mm","materiau")
            if callable(getattr(module,nom,None))}
        archive = json.loads((dossier/"geometrie.json").read_text(encoding="utf-8"))
        if G.json_octets(geometrie_fdtd) != G.json_octets(archive):
            raise ValueError("geometrie construite par FDTD differente des sources courantes")
    f, s = lit_s1p(str(dossier/"s11.s1p"))
    a = m["montage"]["acquisition"]
    if not np.array_equal(f, np.linspace(a["f_min"], a["f_max"], a["points"])):
        raise ValueError("grille du S11 differente de l'acquisition")
    return f, s, m, q


def valide_campagne(m, q, antenne, niveau, duree_ns):
    """Refuse qu'un simple nom de dossier tienne lieu de preuve de configuration."""
    if (m["antenne"] != antenne or q["antenne"] != antenne or q["niveau"] != niveau or
            G.json_octets(q["montage"]) != G.json_octets(asdict(montage_campagne(niveau,duree_ns)))):
        raise ValueError("configuration differente du niveau de campagne attendu")
    e = m["execution"]
    dt = e["dt_s"]
    if (not np.isfinite(dt) or dt <= 0 or e.get("fin_energie_active",True) or
            not np.isclose(e["duree_demandee_s"], duree_ns*1e-9, rtol=1e-12, atol=1e-21)):
        raise ValueError("duree/pas/arret de campagne incorrects")
    n = int(np.ceil(duree_ns*1e-9/dt))+1
    if e["n_pas"] != n:
        raise ValueError("nombre de pas different de la duree demandee")
    for nom, decalage in (("port_ut_1",0.),("port_it_1",.5)):
        sonde = m["sondes"][nom]
        if (sonde["echantillons"] != n+1 or
                not np.isclose(sonde["dt_effectif_s"],dt,rtol=2e-7,atol=1e-18) or
                abs(sonde["debut_s"]/dt-decalage) > 2e-6 or
                abs(sonde["fin_s"]/dt-(n+decalage)) > 2e-6):
            raise ValueError("sondes incompatibles avec la duree reelle de campagne")


def extinction(dossier):
    """Diagnostic de queue, distinct du controle par prolongation du calcul."""
    resultat={}
    for nom in ("port_ut_1", "port_it_1"):
        data=np.loadtxt(Path(dossier)/nom,comments="%")
        signal=data[:,1]
        dernier=signal[-max(2,len(signal)//10):]
        pic=float(np.max(np.abs(signal)))
        resultat[nom]=dict(dernier_dixieme_rms_sur_pic_db=float(
            20*np.log10(max(float(np.sqrt(np.mean(dernier**2)))/max(pic,1e-300),1e-300))),
            fraction_energie_dernier_dixieme=float(np.sum(dernier**2)/max(np.sum(signal**2),1e-300)))
    return resultat


def figures(antenne, courbes, sortie):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11,11), sharex=True)
    for nom, f, s in courbes:
        axes[0].plot(f/1e9,20*np.log10(np.maximum(np.abs(s),1e-15)),label=nom)
    axes[0].axhline(-10,color="k",lw=.7,ls="--")
    axes[0].axhline(-6,color="gray",lw=.7,ls=":")
    axes[0].set(ylim=(-40,1),ylabel="S11 (dB)")
    axes[0].legend()
    nom, f, s = courbes[-1]
    z=50*(1+s)/(1-s)
    axes[1].plot(f/1e9,z.real,label="R")
    axes[1].plot(f/1e9,z.imag,label="X")
    axes[1].set(ylim=(-250,350),ylabel="Z (ohms)")
    axes[1].legend()
    axes[2].plot(f/1e9,np.unwrap(np.angle(s))*180/np.pi)
    axes[2].set(xlabel="Frequence (GHz)",ylabel="Phase S11 (degres)")
    for ax in axes: ax.grid(alpha=.25)
    fig.suptitle(antenne+" - PCB de production, port ideal au bord de carte\nSMA coaxial et ENIG non modelises en 3D")
    fig.tight_layout()
    fig.savefig(sortie/"comparaison_convergence.png",dpi=160)
    plt.close(fig)


def comparer(base=BASE, ecrire=True):
    if (Path(base)/"selection_qualification.json").is_file():
        import qualification_adaptative as A
        return A.comparer(base, ecrire=ecrire)
    bilan={"schema":"qualification_pcbway_r1", "antennes":{}, "tous_reussis":True}
    for nom in ANTENNES:
        racine=Path(base)/nom
        selections=[("base",racine/"base_8ns"),("fin",racine/"fin_8ns"),
                    ("fin prolonge",racine/"fin_12ns")]
        donnees=[(label,*charge_calcul(p,exiger_courant=True)) for label,p in selections]
        for d,(niveau,duree) in zip(donnees,[("base",8.),("fin",8.),("fin",12.)]):
            valide_campagne(d[3],d[4],nom,niveau,duree)
        if len({d[4]["geometrie_sha256"] for d in donnees}) != 1:
            raise ValueError("geometries differentes entre les calculs de "+nom)
        contrats=[G.json_octets(d[4]["simulation_contract"]) for d in donnees]
        if any(c != contrats[0] for c in contrats[1:]):
            raise ValueError("materiau/connectique differents entre les calculs de "+nom)
        for cle in ("sources_sha256","environnement"):
            if any(d[3][cle] != donnees[0][3][cle] for d in donnees[1:]):
                raise ValueError("sources/environnement differents entre les calculs de "+nom)
        a,b,c=donnees
        spatial=ecarts(a[1],a[2],b[1],b[2])
        temporel=ecarts(b[1],b[2],c[1],c[2],temporel=True)
        if b[3]["maillage"] != c[3]["maillage"]:
            raise ValueError("la comparaison temporelle doit conserver le meme maillage")
        if b[3]["execution"]["dt_s"] != c[3]["execution"]["dt_s"]:
            raise ValueError("la comparaison temporelle doit conserver le meme pas temporel")
        resultat=dict(spatial=spatial,temporel=temporel,reference=str(selections[-1][1]),
            geometrie_sha256=c[4]["geometrie_sha256"],indicateurs=indicateurs(c[1],c[2]),
            hypothese_plan=c[4]["simulation_contract"],
            extinction=extinction(selections[-1][1]),
            preuves_sha256={str(p.relative_to(base)).replace('\\','/'):
                hashlib.sha256(p.read_bytes()).hexdigest()
                for _, dossier in selections for p in Path(dossier).rglob('*')
                if p.is_file()})
        resultat["reussi"]=(spatial["reussi"] and temporel["reussi"]
                              and resultat["indicateurs"]["passivite_numerique"])
        bilan["tous_reussis"] &= resultat["reussi"]
        bilan["antennes"][nom]=resultat
        sortie=racine/"comparaison"
        f,s=c[1],c[2]
        z=50*(1+s)/(1-s)
        colonnes=np.column_stack([f,s.real,s.imag,20*np.log10(np.maximum(np.abs(s),1e-15)),z.real,z.imag])
        if ecrire:
            sortie.mkdir(exist_ok=True)
            figures(nom,[(d[0],d[1],d[2]) for d in donnees],sortie)
            np.savetxt(sortie/"reference_simulation.csv",
                colonnes,
                delimiter=",",header="f_Hz,S11_re,S11_im,S11_dB,Z_re_ohm,Z_im_ohm",comments="# ")
            F.ecrit_s1p(str(sortie/"reference_simulation.s1p"),f,s,
                commentaire="PCB de production; port ideal au bord PCB; voir qualification JSON")
        fc,sc=lit_s1p(str(sortie/"reference_simulation.s1p"))
        csv=np.loadtxt(sortie/"reference_simulation.csv",delimiter=",",comments="#")
        if (not np.array_equal(fc,f) or not np.allclose(sc,s,rtol=2e-12,atol=2e-13) or
                csv.shape != colonnes.shape or not np.allclose(csv,colonnes,rtol=2e-12,atol=2e-13)):
            raise ValueError("reference de comparaison alteree ou differente du calcul")
        resultat["sorties_sha256"]={str(p.relative_to(base)).replace('\\','/'):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                sortie/"reference_simulation.s1p",sortie/"reference_simulation.csv",
                sortie/"comparaison_convergence.png")}
        if ecrire:
            sauve(sortie/"qualification.json",resultat)
    if ecrire:
        sauve(Path(base)/"qualification_globale.json",bilan)
        print(json.dumps(bilan,ensure_ascii=False,indent=2),flush=True)
    return bilan


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--antenne",choices=ANTENNES)
    p.add_argument("--niveau",choices=NIVEAUX,default="base")
    p.add_argument("--duree-ns",type=float,default=8.)
    p.add_argument("--fils",type=int,default=10)
    p.add_argument("--cout",action="store_true")
    p.add_argument("--comparer",action="store_true")
    p.add_argument("--base",type=Path,default=BASE)
    args=p.parse_args(argv)
    if args.comparer:
        return 0 if comparer(args.base)["tous_reussis"] else 2
    if not args.antenne:p.error("choisir --antenne ou --comparer")
    calcule(args.antenne,args.niveau,args.duree_ns,args.fils,args.cout,args.base)
    return 0
