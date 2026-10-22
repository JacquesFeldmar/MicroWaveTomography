"""Selection explicite de calculs de convergence, avec historique conserve.

Aucun calcul FDTD n'est execute et aucun seuil de qualifie_pcbway n'est modifie.
Le fichier BASE/selection_qualification.json suit ce schema :

  {"schema": "selection_qualification_pcbway_v1", "antennes": {
    "diamant_uwb": {
      "spatial": ["base_16ns", "fin_16ns"],
      "temporel": ["fin_12ns", "fin_16ns"], "reference": "fin_16ns",
      "preliminaires": [
        {"type": "spatial", "calculs": ["base_8ns", "fin_8ns"],
         "motif": "Premiere comparaison spatiale"},
        {"type": "temporel", "calculs": ["fin_8ns", "fin_12ns"],
         "motif": "La fenetre 8 ns ne satisfait pas les criteres initiaux"}]}}}

Une antenne omise conserve le protocole standard base8/fin8 puis fin8/fin12.
La selection effective est inscrite dans chaque resultat. Le mode ecrire=False
verifie les sorties deja produites et ne les repare jamais.
Chaque comparaison temporelle prolonge d'au moins 4 ns. La reference ne peut
preceder un profil preliminaire; une adaptation a la duree initiale de 12 ns
requiert un raffinement spatial effectif du niveau fin. Lors d'une relecture
deplacee, seul l'ancien prefixe local du chemin reference est neutralise.

Preparer et valider un BROUILLON hors de BASE, sans calcul :
  python qualification_adaptative.py --creer-selection brouillon_20ns.json \
      --adapter vivaldi_tomographie --duree-ns 20 --depuis-ns 16 \
      --motif "Sensibilite temporelle a mesurer avec une fenetre plus longue"
  python qualification_adaptative.py --valider-selection brouillon_20ns.json
Une option --selection-source permet de prolonger une selection precedente.
La creation refuse tout fichier existant. Elle ne predeclare aucun resultat.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import numpy as np

import qualifie_pcbway as Q


FICHIER_SELECTION = "selection_qualification.json"
SCHEMA_SELECTION = "selection_qualification_pcbway_v1"
INTERVALLE_TEMPOREL_MIN_NS = Decimal("4")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def profil(nom):
    """Un seul nom de dossier, niveau connu et duree decimale positive finie."""
    niveaux = "|".join(re.escape(k) for k in sorted(Q.NIVEAUX,key=len,reverse=True))
    expression = rf"(?P<niveau>{niveaux})_(?P<duree>(?:0|[1-9][0-9]*)(?:\.[0-9]+)?)ns"
    m = re.fullmatch(expression,nom) if isinstance(nom,str) else None
    if m is None:
        raise ValueError(f"profil de calcul invalide : {nom!r}")
    duree = float(m.group("duree"))
    if not np.isfinite(duree) or duree <= 0:
        raise ValueError(f"duree du profil non positive ou non finie : {nom}")
    return m.group("niveau"),duree


def selection_standard():
    return dict(spatial=["base_8ns","fin_8ns"],temporel=["fin_8ns","fin_12ns"],
                reference="fin_12ns",preliminaires=[])


def _duree_exacte(nom):
    profil(nom)
    return Decimal(nom.rsplit("_",1)[1][:-2])


def _raffinement(grossier,fin):
    a,b = Q.NIVEAUX[grossier],Q.NIVEAUX[fin]
    return (a != b and a["mailles_par_lambda"] <= b["mailles_par_lambda"] and
            a["mailles_par_lambda_air"] <= b["mailles_par_lambda_air"] and
            a["maille_min"] >= b["maille_min"])


def _paire(type_,noms):
    if type_ not in ("spatial","temporel") or not isinstance(noms,list) or len(noms) != 2:
        raise ValueError("une paire spatiale/temporelle de deux profils est requise")
    a,b = (profil(n) for n in noms)
    if noms[0] == noms[1]:
        raise ValueError("deux calculs distincts sont requis")
    if type_ == "spatial":
        if a[1] != b[1]:
            raise ValueError("comparaison spatiale a duree identique requise")
        if not _raffinement(a[0],b[0]):
            raise ValueError("la paire spatiale doit raffiner effectivement le maillage")
    else:
        if a[0] != b[0] or a[1] >= b[1]:
            raise ValueError("comparaison temporelle : meme niveau et durees strictement croissantes requis")
        # Comparaison decimale exacte : un JSON 11.999->12 ns n'est pas un
        # prolongement suffisant, et 14.9->18.9 ne depend pas d'un arrondi binaire.
        if _duree_exacte(noms[1])-_duree_exacte(noms[0]) < INTERVALLE_TEMPOREL_MIN_NS:
            raise ValueError("comparaison temporelle : prolongement minimal de 4 ns requis")
    return a,b


def _selection_effective(spec):
    if not isinstance(spec,dict) or set(spec)-{"spatial","temporel","reference","preliminaires"}:
        raise ValueError("cles de selection inconnues ou selection non objet")
    if not {"spatial","temporel","reference"} <= set(spec):
        raise ValueError("spatial, temporel et reference explicites requis")
    out = deepcopy(spec)
    out.setdefault("preliminaires",[])
    spatial = _paire("spatial",out["spatial"])
    temporel = _paire("temporel",out["temporel"])
    reference = profil(out["reference"])
    if out["temporel"][1] != out["reference"]:
        raise ValueError("la reference doit etre le calcul temporel le plus long")
    if spatial[1][0] != reference[0] or temporel[0][0] != reference[0]:
        raise ValueError("niveau fin spatial, temporel et reference doivent etre identiques")
    if out["spatial"][1] not in out["temporel"]:
        raise ValueError("comparaisons deconnectees : le profil fin spatial doit appartenir a la paire temporelle")
    if not isinstance(out["preliminaires"],list):
        raise ValueError("liste d'essais preliminaires requise")
    vus = set()
    for essai in out["preliminaires"]:
        if not isinstance(essai,dict) or set(essai) != {"type","calculs","motif"}:
            raise ValueError("essai preliminaire : type, calculs et motif seuls sont requis")
        _paire(essai["type"],essai["calculs"])
        if not isinstance(essai["motif"],str) or not essai["motif"].strip():
            raise ValueError("motif explicite de l'essai preliminaire requis")
        cle = (essai["type"],tuple(essai["calculs"]))
        if cle in vus:
            raise ValueError("essai preliminaire duplique")
        vus.add(cle)
    standard = selection_standard()
    adapte = any(out[k] != standard[k] for k in ("spatial","temporel","reference"))
    historiques = {(t,tuple(standard[t])) for t in ("spatial","temporel")}
    if adapte and not historiques <= vus:
        raise ValueError("une adaptation doit conserver les deux essais initiaux dans les preliminaires")
    duree_reference = _duree_exacte(out["reference"])
    if any(_duree_exacte(p) > duree_reference for e in out["preliminaires"] for p in e["calculs"]):
        raise ValueError("la reference ne peut etre plus courte qu'un calcul preliminaire")
    duree_initiale = _duree_exacte(standard["reference"])
    if adapte and duree_reference <= duree_initiale:
        niveau_initial = profil(standard["reference"])[0]
        if duree_reference != duree_initiale or not _raffinement(niveau_initial,reference[0]):
            raise ValueError("une adaptation doit prolonger la reference initiale, ou raffiner son niveau fin a 12 ns")
    return out


def _objet_unique(paires):
    out = {}
    for cle,valeur in paires:
        if cle in out:
            raise ValueError("cle JSON dupliquee dans la selection : "+cle)
        out[cle] = valeur
    return out


def lire_selection(base):
    return lire_fichier_selection(Path(base)/FICHIER_SELECTION)


def _normalise_configuration(cfg):
    if not isinstance(cfg,dict) or set(cfg) != {"schema","antennes"} or cfg["schema"] != SCHEMA_SELECTION:
        raise ValueError("schema de selection de qualification inconnu")
    if not isinstance(cfg["antennes"],dict) or set(cfg["antennes"])-set(Q.ANTENNES):
        raise ValueError("antenne inconnue dans la selection")
    return {nom:_selection_effective(cfg["antennes"].get(nom,selection_standard())) for nom in Q.ANTENNES}


def lire_fichier_selection(chemin):
    """Validation structurelle uniquement, sans charger les resultats FDTD."""
    chemin = Path(chemin)
    octets = chemin.read_bytes()
    cfg = json.loads(octets.decode("utf-8-sig"),object_pairs_hook=_objet_unique)
    effectives = _normalise_configuration(cfg)
    return cfg,effectives,hashlib.sha256(octets).hexdigest(),octets


def proposer_selection(antenne,duree_ns,depuis_ns,motif,selection_source=None):
    """Propose un prolongement documente sans presumer de sa reussite.

    La source est un objet JSON valide ou None pour les selections standard.
    Tous les essais precedents sont conserves. Un palier temporel intermediaire
    est declare lorsqu'il separe la precedente reference du nouveau depart.
    """
    if antenne not in Q.ANTENNES or not isinstance(motif,str) or not motif.strip():
        raise ValueError("antenne connue et motif explicite requis")
    if not np.isfinite(duree_ns) or not np.isfinite(depuis_ns) or not 0 < depuis_ns < duree_ns:
        raise ValueError("durees de depart/cible positives, finies et croissantes requises")
    cfg = (dict(schema=SCHEMA_SELECTION,antennes={}) if selection_source is None
           else deepcopy(selection_source))
    selections = _normalise_configuration(cfg)
    avant = selections[antenne]
    niveau,ancienne_duree = profil(avant["reference"])
    grossier = profil(avant["spatial"][0])[0]
    if duree_ns <= ancienne_duree:
        raise ValueError("la cible doit prolonger la reference precedente")
    precedent = deepcopy(avant["preliminaires"])

    def ajoute(type_,calculs,texte):
        if not any(e["type"] == type_ and e["calculs"] == calculs for e in precedent):
            precedent.append(dict(type=type_,calculs=list(calculs),motif=texte))

    for type_ in ("spatial","temporel"):
        ajoute(type_,avant[type_],motif.strip()+" ; essai anterieur conserve")
    if depuis_ns > ancienne_duree:
        ajoute("temporel",[avant["reference"],f"{niveau}_{depuis_ns:g}ns"],
               motif.strip()+" ; palier temporel intermediaire a evaluer")
    apres = dict(spatial=[f"{grossier}_{duree_ns:g}ns",f"{niveau}_{duree_ns:g}ns"],
        temporel=[f"{niveau}_{depuis_ns:g}ns",f"{niveau}_{duree_ns:g}ns"],
        reference=f"{niveau}_{duree_ns:g}ns",preliminaires=precedent)
    selections[antenne] = _selection_effective(apres)
    return dict(schema=SCHEMA_SELECTION,antennes=selections)


def creer_selection(chemin,configuration):
    """Ecrit un fichier neuf uniquement; refuse les campagnes en cours.

    Cette fonction ne lance ni ne qualifie un calcul. Une cible dans le dossier
    reel BASE est protegee tant qu'un manifeste de calcul y est actif.
    """
    _normalise_configuration(configuration)
    chemin = Path(chemin).resolve()
    if chemin.is_relative_to(Path(Q.BASE).resolve()):
        for p in Path(Q.BASE).rglob("simulation_manifest.json"):
            m = json.loads(p.read_text(encoding="utf-8"))
            if m.get("etat") in ("prepare","calcul_en_cours","derivation_en_cours"):
                raise ValueError("campagne en cours : conserver la selection comme brouillon hors BASE")
    chemin.parent.mkdir(parents=True,exist_ok=True)
    with chemin.open("xb") as out:
        out.write(Q.G.json_octets(configuration))
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _profils_selection(spec):
    ordre = []
    for noms in [*(e["calculs"] for e in spec["preliminaires"]),spec["spatial"],spec["temporel"],[spec["reference"]]]:
        for nom in noms:
            if nom not in ordre:
                ordre.append(nom)
    ordre.remove(spec["reference"])
    ordre.append(spec["reference"])
    return ordre


def calculs_utilises(bilan,nom):
    """Profils uniques preuves incluses, ou les trois profils de l'ancien Q."""
    resultat = bilan["antennes"][nom]
    if "calculs_utilises" not in resultat:
        return ["base_8ns","fin_8ns","fin_12ns"]
    profils = resultat["calculs_utilises"]
    if (not isinstance(profils,list) or not profils or
            not all(isinstance(p,str) for p in profils) or len(set(profils)) != len(profils)):
        raise ValueError("liste de calculs utilises vide ou dupliquee")
    for p in profils:
        profil(p)
    if _profil_reference(resultat["reference"]) not in profils:
        raise ValueError("reference absente des calculs utilises")
    return list(profils)


