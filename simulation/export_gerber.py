"""EXPORT GERBER -- des geometries simulees aux fichiers que PCBWay attend.

    python export_gerber.py --antenne vivaldi_tomographie
    python export_gerber.py --panneau losanges
    python export_gerber.py --tout

Regle du projet : les cotes n'existent qu'a UN endroit, le `geometrie.py` de
l'antenne. Cet outil leur demande leurs contours a plat et ecrit directement
le jeu Gerber RS-274X plus le fichier de percage, zippe, sans passer par
KiCad. L'etape manuelle qu'imposait `export_dxf.py` etait le seul endroit du
projet ou les cotes pouvaient diverger de celles qui ont ete simulees.

CE QUI EST PRODUIT, et pourquoi ce jeu-la
-----------------------------------------
    .GTL .GBL   les deux cuivres
    .GTS .GBS   vernis epargne, OUVERT SUR TOUT LE CUIVRE
    .GKO        contour de decoupe, fraisages interieurs compris
    .DRL        percages, tous non metallises
    lisez_moi   les options a cocher sur le formulaire PCBWay

Les couches de vernis reprennent les formes du CUIVRE, et non les pastilles
d'une carte ordinaire : le vernis est retire partout ou il y a du cuivre, et
ne subsiste que sur le FR4 nu. La simulation suppose du cuivre nu, et le
connecteur doit pouvoir se souder sur toute la tranche. Ce qui reste de vernis
dans les fentes deplace la frequence de moins de 1 % -- dix fois moins que la
tolerance du FR4 sur sa permittivite.

GERBER, en deux lignes. Un fichier par couche. `G36*`/`G37*` encadre un
polygone PLEIN ; en dehors, les coordonnees tracent un trait de la largeur de
l'ouverture courante. Les coordonnees sont en micrometres de millimetre
(format 4.6), ce que declarent les entetes `%FSLAX46Y46*%` et `%MOMM*%`.
"""
import argparse
import os
import zipfile

import numpy as np

import fdtd as F

# ---------------------------------------------------------------- Gerber
ENTETE = """G04 {titre}*
%TF.GenerationSoftware,MicroWaveTomography,export_gerber.py,1.0*%
%TF.FileFunction,{fonction}*%
%TF.Part,{part}*%
%FSLAX46Y46*%
%MOMM*%
%LPD*%
%ADD10C,{diametre:.6f}*%
D10*
G01*"""


def _xy(x, y):
    return f"X{int(round(x * 1e6))}Y{int(round(y * 1e6))}"


def ecrit_gerber(chemin, titre, fonction, pleins=(), traits=(),
                 diametre=0.100, part="Single"):
    """Un fichier RS-274X : des polygones pleins, puis des traits.

    `part` est l'attribut X2 qui dit au fabricant si le fichier decrit UNE
    carte ou un PANNEAU de plusieurs. Un panneau annonce comme une carte
    simple, c'est un contour interieur qu'il prendra pour une erreur.
    """
    mor = [ENTETE.format(titre=titre, fonction=fonction, diametre=diametre,
                         part=part)]
    for poly in pleins:
        pts = [tuple(p) for p in poly]
        mor.append("G36*")
        mor.append(_xy(*pts[0]) + "D02*")
        for p in pts[1:]:
            mor.append(_xy(*p) + "D01*")
        mor.append(_xy(*pts[0]) + "D01*")
        mor.append("G37*")
    for poly in traits:
        pts = [tuple(p) for p in poly]
        mor.append(_xy(*pts[0]) + "D02*")
        for p in pts[1:]:
            mor.append(_xy(*p) + "D01*")
    mor.append("M02*")
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(mor) + "\n")
    return chemin


def ecrit_excellon(chemin, trous, titre=""):
    """Percages, en millimetres a point decimal explicite.

    Le point decimal evite toute discussion sur la suppression des zeros,
    qui est la faute classique de ce format -- et elle se paie en trous au
    centieme de millimetre de leur place.
    """
    diametres = sorted({round(d, 3) for _, _, d in trous})
    mor = ["M48", f";{titre}",
           ";FORMAT={3:3 / absolute / metric / decimal}",
           "FMAT,2", "METRIC,TZ", "G90", "G05"]
    for i, d in enumerate(diametres, start=1):
        mor.append(f"T{i}C{d:.3f}")
    mor += ["%"]
    for i, d in enumerate(diametres, start=1):
        mor.append(f"T{i}")
        for x, y, dd in trous:
            if abs(round(dd, 3) - d) < 1e-9:
                mor.append(f"X{x:.3f}Y{y:.3f}")
    mor += ["T0", "M30"]
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(mor) + "\n")
    return chemin


