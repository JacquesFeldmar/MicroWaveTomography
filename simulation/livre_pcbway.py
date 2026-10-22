"""Prepare une livraison PCBWay neuve UNIQUEMENT apres qualification reussie.

    python -B -Xutf8 livre_pcbway.py --base resultats/pcbway_r1 \
        --sortie livraison_pcbway/revision_r1

Ne lance aucun solveur, ne modifie pas la campagne et n'envoie rien a PCBWay.
Les controles numeriques sont recalcules par qualifie_pcbway en lecture seule.
Les ZIP verifies sont copies octet pour octet, jamais regeneres ici.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

import export_gerber as G
import qualifie_pcbway as Q
import verifie_gerber as V

RACINE = Path(__file__).resolve().parent
CALCULS = ("base_8ns", "fin_8ns", "fin_12ns")
SORTIES = ("reference_simulation.s1p", "reference_simulation.csv",
           "comparaison_convergence.png")
REFERENCES = ("cinch_catalogue.pdf", "sma_cinch_142-0701-851.pdf",
              "S1000H_fiche_PCBWay.pdf", "cinch_implantation.png", "sma_cinch_plan.png")
GUIDES = ("README.md", "CONTROLE_RECEPTION.md", "VERIFICATION_EMPREINTE_SMA.md",
          "instructions_pcbway_anglais.txt")
MANIFESTE = "manifest_sha256.json"


def _sha(chemin):
    h = hashlib.sha256()
    with Path(chemin).open("rb") as f:
        for bloc in iter(lambda: f.read(1024*1024), b""):
            h.update(bloc)
    return h.hexdigest()


def _json(chemin):
    return json.loads(Path(chemin).read_text(encoding="utf-8-sig"))


def _relatif_sur(nom):
    if (not isinstance(nom, str) or not nom or "\\" in nom or ":" in nom or
            PurePosixPath(nom).is_absolute() or any(p in ("", ".", "..")
            for p in nom.split("/"))):
        raise ValueError("chemin relatif interdit : " + repr(nom))
    return PurePosixPath(nom)


def _fichier_sur(racine, nom):
    relatif = _relatif_sur(nom)
    chemin = Path(racine).joinpath(*relatif.parts)
    if (chemin.is_symlink() or not chemin.is_file() or
            not chemin.resolve().is_relative_to(Path(racine).resolve())):
        raise ValueError("fichier absent ou hors du perimetre : " + str(chemin))
    # Also reject directory links, including links that point back inside.
    if any(p.is_symlink() for p in [chemin, *chemin.parents]
           if p != Path(racine).parent and p.is_relative_to(Path(racine))):
        raise ValueError("lien symbolique interdit : " + str(chemin))
    return chemin


def _profils_calculs(bilan, antenne):
    """Use the adaptive module's selection contract; retain the original fallback."""
    resultat = bilan["antennes"][antenne]
    if "calculs_utilises" in resultat:
        import qualification_adaptative as A
        profils = A.calculs_utilises(bilan, antenne)
    else:
        profils = list(CALCULS)
    if (not isinstance(profils, (list, tuple)) or not profils or
            any(not isinstance(p, str) or len(_relatif_sur(p).parts) != 1 for p in profils) or
            len(set(profils)) != len(profils)):
        raise ValueError("profils de qualification invalides ou dupliques : " + antenne)
    return list(profils)


def _reference_profil(bilan, antenne):
    reference = bilan["antennes"][antenne].get("reference")
    if not isinstance(reference, str):
        raise ValueError("reference de qualification absente : " + antenne)
    profil = reference.replace("\\", "/").rstrip("/").split("/")[-1]
    if profil not in _profils_calculs(bilan, antenne):
        raise ValueError("reference absente des calculs selectionnes : " + antenne)
    return profil


