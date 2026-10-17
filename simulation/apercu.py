"""APERCU -- dessiner et controler une antenne AVANT de payer la simulation.

    python apercu.py --antenne vivaldi_tomographie
    python apercu.py --toutes

Une simulation FDTD coute dix minutes ; un dessin coute une seconde. Cet outil
est la pour attraper les fautes de TOPOLOGIE -- un conducteur qui se pince
jusqu'a disparaitre, un cuivre qui deborde de la carte, une piste plus fine
que ce que le fabricant sait graver -- avant d'avoir paye la simulation.

Il a ete ecrit apres en avoir attrape une : l'evasement de la Vivaldi etait
ecrete a l'ouverture, si bien que le dernier tiers de chaque aile etait un
fil et non du cuivre. Les cotes, elles, etaient justes. Aucune relecture du
code ne l'a vu ; un dessin l'aurait montre tout de suite.

LE CONTROLE PRINCIPAL. Pour chaque tranche perpendiculaire au grand axe, on
mesure la quantite de cuivre presente. Un conducteur qui se pince le montre
par une tranche presque vide. C'est volontairement grossier : un detecteur
de pointes fines se plaindrait de chaque sommet de losange.
"""
import argparse
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path

import fdtd as F

PAS = 0.2               # mm, pas de la rasterisation
LARGEUR_MINI = 0.5      # mm, en deca on considere que le conducteur a disparu
GRAVURE_MINI = 0.15     # mm, limite de gravure annoncee par PCBWay


def _masque(polylignes, xs, ys, evide=False):
    """Rasterise des polygones sur la grille xs x ys.

    `evide` dit comment combiner plusieurs contours, et les deux cas existent
    dans le projet :

      - un CUIVRE est une reunion. Deux polygones qui se chevauchent sur une
        meme face donnent du cuivre partout, pas un trou au milieu. C'est le
        cas de la masse d'une Vivaldi, qui est a la fois un rectangle
        d'alimentation et une aile.
      - un CONTOUR DE DECOUPE est une difference : le contour exterieur moins
        les fraisages interieurs. C'est le cas du panneau des losanges, dont
        la fente de separation est un contour ferme a l'interieur.
    """
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    dedans = np.zeros(len(pts), dtype=bool)
    for poly in polylignes:
        dans = Path(np.asarray(poly, dtype=float)).contains_points(pts)
        dedans = (dedans ^ dans) if evide else (dedans | dans)
    return dedans.reshape(gy.shape)


def controle(contours, percages=(), recouvrement_max=float("inf")):
    """Rend (rapport, profils). Le rapport est une liste de (ok, texte)."""
    pts = np.array([p for polys in contours.values() for poly in polys
                    for p in poly], dtype=float)
    x0, x1 = pts[:, 0].min(), pts[:, 0].max()
    y0, y1 = pts[:, 1].min(), pts[:, 1].max()
    xs = np.arange(x0 - PAS, x1 + PAS, PAS)
    ys = np.arange(y0 - PAS, y1 + PAS, PAS)

    bord = _masque(contours["Edge_Cuts"], xs, ys, evide=True)
    rapport, profils, cuivres = [], {}, {}
    rapport.append((True, f"carte : {x1-x0:.2f} x {y1-y0:.2f} mm, "
                          f"surface {(x1-x0)*(y1-y0)/100:.1f} cm2"))

    for calque in ("F_Cu", "B_Cu"):
        if calque not in contours:
            continue
        cu = _masque(contours[calque], xs, ys)
        cuivres[calque] = cu
        profils[calque] = cu.sum(axis=1) * PAS        # cuivre par tranche
        deborde = np.logical_and(cu, ~bord).sum() * PAS * PAS
        rapport.append((deborde < 1.0,
                        f"{calque} : {cu.sum()*PAS*PAS/100:.1f} cm2 de cuivre, "
                        f"{deborde:.2f} mm2 hors de la carte"))
        # La tranche la plus pauvre, en ne regardant que les tranches qui
        # contiennent du cuivre : les tranches vides sont legitimes.
        occupe = profils[calque] > 0
        if occupe.any():
            i = np.argmin(np.where(occupe, profils[calque], np.inf))
            rapport.append((profils[calque][i] >= LARGEUR_MINI,
                            f"{calque} : tranche la plus pauvre "
                            f"{profils[calque][i]:.2f} mm de cuivre, "
                            f"a y = {ys[i]:.1f} mm"))

    # LE RECOUVREMENT DES DEUX CUIVRES. La ou les deux faces se superposent,
    # le substrat fait une ligne de transmission, et sa largeur en fixe
    # l'impedance. Une Vivaldi antipodale ne doit se recouvrir que sur la
    # largeur de sa ligne d'alimentation : 35 mm de recouvrement, ce sont
    # 10 ohms au milieu du trajet, et un |S11| plat a -4 dB.
    if "F_Cu" in cuivres and "B_Cu" in cuivres:
        rec = np.logical_and(cuivres["F_Cu"], cuivres["B_Cu"])
        profils["recouvrement"] = rec.sum(axis=1) * PAS
        pire = profils["recouvrement"].max()
        rapport.append((pire <= recouvrement_max,
                        f"recouvrement des deux cuivres : au plus "
                        f"{pire:.2f} mm par tranche "
                        f"(limite retenue {recouvrement_max:.2f} mm)"))

    for k, (hx, hy, diam) in enumerate(percages):
        dans = (x0 <= hx <= x1) and (y0 <= hy <= y1)
        rapport.append((dans and diam >= 0.3,
                        f"percage {k+1} : diam {diam:.2f} mm en "
                        f"({hx:.1f}, {hy:.1f})"))
    return rapport, (xs, ys, profils)


