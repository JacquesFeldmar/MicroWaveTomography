"""
CALIBRATION SOL (Short-Open-Load) LOGICIELLE DU LITEVNA.

POURQUOI CE MODULE EXISTE
    Le LiteVNA possede un menu CAL, mais son interface USB renvoie TOUJOURS des
    donnees BRUTES, par conception : la calibration faite sur l'appareil ne
    corrige que son propre ecran. Tout ce que lit `vna.get_s11_s21()` est
    non corrige. La correction doit donc etre refaite ici.

CE QU'ELLE CORRIGE
    Modele d'erreur a un port :

        Gamma_mes = e00 + (e10.e01 . Gamma_vrai) / (1 - e11 . Gamma_vrai)

        e00     directivite        : le signal qui fuit du pont vers le
                                     recepteur sans jamais atteindre l'antenne.
                                     C'est LUI qui cree le faux echo a distance
                                     nulle et qui limite le plancher.
        e11     desadaptation source : les allers-retours entre le VNA et
                                     l'antenne mal adaptee (-6,6 dB dans notre
                                     bande haute : 22 % reflechi !).
        e10.e01 suivi en reflexion : la reponse en amplitude et en phase du
                                     cable et du pont.

    Inverser ce modele donne :

        Gamma_vrai = (Gamma_mes - e00) / (e10.e01 + e11 . (Gamma_mes - e00))

OU PLACER LE PLAN DE REFERENCE
    Visser les etalons LA OU IRA L'ANTENNE, c'est-a-dire au bout du cable.
    Tout ce qui est en amont (cable, connecteurs, pont) est alors corrige.
    Il restera ensuite a prolonger le plan jusqu'au plan rayonnant de
    l'antenne : c'est le role de la plaque metallique (qualif_centre_phase.py).

ETALONS IMPARFAITS : EST-CE GRAVE ?
    Un kit generique ne publie pas ses coefficients. Simulation de la chaine
    complete (mesure -> calibration avec etalons supposes ideaux -> inversion
    par le modele physique avec retard et gain complexe libres), biais resultant
    sur une couche de cartilage de 1 a 5 mm :

        ouvert, 20 a 100 fF ignores .............. 0,01 a 0,04 mm   negligeable
        offsets de 5 ps ignores .................. 0,03 mm          negligeable
        court-circuit, 0,10 nH ignore ............ 0,07 mm          acceptable
        court-circuit, 0,30 nH ignore ............ jusqu'a 0,98 mm  redhibitoire
        charge mediocre (-25 dB au lieu de -45) .. jusqu'a 1,24 mm  redhibitoire

    L'ordre d'importance est donc CHARGE >> COURT-CIRCUIT >> OUVERT, et non
    l'inverse comme on le suppose souvent. La raison : tout ce qui est lineaire
    en frequence (capacite de frange de l'ouvert, offsets) est absorbe par le
    reglage du plan de reference sur la plaque metallique ; seule la courbure
    subsiste. L'inductance du court-circuit et surtout la reflexion residuelle
    de la charge, elles, ne sont pas lineaires : elles se logent dans la
    directivite, exactement la ou vit l'echo de fond de couche.

    Concretement : la charge est la piece critique du kit. Le mode --verifier
    la mesure. Si le plancher est mediocre, c'est elle qu'il faut remplacer.

UTILISATION
    Acquisition d'une calibration :
        python calibration_sol.py --nom banc

    Verification (plancher effectif) :
        python calibration_sol.py --verifier --nom banc

    Recalcul a posteriori, sans rien remesurer, avec de meilleurs modeles
    d'etalons (les balayages bruts sont conserves) :
        python calibration_sol.py --rejouer --nom banc --open-c0 55e-15

    Depuis un autre programme :
        import calibration_sol
        cal = calibration_sol.charger()                 # None si absente
        s11_corrige = calibration_sol.applique(cal, freqs, s11_brut)
"""

import argparse
import os
import sys

import numpy as np

Z0 = 50.0
PORT_VNA = "ASRL6::INSTR"
DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration")
NOM_DEFAUT = "sol_courante"

# Coefficients d'etalons. Tout a zero = etalons ideaux. Renseigner si le
# fabricant les publie (fichier .cal / .s1p de Keysight, Maury, SDR-Kits...).
ETALONS_IDEAUX = dict(
    open_offset_ps=0.0, open_c0=0.0, open_c1=0.0, open_c2=0.0, open_c3=0.0,
    short_offset_ps=0.0, short_l0=0.0, short_l1=0.0, short_l2=0.0, short_l3=0.0,
)


