"""Compare une reference S11 aux acquisitions complexes, aux plans declares.

    python compare_s11.py --simulation reference_simulation.s1p \
        --mesure reconnexion01.s1p reconnexion02.s1p \
        --sortie comparaison_neuve \
        --plan-mesure "SOL au SMA male du cable, antenne reconnectee"

Touchstone S/RI/50 ohms, grilles strictement identiques, aucun recalage ou
interpolation. Les ecarts complexes et de phase sont descriptifs : le plan
ideal du PCB et le plan SMA reel ne deviennent pas equivalents par ce calcul.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from donnees import lit_s1p
from traitement import bandes_adaptees, en_db


PLAN_SIMULATION = "bord du PCB, port ideal 50 ohms ; corps SMA et soudures non modelises en 3D"


def sha256(octets):
    return hashlib.sha256(octets).hexdigest()


def charge(chemin):
    """Capture les octets lus et leur SHA, avec le lecteur strict du projet."""
    p = Path(chemin).resolve()
    if not p.is_file() or p.suffix.lower() != ".s1p":
        raise ValueError(f"fichier Touchstone .s1p attendu : {p}")
    octets = p.read_bytes()
    f, s = lit_s1p(str(p))
    if p.read_bytes() != octets:
        raise ValueError(f"fichier modifie pendant sa lecture : {p}")
    return dict(source=str(p), nom=p.name, freqs=f, s11=s,
                octets=octets, sha256=sha256(octets))


def phase_deg(s):
    """Phase deroulee par segments non nuls, sans ajustement de retard/offset.

    La phase d'un coefficient exactement nul est indefinie : NaN dans le
    calcul/figure et cellule vide dans le CSV. Chaque segment reprend sa
    branche native ; aucun raccord n'est invente a travers un zero.
    """
    s = np.asarray(s, dtype=complex)
    resultat = np.full(s.shape, np.nan)
    idx = np.flatnonzero(np.abs(s) > 0)
    for groupe in np.split(idx, np.flatnonzero(np.diff(idx) > 1)+1):
        if len(groupe):
            resultat[groupe] = np.rad2deg(np.unwrap(np.angle(s[groupe])))
    return resultat


def impedance(s):
    """50(1+S)/(1-S) ; le circuit ouvert exact a une impedance indefinie."""
    s = np.asarray(s, dtype=complex)
    z = np.full(s.shape, complex(np.nan, np.nan))
    defini = np.abs(1-s) > 0
    z[defini] = 50*(1+s[defini])/(1-s[defini])
    return z


def indicateurs(f, s):
    modules = np.abs(s)
    db = en_db(modules)
    minimum = int(np.argmin(modules))
    locaux = [i for i in range(1,len(s)-1)
              if modules[i] < modules[i-1] and modules[i] <= modules[i+1]]
    locaux.sort(key=lambda i: modules[i])

    def decrit(i):
        return dict(frequence_hz=float(f[i]), module=float(modules[i]),
                    niveau_db=float(db[i]), bord_balayage=i in (0,len(s)-1))

    utile = (f >= 1.4e9) & (f <= 6e9)
    bande_utile = None
    if f[0] <= 1.4e9 and f[-1] >= 6e9 and utile.sum() >= 3:
        bande_utile = dict(bande_hz=[float(f[utile][0]),float(f[utile][-1])],
            moins_10_db=bandes_adaptees(f[utile],s[utile],-10),
            moins_6_db=bandes_adaptees(f[utile],s[utile],-6))
    return dict(points=len(f), bande_hz=[float(f[0]),float(f[-1])],
        moins_10_db=bandes_adaptees(f,s,-10), moins_6_db=bandes_adaptees(f,s,-6),
        bande_utile_1p4_6=bande_utile,
        puissance_reflechie_moyenne_db=float(10*np.log10(max(float(np.mean(modules**2)),1e-36))),
        minimum_global=decrit(minimum), minima_locaux=[decrit(i) for i in locaux[:8]],
        minima="frequences echantillonnees, descriptives, sans interpolation ni appariement force",
        phase_indefinie_points=int(np.sum(modules == 0)),
        impedance_indefinie_points=int(np.sum(np.abs(1-s) == 0)))


def ecarts(reference, mesure):
    """Ecarts diagnostiques sans seuil d'accord physique."""
    delta = mesure-reference
    module_delta = np.abs(mesure)-np.abs(reference)
    masque = (np.abs(reference) >= .1) & (np.abs(mesure) >= .1)
    delta_db = np.abs(en_db(np.abs(mesure))-en_db(np.abs(reference)))
    delta_phase = np.abs(np.angle(mesure*np.conj(reference),deg=True))
    return dict(maximum_complexe=float(np.abs(delta).max()),
        rms_complexe=float(np.sqrt(np.mean(np.abs(delta)**2))),
        maximum_ecart_module_lineaire=float(np.abs(module_delta).max()),
        rms_ecart_module_lineaire=float(np.sqrt(np.mean(module_delta**2))),
        percentile95_ecart_db=float(np.percentile(delta_db[masque],95)) if masque.any() else None,
        percentile95_ecart_phase_principale_deg=float(np.percentile(delta_phase[masque],95)) if masque.any() else None,
        points_masque_db_phase=int(masque.sum()),
        masque_db_phase="les deux modules >= 0.1 (-20 dB)",
        interpretation="diagnostic aux plans declares ; aucun seuil ni verdict de qualification")