def _grilles_temporelles(noms,chemins):
    """Les resumes et dt ne remplacent pas les coordonnees NPZ effectives."""
    Q.verifie_grilles_temporelles([chemins[n] for n in noms])


def _mesure_ecarts(type_,noms,donnees,chemins):
    a,b = (donnees[n] for n in noms)
    if type_ == "temporel":
        if a[2]["maillage"] != b[2]["maillage"]:
            raise ValueError("la comparaison temporelle doit conserver le meme maillage")
        if a[2]["execution"]["dt_s"] != b[2]["execution"]["dt_s"]:
            raise ValueError("la comparaison temporelle doit conserver le meme pas temporel")
        _grilles_temporelles(noms,chemins)
    return Q.ecarts(a[0],a[1],b[0],b[1],temporel=type_ == "temporel")


def _profil_reference(reference,attendu=None):
    """Neutralise seulement l'ancien prefixe de chemin d'une reference valide."""
    if not isinstance(reference,str):
        raise ValueError("chemin de reference textuel requis")
    nom = reference.replace("\\","/").rstrip("/").rsplit("/",1)[-1]
    profil(nom)
    if attendu is not None and nom != attendu:
        raise ValueError("profil de reference different de la selection")
    return nom


def _resultat_sans_reference_locale(resultat,attendu):
    copie = deepcopy(resultat)
    copie["reference"] = _profil_reference(copie["reference"],attendu)
    return copie


