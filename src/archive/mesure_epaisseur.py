"""
MESURE D'EPAISSEUR PAR LES DEUX METHODES, SUR LES MEMES DONNEES.

POURQUOI CE PROGRAMME
    radar_cartilage_online.py ne sait faire que la detection a deux pics.
    erreur_epaisseur.py contient le modele stratifie exact, mais en simulation :
    il ne lit pas l'instrument. Il manquait donc l'outil qui applique les DEUX
    methodes au MEME balayage et compare -- c'est-a-dire le seul moyen de
    valider le logiciel sur un objet d'epaisseur connue.

LES DEUX METHODES

  A. DETECTION A DEUX PICS
     TF inverse du S11 fenetre, recherche des deux pics les plus saillants,
     interpolation parabolique. L'epaisseur vaut l'ecart apparent divise par
     sqrt(eps_r). Simple, mais ne fonctionne que si les deux echos sont
     separes, donc au-dela d'environ 52 mm d'ecart apparent en bande complete.

  B. INVERSION SUR MODELE STRATIFIE
     On ajuste le coefficient de reflexion exact

         G(f) = (r12 + r23.exp(-2j.beta2.d)) / (1 + r12.r23.exp(-2j.beta2.d))

     sur la mesure, en laissant libres l'epaisseur d, le retard de standoff
     tau0 et un facteur complexe K (gain et phase residuels). Fonctionne
     quelle que soit l'epaisseur, y compris tres en dessous de la resolution.

     L'optimisation est non convexe : grille grossiere en (d, tau0) puis
     raffinement. Une simple descente locale se piege.

UTILISATION
    Autotest sur donnees synthetiques (aucun instrument requis) :
        python mesure_epaisseur.py --autotest

    Mesure d'une plaque de PMMA de 50 mm, libre dans l'air :
        python mesure_epaisseur.py --mesure --eps 2.6 --substrat air --max-ep 70

    Cartilage sur os :
        python mesure_epaisseur.py --mesure --eps 42.5 --substrat os

    Re-analyse d'un balayage deja enregistre :
        python mesure_epaisseur.py --fichier mesures/pmma50.npz --eps 2.6 \
                                   --substrat air --max-ep 70
"""

import argparse
import os
import sys

import numpy as np
from scipy.optimize import minimize
from scipy.signal import find_peaks

import calibration_sol

c = 299_792_458.0
eps0 = 8.8541878128e-12
PORT_VNA = "ASRL6::INSTR"
DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mesures")

# Position du pic fixe de l'antenne sur l'axe brut. Les distances affichees
# en sont retranchees, pour se lire depuis le plan rayonnant. MESUREE le
# 21/08/2026 (plaque metallique a deux distances) ; identique a la constante
# du meme nom dans radar_cartilage_online.py, a garder synchronisee.
PLAN_ANTENNE_MM = 702.0

# Substrats disponibles : (eps_r, sigma en S/m)
SUBSTRATS = {
    "air":        (1.0, 0.0),
    "os":         (11.0, 0.30),
    "os_spongieux": (20.0, 0.80),
    "metal":      (None, None),        # traite a part : r23 = -1
    "eau":        (70.0, 2.0),
}


# ======================================================================
# MODELE PHYSIQUE
# ======================================================================
def indice(freqs, eps_r, sigma):
    return np.sqrt(eps_r - 1j * sigma / (2 * np.pi * freqs * eps0))


def gamma_couche(freqs, d, eps_r, sigma, substrat):
    """Coefficient de reflexion d'une couche sur un substrat, serie complete."""
    n2 = indice(freqs, eps_r, sigma)
    r12 = (1.0 - n2) / (1.0 + n2)
    if substrat == "metal":
        r23 = -np.ones_like(n2)
    else:
        e3, s3 = SUBSTRATS[substrat]
        n3 = indice(freqs, e3, s3)
        r23 = (n2 - n3) / (n2 + n3)
    prop = np.exp(-2j * (2 * np.pi * freqs / c) * n2 * d)
    return (r12 + r23 * prop) / (1.0 + r12 * r23 * prop)


