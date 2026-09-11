"""
CALIBRATION -- les corrections appliquees a CHAQUE mesure.

Ce programme produit des NOMBRES, rangés dans calibration/, que radar.py
applique ensuite systematiquement. C'est ce qui le distingue de
qualification.py, qui rend des verdicts sur le materiel et ne corrige rien.

DEUX CORRECTIONS, ET ELLES SONT DISTINCTES

  1. CALIBRATION SOL  (--sol)
     Etalons Short / Open / Load visses AU BOUT DU CABLE. Elle retire :
        e00      directivite -- la fuite du pont vers le recepteur, qui cree
                 le faux echo a distance nulle et fixe le plancher ;
        e11      desadaptation source -- les allers-retours entre le VNA et
                 une antenne mal adaptee ;
        e10.e01  suivi en reflexion -- la reponse du cable et du pont.

     Le LiteVNA a bien un menu CAL, mais son USB renvoie TOUJOURS des donnees
     brutes : sa calibration ne corrige que son propre ecran. D'ou ce
     programme.

  2. PLAN DE REFERENCE  (--plan)
     Le SOL ramene le plan au bout du cable, pas au plan rayonnant. Une plaque
     metallique mesuree a DEUX distances connues donne :
        la PENTE  -- doit valoir 1,000, elle verifie l'echelle des distances ;
        l'OFFSET  -- constant, c'est la position du plan de l'antenne.
     Un offset qui change entre les deux positions signale une erreur
     d'echelle, ou que les distances ne sont pas celles que l'on croit.
     Une pente a plus de 5 % de 1 est REFUSEE : rien n'est ecrit, le plan
     precedent reste en place.

UTILISATION
    python calibration.py --sol                  # les trois etalons
    python calibration.py --verifier             # plancher reel
    python calibration.py --plan 100 200         # plaque metal, 2 distances
    python calibration.py --etat                 # ce qui est en place
    python calibration.py --rejouer --short-l0 0.1e-9    # sans remesurer
"""

import argparse
import datetime
import io
import os
import sys

import numpy as np

import noyau
from noyau import c, DOSSIER_CAL
from commun.sol import (ETALONS_IDEAUX, gamma_open, gamma_short,  # noqa: E402,F401
                        gamma_load, resoudre, applique)

NOM_DEFAUT = "sol_courante"

# Le modele des etalons, la resolution et l'application de la SOL vivent
# dans commun/sol.py, partage avec le projet de tomographie. Importes ici,
# ils restent accessibles comme calibration.applique, calibration.resoudre...


def charger(nom=NOM_DEFAUT, silencieux=False):
    chemin = os.path.join(DOSSIER_CAL, f"{nom}.npz")
    if not os.path.exists(chemin):
        if not silencieux:
            print(f"  [cal] Aucune calibration ({nom}). Mesures BRUTES.")
        return None
    z = np.load(chemin, allow_pickle=True)
    cal = {k: z[k] for k in ("freqs", "e00", "e11", "e10e01")}
    if not silencieux:
        d = np.median(20 * np.log10(np.abs(cal["e00"]) + 1e-18))
        print(f"  [cal] '{nom}' : {cal['freqs'][0]/1e9:.3f}-"
              f"{cal['freqs'][-1]/1e9:.3f} GHz, {len(cal['freqs'])} pts, "
              f"directivite {d:.1f} dB")
    return cal