def dispersion(mesures):
    """Dispersion des fichiers fournis, sans supposer leur independance."""
    s = np.stack([m["s11"] for m in mesures])
    modules = np.abs(s)
    moyenne = s.mean(axis=0)
    if len(s) < 2:
        return dict(nombre_acquisitions=1, disponible=False), None
    sigma = np.sqrt(np.sum(np.abs(s-moyenne)**2,axis=0)/(len(s)-1))
    sigma_module = modules.std(axis=0,ddof=1)
    resume = dict(nombre_acquisitions=len(s), disponible=True,
        ecart_type_complexe_max=float(sigma.max()),
        ecart_type_complexe_rms=float(np.sqrt(np.mean(sigma**2))),
        ecart_type_module_max=float(sigma_module.max()),
        ecart_type_module_rms=float(np.sqrt(np.mean(sigma_module**2))),
        definition="ecarts types echantillonnaux (N-1), complexe autour de la moyenne complexe",
        interpretation="dispersion descriptive ; repetabilite et independance des acquisitions a documenter")
    return resume, dict(moyenne=moyenne, sigma=sigma, sigma_module=sigma_module,
                       min_db=en_db(modules.min(axis=0)),max_db=en_db(modules.max(axis=0)))


def _csv(path, colonnes, lignes):
    with Path(path).open("w",encoding="utf-8",newline="") as fichier:
        out = csv.DictWriter(fichier,fieldnames=colonnes)
        out.writeheader()
        out.writerows(lignes)


def _fini(x):
    return float(x) if np.isfinite(x) else ""


def figure(reference, mesures, chemin, plan_simulation, plan_mesure, dispersion_freq):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes = plt.subplots(3,1,figsize=(12,11),sharex=True)
    f = reference["freqs"]/1e9
    couleurs = plt.get_cmap("tab10")
    for i,courbe in enumerate([reference,*mesures]):
        s = courbe["s11"]
        couleur = "black" if i == 0 else couleurs((i-1)%10)
        label = "Simulation" if i == 0 else f"{courbe['id']} : {courbe['nom']}"
        largeur = 2.2 if i == 0 else 1.2
        axes[0].plot(f,en_db(np.abs(s)),color=couleur,lw=largeur,label=label)
        z = impedance(s)
        axes[1].plot(f,z.real,color=couleur,lw=largeur)
        axes[1].plot(f,z.imag,color=couleur,lw=largeur,ls="--",alpha=.8)
        axes[2].plot(f,phase_deg(s),color=couleur,lw=largeur)
    if dispersion_freq is not None:
        axes[0].fill_between(f,dispersion_freq["min_db"],dispersion_freq["max_db"],
                             color="gray",alpha=.18,label="enveloppe des acquisitions")
    for seuil in (-10,-6):
        axes[0].axhline(seuil,color="gray",ls=":" if seuil == -6 else "--",lw=.7)
    axes[0].set(ylabel="|S11| (dB)",title="Module : courbes originales aux plans declares")
    axes[0].legend(fontsize=8,loc="best")
    axes[1].set_yscale("symlog",linthresh=100)
    axes[1].set(ylabel="Z (ohms, echelle symlog)",title="Resistance : trait plein ; reactance : tirets")
    axes[2].set(xlabel="Frequence (GHz)",ylabel="Phase deroulee (degres)",
                title="Phase native, sans recalage ; indefinie lorsque S11 = 0")
    for ax in axes:
        ax.grid(alpha=.25)
    import textwrap
    titre = "Comparaison descriptive S11, sans critere automatique d'accord physique"
    texte = "Simulation : "+plan_simulation+"\nMesures : "+plan_mesure
    texte = "\n".join(textwrap.fill(ligne,width=115) for ligne in texte.splitlines())
    fig.suptitle(titre,fontsize=12)
    fig.text(.02,.01,texte,fontsize=8,va="bottom")
    lignes = len(texte.splitlines())
    fig.tight_layout(rect=(0,.035+.013*lignes,1,.97))
    fig.savefig(chemin,dpi=150)
    plt.close(fig)