# ======================================================================
# METHODE A : DETECTION A DEUX PICS
# ======================================================================
def profil_distance(freqs, s11, zoom=16):
    """Enveloppe et axe des distances (aller simple equivalent, en mm).

    Le pas temporel vaut 1/(n_fft.df) avec df = BW/(N-1) : utiliser 1/BW
    surestime les distances de N/(N-1).
    """
    fen = np.hanning(len(s11))
    n_fft = len(s11) * zoom
    prof = np.abs(np.fft.ifft(s11 * fen, n=n_fft)) * zoom
    df = (freqs[-1] - freqs[0]) / (len(freqs) - 1)
    pas = 1.0 / (n_fft * df) * c / 2.0 * 1e3
    dist = np.arange(n_fft) * pas
    demi = n_fft // 2
    return dist[:demi], prof[:demi], pas


def offset_parabolique(y, i):
    if i <= 0 or i >= len(y) - 1:
        return 0.0
    den = y[i - 1] - 2.0 * y[i] + y[i + 1]
    if den == 0.0:
        return 0.0
    return max(-0.5, min(0.5, 0.5 * (y[i - 1] - y[i + 1]) / den))


def methode_deux_pics(freqs, s11, eps_r, d_min_mm=10.0):
    """Rend (epaisseur_mm, ecart_apparent_mm, positions) ou None si echec."""
    dist, prof, pas = profil_distance(freqs, s11)
    m = dist >= d_min_mm
    dd, pp = dist[m], prof[m]
    seuil = 3.0 * np.median(pp)
    ecart_min = max(1, int(round(15.0 / pas)))
    idx, props = find_peaks(pp, prominence=seuil, distance=ecart_min)
    if len(idx) < 2:
        return None
    deux = np.sort(idx[np.argsort(props["prominences"])[-2:]])
    pos = [dd[i] + offset_parabolique(pp, i) * pas for i in deux]
    ecart = pos[1] - pos[0]
    return ecart / np.sqrt(eps_r), ecart, pos


# ======================================================================
# METHODE B : INVERSION SUR MODELE
# ======================================================================
def _cout_projete(g, mod):
    """Residu de ||g - K.mod||^2 minimise sur K complexe."""
    den = np.sum(np.abs(mod) ** 2, axis=-1)
    num = np.abs(np.tensordot(np.conj(mod), g, axes=([-1], [0]))) ** 2
    return float(np.vdot(g, g).real) - num / den


def methode_modele(freqs, s11, eps_r, sigma, substrat,
                   d_max_mm=8.0, tau_centre=None, tau_demi=None):
    """Ajuste (d, tau0) avec K complexe libre.

    Rend (epaisseur_mm, standoff_mm, residu, modele_ajuste). Le standoff
    est la distance a la PREMIERE SURFACE, estimee et non fournie : le
    programme mesure donc la distance ET l'epaisseur d'un seul ajustement.
    """
    g = np.asarray(s11)
    if tau_centre is None:
        # depart : position du pic le plus fort du profil
        dist, prof, _ = profil_distance(freqs, g)
        tau_centre = 2.0 * dist[int(np.argmax(prof))] * 1e-3 / c
    if tau_demi is None:
        tau_demi = 200e-12

    d_grille = np.linspace(0.05e-3, d_max_mm * 1e-3, max(400, int(d_max_mm * 40)))
    t_grille = tau_centre + np.linspace(-tau_demi, tau_demi, 121)
    mod_d = np.array([gamma_couche(freqs, d, eps_r, sigma, substrat)
                      for d in d_grille])

    best, arg = np.inf, (0, 0)
    for it, t in enumerate(t_grille):
        r = _cout_projete(g, mod_d * np.exp(-2j * np.pi * freqs * t))
        i = int(np.argmin(r))
        if r[i] < best:
            best, arg = r[i], (i, it)

    def cout(x):
        d, t = x
        if not (1e-6 < d < d_max_mm * 1.5e-3):
            return 1e9
        m = np.exp(-2j * np.pi * freqs * t) * gamma_couche(
            freqs, d, eps_r, sigma, substrat)
        return _cout_projete(g, m)

    r = minimize(cout, [d_grille[arg[0]], t_grille[arg[1]]],
                 method="Nelder-Mead",
                 options=dict(xatol=1e-12, fatol=1e-18, maxiter=6000))
    residu = r.fun / float(np.vdot(g, g).real)

    # modele ajuste, pour la superposition graphique
    d_hat, t_hat = r.x
    m = np.exp(-2j * np.pi * freqs * t_hat) * gamma_couche(
        freqs, d_hat, eps_r, sigma, substrat)
    K = np.vdot(m, g) / np.vdot(m, m)
    standoff_mm = t_hat * c / 2.0 * 1e3      # distance a la 1re surface
    return d_hat * 1e3, standoff_mm, residu, K * m