# ---------------------------------------------------------------- notice
NOTICE = """Commande PCBWay -- {nom}

{description}

A COCHER SUR LE FORMULAIRE
--------------------------
  Board Type .................. Single pieces{panneau}
  Different Design ............ 1
  Size ........................ {largeur:.1f} x {hauteur:.1f} mm
  Quantity .................... 5
  Layers ...................... 2
  Material .................... FR-4, TG130 ou TG150
  Thickness ................... {epaisseur:.1f} mm
  Min track/spacing ........... 6/6 mil, l'option par defaut
                                (le plus petit detail du dessin fait
                                 {piste:.2f} mm, soit {pistemil:.0f} mil)
  Min hole size ............... 0.3 mm, l'option par defaut
                                (le plus petit trou fait {min_trou})
  Solder mask ................. n'importe quelle couleur (voir plus bas)
  Silkscreen .................. None
  Edge connector .............. No
  Surface finish .............. ENIG (or) ou Immersion silver (argent)
  Copper weight ............... 1 oz
  Gold fingers ................ No
  Castellated holes ........... No
  Remove product No. .......... Yes

LE VERNIS : OUVERT SUR TOUT LE CUIVRE
-------------------------------------
Les deux couches de vernis fournies ne sont pas celles d'une carte ordinaire :
elles reprennent exactement les formes du cuivre. Le vernis est donc RETIRE
partout ou il y a du cuivre, et ne subsiste que sur le FR4 nu -- les fentes.

Pourquoi : la simulation suppose du cuivre nu. Le vernis sur le cuivre n'a
aucun effet radio -- le champ tangentiel y est nul -- mais il faut pouvoir
souder le connecteur n'importe ou sur la tranche, et il faut que la finition
protege toute la surface.

Ce qui reste de vernis, dans les fentes, deplace la frequence de moins de 1 %
-- vingt micrometres contre 1,6 mm de substrat. C'est dix fois moins que la
tolerance du FR4 lui-meme sur sa permittivite. On aurait pu demander « pas de
vernis du tout » et coller encore mieux a la simulation, mais ce n'est pas une
option sure du formulaire, et le risque de blocage de la commande est plus
couteux que ce 1 %.

La couleur du vernis est donc indifferente. La finition, non : ENIG est le
choix robuste ; sa couche de nickel est legerement plus dissipative en
hyperfrequence que l'argent chimique, ce qui se discute sur la ligne
d'alimentation et nulle part ailleurs. L'argent chimique est meilleur en radio
et se ternit en quelques mois a l'air libre.

LE CONNECTEUR
-------------
Aucune empreinte de connecteur n'est posee : le SMA est un modele BORD DE
CARTE (edge-launch), qui se sertit sur la tranche et se soude d'un cote sur le
ruban, de l'autre sur la masse. C'est ce que suppose la simulation, dont le
port se trouve exactement dans le plan de cette tranche.
{feed}

FICHIERS
--------
{fichiers}

CONTROLE AVANT COMMANDE
-----------------------
Ouvrir le ZIP dans un visualiseur Gerber (gerbv, ou celui de PCBWay apres
depot) et mesurer :
{controles}

Si ces cotes ne sont pas retrouvees, ce ne sont pas les fichiers simules.
"""


# ---------------------------------------------------------------- cartes
def _translate(polys, dx, dy):
    return [[(float(x) + dx, float(y) + dy) for x, y in poly] for poly in polys]


def carte_antenne(nom):
    """Une antenne seule, telle que son `geometrie.py` la decrit."""
    ant = F.charge_antenne(nom)
    if not hasattr(ant, "contours_mm"):
        raise SystemExit(f"{nom} n'expose pas contours_mm().")
    c = ant.contours_mm()
    d = ant.cotes()
    controles = getattr(ant, "controles_fabrication", lambda: "")()
    return dict(
        nom=ant.NOM, description=ant.DESCRIPTION,
        epaisseur=d.get("h", 1.6),
        F_Cu=c["F_Cu"], B_Cu=c["B_Cu"], Edge_Cuts=c["Edge_Cuts"],
        trous=list(getattr(ant, "percages_mm", lambda: [])()),
        controles=controles, panneau="", feed="",
        detail=getattr(ant, "detail_mini_mm", lambda: float("nan"))())