def _bilan_sans_reference_locale(bilan,effectives):
    copie = deepcopy(bilan)
    if set(copie["antennes"]) != set(effectives):
        raise ValueError("antennes du bilan differentes de la selection")
    copie["antennes"] = {nom:_resultat_sans_reference_locale(r,effectives[nom]["reference"])
                         for nom,r in copie["antennes"].items()}
    return copie


def _reference(base,nom,spec,donnees,resultat,ecrire):
    sortie = base/nom/"comparaison"
    f,s = donnees[spec["reference"]][:2]
    z = 50*(1+s)/(1-s)
    colonnes = np.column_stack([f,s.real,s.imag,20*np.log10(np.maximum(np.abs(s),1e-15)),z.real,z.imag])
    if ecrire:
        sortie.mkdir(exist_ok=True)
        Q.figures(nom,[(p,*donnees[p][:2]) for p in resultat["calculs_utilises"]],sortie)
        np.savetxt(sortie/"reference_simulation.csv",colonnes,delimiter=",",
            header="f_Hz,S11_re,S11_im,S11_dB,Z_re_ohm,Z_im_ohm",comments="# ")
        Q.F.ecrit_s1p(str(sortie/"reference_simulation.s1p"),f,s,
            commentaire="PCB de production; port ideal au bord PCB; voir qualification JSON")
    fc,sc = Q.lit_s1p(str(sortie/"reference_simulation.s1p"))
    csv = np.loadtxt(sortie/"reference_simulation.csv",delimiter=",",comments="#")
    if (not np.array_equal(fc,f) or not np.allclose(sc,s,rtol=2e-12,atol=2e-13) or
            csv.shape != colonnes.shape or not np.allclose(csv,colonnes,rtol=2e-12,atol=2e-13)):
        raise ValueError("reference de comparaison alteree ou differente du calcul selectionne")
    resultat["sorties_sha256"] = {p.relative_to(base).as_posix():_sha(p) for p in (
        sortie/"reference_simulation.s1p",sortie/"reference_simulation.csv",sortie/"comparaison_convergence.png")}
    if not ecrire:
        precedent = json.loads((sortie/"qualification.json").read_text(encoding="utf-8"))
        if (Q.G.json_octets(_resultat_sans_reference_locale(precedent,spec["reference"])) !=
                Q.G.json_octets(_resultat_sans_reference_locale(resultat,spec["reference"]))):
            raise ValueError("qualification ou sorties alterees depuis la generation")
    else:
        Q.sauve(sortie/"qualification.json",resultat)


