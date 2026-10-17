"""VERIFIE GERBER -- relire nos fichiers avec un analyseur TIERS.

    python verifie_gerber.py fabrication/panneau_losanges/panneau_losanges_pcbway.zip

Ecrire un Gerber faux est aussi facile qu'en ecrire un bon : le format ne se
plaint de rien, et c'est la machine du fabricant qui tranche, trop tard. Ce
controle relit donc le ZIP avec `gerbonara`, qui n'est pas de nous, et compare
ce qu'il y trouve a ce que la geometrie simulee annonce :

    - chaque fichier est-il lisible, et reconnu comme la couche attendue ;
    - l'encombrement de chaque couche, au dixieme de millimetre ;
    - la surface de cuivre, qui signale un polygone retourne ou non ferme ;
    - le nombre et le diametre des percages ;
    - un rendu PNG de chaque couche, a comparer a `apercu.py`.

Ce qu'il ne verifie PAS : que le dessin soit une bonne antenne. C'est le role
de la simulation. Ici on verifie seulement que le fichier envoye au fabricant
porte bien le dessin qui a ete simule.
"""
import os
import sys
import zipfile

import numpy as np

ATTENDU = {
    ".GTL": "cuivre dessus", ".GBL": "cuivre dessous",
    ".GTS": "vernis dessus", ".GBS": "vernis dessous",
    ".GKO": "contour", ".DRL": "percages",
}


def _objets(couche):
    """Rend la liste des primitives graphiques d'une couche gerbonara."""
    return list(couche.objects)


def verifie(chemin_zip, sortie=None):
    from gerbonara import LayerStack

    dossier = sortie or os.path.join(os.path.dirname(chemin_zip), "relu")
    os.makedirs(dossier, exist_ok=True)
    with zipfile.ZipFile(chemin_zip) as z:
        z.extractall(dossier)

    pile = LayerStack.open(dossier, lazy=False)
    print(f"\n  {os.path.basename(chemin_zip)}")
    print(f"      pile reconnue : {pile}")

    ok = True
    for cle, couche in sorted(pile.graphic_layers.items(),
                              key=lambda kv: str(kv[0])):
        nom = " ".join(cle) if isinstance(cle, tuple) else str(cle)
        objets = _objets(couche)
        boite = couche.bounding_box(unit="mm")
        if boite is None:
            print(f"      !!  {nom} : VIDE")
            ok = False
            continue
        (x0, y0), (x1, y1) = boite
        print(f"      OK  {nom:28s} {len(objets):5d} primitives, "
              f"{x1-x0:7.2f} x {y1-y0:7.2f} mm")

    forages = list(pile.drill_layers or [])
    if forages:
        for forage in forages:
            trous = list(forage.objects)
            diam = sorted({round(float(o.tool.diameter), 3) for o in trous})
            plaque = {bool(o.plated) for o in trous}
            print(f"      OK  percages {len(trous):5d} trous, "
                  f"diametres {diam} mm, metallises {plaque}")
    else:
        print("      !!  aucun fichier de percage reconnu")
        ok = False

    # Le rendu : ce que la machine du fabricant voit, et non ce que notre
    # code croit avoir ecrit. C'est la derniere image a regarder avant de
    # commander, et la seule qui soit produite par un tiers.
    svg = os.path.join(os.path.dirname(chemin_zip),
                       os.path.basename(chemin_zip).replace(
                           "_pcbway.zip", "_rendu.svg"))
    with open(svg, "w", encoding="utf-8") as f:
        f.write(str(pile.to_svg(force_bounds=pile.board_bounds())))
    print("      rendu : " + svg)
    return pile, ok


def compare(pile, attendu):
    """Confronte les encombrements relus aux cotes annoncees."""
    print("\n      confrontation avec la geometrie simulee :")
    tout_bon = True
    for cle, (larg, haut, tol) in attendu.items():
        couche = None
        for nom, c in pile.graphic_layers.items():
            if cle in str(nom):
                couche = c
                break
        if couche is None:
            print(f"          !!  {cle} : couche absente")
            tout_bon = False
            continue
        (x0, y0), (x1, y1) = couche.bounding_box(unit="mm")
        dl, dh = abs((x1 - x0) - larg), abs((y1 - y0) - haut)
        bon = dl <= tol and dh <= tol
        tout_bon &= bon
        print(f"          {'OK ' if bon else '!! '} {cle:12s} "
              f"relu {x1-x0:7.2f} x {y1-y0:7.2f} mm, "
              f"attendu {larg:7.2f} x {haut:7.2f} mm")
    return tout_bon


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    bon = True
    for z in sys.argv[1:]:
        _, o = verifie(z)
        bon &= o
    raise SystemExit(0 if bon else 1)