# ======================================================================
# MODES
# ======================================================================
def mode_sol(args, p):
    print("=" * 74)
    print("  CALIBRATION SOL")
    print("=" * 74)
    print(f"  {args.start}-{args.stop} GHz, {args.points} points, "
          f"{args.moy} moyennes (gain {10*np.log10(args.moy):.0f} dB)")
    print("""
  PLAN DE REFERENCE : visse les etalons AU BOUT DU CABLE, la ou ira
  l'antenne. Ne debranche rien d'autre entre les trois mesures et NE
  DEPLACE PAS LE CABLE : sa flexion change sa phase et ruine la
  calibration. Serre les SMA fermement mais sans forcer.
""")
    vna = noyau.ouvrir_vna(args.start, args.stop, args.points,
                           simu=['short', 'open', 'load'] if args.simu else None)
    mesures, freqs = [], None
    try:
        for nom, libelle in (("short", "COURT-CIRCUIT (SHORT)"),
                             ("open", "CIRCUIT OUVERT (OPEN)"),
                             ("load", "CHARGE 50 OHMS (LOAD)")):
            input(f"  Visse le {libelle} puis Entree... ")
            f, s = noyau.acquiert(vna, args.moy)
            if freqs is None:
                freqs = f
            mesures.append(s)
            db = np.median(20 * np.log10(np.abs(s) + 1e-18))
            print(f"      |S11| median {db:6.1f} dB")
            if nom in ("short", "open") and db < -3:
                print("      >> SUSPECT : un short ou un open doit renvoyer")
                print("         presque tout (~0 dB). Connecteur mal visse ?")
            if nom == "load" and db > -15:
                print("      >> SUSPECT : la charge reflechit beaucoup trop.")
            print()
    finally:
        try:
            vna.close()
        except Exception:
            pass

    ideaux = [gamma_short(freqs, p), gamma_open(freqs, p), gamma_load(freqs, p)]
    coefs, conds = resoudre(ideaux, mesures)
    _rapport(coefs, conds)
    os.makedirs(DOSSIER_CAL, exist_ok=True)
    chemin = os.path.join(DOSSIER_CAL, f"{args.nom}.npz")
    np.savez_compressed(chemin, freqs=freqs, **coefs,
                        brut_short=mesures[0], brut_open=mesures[1],
                        brut_load=mesures[2],
                        etalons=np.array([f"{k}={v:g}" for k, v in sorted(p.items())]))
    print(f"\n  Ecrit : {chemin}")
    print("  ETAPE SUIVANTE : --verifier, puis --plan 100 200")


def _rapport(coefs, conds):
    print("-" * 74)
    print("  TERMES D'ERREUR")
    print("-" * 74)
    for cle, lib in (("e00", "directivite"), ("e11", "desadaptation source"),
                     ("e10e01", "suivi en reflexion")):
        db = 20 * np.log10(np.abs(coefs[cle]) + 1e-18)
        print(f"  {lib:<24} {np.median(db):7.1f} dB  "
              f"(min {np.min(db):6.1f} / max {np.max(db):6.1f})")
    print(f"  conditionnement          median {np.median(conds):.1f}, "
          f"max {np.max(conds):.1f}")
    if np.max(conds) > 50:
        print("  >> Conditionnement eleve : etalons trop peu distincts a")
        print("     certaines frequences. Verifie les connexions.")


def mode_verifier(args):
    cal = charger(args.nom)
    if cal is None:
        sys.exit(1)
    print("\n  VERIFICATION : revisse la CHARGE 50 ohms au plan de reference.")
    print("  Apres correction sa reflexion devrait etre nulle : ce qui reste")
    print("  est le PLANCHER REEL du systeme.\n")
    input("  Entree quand la charge est en place... ")
    vna = noyau.ouvrir_vna(args.start, args.stop, args.points,
                           simu=['load'] if args.simu else None)
    try:
        freqs, brut = noyau.acquiert(vna, args.moy)
    finally:
        try:
            vna.close()
        except Exception:
            pass
    db = 20 * np.log10(np.abs(applique(cal, freqs, brut)) + 1e-18)
    bd = 20 * np.log10(np.abs(brut) + 1e-18)
    print(f"\n  Charge AVANT : median {np.median(bd):6.1f} dB, "
          f"pire {np.max(bd):6.1f} dB")
    print(f"  Charge APRES : median {np.median(db):6.1f} dB, "
          f"pire {np.max(db):6.1f} dB")
    print(f"  Gain de directivite : {np.median(bd) - np.median(db):.1f} dB")
    print("\n  L'echo de fond de couche recherche se situe vers -17 dB.")
    pire = np.max(db)
    if pire < -35:
        print(f"\n  VERDICT : BON ({pire:.0f} dB au pire).")
    elif pire < -25:
        print(f"\n  VERDICT : ACCEPTABLE ({pire:.0f} dB). La charge du kit")
        print("            limite le plancher ; utilisable sans marge.")
    else:
        print(f"\n  VERDICT : INSUFFISANT ({pire:.0f} dB). Reprends le serrage")
        print("            des connecteurs, puis la charge elle-meme.")