# ======================================================================
# MODELE DES ETALONS
# ======================================================================
def gamma_open(freqs, p):
    """Ouvert : capacite de frange C(f) = C0 + C1.f + C2.f^2 + C3.f^3, puis
    rotation du plan par le retard d'offset."""
    f = np.asarray(freqs, dtype=float)
    C = p["open_c0"] + p["open_c1"] * f + p["open_c2"] * f**2 + p["open_c3"] * f**3
    w = 2 * np.pi * f
    g = (1.0 - 1j * w * C * Z0) / (1.0 + 1j * w * C * Z0)
    return g * np.exp(-2j * w * p["open_offset_ps"] * 1e-12)


def gamma_short(freqs, p):
    """Court-circuit : inductance serie L(f), puis rotation du plan."""
    f = np.asarray(freqs, dtype=float)
    L = p["short_l0"] + p["short_l1"] * f + p["short_l2"] * f**2 + p["short_l3"] * f**3
    w = 2 * np.pi * f
    Zc = 1j * w * L
    g = (Zc - Z0) / (Zc + Z0)
    return g * np.exp(-2j * w * p["short_offset_ps"] * 1e-12)


def gamma_load(freqs, p):
    """Charge : supposee parfaite. Son defaut reel est indiscernable de la
    directivite -- c'est precisement ce que mesure le mode --verifier."""
    return np.zeros(len(freqs), dtype=complex)


# ======================================================================
# RESOLUTION DU MODELE D'ERREUR
# ======================================================================
def resoudre(g_ideaux, g_mesures):
    """Trois etalons, trois inconnues (e00, e11, e10e01), a chaque frequence.

    En posant  d = e00,  s = e11,  t = e10.e01 - e00.e11 , le modele
        G_m = e00 + t.G_a / (1 - e11.G_a)
    devient LINEAIRE :
        G_m = d + s.(G_a.G_m) + t.G_a
    soit un systeme 3x3 exact par frequence. C'est la forme bilineaire
    classique, numeriquement bien plus sure qu'une resolution directe.
    """
    n = len(g_mesures[0])
    e00 = np.empty(n, dtype=complex)
    e11 = np.empty(n, dtype=complex)
    e10e01 = np.empty(n, dtype=complex)
    conds = np.empty(n)

    for k in range(n):
        A = np.array([[1.0, g_ideaux[i][k] * g_mesures[i][k], g_ideaux[i][k]]
                      for i in range(3)], dtype=complex)
        b = np.array([g_mesures[i][k] for i in range(3)], dtype=complex)
        conds[k] = np.linalg.cond(A)
        d, s, t = np.linalg.solve(A, b)
        e00[k], e11[k], e10e01[k] = d, s, t + d * s

    return dict(e00=e00, e11=e11, e10e01=e10e01), conds


def applique(cal, freqs, s11_brut):
    """Corrige un balayage brut. `cal` est le dictionnaire rendu par charger().

    Si l'axe frequentiel differe de celui de la calibration, les termes
    d'erreur sont interpoles (partie reelle et imaginaire separement) et un
    avertissement est emis une seule fois.
    """
    if cal is None:
        return s11_brut
    f_cal = cal["freqs"]
    f = np.asarray(freqs, dtype=float)

    if len(f) != len(f_cal) or not np.allclose(f, f_cal, rtol=1e-9):
        if not cal.get("_averti", False):
            print("  [cal] ATTENTION : le balayage ne correspond pas a celui de "
                  "la calibration.\n"
                  f"        cal  : {f_cal[0]/1e9:.3f}-{f_cal[-1]/1e9:.3f} GHz, "
                  f"{len(f_cal)} pts\n"
                  f"        mesure: {f[0]/1e9:.3f}-{f[-1]/1e9:.3f} GHz, {len(f)} pts\n"
                  "        Les termes d'erreur sont interpoles -- refais plutot "
                  "la calibration sur le balayage de travail.")
            cal["_averti"] = True
        if f[0] < f_cal[0] - 1e3 or f[-1] > f_cal[-1] + 1e3:
            print("  [cal] Extrapolation hors bande : calibration ignoree.")
            return s11_brut

        def interp(v):
            return (np.interp(f, f_cal, v.real) + 1j * np.interp(f, f_cal, v.imag))
        e00, e11, e10e01 = interp(cal["e00"]), interp(cal["e11"]), interp(cal["e10e01"])
    else:
        e00, e11, e10e01 = cal["e00"], cal["e11"], cal["e10e01"]

    num = np.asarray(s11_brut) - e00
    return num / (e10e01 + e11 * num)