# --------------------------------------------------- le panneau des losanges
GAP = 3.0               # mm, largeur du fraisage entre les deux cartes
PONTETS = ((10.0, 13.0), (27.0, 30.0))      # en y, le long du fraisage
TROU_PONTET = 0.6       # mm, amorces de rupture
PAS_PONTET = 0.9        # mm


def carte_panneau_losanges():
    """Les deux losanges sur un panneau, relies par deux pontets secables.

    Pourquoi un panneau et pas deux commandes : PCBWay facture le nombre de
    DESSINS, pas le nombre de cartes. Deux losanges sur une plaque, c'est un
    dessin. Pourquoi des pontets et pas un trait de scie : la rupture doit
    tomber loin du cuivre, et sur une tranche franche -- scier du FR4 a cote
    d'un bord rayonnant abime justement ce que la simulation suppose net.

    Pourquoi pas de rainurage en V : les deux cartes n'ont pas la meme
    hauteur, et une rainure doit traverser le panneau de bord a bord.

    Les deux bords d'alimentation sont tous deux sur le bord EXTERIEUR du
    panneau, en y = 0 : ce sont eux qui recoivent le SMA, ils doivent sortir
    fraises net et non casses.
    """
    petit = F.charge_antenne("diamant_uwb")
    grand = F.charge_antenne("diamant_uwb_x18")
    cp, cg = petit.contours_mm(), grand.contours_mm()
    dp, dg = petit.cotes(), grand.cotes()

    lp, hp = dp["carte_l"], dp["carte_w"]           # 32 x 40
    lg, hg = dg["carte_l"], dg["carte_w"]           # 57,6 x 72
    x_gauche = lp + GAP                              # bord gauche du grand
    larg = x_gauche + lg

    # Les contours des antennes sont centres ; on les pose sur le panneau.
    tp = (lp / 2, hp / 2)
    tg = (x_gauche + lg / 2, hg / 2)
    f_cu = _translate(cp["F_Cu"], *tp) + _translate(cg["F_Cu"], *tg)
    b_cu = _translate(cp["B_Cu"], *tp) + _translate(cg["B_Cu"], *tg)

    # Contour exterieur : le L des deux cartes, entaille aux deux bouts du
    # fraisage. Entre les deux entailles, la matiere reste : c'est elle que
    # le fraisage interieur viendra reduire aux deux pontets.
    y0, y1 = PONTETS[0][0], PONTETS[-1][1]
    exterieur = [(0.0, 0.0), (lp, 0.0), (lp, y0), (x_gauche, y0),
                 (x_gauche, 0.0), (larg, 0.0), (larg, hg),
                 (x_gauche, hg), (x_gauche, y1), (lp, y1),
                 (lp, hp), (0.0, hp)]
    # Fraisage interieur : la fente entre les deux pontets.
    interieur = [(lp, PONTETS[0][1]), (x_gauche, PONTETS[0][1]),
                 (x_gauche, PONTETS[1][0]), (lp, PONTETS[1][0])]

    trous = []
    for a, b in PONTETS:
        n = max(2, int(round((b - a) / PAS_PONTET)) + 1)
        for y in np.linspace(a, b, n):
            trous.append((lp, float(y), TROU_PONTET))
            trous.append((x_gauche, float(y), TROU_PONTET))

    return dict(
        nom="panneau_losanges",
        description=("panneau de deux monopoles en losange : la conception "
                     "publiee (32 x 40 mm) et la meme a l'echelle 1,8 "
                     "(57,6 x 72 mm), reliees par deux pontets secables"),
        epaisseur=dp["h"],
        F_Cu=f_cu, B_Cu=b_cu,
        Edge_Cuts=[exterieur, interieur], trous=trous,
        detail=min(petit.detail_mini_mm(), grand.detail_mini_mm()),
        panneau="  (panneau client : DEUX cartes, un seul dessin)",
        feed=("\nLes DEUX bords d'alimentation sont en bas du panneau, sur le "
              "bord\nexterieur : ils sortent fraises, pas casses. Les deux "
              "pontets sont sur\nle cote, perces d'amorces de rupture."),
        controles=(f"   - encombrement du panneau : {larg:.2f} x {hg:.2f} mm\n"
                   f"   - petit losange : {lp:.2f} x {hp:.2f} mm\n"
                   f"   - grand losange : {lg:.2f} x {hg:.2f} mm\n"
                   f"   - fraisage de separation : {GAP:.2f} mm de large\n"
                   f"   - deux pontets de {PONTETS[0][1]-PONTETS[0][0]:.1f} mm"
                   f", perces a {TROU_PONTET:.1f} mm"))


