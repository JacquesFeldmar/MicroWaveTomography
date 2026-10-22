"""EXPORT DXF -- des geometries simulees aux fichiers de fabrication.

Regle du projet : les cotes n'existent qu'a UN endroit, le `geometrie.py` de
l'antenne. Cet outil leur demande leurs contours a plat et les ecrit en DXF,
pour KiCad puis PCBWay. Si les deux divergeaient, la simulation ne vaudrait
plus rien.

    python export_dxf.py --antenne diamant_uwb
    python export_dxf.py --antenne diamant_uwb_x18
    python export_dxf.py --antenne vivaldi_tomographie

Chaque module d'antenne expose :

    contours_mm() -> {"F_Cu": [polyligne, ...], "B_Cu": [...],
                      "Edge_Cuts": [...]}

une polyligne etant une liste de (x, y) en millimetres, fermee implicitement.

Format produit : DXF R2000 (AC1015), LWPOLYLINE fermees, $INSUNITS=4 (mm).
"""
import argparse
import os

import numpy as np

import fdtd as F

CALQUES = ("F_Cu", "B_Cu", "Edge_Cuts")

NOTICE = """Fabrication chez PCBWay -- {nom}

{description}

Carte : {largeur:.2f} x {hauteur:.2f} mm. Ces DXF servent a l'inspection et a
l'edition. Les ZIP produits par export_gerber.py sont les fichiers a fournir
a PCBWay; leur notice porte le contrat de matiere et de finition.

Dans KiCad
----------
1. Nouveau projet, ouvrir l'editeur de circuit imprime.
2. Fichier > Importer > Graphiques... pour chacun des DXF :
{lignes_import}
   Unites : millimetres, echelle 1, origine (0, 0).
3. Les polylignes importees sont des CONTOURS. Les convertir en zones
   pleines : selectionner le contour, clic droit > Creer a partir de la
   selection > Zone. Sans cela, seul le trait serait grave.
4. L'empreinte SMA fait deja partie des cuivres quand elle est active dans
   geometrie.py; ne pas ajouter une seconde empreinte. Les percages/vias
   sont dans les Excellon du ZIP Gerber, pas dans ces DXF de contours.
5. Fichier > Fabrication > Gerbers, plus le fichier de percage.

Controle avant commande
-----------------------
Mesurer dans KiCad :
{controles}
Si ces cotes ne sont pas retrouvees, l'import s'est fait a une autre echelle
et la carte ne correspondrait plus a la simulation.
"""


def ecrit_dxf(chemin, polylignes, calque):
    """DXF R2000, explicit millimetres; R12 does not support LWPOLYLINE."""
    mor = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1015",
           "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
           "0", "SECTION", "2", "ENTITIES"]
    for pts in polylignes:
        mor += ["0", "LWPOLYLINE", "8", calque, "90", str(len(pts)), "70", "1"]
        for x, y in pts:
            mor += ["10", f"{x:.4f}", "20", f"{y:.4f}"]
    mor += ["0", "ENDSEC", "0", "EOF"]
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="ascii", newline="\r\n") as f:
        f.write("\n".join(mor) + "\n")
    return chemin


def etendue(contours):
    """(largeur, hauteur) de l'ensemble des contours, en mm."""
    pts = np.array([p for polys in contours.values() for poly in polys
                    for p in poly])
    return (pts[:, 0].max() - pts[:, 0].min(),
            pts[:, 1].max() - pts[:, 1].min())


def principal():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--antenne", required=True,
                   help="dossier sous antennes/ : " +
                        ", ".join(F.antennes_disponibles()))
    p.add_argument("--sortie", default=None)
    args = p.parse_args()

    ant = F.charge_antenne(args.antenne)
    if not hasattr(ant, "contours_mm"):
        raise SystemExit(f"{args.antenne} n'expose pas contours_mm() : cette "
                         f"antenne n'est pas prete pour la fabrication.")
    contours = ant.contours_mm()
    # Pas « gerbers » : ce dossier ne contient que du DXF. Les vrais Gerbers,
    # ceux qu'on depose chez le fabricant, sont ecrits par export_gerber.py
    # dans simulation/fabrication/.
    sortie = args.sortie or os.path.join(F.DOSSIER_ANTENNES, args.antenne,
                                         "dxf")
    base = os.path.join(sortie, ant.NOM)

    ecrits, lignes_import = [], []
    for calque in CALQUES:
        if calque not in contours:
            continue
        chemin = f"{base}_{calque}.dxf"
        ecrits.append(ecrit_dxf(chemin, contours[calque], calque))
        lignes_import.append(f"       {os.path.basename(chemin):40s} -> "
                             f"couche {calque.replace('_', '.')}")

    larg, haut = etendue(contours)
    controles = getattr(ant, "controles_fabrication", None)
    texte = NOTICE.format(
        nom=ant.NOM, description=ant.DESCRIPTION, largeur=larg, hauteur=haut,
        lignes_import="\n".join(lignes_import),
        controles=(controles() if controles else
                   f"   - l'encombrement total : {larg:.2f} x {haut:.2f} mm"))
    notice = base + "_lisez_moi.txt"
    with open(notice, "w", encoding="utf-8") as f:
        f.write(texte)

    print(f"  {ant.NOM} : {larg:.1f} x {haut:.1f} mm")
    for c in ecrits + [notice]:
        print("      " + c)


if __name__ == "__main__":
    principal()