def _fichiers_calculs(base, bilan):
    fichiers = {}
    for antenne in Q.ANTENNES:
        for niveau in _profils_calculs(bilan, antenne):
            dossier = Path(base) / antenne / niveau
            if not dossier.is_dir() or dossier.is_symlink():
                raise ValueError("dossier de calcul absent ou lie : " + str(dossier))
            for f in sorted(dossier.rglob("*")):
                relatif = f.relative_to(base).as_posix()
                if "comparaison" in f.relative_to(dossier).parts:
                    continue
                if f.is_symlink():
                    raise ValueError("lien dans les preuves : " + str(f))
                if f.is_file():
                    fichiers[relatif] = _fichier_sur(base, relatif)
    return fichiers


def _sans_reference_locale(bilan):
    copie = copy.deepcopy(bilan)
    for resultat in copie["antennes"].values():
        # An absolute development path is informative; all actual selections
        # are fixed below and independently reloaded through Q.
        resultat.pop("reference", None)
    return copie


def _verifie_qualification(base):
    chemin = Path(base) / "qualification_globale.json"
    if not chemin.is_file():
        raise ValueError("qualification_globale.json absent : livraison refusee")
    octets = chemin.read_bytes()
    original = json.loads(octets)
    if original.get("tous_reussis") is not True:
        raise ValueError("convergence non reussie : livraison refusee")
    if set(original.get("antennes", {})) != set(Q.ANTENNES):
        raise ValueError("la qualification doit porter sur les trois antennes")
    fichiers = _fichiers_calculs(base, original)
    preuves = {}
    calculs = {}
    configuration = original.get("configuration_sha256", {})
    if not isinstance(configuration, dict):
        raise ValueError("inventaire de configuration invalide")
    adaptatif = any("calculs_utilises" in r for r in original["antennes"].values())
    if adaptatif and not configuration:
        raise ValueError("configuration de selection adaptative absente")
    for relatif, sha in configuration.items():
        fichier = _fichier_sur(base, relatif)
        if _sha(fichier) != sha:
            raise ValueError("configuration SHA-256 alteree : " + relatif)
        preuves[relatif] = sha
    if "selection_qualification.json" in configuration:
        if G.json_octets(_json(Path(base) / "selection_qualification.json")) != G.json_octets(original.get("selection")):
            raise ValueError("instantane de selection different de la configuration archivee")
    for nom in Q.ANTENNES:
        resultat = original["antennes"][nom]
        if resultat.get("reussi") is not True:
            raise ValueError("qualification non reussie : " + nom)
        inventaire = resultat.get("preuves_sha256", {})
        propres = {p: f for p, f in fichiers.items() if PurePosixPath(p).parts[0] == nom}
        if not inventaire or set(inventaire) != set(propres):
            raise ValueError("inventaire des preuves incomplet ou excedentaire : " + nom)
        for relatif, sha in inventaire.items():
            fichier = _fichier_sur(base, relatif)
            if _sha(fichier) != sha:
                raise ValueError("preuve SHA-256 alteree : " + relatif)
            preuves[relatif] = sha
        carte = G.carte_antenne(nom)
        _reference_profil(original, nom)
        for niveau in _profils_calculs(original, nom):
            dossier = Path(base) / nom / niveau
            _, _, manifeste, entree = Q.charge_calcul(dossier, exiger_courant=True)
            # The explicit comparison also records the bridge to the Gerber
            # canonical representation, rather than trusting a folder name.
            if (G.json_octets(entree["geometrie"]) != G.json_octets(G.geometrie_canonique(carte)) or
                    G.json_octets(entree["simulation_contract"]) !=
                    G.json_octets(carte["simulation_contract"])):
                raise ValueError("geometrie/contrat differents des sources courantes : " + str(dossier))
            calculs[f"{nom}/{niveau}"] = dict(
                geometrie_sha256=entree["geometrie_sha256"],
                signature_physique=entree["signature_physique"],
                contrat_sha256=hashlib.sha256(G.json_octets(entree["simulation_contract"])).hexdigest(),
                sources_sha256=manifeste["sources_sha256"])
    # Q owns the acceptance thresholds, actual grid/duration checks and metrics.
    # Never duplicate those formulas here and never call a solver.
    recalcule = Q.comparer(base=base, ecrire=False)
    if recalcule.get("tous_reussis") is not True:
        raise ValueError("recalcul des criteres de convergence en echec")
    if G.json_octets(_sans_reference_locale(original)) != G.json_octets(_sans_reference_locale(recalcule)):
        raise ValueError("qualification enregistree differente de sa verification actuelle")
    sorties = {}
    for nom in Q.ANTENNES:
        resultat = original["antennes"][nom]
        repertoire = Path(base) / nom / "comparaison"
        inventaire = resultat.get("sorties_sha256", {})
        # Q records all paths relative to the campaign root.
        if set(inventaire) != {f"{nom}/comparaison/{f}" for f in SORTIES}:
            raise ValueError("empreintes des courbes de qualification absentes ou incompletes : " + nom)
        for relatif, sha in inventaire.items():
            fichier = _fichier_sur(base, relatif)
            if _sha(fichier) != sha:
                raise ValueError("courbe de qualification alteree : " + nom + "/" + relatif)
            sorties[relatif] = sha
        q = _fichier_sur(repertoire, "qualification.json")
        if G.json_octets(_json(q)) != G.json_octets(resultat):
            raise ValueError("qualification individuelle differente du bilan global : " + nom)
        sorties[f"{nom}/comparaison/qualification.json"] = _sha(q)
    return original, preuves, sorties, calculs, hashlib.sha256(octets).hexdigest()