def mode_plan(args):
    """Plaque metallique a deux distances connues : pente et offset."""
    d1, d2 = args.plan
    if abs(d2 - d1) < 50:
        print("  Les deux distances doivent differer d'au moins 50 mm.")
        sys.exit(1)
    cal = charger(args.nom)
    print("\n" + "=" * 74)
    print(f"  PLAN DE REFERENCE -- plaque metallique a {d1:.0f} puis "
          f"{d2:.0f} mm")
    print("=" * 74)
    print("  Mesure les distances au reglet DEPUIS LA FACE DE L'ANTENNE.")
    print("  Plaque d'au moins 300 x 300 mm, rien d'autre dans l'axe.\n")

    vna = noyau.ouvrir_vna(
        args.start, args.stop, args.points,
        simu=[f'metal@{d1:.0f}', f'metal@{d2:.0f}'] if args.simu else None)
    pics = []
    try:
        for d in (d1, d2):
            input(f"  Place la plaque a {d:.0f} mm puis Entree... ")
            freqs, s = noyau.acquiert(vna, args.moy)
            s = applique(cal, freqs, s)
            dist, prof, pas = noyau.profil_distance(freqs, s)
            i = int(np.argmax(prof))
            p = dist[i] + noyau._offset_parabolique(prof, i) * pas
            pics.append(p)
            print(f"      pic a {p:.1f} mm (plan du VNA)")
    finally:
        try:
            vna.close()
        except Exception:
            pass

    pente = (pics[1] - pics[0]) / (d2 - d1)
    off = [pics[0] - d1, pics[1] - d2]
    plan = float(np.mean(off))
    print("\n" + "-" * 74)
    print(f"  Pente ...... {pente:.4f}   (doit valoir 1,000)")
    print(f"  Offsets .... {off[0]:+.1f} et {off[1]:+.1f} mm")
    print(f"  Plan de l'antenne : {plan:.1f} mm")
    ecart = abs(off[0] - off[1])
    if ecart > 10:
        print(f"\n  ATTENTION : offsets incoherents ({ecart:.0f} mm d'ecart).")
    ch = os.path.join(DOSSIER_CAL, "plan.npz")
    if abs(pente - 1.0) > noyau.PENTE_TOLERANCE:
        print(f"\n  REFUSE : pente a {pente:.3f}. Un ecart de plus de "
              f"{100 * noyau.PENTE_TOLERANCE:.0f} %")
        print("  n'est PAS une erreur de plan de reference. Verifie que les")
        print("  deux distances sont bien celles que tu crois -- confondre")
        print("  'a 200 mm' et 'de 200 mm' donne exactement une pente double.")
        print()
        if os.path.exists(ch):
            print(f"  RIEN N'EST ECRIT. Le plan en place est conserve : {ch}")
        else:
            print("  RIEN N'EST ECRIT. radar.py garde la valeur par defaut, "
                  f"{noyau.PLAN_ANTENNE_MM:.0f} mm.")
        print(f"  Replace la plaque et relance : python calibration.py "
              f"--plan {d1:.0f} {d2:.0f}")
        return False
    os.makedirs(DOSSIER_CAL, exist_ok=True)
    np.savez_compressed(ch, plan_mm=plan, pente=pente,
                        distances=np.array([d1, d2]), pics=np.array(pics))
    print(f"\n  Ecrit : {ch}")
    print("  radar.py l'utilisera automatiquement.")
    return True


def mode_etat():
    print("=" * 74)
    print("  ETAT DE LA CALIBRATION")
    print("=" * 74)
    sol = os.path.join(DOSSIER_CAL, f"{NOM_DEFAUT}.npz")
    if os.path.exists(sol):
        z = np.load(sol)
        d = np.median(20 * np.log10(np.abs(z["e00"]) + 1e-18))
        print(f"  SOL .............. OK   {z['freqs'][0]/1e9:.2f}-"
              f"{z['freqs'][-1]/1e9:.2f} GHz, {len(z['freqs'])} pts, "
              f"directivite {d:.1f} dB")
    else:
        print("  SOL .............. ABSENT   -> python calibration.py --sol")
    pl = os.path.join(DOSSIER_CAL, "plan.npz")
    if os.path.exists(pl):
        z = np.load(pl)
        pente = float(z["pente"])
        if abs(pente - 1.0) > noyau.PENTE_TOLERANCE:
            print(f"  Plan d'antenne ... ECARTE {float(z['plan_mm']):.1f} mm "
                  f"(pente {pente:.3f}) -> --plan 100 200")
        else:
            print(f"  Plan d'antenne ... OK   {float(z['plan_mm']):.1f} mm "
                  f"(pente {pente:.3f})")
    else:
        print(f"  Plan d'antenne ... ABSENT -> --plan 100 200 "
              f"(valeur par defaut {noyau.PLAN_ANTENNE_MM:.0f} mm)")
    fond = os.path.join(noyau.DOSSIER_MES, "fond.npz")
    print("  Fond d'antenne ... " + ("OK" if os.path.exists(fond) else
          "ABSENT -> python radar.py --mesure --nom fond, RIEN devant"))


