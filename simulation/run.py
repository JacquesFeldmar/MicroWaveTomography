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
                          symetrie=not args.sans_symetrie))


def _sortie(res, freqs, dossier, prefixe, titre):
    os.makedirs(dossier, exist_ok=True)
    print("\n" + tr.table_bilan(res))
    print("\n  rappel des mesures du 9 octobre :")
    for d_cm, (proche, lointain) in sorted(MESURES_9_OCT.items()):
        print(f"       {d_cm:.0f} cm : ecarts {proche-d_cm:.2f} et "
              f"{lointain-d_cm:.2f} cm")
    chemins = fig.toutes(res, freqs, dossier, prefixe, titre)
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
    res = tr.bilan(freqs, fond, mesures, a)
    _sortie(res, freqs, args.sortie, "analytique_",
            "Modèle analytique du montage")


def mode_mesures(args):
    from donnees import charge_dossier
    freqs, fond, mesures = charge_dossier(args.donnees)
    a = Acquisition(f_min=freqs[0], f_max=freqs[-1], points=len(freqs))
    print(f"\n  mesures lues dans {args.donnees} : {len(mesures)} positions, "
          f"{len(freqs)} points de {freqs[0]/1e9:.2f} a {freqs[-1]/1e9:.2f} GHz")
    res = tr.bilan(freqs, fond, mesures, a)
    _sortie(res, freqs, args.sortie, "mesures_", "Mesures réelles")


def mode_fdtd(args, avec_plaque):
    import fdtd as F
    m = _montage(args)
    antenne = F.charge_antenne(args.antenne)
    sortie = os.path.join(args.sortie, antenne.NOM)
    retard = getattr(antenne, "retard_attendu_ns", lambda: None)()
    print(f"\n  antenne : {antenne.DESCRIPTION}")
    if retard is not None:
        print(f"  retard attendu : {retard:.3f} ns -> decalage "
              f"{299792458.0*retard*1e-9*100:.1f} cm")
    print(m.resume())

    distances = args.distances if avec_plaque else [None]
    print("\n  cout estime :")
    for x in distances:
        cells, pas, minutes = F.estime_cout(m, x)
        nom = "antenne seule" if x is None else f"plaque a {x:.0f} cm"
        print(f"    {nom:22s} {cells/1e6:7.2f} Mcellules, {pas:6d} pas, "
              f"~{minutes:6.1f} min")
    if args.cout:
        print("\n  (--cout : rien n'a ete lance)")
        return

    a = m.acquisition
    sorties = {}
    for x in distances:
        freqs, s11 = F.lance(m, antenne, x, fils=args.fils,
                             verbose=args.verbose)
        nom = "antenne_seule" if x is None else f"plaque_{x:.0f}cm"
        F.ecrit_s1p(os.path.join(sortie, nom + ".s1p"), freqs, s11,
                    commentaire=f"openEMS, {antenne.NOM}, {nom}")
        sorties[x] = s11
    if not avec_plaque:
        freqs, s11 = freqs, sorties[None]
        bande = getattr(antenne, "bande_attendue_ghz", lambda: None)()
        ref = getattr(antenne, "s11_fiche", None)
        chemin = fig.figure_s11(
            freqs, s11, os.path.join(sortie, "s11_antenne_seule.png"),
            bande_attendue=bande, reference=ref() if ref else None,
            titre=f"{antenne.NOM} — antenne seule")
        db = 20 * np.log10(np.abs(s11))
        sous = freqs[db < -10] / 1e9
        print(f"\n  |S11| < -10 dB de {sous.min():.2f} a {sous.max():.2f} GHz "
              f"(couverture dans cet intervalle : "
              f"{100*(db[(freqs/1e9>=sous.min())&(freqs/1e9<=sous.max())] < -10).mean():.0f} %)")
        if bande:
            print(f"  bande annoncee par l'antenne : {bande[0]:.2f} - "
                  f"{bande[1]:.2f} GHz")
        print("  figure : " + chemin)
        return
    freqs, fond = F.lance(m, antenne, None, fils=args.fils,
                          verbose=args.verbose)
    F.ecrit_s1p(os.path.join(sortie, "antenne_seule.s1p"), freqs, fond,
                commentaire=f"openEMS, {antenne.NOM}, fond")
    res = tr.bilan(freqs, fond, {x: sorties[x] for x in args.distances}, a)
    _sortie(res, freqs, sortie, "fdtd_", f"Simulation openEMS — {antenne.NOM}")


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
    p.add_argument("--sans-symetrie", action="store_true")
    p.add_argument("--fils", type=int, default=None)
    p.add_argument("--verbose", type=int, default=0)
    p.add_argument("--cout", action="store_true",
                   help="estime le cout de la simulation sans la lancer")
    args = p.parse_args()

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
