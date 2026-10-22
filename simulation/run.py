"""RUN -- point d'entree unique du projet.

    python run.py --mode analytique                     # sans openEMS, instantane
    python run.py --mode analytique --derive -0.25 --cote-plaque 30
    python run.py --mode mesures --donnees chemin/vers/data
    python run.py --mode fdtd-antenne --cout            # cout seulement
    python run.py --mode fdtd-antenne                   # openEMS, antenne seule
    python run.py --mode fdtd --distances 50 60 70      # openEMS, avec la plaque

Chaque mode produit le meme jeu de figures et le meme tableau que le rapport
pour John, de sorte que les trois sources -- modele, simulation, mesure --
soient comparables ligne a ligne.
"""
import argparse
import os

import numpy as np

from banc import Acquisition, Antenne, Maillage, Montage, Plaque, MESURES_9_OCT
import traitement as tr
import figures as fig
from modele import ModeleAntenne, simule


def _montage(args):
    return Montage(
        acquisition=Acquisition(f_min=args.fmin * 1e9, f_max=args.fmax * 1e9,
                                points=args.points),
        antenne=Antenne(),
        plaque=Plaque(cote=args.cote_plaque * 10,
                      distances_cm=tuple(args.distances)),
        maillage=Maillage(mailles_par_lambda_air=args.mailles_air,
                          mailles_par_lambda=args.mailles_substrat,
                          maille_min=args.maille_min, rapport_max=args.rapport_max,
                          facteur_courant=args.facteur_courant,
                          marge_air_mm=args.marge_air, n_pas_max=args.n_pas_max,
                          duree_ns=args.duree_ns, symetrie=False))


def _options_pics(args):
    return dict(seuil_relatif_db=args.seuil_pics_db,
                prominence_min_db=args.proeminence_pics_db,
                mode_pics=args.mode_pics)


def _sortie(res, freqs, dossier, prefixe, titre, reference_9_oct=False):
    os.makedirs(dossier, exist_ok=True)
    print("\n" + tr.table_bilan(res))
    if reference_9_oct:
        print("\n  repere historique UWB Surveyor du 9 octobre (autre antenne/banc) :")
        for d_cm, (proche, lointain) in sorted(MESURES_9_OCT.items()):
            print(f"       {d_cm:.0f} cm : ecarts {proche-d_cm:.2f} et "
                  f"{lointain-d_cm:.2f} cm")
    chemins = fig.toutes(res, freqs, dossier, prefixe, titre,
                        reference_9_oct=reference_9_oct)
    print("\n  figures :")
    for c in chemins:
        print("      " + c)


# ======================================================================
def mode_analytique(args):
    m = _montage(args)
    a = m.acquisition
    freqs = np.linspace(a.f_min, a.f_max, a.points)
    ant = ModeleAntenne(tau1_ns=args.tau1, tau2_ns=args.tau2, a2=args.a2,
                        derive_ns=args.derive)
    print(f"\n  modele analytique : tau1 = {ant.tau1_ns:.4f} ns "
          f"({299792458.0*ant.tau1_ns*1e-9*100:.1f} cm), "
          f"tau2 = {ant.tau2_ns:.4f} ns, a2 = {ant.a2:.2f}, "
          f"derive = {ant.derive_ns:+.2f} ns")
    print(m.resume())
    echos = tuple() if args.sans_echos else ((0.05, 95.0),)
    fond = simule(freqs, 50.0, ant, args.cote_plaque / 100, echos)[0]
    mesures = {x: simule(freqs, x, ant, args.cote_plaque / 100, echos,
                         bruit_db=args.bruit)[1] for x in args.distances}
    res = tr.bilan(freqs, fond, mesures, a, **_options_pics(args))
    _sortie(res, freqs, args.sortie, "analytique_",
            "Modèle analytique du montage", args.reference_9_oct)