# ======================================================================
# ASSISTANT GUIDE  (mode par defaut, sans argument)
# ======================================================================
def _journal(txt):
    """Trace horodatee de la session.

    C'est elle qui permet de diagnostiquer a distance, des jours plus tard, ce
    qui s'est reellement passe -- exactement ce qui avait servi a trouver
    l'offset de plan de reference de +31,7 mm.
    """
    os.makedirs(DOSSIER_CAL, exist_ok=True)
    with io.open(os.path.join(DOSSIER_CAL, "journal.txt"), "a",
                 encoding="utf-8") as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                + " | " + txt + "\n")


def _etape(n, total, titre, pourquoi, action):
    """Affiche une etape et demande confirmation. Rend False si sautee."""
    print()
    print("=" * 74)
    print("  ETAPE {}/{} -- {}".format(n, total, titre))
    print("=" * 74)
    for ligne in pourquoi:
        print("  POURQUOI : " + ligne if ligne is pourquoi[0]
              else "             " + ligne)
    print()
    for ligne in action:
        print("  > " + ligne)
    print()
    r = input("  [Entree] faire  |  [s] sauter  |  [q] quitter : ").strip().lower()
    if r == "q":
        print()
        print("  Session interrompue. Pour reprendre : python calibration.py")
        _journal("etape {} ({}) : INTERROMPU".format(n, titre))
        sys.exit(0)
    if r == "s":
        print("  -> etape sautee.")
        _journal("etape {} ({}) : sautee".format(n, titre))
        return False
    return True


def mode_guide(args, p):
    """Deroule la mise en route complete du banc, une etape a la fois.

    Reprend le principe du protocole guide de l'ancienne interface : une seule
    instruction a l'ecran, un avancement visible, une verification par etape et
    un journal de tout ce qui s'est passe.
    """
    total = 5
    print("=" * 74)
    print("  ASSISTANT DE MISE EN ROUTE DU BANC")
    print("=" * 74)
    print()
    print("  Cinq etapes. Chacune explique ce qu'elle fait et pourquoi, puis")
    print("  verifie son propre resultat. Tu peux sauter une etape deja faite,")
    print("  quitter et reprendre plus tard : l'assistant detecte ce qui est")
    print("  deja en place.")
    print()
    print("  Tout est consigne dans calibration/journal.txt.")
    _journal("--- nouvelle session d'assistant ---")
    if args.simu:
        print()
        print("  [SIMU] instrument simule : aucun materiel necessaire.")

    if _etape(1, total, "ETAT DES LIEUX",
              ["savoir ce qui est deja en place evite de tout refaire"],
              ["Rien a manipuler."]):
        mode_etat()
        _journal("etape 1 (etat) : affiche")

    if _etape(2, total, "CALIBRATION SOL",
              ["retire la directivite du pont, la desadaptation source et la",
               "reponse du cable. Sans elle les amplitudes sont fausses et le",
               "plancher de mesure reste haut."],
              ["Prepare les trois etalons : COURT-CIRCUIT, OUVERT, CHARGE.",
               "Ils se vissent AU BOUT DU CABLE, la ou ira l'antenne.",
               "NE DEPLACE PAS LE CABLE de toute l'operation : sa flexion",
               "  change sa phase et ruine la calibration.",
               "Serre fermement sans forcer, de la meme facon a chaque fois."]):
        mode_sol(args, p)
        _journal("etape 2 (SOL) : ecrit " + args.nom + ".npz")

    if _etape(3, total, "VERIFICATION DU PLANCHER",
              ["mesure ce que la calibration NE corrige pas. C'est le plancher",
               "reel du systeme, et il decide de tout le reste : l'echo de fond",
               "de couche recherche se situe vers -17 dB."],
              ["Revisse la CHARGE 50 ohms au bout du cable."]):
        mode_verifier(args)
        _journal("etape 3 (verification) : faite")

    plan_refuse = False
    if _etape(4, total, "PLAN DE REFERENCE",
              ["la calibration place l'origine des distances au bout du cable,",
               "pas au plan rayonnant de l'antenne. La plaque metallique, vue a",
               "deux distances connues, fait le report."],
              ["Visse l'ANTENNE au bout du cable.",
               "Prepare une PLAQUE METALLIQUE d'au moins 300 x 300 mm.",
               "Tu la placeras a DEUX distances, mesurees au reglet DEPUIS LA",
               "  FACE DE L'ANTENNE : d'abord 100 mm, puis 200 mm.",
               "ATTENTION : 200 mm est une position ABSOLUE, pas un",
               "  deplacement de 200 mm. Confondre les deux double la pente",
               "  mesuree, et c'est deja arrive."]):
        args.plan = [100.0, 200.0]
        if mode_plan(args):
            _journal("etape 4 (plan) : fait")
        else:
            plan_refuse = True
            _journal("etape 4 (plan) : REFUSE, pente hors tolerance")

    if _etape(5, total, "FOND D'ANTENNE",
              ["la reflexion propre de l'antenne est ADDITIVE et absente du",
               "modele stratifie. Non retiree, elle fausse l'epaisseur de",
               "~0,4 mm et rend la distance absurde."],
              ["Retire la plaque.",
               "RIEN devant l'antenne, rien a moins de 2 m dans l'axe."]):
        vna = noyau.ouvrir_vna(args.start, args.stop, args.points,
                               simu=["vide"] if args.simu else None)
        try:
            freqs, brut = noyau.acquiert(vna, args.moy)
        finally:
            try:
                vna.close()
            except Exception:
                pass
        ch = noyau.enregistre(os.path.join(noyau.DOSSIER_MES, "fond.npz"),
                              freqs, brut)
        print()
        print("  Fond enregistre : " + ch)
        _journal("etape 5 (fond) : ecrit fond.npz")

    print()
    print("=" * 74)
    print("  BILAN")
    print("=" * 74)
    mode_etat()
    print()
    if plan_refuse:
        print("  Le banc N'EST PAS pret : le plan de reference a ete REFUSE a")
        print("  l'etape 4. Replace la plaque a 100 puis 200 mm, et relance :")
        print()
        print("      python calibration.py --plan 100 200")
    else:
        print("  Le banc est pret. Mesure d'une plaque de PMMA de 12 mm :")
        print()
        print("      python radar.py --mesure --nom pmma12 --fond fond \\")
        print("             --milieu pmma --substrat air --max-ep 20")
    print()
    print("  Journal de la session : calibration/journal.txt")
    _journal("--- session terminee ---")