def methode_permittivite(freqs, s11, d_mm, sigma, substrat,
                         eps_min=1.5, eps_max=90.0):
    """Probleme INVERSE : l'epaisseur est connue (pied a coulisse), on cherche
    eps_r. C'est la mesure qui valide toute la chaine, et c'est la repetition
    de la caracterisation dielectrique du cartilage.

    Rend (eps_r, residu, modele_ajuste).
    """
    g = np.asarray(s11)
    d = d_mm * 1e-3
    dist, prof, _ = profil_distance(freqs, g)
    tau0 = 2.0 * dist[int(np.argmax(prof))] * 1e-3 / c

    e_grille = np.linspace(eps_min, eps_max, 900)
    t_grille = tau0 + np.linspace(-200e-12, 200e-12, 121)
    mod_e = np.array([gamma_couche(freqs, d, e, sigma, substrat)
                      for e in e_grille])

    best, arg = np.inf, (0, 0)
    for it, t in enumerate(t_grille):
        r = _cout_projete(g, mod_e * np.exp(-2j * np.pi * freqs * t))
        i = int(np.argmin(r))
        if r[i] < best:
            best, arg = r[i], (i, it)

    def cout(x):
        e, t = x
        if not (eps_min < e < eps_max):
            return 1e9
        m = np.exp(-2j * np.pi * freqs * t) * gamma_couche(
            freqs, d, e, sigma, substrat)
        return _cout_projete(g, m)

    r = minimize(cout, [e_grille[arg[0]], t_grille[arg[1]]],
                 method="Nelder-Mead",
                 options=dict(xatol=1e-10, fatol=1e-18, maxiter=6000))
    e_hat, t_hat = r.x
    m = np.exp(-2j * np.pi * freqs * t_hat) * gamma_couche(
        freqs, d, e_hat, sigma, substrat)
    K = np.vdot(m, g) / np.vdot(m, m)
    return e_hat, r.fun / float(np.vdot(g, g).real), K * m