def charger(nom=NOM_DEFAUT, silencieux=False):
    """Charge une calibration. Rend None si le fichier n'existe pas."""
    chemin = os.path.join(DOSSIER, f"{nom}.npz")
    if not os.path.exists(chemin):
        if not silencieux:
            print(f"  [cal] Aucune calibration ({chemin}). Mesures BRUTES.")
        return None
    z = np.load(chemin, allow_pickle=True)
    cal = {k: z[k] for k in ("freqs", "e00", "e11", "e10e01")}
    if not silencieux:
        d_db = 20 * np.log10(np.abs(cal["e00"]) + 1e-18)
        print(f"  [cal] Calibration '{nom}' chargee : "
              f"{cal['freqs'][0]/1e9:.3f}-{cal['freqs'][-1]/1e9:.3f} GHz, "
              f"{len(cal['freqs'])} pts | directivite mediane {np.median(d_db):.1f} dB")
    return cal


# ======================================================================
# ACQUISITION
# ======================================================================
def acquiert(vna, n_moy, n_jetes=2):
    """Moyennage VECTORIEL : abaisse le plancher de bruit de 10.log10(N) dB."""
    for _ in range(n_jetes):
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


def ouvrir_vna(start_ghz, stop_ghz, points):
    from skrf.vi.vna.nanovna import NanoVNAv2
    import skrf as rf
    vna = NanoVNAv2(PORT_VNA, backend='@py')
    vna.frequency = rf.Frequency(start=start_ghz, stop=stop_ghz,
                                 npoints=points, unit='GHz')
    return vna