def comparer(base=Q.BASE,ecrire=True):
    """Compare exclusivement les profils declares, avec les seuils Q inchanges."""
    base = Path(base).resolve()
    selection,effectives,sha_cfg,octets_cfg = lire_selection(base)
    bilan = dict(schema="qualification_pcbway_r1",antennes={},tous_reussis=True,
        configuration_sha256={FICHIER_SELECTION:sha_cfg},selection=selection,
        methode="selection explicite et historique preliminaire conserve ; seuils Q inchanges")
    if not ecrire:
        precedent = json.loads((base/"qualification_globale.json").read_text(encoding="utf-8"))
        if (precedent.get("configuration_sha256") != bilan["configuration_sha256"] or
                precedent.get("selection") != selection):
            raise ValueError("configuration de selection modifiee depuis la qualification")
    campagnes = {}
    moteur_campagne = None
    for nom in Q.ANTENNES:
        spec = effectives[nom]
        noms = _profils_selection(spec)
        racine = (base/nom).resolve()
        chemins = {p:(racine/p).resolve() for p in noms}
        if any(not p.is_relative_to(racine) for p in chemins.values()):
            raise ValueError("dossier de calcul hors du repertoire de l'antenne")
        donnees = {}
        for p in noms:
            niveau,duree = profil(p)
            donnees[p] = Q.charge_calcul(chemins[p],exiger_courant=True)
            Q.valide_campagne(donnees[p][2],donnees[p][3],nom,niveau,duree)
            moteur = Q.identite_moteur(donnees[p][2],donnees[p][3])
            if moteur_campagne is None:
                moteur_campagne = moteur
                Q.niveaux_moteur(moteur)
            if moteur != moteur_campagne:
                raise ValueError("melange de moteurs entre calculs ou antennes de la campagne")
        initial = donnees[noms[0]]
        for d in donnees.values():
            if d[3]["geometrie_sha256"] != initial[3]["geometrie_sha256"]:
                raise ValueError("geometries differentes entre calculs retenus ou preliminaires")
            if Q.G.json_octets(d[3]["simulation_contract"]) != Q.G.json_octets(initial[3]["simulation_contract"]):
                raise ValueError("contrats differents entre calculs retenus ou preliminaires")
            if any(d[2][cle] != initial[2][cle] for cle in ("sources_sha256","environnement")):
                raise ValueError("sources/environnement differents entre calculs retenus ou preliminaires")
        campagnes[nom] = (spec,noms,chemins,donnees)
    if moteur_campagne == Q.MOTEUR_F2:
        bilan["moteur"] = Q.MOTEUR_F2
    for nom in Q.ANTENNES:
        spec,noms,chemins,donnees = campagnes[nom]
        final = donnees[spec["reference"]]
        spatial = _mesure_ecarts("spatial",spec["spatial"],donnees,chemins)
        temporel = _mesure_ecarts("temporel",spec["temporel"],donnees,chemins)
        essais = [dict(**deepcopy(e),ecarts=_mesure_ecarts(e["type"],e["calculs"],donnees,chemins))
                  for e in spec["preliminaires"]]
        resultat = dict(spatial=spatial,temporel=temporel,reference=str(chemins[spec["reference"]]),
            geometrie_sha256=final[3]["geometrie_sha256"],indicateurs=Q.indicateurs(final[0],final[1]),
            hypothese_plan=final[3]["simulation_contract"],extinction=Q.extinction(chemins[spec["reference"]]),
            calculs_utilises=noms,selection_effective=deepcopy(spec),essais_preliminaires=essais,
            preuves_sha256={p.relative_to(base).as_posix():_sha(p)
                for dossier in chemins.values() for p in sorted(dossier.rglob("*")) if p.is_file()})
        resultat["reussi"] = bool(spatial["reussi"] and temporel["reussi"] and resultat["indicateurs"]["passivite_numerique"])
        bilan["tous_reussis"] = bool(bilan["tous_reussis"] and resultat["reussi"])
        _reference(base,nom,spec,donnees,resultat,ecrire)
        bilan["antennes"][nom] = resultat
    if (base/FICHIER_SELECTION).read_bytes() != octets_cfg:
        raise ValueError("selection modifiee pendant la qualification")
    if ecrire:
        Q.sauve(base/"qualification_globale.json",bilan)
        print(json.dumps(bilan,ensure_ascii=False,indent=2),flush=True)
    elif (Q.G.json_octets(_bilan_sans_reference_locale(precedent,effectives)) !=
            Q.G.json_octets(_bilan_sans_reference_locale(bilan,effectives))):
        raise ValueError("bilan global altere ou different des calculs recalcules")
    return bilan