# ---------------------------------------------------------------- jeu complet
COUCHES = (
    ("GTL", "F_Cu", "Copper,L1,Top", "cuivre superieur", 0.100),
    ("GBL", "B_Cu", "Copper,L2,Bot", "cuivre inferieur", 0.100),
    ("GTS", "F_Cu", "Soldermask,Top", "vernis superieur, ouvert sur tout le "
     "cuivre", 0.100),
    ("GBS", "B_Cu", "Soldermask,Bot", "vernis inferieur, ouvert sur tout le "
     "cuivre", 0.100),
)


def ecrit_jeu(carte, dossier):
    base = os.path.join(dossier, carte["nom"])
    os.makedirs(dossier, exist_ok=True)
    ecrits = []
    part = "Array" if carte.get("panneau") else "Single"
    for ext, cle, fonction, titre, diam in COUCHES:
        ecrits.append(ecrit_gerber(f"{base}.{ext}", titre, fonction,
                                   pleins=carte[cle], diametre=diam,
                                   part=part))
    ecrits.append(ecrit_gerber(
        f"{base}.GKO", "contour de decoupe", "Profile,NP",
        traits=[list(p) + [p[0]] for p in carte["Edge_Cuts"]],
        diametre=0.100, part=part))
    if carte["trous"]:
        # Le suffixe NPTH est ce qui dit au fabricant que ces trous ne sont
        # pas metallises. Sans lui, il les cuivrerait -- sans consequence sur
        # des trous de fixation, mais les amorces de rupture d'un pontet
        # metallisees ne se cassent plus proprement.
        ecrits.append(ecrit_excellon(f"{base}-NPTH.DRL", carte["trous"],
                                     f"{carte['nom']} -- tous non metallises"))
    return ecrits


def etendue(carte):
    pts = np.array([p for cle in ("F_Cu", "B_Cu", "Edge_Cuts")
                    for poly in carte[cle] for p in poly], dtype=float)
    return (pts[:, 0].max() - pts[:, 0].min(),
            pts[:, 1].max() - pts[:, 1].min())


def exporte(carte, dossier):
    ecrits = ecrit_jeu(carte, dossier)
    larg, haut = etendue(carte)
    mini = min(d for _, _, d in carte["trous"]) if carte["trous"] else None
    piste = carte["detail"]
    texte = NOTICE.format(
        nom=carte["nom"], description=carte["description"],
        largeur=larg, hauteur=haut, epaisseur=carte["epaisseur"],
        panneau=carte["panneau"], feed=carte["feed"],
        piste=piste, pistemil=piste / 0.0254,
        min_trou=(f"{mini:.1f} mm" if mini else "aucun percage"),
        fichiers="\n".join("   " + os.path.basename(c) for c in ecrits),
        controles=carte["controles"])
    notice = os.path.join(dossier, carte["nom"] + "_lisez_moi.txt")
    with open(notice, "w", encoding="utf-8") as f:
        f.write(texte)

    zip_chemin = os.path.join(dossier, carte["nom"] + "_pcbway.zip")
    with zipfile.ZipFile(zip_chemin, "w", zipfile.ZIP_DEFLATED) as z:
        for c in ecrits + [notice]:
            z.write(c, os.path.basename(c))

    print(f"\n  {carte['nom']} : {larg:.2f} x {haut:.2f} mm, "
          f"FR4 {carte['epaisseur']:.1f} mm, "
          f"{len(carte['trous'])} percages")
    for c in ecrits + [notice]:
        print("      " + c)
    print("      --> " + zip_chemin)
    return zip_chemin


def principal():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--antenne", default=None)
    p.add_argument("--panneau", default=None, choices=["losanges"])
    p.add_argument("--tout", action="store_true")
    p.add_argument("--sortie", default=None)
    args = p.parse_args()

    travaux = []
    if args.tout or args.panneau == "losanges":
        travaux.append((carte_panneau_losanges(),
                        args.sortie or os.path.join("fabrication",
                                                    "panneau_losanges")))
    if args.tout:
        travaux.append((carte_antenne("vivaldi_tomographie"),
                        args.sortie or os.path.join("fabrication",
                                                    "vivaldi_tomographie")))
    elif args.antenne:
        travaux.append((carte_antenne(args.antenne),
                        args.sortie or os.path.join("fabrication",
                                                    args.antenne)))
    if not travaux:
        p.error("choisir --antenne, --panneau losanges, ou --tout")
    for carte, dossier in travaux:
        exporte(carte, dossier)


if __name__ == "__main__":
    principal()