def dessine(nom, contours, percages, chemin, rapport):
    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(13, 7), gridspec_kw={"width_ratios": [2, 1]})
    for poly in contours["Edge_Cuts"]:
        p = np.array(poly + [poly[0]], dtype=float)
        ax.plot(p[:, 0], p[:, 1], "k-", lw=1.2, label="contour de carte")
    for calque, couleur in (("F_Cu", "#c0392b"), ("B_Cu", "#2980b9")):
        for j, poly in enumerate(contours.get(calque, [])):
            p = np.array(poly, dtype=float)
            ax.fill(p[:, 0], p[:, 1], color=couleur, alpha=0.45,
                    label=calque if j == 0 else None)
            ax.plot(np.append(p[:, 0], p[0, 0]), np.append(p[:, 1], p[0, 1]),
                    color=couleur, lw=0.8)
    for hx, hy, diam in percages:
        ax.add_patch(plt.Circle((hx, hy), diam / 2, fill=False, color="k"))
    ax.set_aspect("equal")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_title(f"{nom} — cuivre a plat")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3)

    xs, ys, profils = chemin[1]
    for calque, couleur in (("F_Cu", "#c0392b"), ("B_Cu", "#2980b9"),
                            ("recouvrement", "#7d3c98")):
        if calque in profils:
            bx.plot(profils[calque], ys, color=couleur, label=calque)
    bx.axvline(LARGEUR_MINI, color="k", ls=":", lw=1)
    bx.set_xlabel("cuivre par tranche (mm)")
    bx.set_ylabel("y (mm)")
    bx.set_title("Un conducteur qui se pince\nse voit ici")
    bx.legend(fontsize=8)
    bx.grid(alpha=0.3)

    fig.suptitle("\n".join(("OK  " if ok else "!!  ") + t
                           for ok, t in rapport), fontsize=8, y=0.995,
                 ha="left", x=0.01)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(chemin[0], dpi=130)
    plt.close(fig)
    return chemin[0]


def une(nom, sortie):
    ant = F.charge_antenne(nom)
    if not hasattr(ant, "contours_mm"):
        print(f"  {nom} : pas de contours_mm(), rien a dessiner")
        return True
    contours = ant.contours_mm()
    percages = getattr(ant, "percages_mm", lambda: [])()
    rapport, profils = controle(
        contours, percages,
        getattr(ant, "RECOUVREMENT_MAX_MM", float("inf")))
    dossier = os.path.join(sortie, nom)
    os.makedirs(dossier, exist_ok=True)
    png = dessine(ant.NOM, contours, percages,
                  (os.path.join(dossier, "contours.png"), profils), rapport)
    print(f"\n  {nom}")
    for ok, texte in rapport:
        print(f"      {'OK ' if ok else '!! '} {texte}")
    print("      figure : " + png)
    return all(ok for ok, _ in rapport)


def un_panneau(quoi, sortie):
    """Le meme controle, mais sur un panneau assemble par export_gerber."""
    import export_gerber as G
    assemble = {"losanges": G.carte_panneau_losanges}[quoi]()
    carte = {k: assemble[k] for k in ("F_Cu", "B_Cu", "Edge_Cuts")}
    rapport, profils = controle(carte, assemble["trous"])
    dossier = os.path.join(sortie, assemble["nom"])
    os.makedirs(dossier, exist_ok=True)
    png = dessine(assemble["nom"], carte, assemble["trous"],
                  (os.path.join(dossier, "contours.png"), profils), rapport)
    print(f"\n  {assemble['nom']}")
    for ok, texte in rapport:
        print(f"      {'OK ' if ok else '!! '} {texte}")
    print("      figure : " + png)
    return all(ok for ok, _ in rapport)


def principal():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--antenne", default=None)
    p.add_argument("--toutes", action="store_true")
    p.add_argument("--panneau", default=None, choices=["losanges"])
    p.add_argument("--sortie", default="resultats")
    args = p.parse_args()

    tout_bon = True
    if args.panneau:
        tout_bon &= un_panneau(args.panneau, args.sortie)
    if args.panneau and not (args.toutes or args.antenne):
        noms = []
    else:
        noms = (F.antennes_disponibles() if args.toutes
                else [args.antenne or "vivaldi_tomographie"])
    for nom in noms:
        tout_bon &= une(nom, args.sortie)
    print("\n  " + ("tous les controles passent"
                    if tout_bon else "AU MOINS UN CONTROLE ECHOUE"))
    raise SystemExit(0 if tout_bon else 1)


if __name__ == "__main__":
    principal()
