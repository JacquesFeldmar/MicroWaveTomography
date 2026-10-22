"""Produit le bilan PDF uniquement apres qualification complete de la campagne.

Depuis simulation/ (Python de traitement avec reportlab et pypdf) :
  python -B -X utf8 chatGPT_critical_review/construit_bilan_qualification_pcbway.py \
    --base resultats/pcbway_r1 --sortie chatGPT_critical_review/bilan_pcbway_r1.pdf

Lecture seule des calculs et des archives de fabrication. Aucun solveur et
aucun exportateur ne sont executes. Le bilan est revalide par le meme controle
que la livraison PCBWay, puis les archives sont relues independamment. Une
campagne absente, incomplete, alteree ou non convergee interdit la creation.
Le chemin de sortie doit etre nouveau. Les PDF d'audit existants sont preserves.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import zipfile
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
# A cote des outils dans la livraison autonome, ou dans le dossier de revue
# du depot de travail : choisir la racine par son contenu, pas par sa profondeur.
ICI = Path(__file__).resolve().parent
RACINE = next((p for p in (ICI, ICI.parent)
               if (p / "qualifie_pcbway.py").is_file()), ICI.parent)
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

ANTENNES = ("diamant_uwb", "diamant_uwb_x18", "vivaldi_tomographie")
NOMS = {"diamant_uwb": "Losange ×1", "diamant_uwb_x18": "Losange ×1,8",
        "vivaldi_tomographie": "Vivaldi"}
NOMS_COURTS = {"diamant_uwb": "L ×1", "diamant_uwb_x18": "L ×1,8",
               "vivaldi_tomographie": "Vivaldi"}
CALCULS = ("base_8ns", "fin_8ns", "fin_12ns")


def sha256(chemin):
    h = hashlib.sha256()
    with Path(chemin).open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


def lit_json(chemin):
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def selection_dessin(bilan, nom):
    """Selection explicite par dessin ; compatibilite avec le bilan Q initial."""
    resultat = bilan["antennes"][nom]
    spec = resultat.get("selection_effective")
    if spec is None:
        selection = bilan.get("selection")
        if selection is not None:
            spec = selection.get("antennes", {}).get(nom)
            if spec is None:
                raise ValueError("selection adaptative absente pour " + nom)
        else:
            spec = dict(spatial=list(CALCULS[:2]), temporel=list(CALCULS[1:]),
                        reference=CALCULS[-1], preliminaires=[])
    if not isinstance(spec, dict):
        raise ValueError("selection invalide pour " + nom)
    for cle in ("spatial", "temporel"):
        if not isinstance(spec.get(cle), list) or len(spec[cle]) != 2:
            raise ValueError("paire " + cle + " absente pour " + nom)
    reference = spec.get("reference")
    preliminaires = resultat.get("essais_preliminaires", [])
    requis = [*spec["spatial"], *spec["temporel"], reference]
    for essai in preliminaires:
        if essai.get("type") not in ("spatial", "temporel") or len(essai.get("calculs", [])) != 2:
            raise ValueError("essai preliminaire invalide pour " + nom)
        if essai["ecarts"]["seuils_acceptation"] != resultat[essai["type"]]["seuils_acceptation"]:
            raise ValueError("seuils modifies entre essai preliminaire et final pour " + nom)
        requis.extend(essai["calculs"])
    profils = resultat.get("calculs_utilises", list(dict.fromkeys(requis)))
    if (not isinstance(profils, list) or len(profils) != len(set(profils)) or
            set(profils) != set(requis)):
        raise ValueError("profils de calcul incomplets ou invalides pour " + nom)
    # Le catalogue appartient au qualificateur. Son enregistrement explicite
    # est assure par la chaine de qualification, jamais par ce constructeur.
    import qualification_adaptative as A
    for profil in profils:
        try:
            A.profil(profil)
        except ValueError as erreur:
            raise ValueError("profil de calcul invalide pour " + nom + " : " + repr(profil)) from erreur
    return dict(spatial=spec["spatial"], temporel=spec["temporel"], reference=reference,
                profils=profils, preliminaires=preliminaires)


def charge_dossier(base, fabrication=None):
    """Barriere de production : revalidation sans ecriture dans les entrees."""
    import export_gerber as G
    import livre_pcbway as L
    import verifie_gerber as V

    base = Path(base).resolve()
    chemin_bilan = base / "qualification_globale.json"
    if not chemin_bilan.is_file():
        raise ValueError("qualification_globale.json absent : aucun rapport final produit")
    apercu = lit_json(chemin_bilan)
    if (apercu.get("schema") != "qualification_pcbway_r1" or
            apercu.get("tous_reussis") is not True or
            set(apercu.get("antennes", {})) != set(ANTENNES)):
        raise ValueError("qualification globale incomplete ou non convergee : rapport refuse")
    # Le controle de livraison recalcule les criteres en lecture seule,
    # controle tous les calculs selectionnes et preliminaires, sondes et SHA.
    bilan, _, _, _, sha_bilan = L._verifie_qualification(base)
    calculs = {}
    references = {}
    selections = {}
    for nom in ANTENNES:
        resultat = bilan["antennes"][nom]
        bande = resultat["indicateurs"]["bande_1p4_6"]
        if any(bande[cle]["points_total"] != 185
               for cle in ("moins_10_db", "moins_6_db")):
            raise ValueError("185 points requis sur 1,4-6,0 GHz : " + nom)
        if (resultat["indicateurs"]["points"] != 213 or
                resultat["indicateurs"]["bande_hz"] != [1e9, 6.3e9]):
            raise ValueError("grille de campagne inattendue : " + nom)
        for type_ecart in ("spatial", "temporel"):
            if resultat[type_ecart].get("reussi") is not True:
                raise ValueError("convergence refusee : " + nom + "/" + type_ecart)
        selections[nom] = selection_dessin(bilan, nom)
        calculs[nom] = {profil: lit_json(base / nom / profil / "simulation_manifest.json")
                        for profil in selections[nom]["profils"]}
        dossier = base / nom / "comparaison"
        references[nom] = {"s1p": dossier / "reference_simulation.s1p",
                           "figure": dossier / "comparaison_convergence.png",
                           "sha256": sha256(dossier / "reference_simulation.s1p"),
                           "profil": selections[nom]["reference"]}

    articles = []
    cartes = (G.carte_panneau_losanges(), G.carte_antenne("vivaldi_tomographie"))
    # Controle independant des surfaces et percages. Les rapports transitoires
    # sont confines dans le dossier temporaire, jamais dans fabrication/.
    with tempfile.TemporaryDirectory(prefix="mwt_pdf_cam_") as temporaire:
        for numero, carte in enumerate(cartes, 1):
            produit = carte["nom"]
            nom_zip = produit + "_pcbway.zip"
            if fabrication is None:
                candidats = [RACINE / "fabrication" / produit / nom_zip,
                             RACINE.parent / "uploads" / nom_zip]
            else:
                fab = Path(fabrication).resolve()
                candidats = [fab / produit / nom_zip, fab / nom_zip]
            chemin_zip = next((p for p in candidats if p.is_file()), None)
            if chemin_zip is None:
                raise ValueError("archive de fabrication absente : " +
                                 ", ".join(str(p) for p in candidats))
            sha = sha256(chemin_zip)
            sidecar = chemin_zip.with_suffix(".zip.sha256")
            if not sidecar.is_file() or sidecar.read_text(encoding="ascii").split()[0] != sha:
                raise ValueError("empreinte ZIP absente ou incoherente : " + produit)
            with contextlib.redirect_stdout(io.StringIO()):
                _, conforme = V.verifie(chemin_zip, Path(temporaire) / produit,
                                        attendu=carte, rendus=False)
            if not conforme or sha256(chemin_zip) != sha:
                raise ValueError("relecture Gerber/Excellon en echec : " + produit)
            with zipfile.ZipFile(chemin_zip) as archive:
                manifeste = json.loads(archive.read(produit + "_manifest.json"))
            contrats = manifeste["simulation_contract"].get(
                "antennes", [manifeste["simulation_contract"]])
            for contrat in contrats:
                if G.json_octets(contrat) != G.json_octets(
                        bilan["antennes"][contrat["antenne"]]["hypothese_plan"]):
                    raise ValueError("contrat du ZIP different du calcul : " + produit)
            contours = manifeste["geometrie"]["Edge_Cuts"]
            points = [point for poly in contours for point in poly]
            dimensions = [max(p[i] for p in points) - min(p[i] for p in points)
                          for i in (0, 1)]
            articles.append(dict(numero=numero, produit=produit, chemin=chemin_zip,
                sha256=sha, dimensions_mm=dimensions, manifeste=manifeste))
    return dict(base=base, bilan=bilan, sha_bilan=sha_bilan, calculs=calculs,
                references=references, articles=articles, selections=selections,
                creation=datetime.now(ZoneInfo("Europe/Paris")), qualification_verifiee=True)


def texte(valeur):
    return html.escape(re.sub("[\u2010-\u2015]", "-", str(valeur))
                       .replace("\u00a0", " ").replace("\u202f", " "))


def nombre(valeur, decimales=3):
    if not isinstance(valeur, (int, float)) or not math.isfinite(valeur):
        return "indéfini"
    return f"{valeur:.{decimales}f}".replace(".", ",")


def pourcent(bande):
    return nombre(100 * bande["couverture"], 2) + " %"


def segments(bande):
    # Aucun remplacement par l'enveloppe premiere-derniere frequence.
    return "; ".join(nombre(a / 1e9, 3) + " à " + nombre(b / 1e9, 3)
                     for a, b in bande["segments_hz"]) or "aucun point sous ce seuil"


def polices():
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    dossier = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for nom, fichier in (("PCB", "DejaVuSans.ttf"), ("PCB-Bold", "DejaVuSans-Bold.ttf"),
                          ("PCB-Italic", "DejaVuSans-Oblique.ttf"),
                          ("PCBMono", "DejaVuSansMono.ttf")):
        if nom not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nom, str(dossier / fichier)))
    pdfmetrics.registerFontFamily("PCB", normal="PCB", bold="PCB-Bold",
                                  italic="PCB-Italic", boldItalic="PCB-Bold")


def construit_rapport(dossier, sortie):
    """Rendu pur. Les fixtures internes portent un filigrane explicite."""
    if dossier.get("qualification_verifiee") is not True:
        raise ValueError("dossier non valide par charge_dossier")
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                  TableStyle, PageBreak, Image, KeepTogether)
    polices()
    sortie = Path(sortie).resolve()
    if sortie.suffix.lower() != ".pdf" or sortie.exists():
        raise ValueError("la sortie doit etre un nouveau fichier .pdf")
    largeur = A4[0] - 32 * mm
    bleu = colors.HexColor("#17405b")
    encre = colors.HexColor("#24343e")
    pale = colors.HexColor("#eef4f7")
    gris = colors.HexColor("#60727d")
    normal = ParagraphStyle("TextePCB", fontName="PCB", fontSize=9,
        leading=13, textColor=encre, spaceAfter=7, allowWidows=0, allowOrphans=0)
    styles = {
        "body": normal,
        "title": ParagraphStyle("TitrePCB", parent=normal, fontName="PCB-Bold",
            fontSize=22, leading=27, textColor=bleu, spaceAfter=13, keepWithNext=True),
        "h1": ParagraphStyle("H1PCB", parent=normal, fontName="PCB-Bold", fontSize=16,
            leading=20, textColor=bleu, spaceAfter=12, keepWithNext=True),
        "h2": ParagraphStyle("H2PCB", parent=normal, fontName="PCB-Bold", fontSize=11,
            leading=15, textColor=bleu, spaceBefore=8, spaceAfter=6, keepWithNext=True),
        "small": ParagraphStyle("PetitPCB", parent=normal, fontSize=7.7, leading=10.6,
            textColor=gris, spaceAfter=6),
        "cell": ParagraphStyle("CellulePCB", parent=normal, fontSize=7.5, leading=10.4,
            spaceAfter=0, allowWidows=1, allowOrphans=1),
        "th": ParagraphStyle("EntetePCB", parent=normal, fontName="PCB-Bold", fontSize=7.5,
            leading=10.4, textColor=colors.white, spaceAfter=0),
        "mono": ParagraphStyle("CodePCB", parent=normal, fontName="PCBMono", fontSize=7,
            leading=10.1, wordWrap="CJK", splitLongWords=True, spaceAfter=5),
    }
    elements = []
    bilan = dossier["bilan"]
    selections = {nom: selection_dessin(bilan, nom) for nom in ANTENNES}
    total_calculs = sum(len(dossier["calculs"][nom]) for nom in ANTENNES)
    essais = [(nom, essai) for nom in ANTENNES for essai in selections[nom]["preliminaires"]]
    fixture = bool(dossier.get("fixture_test"))
    titre = "Qualification S11 - fabrication PCBWay"

    def p(contenu, style="body", brut=False):
        return Paragraph(contenu if brut else texte(contenu), styles[style])

    def ajout(contenu, style="body", brut=False):
        elements.append(p(contenu, style, brut))

    def tableau(lignes, proportions, taille=None):
        cellules = [[p(v, "th" if i == 0 else "cell") for v in ligne]
                    for i, ligne in enumerate(lignes)]
        t = Table(cellules, colWidths=[largeur * n / sum(proportions) for n in proportions],
                  repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), bleu),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, -1), (-1, -1), .4, colors.HexColor("#d0dde5")),
        ]))
        elements.extend([t, Spacer(1, 7)])

    def nouvelle_page(titre_page):
        elements.append(PageBreak())
        ajout(titre_page, "h1")

    def lien(label, url):
        return '<link href="' + html.escape(url, quote=True) + '" color="#1b628d"><u>' + texte(label) + '</u></link>'

    def pied(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#ccd9e1"))
        canvas.line(16 * mm, 13 * mm, A4[0] - 16 * mm, 13 * mm)
        canvas.setFont("PCB", 7)
        canvas.setFillColor(gris)
        canvas.drawString(16 * mm, 9 * mm, "MicroWaveTomography - référence S11 de production")
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, str(doc.page))
        if fixture:
            canvas.setFillColor(colors.HexColor("#ac2532"))
            canvas.setFont("PCB-Bold", 8)
            canvas.drawCentredString(A4[0] / 2, A4[1] - 10 * mm,
                                      "FIXTURE SYNTHÉTIQUE DE TEST - NON LIVRABLE")
        canvas.restoreState()

    # 1. Synthese : aucune valeur historique n'est recopiee.
    ajout("Qualification S11\nPremière fabrication PCBWay".replace("\n", "<br/>"), "title", True)
    ajout("Campagne pcbway_r1 | édition du " + dossier["creation"].strftime("%d/%m/%Y à %H:%M %Z"), "small")
    ajout("Convergence numérique réussie pour les trois antennes.", "h2")
    ajout("Les références de ce bilan proviennent exclusivement des calculs de la révision de production, "
          "avec vérification des sources, des configurations, des durées et des empreintes. "
          "La convergence satisfait les critères de la campagne ; elle ne mesure pas les performances des cartes reçues.")
    ajout(str(total_calculs) + " dossiers de calcul contrôlés, essais préliminaires compris. " +
          "Références retenues : " + "; ".join(NOMS[nom] + " : " + selections[nom]["reference"] for nom in ANTENNES) + ".", "small")
    ajout("Deux articles à fabriquer", "h2")
    lignes = [["Article / archive", "Découpe nominale (mm)", "Quantité / contenu"]]
    for article in dossier["articles"]:
        w, h = article["dimensions_mm"]
        lignes.append([str(article["numero"]) + " : " + article["chemin"].name,
            nombre(w, 6) + " × " + nombre(h, 6),
            "5 panneaux ; 5 petits et 5 grands losanges séparés" if article["numero"] == 1 else "5 cartes Vivaldi"])
    tableau(lignes, [43, 27, 30])
    ajout("Dimensions calculées depuis les contours des manifestes contenus dans les ZIP ; convention de ligne médiane GKO. "
          "Les losanges sont simulés et mesurés après séparation et arasage des pontets.", "small")
    ajout("Performances simulées sur 1,4-6,0 GHz", "h2")
    lignes = [["Antenne", "Points < −10 dB", "Points < −6 dB", "Puissance réfléchie moyenne", "Pire S11"]]
    for nom in ANTENNES:
        b = bilan["antennes"][nom]["indicateurs"]["bande_1p4_6"]
        lignes.append([NOMS[nom], pourcent(b["moins_10_db"]), pourcent(b["moins_6_db"]),
                       nombre(b["moyenne_puissance_reflechie_db"], 3) + " dB", nombre(b["pire_db"], 3) + " dB"])
    tableau(lignes, [19, 19, 19, 25, 18])
    ajout("Les pourcentages comptent 185 points à pas de 25 MHz, seuil strict. Les intervalles disjoints sont donnés "
          "antenne par antenne. La moyenne en dB vaut 10 log10(moyenne(|S11|²)) ; elle ne représente pas le rendement de rayonnement.", "small")
    ajout("Cadre de comparaison", "h2")
    ajout("Substrat S1000H nominal, h diélectrique = 1,6 mm ; cuivre demandé 1 oz ; ENIG et aucun masque. "
          "Implantation SMA femelle 142-0701-851 ; port idéal au bord du PCB. "
          "Le corps coaxial, le PTFE, la broche et la soudure restent hors du modèle 3D.")
    ajout("Lecture du bilan : convergence ; trois fiches avec courbes ; hypothèses et plans de mesure ; "
          "traçabilité et mode de comparaison. Les références complètes sont jointes aux fichiers de campagne.", "small")

    # 2. Valeurs ET seuils : l'acceptation vient du qualificateur.
    nouvelle_page("Convergence spatiale et temporelle")
    ajout("Les paires de calculs et la référence sont sélectionnées pour chaque dessin. "
          "La comparaison temporelle conserve exactement le même maillage et le même pas temporel. "
          "Les seuils d'acceptation restent ceux définis avant les calculs.")
    lignes = [["Antenne", "Paire spatiale", "Paire temporelle", "Référence"]]
    for nom in ANTENNES:
        spec = selections[nom]
        lignes.append([NOMS[nom], " à ".join(spec["spatial"]),
                       " à ".join(spec["temporel"]), spec["reference"]])
    tableau(lignes, [20, 29, 29, 22])
    lignes = [["Antenne / contrôle", "max |ΔS11| / seuil", "RMS |ΔS11| / seuil", "P95 ΔdB / seuil", "P95 phase (diagnostic)"]]
    for nom in ANTENNES:
        for cle, label in (("spatial", "spatial"), ("temporel", "temporel")):
            c = bilan["antennes"][nom][cle]
            v, s = c["valeurs"], c["seuils_acceptation"]
            lignes.append([NOMS_COURTS[nom] + " / " + label,
                nombre(v["maximum_complexe"], 5) + " / " + nombre(s["maximum_complexe"], 3),
                nombre(v["rms_complexe"], 5) + " / " + nombre(s["rms_complexe"], 3),
                nombre(v["percentile95_db"], 3) + " / " + nombre(s["percentile95_db"], 2) + " dB",
                nombre(v["percentile95_phase_deg"], 3) + "°"])
    tableau(lignes, [24, 20, 20, 20, 16])
    ajout("Tous les contrôles finaux ci-dessus sont réussis, ainsi que la passivité numérique de chaque référence. "
          "Max et RMS complexes portent sur les 213 points de 1,000 à 6,300 GHz. "
          "Les percentiles en dB et phase utilisent les points où les deux modules sont au moins −20 dB. "
          "La phase est un diagnostic enregistré ; aucun seuil de phase ne participe au verdict.", "small")
    ajout("Portée de cette qualification", "h2")
    ajout("Le succès qualifie la stabilité de S11 pour les grilles et durées sélectionnées, avec les seuils déclarés. "
          "Il ne borne pas toutes les erreurs de discrétisation et ne qualifie ni gain, ni diagramme, ni centre de phase, "
          "ni modèle direct de tomographie. Les hypothèses de matériau et de connectique restent à confronter aux prototypes.")
    ajout("Antenne isolée dans l'air, domaine tronqué par huit cellules PML et garde d'air d'au moins 74,95 mm ; "
          "troncature PML non qualifiée indépendamment.")

    if essais:
        ajout("Les essais préliminaires restent conservés avec leurs résultats, y compris les échecs. "
              "La page suivante donne leurs valeurs et les adaptations retenues. "
              "Les seuils d'acceptation restent inchangés.")
        nouvelle_page("Essais préliminaires et adaptations")
        ajout("Les essais ci-dessous motivent le raffinement du maillage ou la prolongation de la durée. "
              "Le verdict final utilise les nouvelles paires de comparaison, détaillées à la page précédente.")
        lignes = [["Antenne / essai", "Paire de calculs", "Max complexe / seuil", "RMS complexe / seuil", "P95 dB / seuil", "État"]]
        for nom, essai in essais:
            e = essai["ecarts"]
            v, s = e["valeurs"], e["seuils_acceptation"]
            lignes.append([NOMS_COURTS[nom] + " / " + essai["type"],
                " à ".join(essai["calculs"]),
                nombre(v["maximum_complexe"], 5) + " / " + nombre(s["maximum_complexe"], 3),
                nombre(v["rms_complexe"], 5) + " / " + nombre(s["rms_complexe"], 3),
                nombre(v["percentile95_db"], 3) + " / " + nombre(s["percentile95_db"], 2),
                "RÉUSSI" if e["reussi"] else "ÉCHEC"])
        tableau(lignes, [19, 23, 17, 17, 16, 8])
        for nom, essai in essais:
            if essai.get("motif"):
                ajout(NOMS[nom] + " / " + essai["type"] + " : " + essai["motif"], "small")
        for nom in ANTENNES:
            echecs = [e for e in selections[nom]["preliminaires"] if e["ecarts"]["reussi"] is False]
            if echecs:
                spec = selections[nom]
                causes = {e["type"] for e in echecs}
                phrases = [NOMS[nom] + " :"]
                if "spatial" in causes:
                    duree_spatiale = dossier["calculs"][nom][spec["spatial"][0]]["execution"]["duree_demandee_s"] * 1e9
                    phrases.append("l'échec spatial initial conduit à raffiner le maillage : " +
                        " à ".join(spec["spatial"]) + ", à durée constante de " +
                        nombre(duree_spatiale, 3) + " ns.")
                if "temporel" in causes:
                    phrases.append("L'échec temporel initial conduit à prolonger la durée ; " +
                        "le contrôle temporel final porte sur " + " à ".join(spec["temporel"]) + ".")
                elif "spatial" in causes:
                    initial_reussi = any(e["type"] == "temporel" and e["ecarts"]["reussi"]
                                         for e in spec["preliminaires"])
                    intro = ("Le contrôle temporel initial était réussi ; le contrôle temporel après raffinement porte sur "
                             if initial_reussi else "Le contrôle temporel après raffinement porte sur ")
                    phrases.append(intro + " à ".join(spec["temporel"]) + ".")
                phrases.append("La référence est " + spec["reference"] +
                    ". Les valeurs et seuils finaux figurent sur la page précédente.")
                ajout(" ".join(phrases), "small")

    ajout("Grilles et exécution réellement conservées", "h2")
    lignes = [["Antenne / référence", "Cellules : paire spatiale", "dt référence (ps)", "Pas référence", "Tension : durée conservée (ns)"]]
    for nom in ANTENNES:
        spec = selections[nom]
        b = dossier["calculs"][nom][spec["spatial"][0]]
        fin_spatial = dossier["calculs"][nom][spec["spatial"][1]]
        f = dossier["calculs"][nom][spec["reference"]]
        sonde = f["sondes"]["port_ut_1"]
        lignes.append([NOMS[nom] + " / " + spec["reference"],
                       f'{b["maillage"]["cellules"]:,} / {fin_spatial["maillage"]["cellules"]:,}'.replace(",", " "),
                       nombre(f["execution"]["dt_s"] * 1e12, 5), str(f["execution"]["n_pas"]),
                       nombre((sonde["fin_s"] - sonde["debut_s"]) * 1e9, 6)])
    tableau(lignes, [19, 30, 15, 15, 21])
    ajout("Le pas est calibré sur l'opérateur openEMS ; les durées sont imposées, avec arrêt par énergie désactivé. "
          "Les sondes et leur pas effectif sont contrôlés par le qualificateur. "
          "Une grille fréquentielle fine ne constitue pas à elle seule une preuve de durée suffisante : le contrôle par prolongation est explicite.")

    # Fiches : les trois figures du qualificateur sont authentifiees.
    for nom in ANTENNES:
        nouvelle_page(NOMS[nom] + " - référence simulée")
        b = bilan["antennes"][nom]["indicateurs"]["bande_1p4_6"]
        ajout("1,4-6,0 GHz : " + pourcent(b["moins_10_db"]) + " des points sous −10 dB ; " +
              pourcent(b["moins_6_db"]) + " sous −6 dB. Moyenne de puissance réfléchie : " +
              nombre(b["moyenne_puissance_reflechie_db"], 3) + " dB.")
        figure = Image(str(dossier["references"][nom]["figure"]), width=largeur * .83, height=largeur * .83)
        figure.hAlign = "CENTER"
        elements.extend([figure, Spacer(1, 4)])
        spec = selections[nom]
        profils_figures = spec["profils"]
        ajout("Figure de qualification : module des calculs " + ", ".join(profils_figures) +
              (" (essais préliminaires inclus)" if spec["preliminaires"] else "") +
              "; impédance et phase de la référence " + spec["reference"] + ". "
              "L'impédance est dérivée de S11 à 50 Ω. Les limites d'axes de la figure peuvent masquer des extrema d'impédance.", "small")
        lignes = [["Seuil strict", "Points / 185", "Segments disjoints échantillonnés (GHz)"]]
        for cle, label in (("moins_10_db", "−10 dB"), ("moins_6_db", "−6 dB")):
            band = b[cle]
            lignes.append([label, str(band["points_sous_seuil"]) + " / 185", segments(band)])
        tableau(lignes, [15, 17, 68])
        ajout("Bornes sans interpolation des franchissements. Une borne à la limite du balayage n'établit pas une fréquence de coupure. "
              "Ces pourcentages sont des proportions de points, sans extrapolation entre des segments séparés.", "small")
        ajout("Référence " + spec["reference"] + " : " + nom + "/comparaison/reference_simulation.s1p", "mono")

    # 6. Hypotheses et protocole de comparaison.
    nouvelle_page("Hypothèses physiques et plans de référence")
    contrat = bilan["antennes"][ANTENNES[0]]["hypothese_plan"]
    mat = contrat["materiau"]
    definition = mat["definition"]
    ajout("Substrat et cuivre", "h2")
    ajout("Le matériau demandé est le stratifié Shengyi S1000H, TG150. Le modèle utilise h = " +
          nombre(contrat["epaisseur_substrat_mm"], 1) + " mm de diélectrique, distinct de l'épaisseur finie incluant cuivre et finition. "
          "Le modèle Debye passif nominal à " + str(len(definition["relaxation_s"])) + " pôles est construit à partir de εr = " +
          nombre(mat["epsilon_reference"], 3) + " et tanδ = " + nombre(mat["tan_delta_reference"], 3) + " à " +
          nombre(mat["frequence_reference_hz"] / 1e9, 1) + " GHz. Il ne constitue pas une identification large bande du lot fabriqué.")
    ajout("La commande demande 1 oz de cuivre par face, finition ENIG, aucun masque ni sérigraphie. "
          "Le calcul emploie un conducteur PEC idéal ; épaisseur résistive, rugosité, pertes ohmiques et empilement ENIG ne sont pas résolus. "
          "La confirmation de stratifié et les mesures d'épaisseur doivent accompagner la réception.")
    ajout("SMA et plans de référence", "h2")
    ajout("Connecteur retenu : Cinch Johnson 142-0701-851, SMA femelle standard, non RP-SMA. "
          "Le calcul comprend les pads cuivre et les vias de masse équivalents, avec un port idéal 50 Ω au bord du PCB. "
          "Le corps coaxial, le PTFE, la broche et les soudures restent hors du modèle 3D.")
    tableau([["Plan simulé", "Plan de mesure"],
             ["Bord du PCB, port idéal ; référence de S11 calculée", "Interface SMA au bout du câble après SOL ; transition du connecteur encore présente"]], [50, 50])
    ajout("Une extension de port peut retirer un retard connu, documenté indépendamment ; elle ne supprime pas les réflexions ni la dispersion. "
          "La comparaison complexe ou de phase exige de maîtriser l'écart entre ces plans. "
          "Aucun retard libre n'est ajusté pour rapprocher les courbes.")
    ajout("Mesure des premières cartes", "h2")
    for n, contenu in enumerate([
        "Identifier et photographier les cartes ; vérifier contours, perçages, cuivre, stratifié et épaisseur. Séparer puis araser les losanges avant mesure.",
        "Monter la SMA suivant son dessin ; conserver références, lot, photos de soudure et contrôles de continuité/absence de court-circuit.",
        "Régler 1,000-6,300 GHz, 213 points, 25 MHz, 50 Ω. Calibrer SOL au bout du câble et enregistrer une charge de contrôle.",
        "Conserver S11 complexe RI corrigé, la calibration et le brut. Pour l'acquisition USB du projet, expliciter la correction SOL appliquée.",
        "Faire trois déconnexions/reconnexions, puis varier câble/support de façon documentée ; mesurer plusieurs cartes lorsque disponibles.",
        "Comparer sans recalage, conserver les plans réels et la dispersion. Rechercher d'abord calibration, montage, dimensions et matériau.",
    ], 1):
        ajout(str(n) + ". " + contenu, "small")

    # 7. Empreintes exactes et commande reproductible.
    nouvelle_page("Traçabilité et comparaison des prototypes")
    ajout("Empreintes des entrées effectivement vérifiées", "h2")
    ajout("qualification_globale.json", "mono")
    ajout(dossier["sha_bilan"], "mono")
    for relatif, sha in bilan.get("configuration_sha256", {}).items():
        ajout(relatif, "small")
        ajout(sha, "mono")
    for article in dossier["articles"]:
        ajout("Article " + str(article["numero"]) + " : " + article["chemin"].name, "small")
        ajout(article["sha256"], "mono")
    for nom in ANTENNES:
        ajout(nom + "/comparaison/reference_simulation.s1p", "small")
        ajout(dossier["references"][nom]["sha256"], "mono")
    ajout("Les manifestes de calcul gardent grille finale, dt, durée, sondes, géométrie, sources et versions. "
          "Les trois figures et références sont reliées au bilan par SHA-256. Les deux archives ont été relues avec le contrôleur Gerber/Excellon "
          "et leur contrat est identique à celui des simulations.", "small")
    ajout("Comparer une mesure depuis simulation/", "h2")
    for ligne in ["python -B -X utf8 compare_s11.py `",
                  "  --simulation resultats/pcbway_r1/vivaldi_tomographie/comparaison/reference_simulation.s1p `",
                  "  --mesure mesures/V-01_reconnexion01.s1p `",
                  '  --plan-mesure "SOL au SMA ; carte V-01 ; aucune extension" `',
                  "  --sortie comparaisons/V-01_premiere_serie"]:
        ajout(ligne, "mono")
    ajout("Remplacer les chemins et la description du plan par ceux de l'acquisition. Le dossier de sortie doit être neuf ou vide. "
          "L'outil refuse les grilles différentes, conserve les S1P originaux, produit courbes/indicateurs/dispersion et n'ajuste ni retard, ni phase, ni amplitude.", "small")
    ajout("Documents de travail et références", "h2")
    ajout("Protocole : PROTOCOLE_MESURE_PCBWAY.md ; outil : compare_s11_usage.md ; "
          "options : fabrication/README.md et instructions_pcbway_anglais.txt. Ces documents accompagnent les références de campagne.", "small")
    sources = [
        ("Fiche matériau S1000H/S1000HB du dossier", dossier["articles"][0]["manifeste"]["fabrication"]["material_datasheet"]),
        ("Catalogue Cinch Johnson - implantation 142-0701-851, p. 58", contrat["connecteur"]["source"]),
        ("Dessin fabricant du connecteur 142-0701-851", "https://www.cinch.com/media/drawings/products/rf-microwave/connectors/dr-ccs-john-142-0701-851.pdf"),
        ("Documentation openEMS : maillage", "https://docs.openems.de/en/latest/concepts/mesh.html"),
        ("Documentation openEMS : simulation", "https://docs.openems.de/en/latest/concepts/simulation.html"),
    ]
    for label, url in sources:
        ajout(lien(label, url), "small", True)
    ajout("Conclusion : les fichiers actuels disposent d'une référence S11 numériquement qualifiée et traçable. "
          "La réception et les mesures ci-dessus restent nécessaires pour confronter le prototype et le modèle ; "
          "un accord S11 ne suffit pas à valider la tomographie.", "small")

    sortie.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bilan_pcbway_pdf_", dir=sortie.parent) as temporaire:
        provisoire = Path(temporaire) / "bilan.pdf"
        doc = SimpleDocTemplate(str(provisoire), pagesize=A4, rightMargin=16 * mm,
            leftMargin=16 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
            title=titre, author="Projet MicroWaveTomography", subject="Qualification S11 PCBWay r1",
            pageCompression=1)
        doc.build(elements, onFirstPage=pied, onLaterPages=pied)
        from pypdf import PdfReader
        lecteur = PdfReader(provisoire)
        contenu = "\n".join(page.extract_text() for page in lecteur.pages)
        for attendu in [dossier["sha_bilan"], *bilan.get("configuration_sha256", {}).values(),
                        *[a["sha256"] for a in dossier["articles"]],
                        *[dossier["references"][n]["sha256"] for n in ANTENNES]]:
            if attendu not in re.sub(r"\s+", "", contenu):
                raise ValueError("empreinte manquante au rendu PDF")
        if "\ufffd" in contenu or len(lecteur.pages) < 7:
            raise ValueError("verification textuelle du PDF en echec")
        if sortie.exists():
            raise FileExistsError("la sortie a ete creee pendant le rendu")
        provisoire.rename(sortie)
    return dict(pdf=str(sortie), pages=len(lecteur.pages), octets=sortie.stat().st_size,
                sha256=sha256(sortie), fixture_test=fixture)


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=RACINE / "resultats" / "pcbway_r1")
    parser.add_argument("--fabrication", type=Path,
                        help="racine fabrication/ ou uploads/ (detection automatique sinon)")
    parser.add_argument("--sortie", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        base = args.base
        if not base.is_absolute() and not base.exists() and (RACINE / base).exists():
            base = RACINE / base
        dossier = charge_dossier(base, fabrication=args.fabrication)
        resultat = construit_rapport(dossier, args.sortie)
    except (ValueError, FileNotFoundError, FileExistsError, KeyError) as erreur:
        parser.exit(2, "Rapport refuse : " + str(erreur) + "\n")
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
    print("Rendu créé ; inspection visuelle des pages PNG requise avant livraison.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