# ======================================================================
# PROGRAMME PRINCIPAL
# ======================================================================
def params_depuis_args(args):
    p = dict(ETALONS_IDEAUX)
    for k in p:
        v = getattr(args, k, None)
        if v is not None:
            p[k] = v
    return p


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nom", default=NOM_DEFAUT)
    ap.add_argument("--start", type=float, default=1.4, help="GHz")
    ap.add_argument("--stop", type=float, default=6.3, help="GHz")
    ap.add_argument("--points", type=int, default=101)
    ap.add_argument("--moy", type=int, default=16)
    ap.add_argument("--verifier", action="store_true",
                    help="mesure le plancher effectif apres calibration")
    ap.add_argument("--rejouer", action="store_true",
                    help="recalcule depuis les balayages bruts sauvegardes")
    for k, v in ETALONS_IDEAUX.items():
        ap.add_argument(f"--{k.replace('_', '-')}", type=float, default=None)
    args = ap.parse_args()

    os.makedirs(DOSSIER, exist_ok=True)
    chemin = os.path.join(DOSSIER, f"{args.nom}.npz")
    p = params_depuis_args(args)

    # ---------------- VERIFICATION ----------------
    if args.verifier:
        cal = charger(args.nom)
        if cal is None:
            sys.exit(1)
        print("\n  VERIFICATION : revisse la CHARGE 50 ohms au plan de reference.")
        print("  Apres correction, sa reflexion devrait etre nulle : ce qui reste")
        print("  est le PLANCHER REEL de ton systeme.\n")
        input("  Entree quand la charge est en place... ")
        vna = ouvrir_vna(args.start, args.stop, args.points)
        try:
            freqs, brut = acquiert(vna, args.moy)
        finally:
            try:
                vna.close()
            except Exception:
                pass
        corr = applique(cal, freqs, brut)
        db = 20 * np.log10(np.abs(corr) + 1e-18)
        brut_db = 20 * np.log10(np.abs(brut) + 1e-18)
        print(f"\n  Charge AVANT calibration : median {np.median(brut_db):6.1f} dB, "
              f"pire {np.max(brut_db):6.1f} dB")
        print(f"  Charge APRES calibration : median {np.median(db):6.1f} dB, "
              f"pire {np.max(db):6.1f} dB")
        print(f"  Gain de directivite      : {np.median(brut_db) - np.median(db):6.1f} dB")
        print("\n  Reference : l'echo de fond de couche que l'on cherche se situe")
        print("  vers -17 dB en absolu. Il faut un plancher NETTEMENT sous cette")
        print("  valeur -- vise -35 dB ou mieux.")
        pire = np.max(db)
        if pire < -35:
            print(f"\n  VERDICT : BON ({pire:.0f} dB au pire).")
        elif pire < -25:
            print(f"\n  VERDICT : ACCEPTABLE ({pire:.0f} dB au pire). La charge du kit")
            print("            limite le plancher ; utilisable mais sans marge.")
        else:
            print(f"\n  VERDICT : INSUFFISANT ({pire:.0f} dB au pire). Verifie le")
            print("            serrage des connecteurs (couple, pas a la main),")
            print("            et que rien n'a bouge entre les trois etalons.")
        return

    # ---------------- REJEU ----------------
    if args.rejouer:
        if not os.path.exists(chemin):
            print(f"  Rien a rejouer : {chemin} absent."); sys.exit(1)
        z = np.load(chemin, allow_pickle=True)
        if "brut_short" not in z:
            print("  Ce fichier ne contient pas les balayages bruts."); sys.exit(1)
        freqs = z["freqs"]
        mesures = [z["brut_short"], z["brut_open"], z["brut_load"]]
        print(f"  Rejeu depuis {chemin} avec les etalons :")
        for k in sorted(p):
            if p[k]:
                print(f"      {k} = {p[k]:g}")
    else:
        # ---------------- ACQUISITION GUIDEE ----------------
        print("=" * 76)
        print("  CALIBRATION SOL DU LITEVNA")
        print("=" * 76)
        print(f"  Bande {args.start}-{args.stop} GHz, {args.points} points, "
              f"{args.moy} moyennes (gain {10*np.log10(args.moy):.0f} dB)")
        print("""
  PLAN DE REFERENCE : visse les etalons AU BOUT DU CABLE, la ou ira
  l'antenne. Ne debranche RIEN d'autre entre les trois mesures et ne
  deplace pas le cable : sa flexion change sa phase et ruine la
  calibration. Serre les SMA fermement mais sans forcer.
""")
        try:
            vna = ouvrir_vna(args.start, args.stop, args.points)
            print(f"  LiteVNA connecte ({vna.id}).\n")
        except Exception as e:
            print(f"  ERREUR de connexion : {e}"); sys.exit(1)

        mesures, freqs = [], None
        try:
            for nom, libelle in (("short", "COURT-CIRCUIT (SHORT)"),
                                 ("open", "CIRCUIT OUVERT (OPEN)"),
                                 ("load", "CHARGE 50 OHMS (LOAD)")):
                input(f"  Visse le {libelle} puis Entree... ")
                f, s = acquiert(vna, args.moy)
                if freqs is None:
                    freqs = f
                mesures.append(s)
                db = 20 * np.log10(np.abs(s) + 1e-18)
                print(f"      mesure : |S11| median {np.median(db):6.1f} dB")
                if nom in ("short", "open") and np.median(db) < -3:
                    print("      >> SUSPECT : un short ou un open doit renvoyer")
                    print("         presque tout (~0 dB). Connecteur mal visse ?")
                if nom == "load" and np.median(db) > -15:
                    print("      >> SUSPECT : la charge reflechit beaucoup trop.")
                print()
        finally:
            try:
                vna.close()
            except Exception:
                pass

    # ---------------- RESOLUTION ----------------
    ideaux = [gamma_short(freqs, p), gamma_open(freqs, p), gamma_load(freqs, p)]
    coefs, conds = resoudre(ideaux, mesures)

    print("-" * 76)
    print("  TERMES D'ERREUR")
    print("-" * 76)
    for cle, libelle in (("e00", "directivite"),
                         ("e11", "desadaptation source"),
                         ("e10e01", "suivi en reflexion")):
        db = 20 * np.log10(np.abs(coefs[cle]) + 1e-18)
        print(f"  {libelle:<24} {np.median(db):7.1f} dB  "
              f"(min {np.min(db):6.1f} / max {np.max(db):6.1f})")
    print(f"  conditionnement du systeme  median {np.median(conds):.1f}, "
          f"max {np.max(conds):.1f}")
    if np.max(conds) > 50:
        print("  >> Conditionnement eleve : les etalons ne sont pas assez")
        print("     distincts a certaines frequences. Verifie les connexions.")

    d_med = np.median(20 * np.log10(np.abs(coefs["e00"]) + 1e-18))
    print(f"\n  La directivite brute vaut {d_med:.1f} dB : c'est le niveau du faux")
    print("  echo qui polluait tes mesures sans calibration. Il est maintenant")
    print("  soustrait.")

    sauve = dict(freqs=freqs, **coefs,
                 brut_short=mesures[0], brut_open=mesures[1], brut_load=mesures[2],
                 etalons=np.array([f"{k}={v:g}" for k, v in sorted(p.items())]))
    np.savez_compressed(chemin, **sauve)
    print(f"\n  Calibration ecrite dans {chemin}")
    print("  radar_cartilage_online.py la chargera automatiquement.")
    print("\n  ETAPE SUIVANTE : `python calibration_sol.py --verifier` pour")
    print("  connaitre le plancher reel, puis la plaque metallique")
    print("  (qualif_centre_phase.py) pour porter le plan de reference")
    print("  jusqu'au plan rayonnant de l'antenne.")


if __name__ == "__main__":
    main()