def mode_mesures(args):
    from donnees import charge_dossier
    freqs, fond, mesures = charge_dossier(args.donnees)
    a = Acquisition(f_min=freqs[0], f_max=freqs[-1], points=len(freqs))
    print(f"\n  mesures lues dans {args.donnees} : {len(mesures)} positions, "
          f"{len(freqs)} points de {freqs[0]/1e9:.2f} a {freqs[-1]/1e9:.2f} GHz")
    res = tr.bilan(freqs, fond, mesures, a, **_options_pics(args))
    _sortie(res, freqs, args.sortie, "mesures_", "Mesures réelles", args.reference_9_oct)


def mode_fdtd(args, avec_plaque):
    import fdtd as F
    m = _montage(args)
    antenne = F.charge_antenne(args.antenne)
    sortie = os.path.abspath(os.path.join(args.sortie, antenne.NOM))
    retard = getattr(antenne, "retard_attendu_ns", lambda: None)()
    print(f"\n  antenne : {antenne.DESCRIPTION}")
    if retard is not None:
        print(f"  estimation interne de l'antenne : {retard:.3f} ns "
              "(ne constitue pas un biais de distance calibre)")
    print(m.resume())

    distances = [None] + args.distances if avec_plaque else [None]
    communes = args.distances if avec_plaque else None
    print("\n  cout estime :")
    for x in distances:
        cells, pas, minutes = F.estime_cout(m, x, antenne_mod=antenne,
                                          distances_communes_cm=communes,
                                          duree_ns=args.duree_ns)
        nom = "fond" if x is None else f"plaque a {x:g} cm"
        print(f"    {nom:22s} {cells/1e6:7.2f} Mcellules, {pas:6d} pas, "
              f"~{minutes:6.1f} min")
    if args.cout:
        print("\n  (--cout : rien n'a ete lance)")
        return

    a = m.acquisition
    if not avec_plaque:
        freqs, s11 = F.lance(m, antenne, None,
                             dossier=os.path.join(sortie, "fdtd", "antenne_seule"),
                             fils=args.fils, verbose=args.verbose,
                             duree_ns=args.duree_ns)
        F.ecrit_s1p(os.path.join(sortie, "antenne_seule.s1p"), freqs, s11,
                    commentaire=f"openEMS, {antenne.NOM}, antenne seule")
        bande = getattr(antenne, "bande_attendue_ghz", lambda: None)()
        ref = getattr(antenne, "s11_fiche", None)
        chemin = fig.figure_s11(
            freqs, s11, os.path.join(sortie, "s11_antenne_seule.png"),
            bande_attendue=bande, reference=ref() if ref else None,
            titre=f"{antenne.NOM} — antenne seule")
        synthese = tr.bandes_adaptees(freqs, s11)
        segments = synthese["segments_hz"]
        texte = "; ".join(f"{bas/1e9:.3f}–{haut/1e9:.3f}" for bas, haut in segments)
        print("\n  |S11| < -10 dB : " + (texte + " GHz" if segments else "aucun point"))
        print(f"  segments contigus aux points echantillonnes, sans interpolation ; "
              f"couverture de toute l'acquisition : {100*synthese['couverture']:.1f} %")
        if bande:
            print(f"  bande annoncee par l'antenne : {bande[0]:.2f} - "
                  f"{bande[1]:.2f} GHz")
        print("  figure : " + chemin)
        return
    freqs, fond, mesures = F.serie(m, antenne, args.distances,
                                  dossier_base=os.path.join(sortie, "fdtd"),
                                  fils=args.fils, verbose=args.verbose,
                                  duree_ns=args.duree_ns)
    F.ecrit_s1p(os.path.join(sortie, "background.s1p"), freqs, fond,
                commentaire=f"openEMS, {antenne.NOM}, fond")
    for x, s11 in mesures.items():
        F.ecrit_s1p(os.path.join(sortie, f"plate_{x:g}cm.s1p"), freqs, s11,
                    commentaire=f"openEMS, {antenne.NOM}, plate_{x:g}cm")
    res = tr.bilan(freqs, fond, mesures, a, **_options_pics(args))
    _sortie(res, freqs, sortie, "fdtd_", f"Simulation openEMS — {antenne.NOM}",
            args.reference_9_oct)