def _copie_verifiee(source, destination, sha):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if _sha(destination) != sha:
        raise ValueError("fichier modifie pendant la preparation : " + str(source))


def _verifie_panneau(carte):
    """Bridge the panel's translated copper/contracts to the three qualified cards."""
    noms = ("diamant_uwb", "diamant_uwb_x18")
    composants = [G.carte_antenne(nom) for nom in noms]
    contrat = carte["simulation_contract"]
    if G.json_octets(contrat["antennes"]) != G.json_octets(
            [c["simulation_contract"] for c in composants]):
        raise ValueError("contrats des composants du panneau differents des antennes qualifiees")
    for couche in ("F_Cu", "B_Cu"):
        attendus = []
        for nom, composant in zip(noms, composants):
            dx, dy = contrat["transformations_mm"][nom]
            attendus.extend([[(float(x)+dx, float(y)+dy) for x, y in poly]
                             for poly in composant[couche]])
        if G.json_octets(attendus) != G.json_octets(carte[couche]):
            raise ValueError("cuivre du panneau different des composants translates : " + couche)
    vias = []
    for nom, composant in zip(noms, composants):
        dx, dy = contrat["transformations_mm"][nom]
        vias.extend([(x+dx, y+dy, d) for x, y, d in composant.get("vias", [])])
        if composant["epaisseur"] != carte["epaisseur"]:
            raise ValueError("epaisseur du panneau differente des composants")
    if G.json_octets(vias) != G.json_octets(carte.get("vias", [])):
        raise ValueError("vias du panneau differents des composants translates")