def comparer(simulation, mesures, sortie, plan_mesure, plan_simulation=PLAN_SIMULATION):
    """Cree une comparaison descriptive dans un dossier neuf ou vide."""
    if not mesures:
        raise ValueError("au moins un fichier de mesure requis")
    if (not isinstance(plan_mesure,str) or not isinstance(plan_simulation,str) or
            not plan_mesure.strip() or not plan_simulation.strip()):
        raise ValueError("plans de mesure et simulation explicites requis")
    dossier = Path(sortie).resolve()
    if dossier.exists() and (not dossier.is_dir() or any(dossier.iterdir())):
        raise FileExistsError(f"dossier de sortie non vide ou non repertoire : {dossier}")
    reference = charge(simulation)
    reference["id"],reference["role"] = "simulation","simulation"
    acquisitions = [charge(p) for p in mesures]
    if len({m["source"] for m in acquisitions}) != len(acquisitions):
        raise ValueError("un meme chemin de mesure a ete fourni plusieurs fois")
    for i,m in enumerate(acquisitions,1):
        if not np.array_equal(reference["freqs"],m["freqs"]):
            raise ValueError(f"grille differente : {m['source']} ; aucune interpolation autorisee")
        m["id"],m["role"] = f"mesure_{i:02d}","mesure"
    resume_dispersion,dispersion_freq = dispersion(acquisitions)
    resume = dict(schema="comparaison_s11_v1",date_utc=datetime.now(timezone.utc).isoformat(),
        plan_simulation=str(plan_simulation).strip(),plan_mesure=str(plan_mesure).strip(),
        portee="comparaison descriptive ; ecarts complexes et phase aux plans declares, sans verdict de qualification",
        conventions=dict(reference_ohms=50,interpolation=False,recalage_retard=False,
            recalage_phase=False,recalage_amplitude=False,
            grilles="strictement identiques, aucune tolerance entre fichiers",
            phase="deroulee par segment non nul, branche native propre a chaque courbe",
            zeros="module en dB borne a -360 dB ; phase S11=0 et impedance S11=1 indefinies (cellules CSV vides)"),
        simulation=None,mesures=[],dispersion=resume_dispersion)
    dossier.mkdir(parents=True,exist_ok=True)
    for courbe in [reference,*acquisitions]:
        relative = (Path("entrees")/"simulation"/courbe["nom"] if courbe["role"] == "simulation"
                    else Path("entrees")/"mesures"/(courbe["id"]+"__"+courbe["nom"]))
        destination = dossier/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(courbe["octets"])
        if sha256(destination.read_bytes()) != courbe["sha256"]:
            raise RuntimeError("copie d'entree incoherente : "+str(destination))
        description = dict(id=courbe["id"],source=courbe["source"],copie=relative.as_posix(),
                           sha256=courbe["sha256"],indicateurs=indicateurs(courbe["freqs"],courbe["s11"]))
        if courbe["role"] == "simulation":
            resume["simulation"] = description
        else:
            description["ecarts_simulation"] = ecarts(reference["s11"],courbe["s11"])
            resume["mesures"].append(description)
    colonnes_resume = ["id","source","sha256","maximum_complexe","rms_complexe",
        "maximum_ecart_module_lineaire","rms_ecart_module_lineaire",
        "percentile95_ecart_db","percentile95_ecart_phase_principale_deg","points_masque_db_phase",
        "minimum_frequence_hz","minimum_db","segments_moins10_hz","segments_moins6_hz"]
    _csv(dossier/"resume_comparaisons.csv",colonnes_resume,
        [dict(id=m["id"],source=m["source"],sha256=m["sha256"],
            **{k:m["ecarts_simulation"][k] for k in colonnes_resume[3:10]},
            minimum_frequence_hz=m["indicateurs"]["minimum_global"]["frequence_hz"],
            minimum_db=m["indicateurs"]["minimum_global"]["niveau_db"],
            segments_moins10_hz=json.dumps(m["indicateurs"]["moins_10_db"]["segments_hz"]),
            segments_moins6_hz=json.dumps(m["indicateurs"]["moins_6_db"]["segments_hz"]))
         for m in resume["mesures"]])
    lignes = []
    for courbe in [reference,*acquisitions]:
        s,z,ph = courbe["s11"],impedance(courbe["s11"]),phase_deg(courbe["s11"])
        db = en_db(np.abs(s))
        for i,f in enumerate(courbe["freqs"]):
            delta = s[i]-reference["s11"][i]
            lignes.append(dict(id=courbe["id"],role=courbe["role"],frequence_hz=float(f),
                s11_re=float(s[i].real),s11_im=float(s[i].imag),module=float(abs(s[i])),
                module_db=float(db[i]),phase_deg=_fini(ph[i]),z_re_ohm=_fini(z[i].real),z_im_ohm=_fini(z[i].imag),
                delta_complexe_re=float(delta.real) if courbe["role"] == "mesure" else "",
                delta_complexe_im=float(delta.imag) if courbe["role"] == "mesure" else "",
                delta_complexe_module=float(abs(delta)) if courbe["role"] == "mesure" else ""))
    _csv(dossier/"courbes.csv",list(lignes[0]),lignes)
    if dispersion_freq is not None:
        _csv(dossier/"dispersion_frequentielle.csv",
             ["frequence_hz","moyenne_s11_re","moyenne_s11_im","ecart_type_complexe","ecart_type_module","minimum_db","maximum_db"],
             [dict(frequence_hz=float(f),moyenne_s11_re=float(dispersion_freq["moyenne"][i].real),
                moyenne_s11_im=float(dispersion_freq["moyenne"][i].imag),
                ecart_type_complexe=float(dispersion_freq["sigma"][i]),
                ecart_type_module=float(dispersion_freq["sigma_module"][i]),
                minimum_db=float(dispersion_freq["min_db"][i]),maximum_db=float(dispersion_freq["max_db"][i]))
              for i,f in enumerate(reference["freqs"])])
    figure(reference,acquisitions,dossier/"comparaison_s11.png",str(plan_simulation),str(plan_mesure),dispersion_freq)
    (dossier/"resultats.json").write_text(json.dumps(resume,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    manifeste = dict(schema="comparaison_s11_preuves_v1",date_utc=resume["date_utc"],
        fichiers_sha256={p.relative_to(dossier).as_posix():sha256(p.read_bytes())
                         for p in sorted(dossier.rglob("*")) if p.is_file()})
    (dossier/"manifest_comparaison.json").write_text(json.dumps(manifeste,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return resume


def principal():
    p = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--simulation",required=True,type=Path)
    p.add_argument("--mesure",required=True,nargs="+",type=Path)
    p.add_argument("--sortie",required=True,type=Path)
    p.add_argument("--plan-mesure",required=True)
    p.add_argument("--plan-simulation",default=PLAN_SIMULATION)
    args = p.parse_args()
    try:
        comparer(args.simulation,args.mesure,args.sortie,args.plan_mesure,args.plan_simulation)
    except (ValueError,OSError) as exc:
        p.error(str(exc))
    print("Comparaison descriptive : "+str((args.sortie/"resultats.json").resolve()))
    print("Superposition : "+str((args.sortie/"comparaison_s11.png").resolve()))


if __name__ == "__main__":
    principal()