if __name__ == "__main__":
    import argparse
    import sys
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",type=Path,default=Q.BASE)
    p.add_argument("--verifier",action="store_true",help="verifie sans ecrire les sorties deja produites")
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--creer-selection",type=Path,help="ecrit un brouillon JSON neuf, sans calcul")
    modes.add_argument("--valider-selection",type=Path,help="validation structurelle d'un JSON, sans calcul")
    p.add_argument("--selection-source",type=Path,help="selection precedente a conserver et prolonger")
    p.add_argument("--adapter",choices=Q.ANTENNES,help="antenne dont prolonger la duree")
    p.add_argument("--duree-ns",type=float)
    p.add_argument("--depuis-ns",type=float)
    p.add_argument("--motif",help="raison documentee du prolongement, sans presumer son resultat")
    args = p.parse_args()
    if args.verifier and (args.creer_selection or args.valider_selection):
        p.error("--verifier concerne uniquement la relecture des resultats")
    if args.valider_selection and (args.adapter or args.selection_source or args.duree_ns is not None or args.depuis_ns is not None or args.motif):
        p.error("--valider-selection n'accepte pas d'options de prolongement")
    try:
        if args.creer_selection:
            if not args.adapter or args.duree_ns is None or args.depuis_ns is None or not args.motif:
                p.error("--creer-selection exige --adapter, --duree-ns, --depuis-ns et --motif")
            source = lire_fichier_selection(args.selection_source)[0] if args.selection_source else None
            cfg = proposer_selection(args.adapter,args.duree_ns,args.depuis_ns,args.motif,source)
            sha = creer_selection(args.creer_selection,cfg)
            print(json.dumps(dict(fichier=str(args.creer_selection.resolve()),sha256=sha,
                validation_structurelle_uniquement=True),ensure_ascii=False))
            sys.exit(0)
        if args.valider_selection:
            cfg,effectives,sha,_ = lire_fichier_selection(args.valider_selection)
            print(json.dumps(dict(validation_structurelle_uniquement=True,sha256=sha,
                calculs_utilises={nom:_profils_selection(s) for nom,s in effectives.items()}),
                ensure_ascii=False,indent=2))
            sys.exit(0)
        if args.adapter or args.selection_source or args.duree_ns is not None or args.depuis_ns is not None or args.motif:
            p.error("les options de prolongement exigent --creer-selection")
        sys.exit(0 if comparer(args.base,ecrire=not args.verifier)["tous_reussis"] else 2)
    except (OSError,ValueError) as exc:
        p.error(str(exc))