# ======================================================================
# AFFICHAGE
# ======================================================================
def trace(freqs, s11, ajuste, pics, ep_pics, ep_mod, residu, titre, chemin):
    """Trois panneaux : profil de distance, module et phase de Gamma(f).

    Le panneau du milieu est le vrai diagnostic : si le modele ne se superpose
    pas a la mesure, le resultat n'a aucune valeur, quel que soit le chiffre
    affiche.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BLEU, ORANGE, ENCRE2 = "#2a78d6", "#eb6834", "#52514e"
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(14.5, 4.6))

    # --- profil de distance ---
    dist, prof, _ = profil_distance(freqs, s11)
    db = 20 * np.log10(prof / np.max(prof) + 1e-12)
    m = dist <= 500
    a1.plot(dist[m], db[m], lw=1.6, color=BLEU)
    res = 1.7 * c / (2 * (freqs[-1] - freqs[0])) * 1e3
    if pics is not None:
        for i, p in enumerate(pics):
            a1.axvline(p, color=ORANGE, ls="--", lw=1.4)
            a1.annotate(f"{p:.1f}", (p, 2), color=ORANGE, fontsize=8.5,
                        ha="center")
        a1.annotate("", (pics[0], -3), (pics[1], -3),
                    arrowprops=dict(arrowstyle="<->", color=ORANGE, lw=1.4))
        a1.annotate(f"ecart {pics[1]-pics[0]:.1f} mm\n"
                    f"= {(pics[1]-pics[0])/res:.2f} x resolution",
                    ((pics[0] + pics[1]) / 2, -3), (0.97, 0.86),
                    textcoords="axes fraction", color=ORANGE, fontsize=8.5,
                    ha="right",
                    arrowprops=dict(arrowstyle="-", color=ORANGE, lw=0.9,
                                    alpha=0.6))
    a1.plot([10, 10 + res], [-45, -45], lw=3, color=ENCRE2, solid_capstyle="butt")
    a1.annotate(f"resolution {res:.0f} mm", (10, -42), fontsize=8.5, color=ENCRE2)
    a1.set_xlabel("Distance apparente (mm)")
    a1.set_ylabel("Niveau relatif (dB)")
    a1.set_ylim(-60, 6)
    a1.set_title("Profil de distance", fontsize=10.5)

    # --- module ---
    fg = freqs / 1e9
    a2.plot(fg, 20 * np.log10(np.abs(s11) + 1e-12), lw=1.8, color=BLEU,
            label="mesure")
    a2.plot(fg, 20 * np.log10(np.abs(ajuste) + 1e-12), lw=1.6, ls="--",
            color=ORANGE, label="modele ajuste")
    a2.set_xlabel("Frequence (GHz)")
    a2.set_ylabel(r"$|\Gamma|$ (dB)")
    a2.legend(fontsize=8.5)
    a2.set_title(f"Franges : residu {residu:.4f}", fontsize=10.5)

    # --- phase ---
    a3.plot(fg, np.degrees(np.angle(s11 * np.conj(ajuste))), lw=1.6,
            color=BLEU)
    a3.axhline(0, color=ENCRE2, ls=":", lw=1.2)
    a3.set_xlabel("Frequence (GHz)")
    a3.set_ylabel("Phase mesure - modele (deg)")
    a3.set_title("Residu de phase", fontsize=10.5)

    for x in (a1, a2, a3):
        x.grid(alpha=0.25, lw=0.6)
        for cote in ("top", "right"):
            x.spines[cote].set_visible(False)
        x.tick_params(colors=ENCRE2)

    sous = f"modele {ep_mod:.3f} mm"
    if ep_pics is not None:
        sous = f"deux pics {ep_pics:.3f} mm  |  " + sous
    fig.suptitle(f"{titre}   —   {sous}", fontsize=12)
    fig.tight_layout()
    fig.savefig(chemin, dpi=140)
    print(f"\n  Graphe enregistre : {chemin}")


# ======================================================================
# ACQUISITION
# ======================================================================
def acquiert(start, stop, points, n_moy):
    from skrf.vi.vna.nanovna import NanoVNAv2
    import skrf as rf
    vna = NanoVNAv2(PORT_VNA, backend="@py")
    vna.frequency = rf.Frequency(start=start, stop=stop, npoints=points,
                                 unit="GHz")
    try:
        for _ in range(2):
            vna.get_s11_s21()
        acc, freqs = None, None
        for k in range(n_moy):
            s11, _ = vna.get_s11_s21()
            if freqs is None:
                freqs = s11.f.copy()
                acc = np.zeros(len(freqs), dtype=complex)
            acc += s11.s[:, 0, 0]
            print(f"      balayage {k + 1}/{n_moy}", end="\r", flush=True)
        print(" " * 32, end="\r")
        return freqs, acc / n_moy
    finally:
        try:
            vna.close()
        except Exception:
            pass


# ======================================================================
# AUTOTEST
# ======================================================================
def autotest():
    print("=" * 72)
    print("  AUTOTEST -- donnees synthetiques, aucun instrument requis")
    print("=" * 72)
    freqs = np.linspace(1.4e9, 6.3e9, 201)
    R = 0.150
    cas = [
        ("PMMA 80 mm dans l'air", 80.0, 2.6, 0.0, "air", 110.0),
        ("PMMA 50 mm dans l'air", 50.0, 2.6, 0.0, "air", 70.0),
        ("PMMA 20 mm dans l'air", 20.0, 2.6, 0.0, "air", 30.0),
        ("PMMA 12 mm dans l'air", 12.0, 2.6, 0.0, "air", 20.0),
        ("PMMA 4 mm dans l'air", 4.0, 2.6, 0.0, "air", 10.0),
        ("Cartilage 3 mm sur os", 3.0, 42.5, 1.6, "os", 8.0),
        ("Cartilage 1 mm sur os", 1.0, 42.5, 1.6, "os", 8.0),
    ]
    print(f"\n  {'cas':<24}{'vrai':>8}{'2 pics':>12}{'modele':>12}"
          f"{'erreur modele':>15}")
    print("  " + "-" * 71)
    ok = True
    for nom, d_mm, eps, sig, sub, dmax in cas:
        g = np.exp(-2j * np.pi * freqs * 2 * R / c) * gamma_couche(
            freqs, d_mm * 1e-3, eps, sig, sub)
        a = methode_deux_pics(freqs, g, eps)
        b, _, _, _ = methode_modele(freqs, g, eps, sig, sub, d_max_mm=dmax)
        txt_a = f"{a[0]:11.3f}" if a else f"{'echec':>11}"
        err = b - d_mm
        if abs(err) > 0.02:
            ok = False
        print(f"  {nom:<24}{d_mm:7.1f} {txt_a} {b:11.3f} {err:+14.4f}")
    print("\n  Le modele doit retrouver la verite a mieux que 0,02 mm partout.")
    print(f"  VERDICT : {'REUSSI' if ok else 'ECHEC'}")
    print("\n  Noter ou la detection a deux pics echoue : c'est exactement la")
    print("  limite de resolution, et la raison d'etre de la seconde methode.")
    return 0 if ok else 1


# ======================================================================
def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--autotest", action="store_true")
    ap.add_argument("--mesure", action="store_true")
    ap.add_argument("--fichier")
    ap.add_argument("--nom", default="mesure")
    ap.add_argument("--eps", type=float, default=42.5, help="eps_r de la couche")
    ap.add_argument("--sigma", type=float, default=None,
                    help="conductivite S/m (defaut : 0 si eps<10, sinon 1,6)")
    ap.add_argument("--substrat", default="os", choices=list(SUBSTRATS))
    ap.add_argument("--max-ep", type=float, default=8.0,
                    help="epaisseur maximale exploree, mm")
    ap.add_argument("--start", type=float, default=1.4)
    ap.add_argument("--stop", type=float, default=6.3)
    ap.add_argument("--points", type=int, default=201)
    ap.add_argument("--moy", type=int, default=16)
    ap.add_argument("--cal", default="sol_courante")
    ap.add_argument("--fond", default=None,
                    help="nom d'un balayage 'scene vide' de mesures/ a "
                         "soustraire (reflexion propre de l'antenne). "
                         "INDISPENSABLE sur mesure reelle.")
    ap.add_argument("--plan-antenne", type=float,
                    default=PLAN_ANTENNE_MM,
                    help="position du pic fixe d'antenne (mm) : les "
                         "distances affichees en sont retranchees. "
                         "N'affecte PAS l'epaisseur mesuree.")
    ap.add_argument("--sans-graphe", action="store_true",
                    help="n'ecrit pas le graphe de diagnostic")
    ap.add_argument("--epaisseur", type=float, default=None,
                    help="epaisseur CONNUE en mm : inverse le probleme et "
                         "mesure eps_r au lieu de l'epaisseur")
    args = ap.parse_args()

    if args.autotest:
        sys.exit(autotest())

    sigma = args.sigma
    if sigma is None:
        sigma = 0.0 if args.eps < 10.0 else 1.6

    if args.fichier:
        z = np.load(args.fichier)
        freqs, s11 = z["freqs"], z["s11"]
        print(f"  Balayage relu : {args.fichier}")
    elif args.mesure:
        print(f"  Acquisition {args.start}-{args.stop} GHz, {args.points} pts, "
              f"{args.moy} moyennes...")
        freqs, s11 = acquiert(args.start, args.stop, args.points, args.moy)
        os.makedirs(DOSSIER, exist_ok=True)
        chemin = os.path.join(DOSSIER, f"{args.nom}.npz")
        np.savez_compressed(chemin, freqs=freqs, s11=s11)
        print(f"  Balayage brut enregistre : {chemin}")
    else:
        ap.error("choisir --autotest, --mesure ou --fichier")

    cal = calibration_sol.charger(args.cal)
    if cal is not None:
        s11 = calibration_sol.applique(cal, freqs, s11)

    # --- Soustraction du fond (reflexion propre de l'antenne) ---
    # Cette reflexion est ADDITIVE et absente du modele stratifie : non retiree,
    # elle fausse l'epaisseur de plusieurs dixiemes et rend la distance absurde.
    # Un residu de soustraction de 3 % ne coute plus que 0,02 mm.
    if args.fond:
        chemin_fond = os.path.join(DOSSIER, f"{args.fond}.npz")
        if not os.path.exists(chemin_fond):
            print(f"  ERREUR : fond introuvable ({chemin_fond}).")
            print("  Enregistre-le d'abord, RIEN devant l'antenne :")
            print(f"      python mesure_epaisseur.py --mesure --nom {args.fond} "
                  "--sans-graphe")
            sys.exit(1)
        zf = np.load(chemin_fond)
        if len(zf["freqs"]) != len(freqs) or not np.allclose(zf["freqs"], freqs):
            print("  ERREUR : le fond n'a pas le meme balayage que la mesure.")
            sys.exit(1)
        fond = zf["s11"]
        if cal is not None:
            fond = calibration_sol.applique(cal, freqs, fond)
        s11 = s11 - fond
        print(f"  Fond '{args.fond}' soustrait.")
    else:
        print("  [fond] AUCUN fond soustrait. Sur mesure reelle, la reflexion")
        print("         propre de l'antenne fausse le resultat -- voir --fond.")

    # ---- Mode inverse : epaisseur connue, on mesure eps_r ----
    if args.epaisseur is not None:
        print("\n" + "=" * 72)
        print(f"  MESURE DE PERMITTIVITE -- epaisseur imposee "
              f"{args.epaisseur} mm, substrat = {args.substrat}")
        print("=" * 72)
        e, residu, ajuste = methode_permittivite(freqs, s11, args.epaisseur,
                                                 sigma, args.substrat)
        print(f"  eps_r mesure ......... {e:8.3f}       "
              f"(residu relatif {residu:.4f})")
        print(f"  indice n = sqrt(eps) . {np.sqrt(e):8.3f}")
        print(f"\n  Reperes : PMMA 2,6 | PTFE 2,1 | verre 6,9 | "
              f"cartilage 40-45 | eau 70-78")
        if residu > 0.2:
            print(f"\n  ATTENTION : residu eleve ({residu:.2f}) -- le modele ne")
            print("  decrit pas la mesure. Verifier le substrat et la calibration.")
        if not args.sans_graphe:
            os.makedirs(DOSSIER, exist_ok=True)
            trace(freqs, s11, ajuste, None, None, args.epaisseur, residu,
                  f"{args.nom} — epaisseur {args.epaisseur} mm imposee, "
                  f"eps_r mesure = {e:.3f}",
                  os.path.join(DOSSIER, f"{args.nom}_eps.png"))
        return

    print("\n" + "=" * 72)
    print(f"  COUCHE eps_r = {args.eps}, sigma = {sigma} S/m, "
          f"substrat = {args.substrat}")
    print("=" * 72)

    a = methode_deux_pics(freqs, s11, args.eps)
    if a is None:
        print("  A. Deux pics ......... ECHEC (moins de deux echos separables)")
        print("     C'est normal si l'ecart apparent est sous la resolution.")
    else:
        ep, ecart, pos = a
        dist, prof, _ = profil_distance(freqs, s11)
        res = 1.7 * c / (2 * (freqs[-1] - freqs[0])) * 1e3
        print(f"  A. Deux pics ......... {ep:8.3f} mm")
        print(f"     pics a {pos[0]-args.plan_antenne:.1f} et "
              f"{pos[1]-args.plan_antenne:.1f} mm du plan d'antenne, ecart "
              f"{ecart:.1f} mm ({ecart/res:.2f} x la resolution de {res:.0f} mm)")

    b, standoff, residu, ajuste = methode_modele(
        freqs, s11, args.eps, sigma, args.substrat, d_max_mm=args.max_ep)
    print(f"  B. Modele stratifie .. {b:8.3f} mm   "
          f"(residu relatif {residu:.4f})")
    print(f"     DISTANCE a la 1re surface : "
          f"{standoff - args.plan_antenne:8.1f} mm du plan d'antenne")
    print("     (estimee par l'ajustement, jamais fournie au programme)")

    if a is not None:
        res = 1.7 * c / (2 * (freqs[-1] - freqs[0])) * 1e3
        ratio = a[1] / res
        ecart_m = abs(a[0] - b)
        print(f"\n  Ecart entre les deux methodes : {ecart_m:.3f} mm "
              f"({ecart_m / max(b, 1e-9) * 100:.1f} %)")
        if ratio < 2.5:
            print(f"  -> NON CONCLUANT. A {ratio:.2f} x la resolution, la")
            print("     detection a deux pics est biaisee de plusieurs pour cent")
            print("     par l'elargissement de la fenetre : son desaccord avec le")
            print("     modele est ATTENDU et ne signale pas un defaut. Il faut")
            print("     un ecart d'au moins 2,5 resolutions pour que la")
            print("     comparaison ait un sens.")
        elif ecart_m / max(b, 1e-9) < 0.02:
            print("  -> COHERENT. Les deux methodes s'accordent a mieux que 2 %.")
        else:
            print("  -> DIVERGENCE. Les echos sont largement separes, la")
            print("     detection a deux pics devrait etre juste : c'est un")
            print("     defaut du logiciel ou de la calibration, pas de la")
            print("     physique. Verifier eps_r, le substrat et la cal.")
    if residu > 0.2:
        print(f"\n  ATTENTION : residu eleve ({residu:.2f}). Le modele ne decrit")
        print("  pas bien la mesure -- mauvais eps_r, mauvais substrat, cible")
        print("  hors axe, ou reflexion parasite dans la scene.")

    if not args.sans_graphe:
        os.makedirs(DOSSIER, exist_ok=True)
        trace(freqs, s11, ajuste,
              a[2] if a else None, a[0] if a else None, b, residu,
              f"{args.nom} — eps_r {args.eps}, substrat {args.substrat}",
              os.path.join(DOSSIER, f"{args.nom}.png"))


if __name__ == "__main__":
    main()