# ======================================================================
def principal():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", default="analytique",
                   choices=["analytique", "mesures", "fdtd-antenne", "fdtd"])
    p.add_argument("--antenne", default="uwb_surveyor",
                   help="dossier sous antennes/ : uwb_surveyor, "
                        "dipole_reference…")
    p.add_argument("--sortie", default="resultats")
    p.add_argument("--distances", type=float, nargs="+", default=[50, 60, 70])
    p.add_argument("--fmin", type=float, default=1.0, help="GHz")
    p.add_argument("--fmax", type=float, default=6.0, help="GHz")
    p.add_argument("--points", type=int, default=201)
    p.add_argument("--cote-plaque", type=float, default=60.0, help="cm")
    p.add_argument("--seuil-pics-db", type=float, default=-25.,
                   help="niveau minimal d'un candidat relatif au maximum (dB)")
    p.add_argument("--proeminence-pics-db", type=float, default=3.,
                   help="proeminence minimale d'un candidat (dB)")
    p.add_argument("--mode-pics", choices=["qualifies", "rapport"], default="qualifies",
                   help="rapport reproduit les maxima historiques, lobes secondaires inclus")
    p.add_argument("--reference-9-oct", action="store_true",
                   help="superpose le repere historique UWB Surveyor, sans validation du PCB courant")
    # modele analytique
    p.add_argument("--tau1", type=float, default=0.6671, help="ns")
    p.add_argument("--tau2", type=float, default=1.0873, help="ns")
    p.add_argument("--a2", type=float, default=0.20)
    p.add_argument("--derive", type=float, default=0.0,
                   help="ns de dispersion ; negatif = plus de retard en bas de bande")
    p.add_argument("--bruit", type=float, default=None, help="dB")
    p.add_argument("--sans-echos", action="store_true")
    # mesures
    p.add_argument("--donnees", default=None, help="dossier des CSV / s1p")
    # fdtd
    p.add_argument("--mailles-air", type=int, default=10)
    p.add_argument("--mailles-substrat", type=int, default=20)
    p.add_argument("--maille-min", type=float, default=.2, help="mm, detail d'alimentation")
    p.add_argument("--rapport-max", type=float, default=1.5, help="rapport de cellules voisines")
    p.add_argument("--facteur-courant", type=float, default=.95)
    p.add_argument("--marge-air", type=float, default=60., help="mm")
    p.add_argument("--n-pas-max", type=int, default=Maillage().n_pas_max)
    p.add_argument("--duree-ns", type=float, default=None, help="duree commune imposee, ns")
    p.add_argument("--sans-symetrie", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--fils", type=int, default=None)
    p.add_argument("--verbose", type=int, default=0)
    p.add_argument("--cout", action="store_true",
                   help="estime le cout de la simulation sans la lancer")
    args = p.parse_args()
    if not (np.isfinite(args.fmin) and np.isfinite(args.fmax) and 0 < args.fmin < args.fmax and args.points >= 3):
        p.error("0 < fmin < fmax et au moins trois points requis")
    if len(set(args.distances)) != len(args.distances) or any(not np.isfinite(x) or x <= 0 for x in args.distances):
        p.error("distances distinctes, finies et positives requises")
    if args.seuil_pics_db > 0 or not np.isfinite(args.seuil_pics_db) or args.proeminence_pics_db < 0 or not np.isfinite(args.proeminence_pics_db):
        p.error("seuil-pics-db <= 0 et proeminence-pics-db >= 0 requis")

    if args.mode == "analytique":
        mode_analytique(args)
    elif args.mode == "mesures":
        if not args.donnees:
            p.error("--mode mesures exige --donnees DOSSIER")
        mode_mesures(args)
    elif args.mode == "fdtd-antenne":
        mode_fdtd(args, avec_plaque=False)
    else:
        mode_fdtd(args, avec_plaque=True)


if __name__ == "__main__":
    principal()