def _archive_preuves(base, preuves, destination):
    """Store exact run snapshots with safe relative names, streamed and hashed."""
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=True) as z:
        for relatif, sha in sorted(preuves.items()):
            _relatif_sur(relatif)
            info = zipfile.ZipInfo(relatif, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            h = hashlib.sha256()
            with _fichier_sur(base, relatif).open("rb") as source, z.open(info, "w") as cible:
                for bloc in iter(lambda: source.read(1024*1024), b""):
                    h.update(bloc)
                    cible.write(bloc)
            if h.hexdigest() != sha:
                raise ValueError("preuve modifiee pendant archivage : " + relatif)
        info = zipfile.ZipInfo("index_preuves_sha256.json", date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        z.writestr(info, G.json_octets(preuves), compresslevel=9)


def _readme(bilan, articles, avec_pdf=False):
    nombre_calculs = sum(len(_profils_calculs(bilan, nom)) for nom in Q.ANTENNES)
    lignes = ["# Livraison PCBWay - revision physique r1", "",
        "Cette livraison associe deux fichiers de commande aux trois antennes de la meme revision.",
        "Les criteres de convergence de la campagne ont ete recalcules avec succes avant copie.",
        "Ils qualifient le calcul dans ses hypotheses ; l'accord aux antennes fabriquees reste a mesurer.", "",
        "## Les deux depots PCBWay", "",
        "| Article | ZIP a deposer | Dimensions de decoupe, mm | Commande |", "|---|---|---|---|"]
    if avec_pdf:
        lignes[5:5] = ["", "[Bilan detaille en PDF](documentation/bilan_qualification_pcbway_r1.pdf)", ""]
    for a in articles:
        largeur, hauteur = a["dimensions_source_mm"]
        commande = ("5 panneaux ; 2 different designs ; Panel by Customer" if a["produit"] == "panneau_losanges"
                    else "5 cartes ; 1 design ; Single pieces")
        fichier = a["zip"]
        lignes.append(f"| {a['article']} | [{Path(fichier).name}]({fichier}) | {largeur:.6f} x {hauteur:.6f} | {commande} |")
    lignes += ["", "Options communes : S1000H TG150, 2 couches, 1,6 mm nominal, cuivre 1 oz, ENIG, masque None, serigraphie None.",
        "Les notices dans uploads/ et le guide dans documentation/fabrication/ decrivent les perçages PTH/NPTH et les exigences CAM.",
        "Les cotes correspondent a la ligne mediane du contour, sans ajouter sa largeur de trait.", "",
        "## Reference S11 de cette revision", "",
        "Les deux losanges sont simules separes du panneau, apres arasage des pontets.",
        "Chaque dessin dispose de sa reference retenue : S11 complexe, CSV, graphique et qualification individuelle dans simulations/<antenne>/.",
        "Les fenetres temporelles de ces comparaisons ont ete controlees sur les sondes et le pas de temps reel par la qualification.", "",
        "| Antenne | Reference retenue | Comparaison spatiale | Comparaison temporelle | Dossiers conserves |",
        "|---|---|---|---|---|"]
    for nom in Q.ANTENNES:
        resultat = bilan["antennes"][nom]
        if "calculs_utilises" in resultat:
            selection = resultat.get("selection_effective") or bilan["selection"]["antennes"][nom]
            spatial, temporel = selection["spatial"], selection["temporel"]
        else:
            spatial, temporel = list(CALCULS[:2]), list(CALCULS[1:])
        profils = _profils_calculs(bilan, nom)
        lignes.append(f"| {nom} | {_reference_profil(bilan, nom)} | {' / '.join(spatial)} | "
                      f"{' / '.join(temporel)} | {', '.join(profils)} |")
    preliminaires = [nom for nom in Q.ANTENNES
                     if bilan["antennes"][nom].get("essais_preliminaires")]
    if preliminaires:
        lignes += ["", "Des essais preliminaires sont conserves pour " + ", ".join(preliminaires) +
                   ". Leurs ecarts et motifs restent dans les JSON ; ils ne remplacent pas les comparaisons finales acceptees."]
        for nom in preliminaires:
            for essai in bilan["antennes"][nom]["essais_preliminaires"]:
                statut = ("comparaison insuffisante" if essai["ecarts"].get("reussi") is False
                          else "diagnostic conserve")
                lignes.append(f"- {nom}, {essai['type']} : {' / '.join(essai['calculs'])} ; "
                              f"{statut} ; {essai['motif']}.")
    lignes += ["",
        "Les pourcentages ci-dessous comptent les points sous le seuil sur 1,4-6,0 GHz, sans masquer les interruptions.", "",
        "| Antenne | Sous -10 dB | Sous -6 dB | Puissance reflechie moyenne, dB | Pire S11, dB |", "|---|---|---|---|---|"]
    for nom in Q.ANTENNES:
        i = bilan["antennes"][nom]["indicateurs"]["bande_1p4_6"]
        lignes.append(f"| {nom} | {100*i['moins_10_db']['couverture']:.2f} % | "
                      f"{100*i['moins_6_db']['couverture']:.2f} % | "
                      f"{i['moyenne_puissance_reflechie_db']:.3f} | {i['pire_db']:.3f} |")
    lignes += ["", "Les segments de frequence et criteres detailles sont conserves dans les JSON de qualification.",
        "Aucun seuil d'adaptation minimum n'est ajoute ici aux criteres numeriques de la campagne.", "",
        "## Comparaison aux cartes produites", "",
        "Les trois cartes recoivent la SMA femelle Cinch/Johnson 142-0701-851.",
        "Le calcul comprend l'implantation cuivre et des vias equivalents, avec un port ideal au bord du PCB.",
        "Le corps coaxial SMA, sa broche, le PTFE, la soudure et la finition ENIG ne sont pas modelises integralement.",
        "Le plan coaxial de calibration VNA doit etre distingue du plan simule.",
        "Suivre [le protocole de mesure](documentation/PROTOCOLE_MESURE_PCBWAY.md) et les controles de reception.", "",
        "Depuis la racine de cette livraison, comparer une future mesure sans ajuster de retard :", "",
        "```powershell",
        "python -B -Xutf8 sources_outils/compare_s11.py --simulation simulations/vivaldi_tomographie/reference_simulation.s1p --mesure chemin/vers/mesure_V01.s1p --sortie ../comparaison_V01 --plan-mesure 'SOL interface SMA du cable ; carte V01 ; aucune extension de port'",
        "```", "",
        "Remplacer le chemin de mesure et decrire le plan reel ; choisir un dossier de sortie externe neuf ou vide.",
        "Le [mode d'emploi du comparateur](documentation/compare_s11_usage.md) et le protocole precisent les grilles et les limites de comparaison.", "",
        "## Tracabilite et reproduction", "",
        "qualification_globale.json conserve le bilan original verifie ; les chemins de developpement qu'il contient sont historiques.",
        f"preuves_calculs.zip contient les {nombre_calculs} dossiers de calcul enumeres ci-dessus, avec leurs sources, XML, grilles et sondes.",
        "Toute configuration explicite de selection est archivee avec son SHA-256 pour conserver le choix des comparaisons et les essais preliminaires.",
        "Les repertoires comparaison/ sont exclus de cette archive pour eviter toute inclusion recursive.",
        "Les outils courants sont dans sources_outils/ ; les sources effectivement utilisees restent dans chaque calcul archive.",
        "Le mode d'emploi du comparateur est conserve dans documentation/, a cote du protocole auquel il renvoie.",
        "Les manifestes conservent l'environnement logiciel et les configurations de calcul.",
        "Extraire les preuves dans un dossier de travail pour refaire l'extraction et les criteres ; aucun solveur n'a ete relance lors de la livraison.", "",
        "```powershell", "Expand-Archive -LiteralPath preuves_calculs.zip -DestinationPath ../rejeu_r1/preuves",
        "python -B -Xutf8 sources_outils/qualifie_pcbway.py --base ../rejeu_r1/preuves --comparer", "```", "",
        "Utiliser l'environnement scientifique documente dans les manifestes (NumPy, SciPy, Matplotlib et, pour CalcPort, openEMS/CSXCAD).",
        "manifest_sha256.json couvre tous les fichiers livres, sauf lui-meme. Ne pas modifier le dossier remis.", ""]
    return "\n".join(lignes)


def _documentation_liee(chemin):
    """Keep copied project guides usable at their new location in the delivery."""
    chemin = Path(chemin)
    texte = chemin.read_text(encoding="utf-8")
    fabrication = chemin.parent.name == "fabrication"
    if fabrication:
        texte = texte.replace("](../references/", "](../../references/")
        texte = texte.replace("](../connectique.py)", "](../../sources_outils/connectique.py)")
        for produit in ("panneau_losanges", "vivaldi_tomographie"):
            texte = texte.replace(f"]({produit}/{produit}_pcbway.zip)",
                                  f"](../../uploads/{produit}_pcbway.zip)")
        texte = texte.replace("](inventaire_livraison_courante.json)", "](../../manifest_sha256.json)")
    if (chemin.name in ("PROTOCOLE_MESURE_PCBWAY.md", "compare_s11_usage.md") or
            (fabrication and chemin.name == "README.md")):
        readme = "../../README.md" if fabrication else "../README.md"
        note = ("> **Contexte de cette copie livrée.** Les exemples « depuis simulation/ », "
                "les tests et les outils USB cités concernent le dépôt complet du projet. "
                "Depuis la racine de cette livraison, utiliser les commandes du "
                f"[README portable]({readme}).\n\n")
        texte = note + texte
    return texte.encode("utf-8")


def livre(base=Q.BASE, sortie=None, racine=RACINE):
    """Validate everything first, then publish one new local directory atomically."""
    base, racine = Path(base).resolve(), Path(racine).resolve()
    sortie = Path(sortie or racine / "livraison_pcbway" / "revision_r1").resolve()
    if sortie.exists():
        raise FileExistsError("dossier de livraison deja present : " + str(sortie))
    if sortie.is_relative_to(base) or base.is_relative_to(sortie):
        raise ValueError("la livraison et la campagne ne doivent pas s'imbriquer")
    bilan, preuves, sorties, calculs, sha_bilan = _verifie_qualification(base)
    assets = {"qualification_globale.json": (base / "qualification_globale.json", sha_bilan)}
    # The optional scheduler logs are diagnostic provenance. They remain
    # outside the immutable run payloads and are copied only after validation.
    for dossier in (base/"journaux", base/"controle_orchestration"):
        if dossier.is_dir():
            for f in sorted(dossier.rglob("*")):
                if f.is_file():
                    relatif=f.relative_to(base).as_posix()
                    f=_fichier_sur(base,relatif)
                    assets["documentation/campagne/"+relatif]=(f,_sha(f))
    for nom in ("pipeline_pcbway_statut.json", "etat_orchestration.json",
                "fin_orchestration.json", "orchestration.lock"):
        if (base/nom).is_file():
            statut=_fichier_sur(base,nom)
            assets["documentation/campagne/"+nom]=(statut,_sha(statut))
    validation=racine/"chatGPT_critical_review"/"verification_finale_reprise"
    if validation.is_dir():
        for f in sorted(validation.glob("*")):
            if f.is_file():
                assets["documentation/verification_logicielle/"+f.name]=(f,_sha(f))
    for relatif, sha in sorties.items():
        parties = PurePosixPath(relatif).parts
        destination = PurePosixPath("simulations", parties[0], *parties[2:]).as_posix()
        assets[destination] = (_fichier_sur(base, relatif), sha)
    for nom in REFERENCES:
        f = _fichier_sur(racine, "references/" + nom)
        assets["references/" + nom] = (f, _sha(f))
    for nom in GUIDES:
        f = _fichier_sur(racine, "fabrication/" + nom)
        if f.suffix == ".md":
            contenu = _documentation_liee(f)
            assets["documentation/fabrication/" + nom] = (contenu, hashlib.sha256(contenu).hexdigest())
        else:
            assets["documentation/fabrication/" + nom] = (f, _sha(f))
    f = _fichier_sur(racine, "PROTOCOLE_MESURE_PCBWAY.md")
    contenu = _documentation_liee(f)
    assets["documentation/" + f.name] = (contenu, hashlib.sha256(contenu).hexdigest())
    rapport_pdf = racine / "chatGPT_critical_review" / "bilan_qualification_pcbway_r1.pdf"
    avec_pdf = rapport_pdf.is_file()
    if avec_pdf:
        assets["documentation/" + rapport_pdf.name] = (rapport_pdf, _sha(rapport_pdf))
        constructeur = _fichier_sur(racine, "chatGPT_critical_review/construit_bilan_qualification_pcbway.py")
        assets["sources_outils/construit_bilan_qualification_pcbway.py"] = (constructeur, _sha(constructeur))
    outils = sorted(f for f in racine.glob("*.py") if not f.name.startswith("test_"))
    if any("calculs_utilises" in r for r in bilan["antennes"].values()):
        # This helper is created after the physical runs and therefore is not
        # part of their immutable sources/. It is essential to replay Q's
        # adaptive dispatch and must be present in the delivered tools.
        outils.append(_fichier_sur(racine, "qualification_adaptative.py"))
    outils += sorted((racine / "antennes").glob("*/geometrie.py"))
    outils += [racine / "requirements_fabrication.txt", racine / "requirements_fdtd.txt"]
    if (racine / "requirements_poursuite.txt").is_file():
        outils += [racine / "requirements_poursuite.txt"]
    if (racine / "compare_s11_usage.md").is_file():
        f = _fichier_sur(racine, "compare_s11_usage.md")
        contenu = _documentation_liee(f)
        assets["documentation/compare_s11_usage.md"] = (contenu, hashlib.sha256(contenu).hexdigest())
    for f in outils:
        relatif = f.relative_to(racine).as_posix()
        f = _fichier_sur(racine, relatif)
        assets["sources_outils/" + relatif] = (f, _sha(f))
    articles = []
    with tempfile.TemporaryDirectory(prefix="mwt_livraison_verification_") as controles:
        cartes = (G.carte_panneau_losanges(), G.carte_antenne("vivaldi_tomographie"))
        _verifie_panneau(cartes[0])
        for numero, carte in enumerate(cartes, 1):
            nom = carte["nom"]
            repertoire = racine / "fabrication" / nom
            fichier = _fichier_sur(repertoire, nom + "_pcbway.zip")
            sha = _sha(fichier)
            if not V.verifie(fichier, Path(controles) / nom, attendu=carte, rendus=True)[1]:
                raise ValueError("ZIP de fabrication non conforme : " + nom)
            if _sha(fichier) != sha:
                raise ValueError("ZIP modifie pendant sa verification : " + nom)
            # V compares the full translated panel with G.carte_panneau_losanges,
            # including component geometries/contracts and source SHA-256.
            with zipfile.ZipFile(fichier) as z:
                manifeste = json.loads(z.read(nom + "_manifest.json"))
                notice = z.read(nom + "_lisez_moi.txt")
            largeur, hauteur = G.etendue(carte)
            articles.append(dict(article=numero, produit=nom, zip="uploads/" + fichier.name,
                zip_sha256=sha, geometrie_sha256=manifeste["geometrie_sha256"],
                dimensions_source_mm=[float(largeur), float(hauteur)]))
            assets["uploads/" + fichier.name] = (fichier, sha)
            # Preserve the verification report and real third-party renders.
            for f in (Path(controles) / nom).rglob("*"):
                if f.is_file():
                    assets[f"verification_gerber/{nom}/{f.name}"] = (f, _sha(f))
            # Bytes taken from the independently verified ZIP, not stale loose files.
            assets["uploads/" + nom + "_lisez_moi.txt"] = (notice, hashlib.sha256(notice).hexdigest())
            assets["uploads/" + fichier.name + ".sha256"] = (
                f"{sha}  {fichier.name}\n".encode("ascii"), None)
        sortie.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=sortie.name + ".preparation_", dir=sortie.parent) as temporaire:
            etape = Path(temporaire) / "contenu"
            etape.mkdir()
            for relatif, (source, sha) in sorted(assets.items()):
                destination = etape.joinpath(*_relatif_sur(relatif).parts)
                if isinstance(source, bytes):
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source)
                    if sha and _sha(destination) != sha:
                        raise ValueError("notice extraite modifiee")
                else:
                    _copie_verifiee(source, destination, sha)
            _archive_preuves(base, preuves, etape / "preuves_calculs.zip")
            (etape / "README.md").write_text(_readme(bilan, articles,avec_pdf), encoding="utf-8", newline="\n")
            manifeste = dict(schema="MicroWaveTomography-livraison-PCBWay-r1", articles=articles,
                calculs=calculs, fichiers_sha256={f.relative_to(etape).as_posix(): _sha(f)
                    for f in sorted(etape.rglob("*")) if f.is_file()})
            (etape / MANIFESTE).write_bytes(G.json_octets(manifeste))
            # Revalidate all archived evidence hashes and copied inputs before
            # exposing the destination. A failure leaves no delivery directory.
            verifie_livraison(etape)
            if sortie.exists():
                raise FileExistsError("dossier apparu pendant la preparation : " + str(sortie))
            etape.rename(sortie)
    return sortie