# ======================================================================
def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sol", action="store_true", help="acquiert S / O / L")
    ap.add_argument("--verifier", action="store_true", help="plancher reel")
    ap.add_argument("--plan", nargs=2, type=float, metavar=("D1", "D2"),
                    help="plaque metallique a deux distances (mm)")
    ap.add_argument("--etat", action="store_true")
    ap.add_argument("--rejouer", action="store_true",
                    help="recalcule depuis les balayages bruts sauvegardes")
    ap.add_argument("--nom", default=NOM_DEFAUT)
    ap.add_argument("--start", type=float, default=noyau.BANDE_DEFAUT[0])
    ap.add_argument("--stop", type=float, default=noyau.BANDE_DEFAUT[1])
    ap.add_argument("--points", type=int, default=noyau.POINTS_DEFAUT)
    ap.add_argument("--moy", type=int, default=16)
    ap.add_argument("--simu", action="store_true",
                    help="instrument SIMULE : apprendre et tester sans materiel")
    for k in ETALONS_IDEAUX:
        ap.add_argument(f"--{k.replace('_', '-')}", type=float, default=None)
    args = ap.parse_args()

    p = dict(ETALONS_IDEAUX)
    for k in p:
        v = getattr(args, k, None)
        if v is not None:
            p[k] = v

    if args.etat:
        return mode_etat()
    if args.verifier:
        return mode_verifier(args)
    if args.plan:
        if not mode_plan(args):
            sys.exit(1)
        return
    if args.rejouer:
        ch = os.path.join(DOSSIER_CAL, f"{args.nom}.npz")
        if not os.path.exists(ch):
            print(f"  Rien a rejouer : {ch} absent.")
            sys.exit(1)
        z = np.load(ch, allow_pickle=True)
        if "brut_short" not in z:
            print("  Ce fichier ne contient pas les balayages bruts.")
            sys.exit(1)
        freqs = z["freqs"]
        mes = [z["brut_short"], z["brut_open"], z["brut_load"]]
        print(f"  Rejeu de {ch} avec :")
        for k in sorted(p):
            if p[k]:
                print(f"      {k} = {p[k]:g}")
        ideaux = [gamma_short(freqs, p), gamma_open(freqs, p),
                  gamma_load(freqs, p)]
        coefs, conds = resoudre(ideaux, mes)
        _rapport(coefs, conds)
        np.savez_compressed(ch, freqs=freqs, **coefs, brut_short=mes[0],
                            brut_open=mes[1], brut_load=mes[2],
                            etalons=np.array([f"{k}={v:g}"
                                              for k, v in sorted(p.items())]))
        print(f"\n  Reecrit : {ch}")
        return
    if args.sol:
        return mode_sol(args, p)
    return mode_guide(args, p)      # aucun mode : assistant guide


if __name__ == "__main__":
    main()