def verifie_livraison(dossier):
    """Read back a prepared delivery and every compressed proof, without writing."""
    dossier = Path(dossier).resolve()
    manifeste = _json(dossier / MANIFESTE)
    inventaire = manifeste["fichiers_sha256"]
    presents = {f.relative_to(dossier).as_posix() for f in dossier.rglob("*")
                if f.is_file() and f.relative_to(dossier).as_posix() != MANIFESTE}
    if not inventaire or set(inventaire) != presents:
        raise ValueError("inventaire de livraison incomplet ou excedentaire")
    for relatif, sha in inventaire.items():
        if _sha(_fichier_sur(dossier, relatif)) != sha:
            raise ValueError("fichier livre altere : " + relatif)
    bilan = _json(dossier / "qualification_globale.json")
    preuves = {p: sha for nom in Q.ANTENNES
               for p, sha in bilan["antennes"][nom]["preuves_sha256"].items()}
    for relatif, sha in bilan.get("configuration_sha256", {}).items():
        _relatif_sur(relatif)
        if relatif in preuves and preuves[relatif] != sha:
            raise ValueError("empreintes de preuve et de configuration contradictoires")
        preuves[relatif] = sha
    with zipfile.ZipFile(dossier / "preuves_calculs.zip") as z:
        if (len(z.namelist()) != len(set(z.namelist())) or
                set(z.namelist()) != set(preuves) | {"index_preuves_sha256.json"} or
                json.loads(z.read("index_preuves_sha256.json")) != preuves):
            raise ValueError("archive de preuves incomplete ou excedentaire")
        for relatif, sha in preuves.items():
            _relatif_sur(relatif)
            h = hashlib.sha256()
            with z.open(relatif) as f:
                for bloc in iter(lambda: f.read(1024*1024), b""):
                    h.update(bloc)
            if h.hexdigest() != sha:
                raise ValueError("preuve livree alteree : " + relatif)
    return True


def principal(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, default=Q.BASE)
    p.add_argument("--sortie", type=Path, default=RACINE / "livraison_pcbway" / "revision_r1")
    args = p.parse_args(argv)
    try:
        resultat = livre(args.base, args.sortie)
    except (ValueError, FileNotFoundError, FileExistsError, KeyError) as e:
        p.exit(2, "Livraison refusee : " + str(e) + "\n")
    print("Livraison locale preparee : " + str(resultat))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
