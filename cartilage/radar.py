"""
RADAR -- mesure en direct, mesure quantitative, enregistrement, rejeu.

Un seul programme pour tout ce qui touche a la mesure. Il donne toujours
LA DISTANCE ET L'EPAISSEUR : les deux sortent du meme ajustement, et la
distance n'est jamais fournie -- elle est estimee.

LES QUATRE MODES

  --live                 affichage temps reel. Sert a VISER, a controler la
                         tare, a voir entrer un objet parasite. Un balayage
                         par image, inversion sur modele en suivi.

  --mesure --nom X       une mesure soignee : N balayages moyennes, les deux
                         estimateurs, un graphe de diagnostic a trois
                         panneaux. C'est le mode qui produit un chiffre.

  --enregistre --nom X   enregistre une sequence de balayages BRUTS avec
                         leurs instants, en affichant en direct.

  --rejeu --nom X        rejoue une sequence enregistree a sa vitesse
                         d'origine, comme si l'instrument etait la. Permet de
                         re-analyser, de mettre au point sans materiel, et de
                         comparer deux traitements sur les MEMES donnees.

LES DEUX ESTIMATEURS, TOUJOURS LES DEUX

  A. deux pics       simple, mais fiable seulement au-dela de 2,5 largeurs de
                     resolution. En deca il rend une valeur fausse mais
                     plausible -- plus dangereux qu'un echec franc.
  B. modele stratifie exact a toute epaisseur. C'est lui qui mesure.

CE QU'IL FAUT AVOIR FAIT AVANT
    python calibration.py --sol           puis --verifier
    python calibration.py --plan 100 200
    python radar.py --mesure --nom fond   RIEN devant l'antenne

UTILISATION
    python radar.py --autotest
    python radar.py --live --milieu pmma --substrat air --max-ep 20
    python radar.py --mesure --nom pmma12 --milieu pmma --substrat air \\
                    --max-ep 20 --fond fond
    python radar.py --mesure --nom pmma12 --epaisseur 12.0 --substrat air
    python radar.py --enregistre --nom scan1 --duree 30
    python radar.py --rejeu --nom scan1
"""

import argparse
import os
import sys
import time

import numpy as np

import noyau
import calibration
from noyau import c, DOSSIER_MES


# ======================================================================
# SOURCES DE BALAYAGES
# ======================================================================
def source_vna(vna, duree=None):
    """Balayages depuis l'instrument, indefiniment ou pendant `duree`.

    Sur instrument SIMULE, la scene avance d'un balayage a l'autre. Le
    simulateur joue une liste de scenes -- c'est sa raison d'etre -- mais
    le mode direct ne l'avancait jamais : la cible restait figee et seul le
    bruit bougeait. L'acquisition moyennee, elle, avancait deja.
    """
    t0 = time.perf_counter()
    while True:
        f, s = noyau.balayage(vna)
        yield time.perf_counter() - t0, f, s
        if hasattr(vna, "avance"):
            vna.avance()
        if duree is not None and time.perf_counter() - t0 >= duree:
            return


def source_fichier(chemin, vitesse=1.0):
    """Balayages relus, restitues a leur cadence d'origine.

    vitesse = 1 -> temps reel ; 0 -> aussi vite que possible.
    """
    freqs, sweeps, temps = noyau.relit(chemin)
    t0 = time.perf_counter()
    for k in range(len(sweeps)):
        if vitesse > 0 and k > 0:
            cible = temps[k] / vitesse
            retard = cible - (time.perf_counter() - t0)
            if retard > 0:
                time.sleep(min(retard, 5.0))
        yield temps[k], freqs, sweeps[k]


# ======================================================================
# CHAINE DE CORRECTION
# ======================================================================
class Correcteur:
    """Applique, dans l'ordre, la calibration SOL puis la soustraction du fond.

    Les deux retirent des choses DIFFERENTES : le SOL corrige l'instrument
    (directivite, desadaptation, cable) ; le fond retire la reflexion PROPRE
    de l'antenne, qui est additive et absente du modele stratifie. Sans lui,
    l'epaisseur se trompe de quelques dixiemes et la distance devient absurde.
    """

    def __init__(self, nom_cal="sol_courante", nom_fond=None, silencieux=False):
        self.cal = calibration.charger(nom_cal, silencieux)
        self.fond = None
        if nom_fond:
            ch = os.path.join(DOSSIER_MES, f"{nom_fond}.npz")
            if not os.path.exists(ch):
                print(f"  ERREUR : fond introuvable ({ch}).")
                print("  Enregistre-le d'abord, RIEN devant l'antenne :")
                print(f"      python radar.py --mesure --nom {nom_fond} "
                      "--sans-graphe")
                sys.exit(1)
            f, sw, _ = noyau.relit(ch)
            self.fond_freqs = f
            self.fond = sw.mean(axis=0)
            if not silencieux:
                print(f"  [fond] '{nom_fond}' charge.")
        elif not silencieux:
            print("  [fond] AUCUN. Sur mesure reelle la reflexion propre de")
            print("         l'antenne fausse le resultat -- voir --fond.")

    def pose_fond(self, freqs, s11):
        """Bouton Tare : memorise la scene courante comme fond."""
        self.fond_freqs = np.asarray(freqs)
        self.fond = np.asarray(s11).copy()

    def retire_fond(self):
        self.fond = None

    def __call__(self, freqs, s11):
        s = calibration.applique(self.cal, freqs, s11)
        if self.fond is not None:
            if len(self.fond) != len(freqs) or not np.allclose(self.fond_freqs,
                                                               freqs):
                print("  ERREUR : le fond n'a pas le meme balayage.")
                sys.exit(1)
            s = s - calibration.applique(self.cal, freqs, self.fond)
        return s


# ======================================================================
# ANALYSE D'UN BALAYAGE
# ======================================================================
def analyse(freqs, s11, eps_r, sigma, substrat, max_ep, suivi=None):
    """Rend un dict complet. `suivi` = (d_mm, tau_ps) precedent, pour accelerer."""
    res = noyau.resolution_mm(freqs)
    a = noyau.methode_deux_pics(freqs, s11, eps_r)
    d0 = tau0 = None
    if suivi is not None:
        d0, tau0 = suivi
    d, standoff, residu, ajuste = noyau.mesure_modele(
        freqs, s11, eps_r, sigma, substrat, d_max_mm=max_ep,
        d0_mm=d0, tau0_ps=tau0)
    return dict(resolution=res, pics=a, ep_modele=d, standoff=standoff,
                residu=residu, ajuste=ajuste,
                suivi=(d, standoff / 1e3 * 2 / c * 1e12))


def imprime(r, plan, verbeux=True):
    a = r["pics"]
    if a is None:
        print("  A. Deux pics ......... ECHEC (moins de deux echos separables)")
        if verbeux:
            print("     Normal si l'ecart apparent est sous la resolution.")
    else:
        ep, ecart, pos = a
        print(f"  A. Deux pics ......... {ep:8.3f} mm")
        if verbeux:
            print(f"     pics a {pos[0]-plan:.1f} et {pos[1]-plan:.1f} mm, "
                  f"ecart {ecart:.1f} mm "
                  f"({ecart/r['resolution']:.2f} x la resolution "
                  f"de {r['resolution']:.0f} mm)")
    print(f"  B. Modele stratifie .. {r['ep_modele']:8.3f} mm   "
          f"(residu {r['residu']:.4f})")
    print(f"     DISTANCE a la 1re surface : {r['standoff']-plan:8.1f} mm")
    if not verbeux:
        return
    print("     (estimee par l'ajustement, jamais fournie au programme)")
    if a is not None:
        ratio = a[1] / r["resolution"]
        e = abs(a[0] - r["ep_modele"])
        print(f"\n  Ecart entre methodes : {e:.3f} mm "
              f"({e/max(r['ep_modele'],1e-9)*100:.1f} %)")
        if ratio < 2.5:
            print(f"  -> NON CONCLUANT. A {ratio:.2f} x la resolution, la")
            print("     detection a deux pics est biaisee de plusieurs pour")
            print("     cent par l'apodisation : son desaccord est ATTENDU.")
        elif e / max(r["ep_modele"], 1e-9) < 0.02:
            print("  -> COHERENT, a mieux que 2 %.")
        else:
            print("  -> DIVERGENCE. Les echos sont largement separes : c'est")
            print("     un defaut du logiciel ou de la calibration.")
    if r["residu"] > 0.2:
        print(f"\n  ATTENTION : residu eleve ({r['residu']:.2f}). Le modele ne")
        print("  decrit pas la mesure -- eps_r ou substrat faux, fond non")
        print("  soustrait, cible hors axe, ou reflexion parasite.")


# ======================================================================
# GRAPHE DE DIAGNOSTIC
# ======================================================================
def trace(freqs, s11, r, plan, titre, chemin):
    """Trois panneaux. Celui du milieu est le vrai controle : si le modele ne
    se superpose pas a la mesure, le chiffre affiche n'a aucune valeur."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BLEU, ORANGE, ENCRE = "#2a78d6", "#eb6834", "#52514e"
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(14.5, 4.6))

    dist, prof, _ = noyau.profil_distance(freqs, s11)
    dist = dist - plan
    db = 20 * np.log10(prof / np.max(prof) + 1e-12)
    m = (dist >= -50) & (dist <= 500)
    a1.plot(dist[m], db[m], lw=1.6, color=BLEU)
    if r["pics"] is not None:
        for p in r["pics"][2]:
            a1.axvline(p - plan, color=ORANGE, ls="--", lw=1.3)
        a1.annotate(f"ecart {r['pics'][1]:.1f} mm\n"
                    f"= {r['pics'][1]/r['resolution']:.2f} x resolution",
                    (0.97, 0.9), xycoords="axes fraction", ha="right",
                    fontsize=8.5, color=ORANGE)
    a1.axvline(r["standoff"] - plan, color=ENCRE, ls=":", lw=1.6)
    a1.annotate(f"modele : {r['standoff']-plan:.1f} mm",
                (0.97, 0.78), xycoords="axes fraction", ha="right",
                fontsize=8.5, color=ENCRE)
    res = r["resolution"]
    a1.plot([-40, -40 + res], [-45, -45], lw=3, color=ENCRE,
            solid_capstyle="butt")
    a1.annotate(f"resolution {res:.0f} mm", (-40, -42), fontsize=8.5,
                color=ENCRE)
    a1.set_xlabel("Distance depuis le plan de l'antenne (mm)")
    a1.set_ylabel("Niveau relatif (dB)")
    a1.set_ylim(-60, 6)
    a1.set_title("Profil de distance", fontsize=10.5)

    fg = freqs / 1e9
    a2.plot(fg, 20 * np.log10(np.abs(s11) + 1e-12), lw=1.8, color=BLEU,
            label="mesure")
    a2.plot(fg, 20 * np.log10(np.abs(r["ajuste"]) + 1e-12), lw=1.6, ls="--",
            color=ORANGE, label="modele ajuste")
    a2.set_xlabel("Frequence (GHz)")
    a2.set_ylabel(r"$|\Gamma|$ (dB)")
    a2.legend(fontsize=8.5)
    a2.set_title(f"Franges : residu {r['residu']:.4f}", fontsize=10.5)

    a3.plot(fg, np.degrees(np.angle(s11 * np.conj(r["ajuste"]))), lw=1.6,
            color=BLEU)
    a3.axhline(0, color=ENCRE, ls=":", lw=1.2)
    a3.set_xlabel("Frequence (GHz)")
    a3.set_ylabel("Phase mesure - modele (deg)")
    a3.set_title("Residu de phase", fontsize=10.5)

    for x in (a1, a2, a3):
        x.grid(alpha=0.25, lw=0.6)
        for k in ("top", "right"):
            x.spines[k].set_visible(False)
        x.tick_params(colors=ENCRE)

    sous = f"modele {r['ep_modele']:.3f} mm"
    if r["pics"] is not None:
        sous = f"deux pics {r['pics'][0]:.3f} mm  |  " + sous
    fig.suptitle(f"{titre}   —   {sous}", fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    fig.savefig(chemin, dpi=140)
    plt.close(fig)
    print(f"\n  Graphe : {chemin}")


# ======================================================================
# MODE TEMPS REEL (live et rejeu partagent cette boucle)
# ======================================================================
def boucle_temps_reel(source, corr, args, eps_r, sigma, plan, titre,
                      enregistre=None):
    """Affichage temps reel, avec commandes.

    Sert a VISER : sans retour visuel continu on ne peut pas orienter une
    antenne, ni voir qu'un objet parasite est entre dans la scene, ni
    reperer une derive. Les commandes reprennent celles de l'ancienne
    interface, qui manquaient depuis la refonte.
    """
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button, Slider

    etat = {"pause": False, "tare": 0, "capture": 0, "eps": eps_r,
            "enr": False, "seq": 0, "rejeu": False}
    tampon = {"sweeps": [], "temps": [], "freqs": None, "dernier": None}

    plt.ion()
    fig = plt.figure(figsize=(13, 7.5))
    ax = fig.add_axes([0.28, 0.20, 0.69, 0.70])
    ligne, = ax.plot([], [], lw=1.8, color="#2a78d6")
    vline = ax.axvline(0, color="#52514e", ls=":", lw=1.6)
    pics_pts, = ax.plot([], [], "o", ms=8, color="#eb6834")
    txt = ax.text(0.02, 0.97, "", transform=ax.transAxes, va="top",
                  fontsize=13, family="monospace",
                  bbox=dict(facecolor="white", alpha=0.9, edgecolor="#c9cfd6"))
    bandeau = fig.text(0.5, 0.975, "", ha="center", va="top", fontsize=11,
                       weight="bold", color="#1b4f8f",
                       bbox=dict(boxstyle="round", facecolor="#fdf6e3",
                                 edgecolor="#eda100"))
    ax.set_xlabel("Distance depuis le plan de l'antenne (mm)")
    ax.set_ylabel("Niveau relatif (dB)")
    ax.set_xlim(-50, args.portee)
    ax.set_ylim(-60, 6)
    ax.grid(alpha=0.3)
    ax.set_title(titre)

    # ---------------- commandes ----------------
    def _bouton(y, libelle, couleur):
        return Button(fig.add_axes([0.03, y, 0.20, 0.062]), libelle,
                      color=couleur, hovercolor="#dddddd")

    b_tare = _bouton(0.80, "Tare (fond vide)", "#c8e6c9")
    b_efface = _bouton(0.72, "Effacer la tare", "#ffcdd2")
    b_capture = _bouton(0.64, "CAPTURER", "#ffe082")
    b_pause = _bouton(0.56, "Pause", "#e0e0e0")
    b_enr = _bouton(0.48, "Enregistrer", "#bbdefb")
    b_rej = _bouton(0.40, "Rejouer", "#d1c4e9")
    sl_eps = Slider(fig.add_axes([0.06, 0.08, 0.17, 0.03]), r"$\varepsilon_r$",
                    1.0, 80.0, valinit=eps_r, valfmt="%1.1f")

    aide = ("Tare : memorise la scene VIDE et la soustrait.   "
            "CAPTURER : un balayage + image + journal.   "
            "Enregistrer : une SEQUENCE, rejouable ici meme.")
    fig.text(0.5, 0.02, aide, ha="center", fontsize=8.5, color="#52514e")

    dernier = {"freqs": None, "brut": None, "s": None, "r": None}
    # source courante et source mise de cote pendant un rejeu
    courant = {"src": iter(source), "garde": None}

    def _tare(_):
        if dernier["brut"] is None:
            return
        corr.pose_fond(dernier["freqs"], dernier["brut"])
        etat["tare"] += 1
        ch = noyau.enregistre(os.path.join(DOSSIER_MES, "fond.npz"),
                              dernier["freqs"], dernier["brut"])
        print(f"\n  >> TARE prise et enregistree : {ch}")

    def _efface(_):
        corr.retire_fond()
        print("\n  >> Tare effacee.")

    def _capture(_):
        if dernier["r"] is None:
            return
        etat["capture"] += 1
        n = etat["capture"]
        base = os.path.join(DOSSIER_MES, f"{args.nom}_capture_{n:02d}")
        noyau.enregistre(base + ".npz", dernier["freqs"], dernier["brut"])
        fig.savefig(base + ".png", dpi=110)
        r = dernier["r"]
        with open(os.path.join(DOSSIER_MES, "journal.txt"), "a",
                  encoding="utf-8") as f:
            f.write(f"{args.nom}_capture_{n:02d} | ep={r['ep_modele']:.3f} mm | "
                    f"dist={r['standoff'] - plan:.1f} mm | "
                    f"residu={r['residu']:.4f} | eps={etat['eps']:.1f} | "
                    f"tare={'oui' if corr.fond is not None else 'non'}\n")
        print(f"\n  >> CAPTURE {n:02d} : {base}.png / .npz")

    def _ecrit_sequence():
        """Ferme la sequence en cours et l ecrit sur le disque."""
        if not tampon["sweeps"]:
            return None
        etat["seq"] += 1
        nom = f"{args.nom}_seq_{etat['seq']:02d}"
        ch = noyau.enregistre(os.path.join(DOSSIER_MES, nom + ".npz"),
                              tampon["freqs"], np.array(tampon["sweeps"]),
                              np.array(tampon["temps"]))
        n = len(tampon["sweeps"])
        tampon["sweeps"], tampon["temps"] = [], []
        tampon["dernier"] = ch
        print(f"{chr(10)}  >> SEQUENCE {etat['seq']:02d} : {n} balayages BRUTS -> {ch}")
        print(f"     Rejeu hors ligne :  python radar.py --rejeu --nom {nom}")
        return ch

    def _enr(_):
        if etat["rejeu"]:
            print(f"{chr(10)}  >> Enregistrement impossible pendant un rejeu.")
            return
        if etat["enr"]:
            etat["enr"] = False
            _ecrit_sequence()
        else:
            tampon["sweeps"], tampon["temps"] = [], []
            etat["enr"] = True
            print(f"{chr(10)}  >> ENREGISTREMENT en cours.")
        b_enr.label.set_text("ARRETER" if etat["enr"] else "Enregistrer")

    def _rej(_):
        """Rejoue la derniere sequence, puis rend la main au direct."""
        if etat["rejeu"]:
            print(f"{chr(10)}  >> Rejeu deja en cours.")
            return
        ch = tampon["dernier"]
        if ch is None:
            ch = os.path.join(DOSSIER_MES, f"{args.nom}_seq_01.npz")
        if not os.path.exists(ch):
            print(f"{chr(10)}  >> Rien a rejouer : enregistrez d'abord une "
                  "sequence.")
            return
        if etat["enr"]:
            etat["enr"] = False
            _ecrit_sequence()
            b_enr.label.set_text("Enregistrer")
        courant["garde"] = courant["src"]
        courant["src"] = iter(source_fichier(ch, args.vitesse))
        etat["rejeu"] = True
        b_rej.label.set_text("REJEU...")
        print(f"{chr(10)}  >> REJEU de {os.path.basename(ch)} "
              f"(vitesse {args.vitesse}).")

    def _pause(_):
        etat["pause"] = not etat["pause"]
        b_pause.label.set_text("Reprendre" if etat["pause"] else "Pause")

    def _eps(v):
        etat["eps"] = v

    b_tare.on_clicked(_tare)
    b_efface.on_clicked(_efface)
    b_capture.on_clicked(_capture)
    b_pause.on_clicked(_pause)
    b_enr.on_clicked(_enr)
    b_rej.on_clicked(_rej)
    sl_eps.on_changed(_eps)

    # ---------------- boucle ----------------
    suivi, n, t_prec = None, 0, None
    if enregistre is not None:          # mode --enregistre : arme d emblee
        etat["enr"] = True
        b_enr.label.set_text("ARRETER")
    freqs = None
    try:
        while True:
            # La source est une variable, pas la cible d un for : c est ce
            # qui permet de glisser un rejeu au milieu du direct, puis de
            # rendre la main a l instrument.
            try:
                t, freqs, brut = next(courant["src"])
            except StopIteration:
                if courant["garde"] is not None:
                    courant["src"], courant["garde"] = courant["garde"], None
                    etat["rejeu"] = False
                    b_rej.label.set_text("Rejouer")
                    print(f"{chr(10)}  >> Fin du rejeu, retour au direct.")
                    continue
                break
            while etat["pause"]:
                plt.pause(0.1)
            s = corr(freqs, brut)
            dernier.update(freqs=freqs, brut=brut, s=s)
            if etat["enr"]:
                tampon["freqs"] = freqs
                tampon["sweeps"].append(brut)
                tampon["temps"].append(t)
            try:
                r = analyse(freqs, s, etat["eps"], sigma, args.substrat,
                            args.max_ep, suivi)
                suivi = r["suivi"] if r["residu"] < 0.5 else None
            except Exception as e:
                print(f"  analyse impossible : {e}")
                continue
            dernier["r"] = r

            dist, prof, _ = noyau.profil_distance(freqs, s)
            db = 20 * np.log10(prof / (np.max(prof) + 1e-18) + 1e-12)
            ligne.set_data(dist - plan, db)
            vline.set_xdata([r["standoff"] - plan] * 2)
            if r["pics"] is not None:
                xs = [p - plan for p in r["pics"][2]]
                pics_pts.set_data(xs, np.interp(xs, dist - plan, db))
            else:
                pics_pts.set_data([], [])
            fps = 1.0 / (t - t_prec) if t_prec is not None and t > t_prec else 0.0
            t_prec = t
            fiable = "OK " if r["residu"] < 0.2 else "!! "
            txt.set_text(
                f"epaisseur {r['ep_modele']:8.3f} mm\n"
                f"distance  {r['standoff'] - plan:8.1f} mm\n"
                f"residu    {fiable}{r['residu']:6.4f}\n"
                f"{fps:4.1f} img/s   n={n}   tare="
                f"{'oui' if corr.fond is not None else 'NON'}"
                + (f"{chr(10)}ENR {len(tampon['sweeps'])} balayages"
                   if etat["enr"] else "")
                + (f"{chr(10)}REJEU en cours" if etat["rejeu"] else ""))
            bandeau.set_text(
                "RESIDU ELEVE -- le modele ne decrit pas la mesure"
                if r["residu"] > 0.2 else
                f"{args.milieu} sur {args.substrat}   |   "
                f"{'tare posee' if corr.fond is not None else 'PAS DE TARE'}")
            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            n += 1
            film = getattr(args, "film", None)
            if film:
                # les deux premieres images servent a stabiliser l'echelle
                if n > 2:
                    os.makedirs(film, exist_ok=True)
                    fig.savefig(os.path.join(film, "%04d.png" % (n - 2)),
                                dpi=110)
                if n - 2 >= getattr(args, "images", 120):
                    print(f"{chr(10)}  Film : {n - 2} images dans {film}")
                    break
            if args.capture_ecran and n >= 3:
                fig.savefig(args.capture_ecran, dpi=110)
                print(f"\n  Copie d'ecran : {args.capture_ecran}")
                break
    except KeyboardInterrupt:
        print("\n  Arret.")
    finally:
        plt.ioff()
        # Une sequence en cours est ecrite quoi qu il arrive : une fenetre
        # fermee ou un Ctrl-C ne doit pas faire perdre l acquisition.
        if etat["enr"] and tampon["sweeps"]:
            if enregistre is not None and etat["seq"] == 0:
                ch = noyau.enregistre(enregistre, tampon["freqs"],
                                      np.array(tampon["sweeps"]),
                                      np.array(tampon["temps"]))
                print(f"{chr(10)}  {len(tampon['sweeps'])} balayages BRUTS "
                      f"enregistres : {ch}")
                print("  Rejeu :  python radar.py --rejeu --nom "
                      f"{os.path.splitext(os.path.basename(ch))[0]}")
            else:
                _ecrit_sequence()
        plt.close("all")


# ======================================================================
# AUTOTEST
# ======================================================================
def autotest():
    return noyau.autotest()


# ======================================================================
def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    m = ap.add_argument_group("modes")
    m.add_argument("--autotest", action="store_true")
    m.add_argument("--live", action="store_true")
    m.add_argument("--mesure", action="store_true")
    m.add_argument("--enregistre", action="store_true")
    m.add_argument("--rejeu", action="store_true")

    ap.add_argument("--nom", default="mesure")
    ap.add_argument("--milieu", default="cartilage",
                    help="couche mesuree : nom (pmma, cartilage...) ou eps_r")
    ap.add_argument("--sigma", type=float, default=None,
                    help="conductivite de la couche, S/m. Par defaut celle du "
                         "--milieu ; en mode --epaisseur, 0 (sans pertes) car "
                         "le materiau est justement inconnu.")
    ap.add_argument("--substrat", default="os",
                    help="ce qu'il y a DERRIERE : air, os, metal...")
    ap.add_argument("--max-ep", type=float, default=8.0,
                    help="epaisseur maximale exploree, mm")
    ap.add_argument("--epaisseur", type=float, default=None,
                    help="epaisseur CONNUE : inverse le probleme et mesure eps_r")
    ap.add_argument("--fond", default=None,
                    help="balayage 'scene vide' a soustraire")
    ap.add_argument("--cal", default="sol_courante")
    ap.add_argument("--moy", type=int, default=16)
    ap.add_argument("--duree", type=float, default=None,
                    help="duree d'enregistrement, s")
    ap.add_argument("--vitesse", type=float, default=1.0,
                    help="rejeu : 1 = temps reel, 0 = le plus vite possible")
    ap.add_argument("--portee", type=float, default=500.0,
                    help="bord droit de l'affichage, mm")
    ap.add_argument("--start", type=float, default=noyau.BANDE_DEFAUT[0])
    ap.add_argument("--stop", type=float, default=noyau.BANDE_DEFAUT[1])
    ap.add_argument("--points", type=int, default=noyau.POINTS_DEFAUT)
    ap.add_argument("--sans-graphe", action="store_true")
    ap.add_argument("--capture-ecran", default=None,
                    metavar="FICHIER",
                    help="copie d ecran puis quitte")
    ap.add_argument("--simu", nargs="?", const="pmma12@150",
                    default=None, metavar="SCENE",
                    help="instrument SIMULE. SCENE : pmma12@150, cartilage3@120, "
                         "metal@200, vide. Plusieurs scenes separees par des "
                         "virgules sont jouees dans l'ordre, une par balayage.")
    ap.add_argument("--film", default=None, metavar="DOSSIER",
                    help="enregistre une suite d'images de la fenetre")
    ap.add_argument("--images", type=int, default=120,
                    help="--film : nombre d'images a enregistrer")
    args = ap.parse_args()

    if args.autotest:
        sys.exit(autotest())

    try:
        eps_r, sigma = noyau.milieu(
            float(args.milieu) if args.milieu.replace('.', '', 1).isdigit()
            else args.milieu)
    except ValueError as e:
        ap.error(str(e))
    plan = noyau.plan_antenne()
    chemin = os.path.join(DOSSIER_MES, f"{args.nom}.npz")

    # ---------------- rejeu ----------------
    if args.rejeu:
        if not os.path.exists(chemin):
            ap.error(f"introuvable : {chemin}")
        corr = Correcteur(args.cal, args.fond)
        freqs, sweeps, _ = noyau.relit(chemin)
        print(f"  {len(sweeps)} balayages, {len(freqs)} points, "
              f"{freqs[0]/1e9:.2f}-{freqs[-1]/1e9:.2f} GHz")
        if len(sweeps) == 1:
            s = corr(freqs, sweeps[0])
            print("\n" + "=" * 74)
            r = analyse(freqs, s, eps_r, sigma, args.substrat, args.max_ep)
            imprime(r, plan)
            if not args.sans_graphe:
                trace(freqs, s, r, plan, args.nom,
                      os.path.join(DOSSIER_MES, f"{args.nom}.png"))
            return
        boucle_temps_reel(source_fichier(chemin, args.vitesse), corr, args,
                          eps_r, sigma, plan, f"REJEU — {args.nom}")
        return

    # ---------------- live / enregistrement ----------------
    if args.live or args.enregistre:
        corr = Correcteur(args.cal, args.fond)
        vna = noyau.ouvrir_vna(args.start, args.stop, args.points,
                               simu=args.simu.split(",") if args.simu else None)
        titre = ("ENREGISTREMENT" if args.enregistre else "DIRECT") \
            + f" — {args.milieu} sur {args.substrat}"
        try:
            boucle_temps_reel(source_vna(vna, args.duree), corr, args,
                              eps_r, sigma, plan, titre,
                              enregistre=chemin if args.enregistre else None)
        finally:
            try:
                vna.close()
            except Exception:
                pass
        return

    # ---------------- mesure ----------------
    if args.mesure:
        print(f"  Acquisition {args.start}-{args.stop} GHz, {args.points} pts, "
              f"{args.moy} moyennes...")
        vna = noyau.ouvrir_vna(args.start, args.stop, args.points,
                               simu=args.simu.split(",") if args.simu else None)
        try:
            freqs, brut = noyau.acquiert(vna, args.moy)
        finally:
            try:
                vna.close()
            except Exception:
                pass
        noyau.enregistre(chemin, freqs, brut)
        print(f"  Balayage BRUT enregistre : {chemin}")
        corr = Correcteur(args.cal, args.fond)
        s = corr(freqs, brut)

        if args.epaisseur is not None:
            # Le sigma herite de --milieu n'a aucun sens ici : c'est
            # justement le materiau que l'on cherche. Sans pertes par
            # defaut, ce qui convient aux dielectriques d'essai.
            sig_inv = 0.0 if args.sigma is None else args.sigma
            print("\n" + "=" * 74)
            print(f"  PERMITTIVITE -- epaisseur imposee {args.epaisseur} mm, "
                  f"substrat {args.substrat}")
            print("=" * 74)
            print(f"  conductivite supposee : {sig_inv} S/m"
                  + ("  (sans pertes -- --sigma pour changer)"
                     if args.sigma is None else ""))
            e, residu, ajuste = noyau.mesure_permittivite(
                freqs, s, args.epaisseur, sig_inv, args.substrat)
            print(f"  eps_r mesure ......... {e:8.3f}   (residu {residu:.4f})")
            print(f"  indice n = sqrt(eps) . {np.sqrt(e):8.3f}")
            print("\n  Reperes : PMMA 2,6 | PTFE 2,1 | verre 6,9 | "
                  "cartilage 40-45 | eau 70-78")
            if residu > 0.2:
                print(f"\n  ATTENTION : residu eleve ({residu:.2f}).")
            return

        print("\n" + "=" * 74)
        print(f"  COUCHE {args.milieu} (eps_r {eps_r}, sigma {sigma} S/m) "
              f"sur {args.substrat}")
        print("=" * 74)
        r = analyse(freqs, s, eps_r, sigma, args.substrat, args.max_ep)
        imprime(r, plan)
        if not args.sans_graphe:
            trace(freqs, s, r, plan,
                  f"{args.nom} — {args.milieu} sur {args.substrat}",
                  os.path.join(DOSSIER_MES, f"{args.nom}.png"))
        return

    ap.error("choisir --autotest, --live, --mesure, --enregistre ou --rejeu")


if __name__ == "__main__":
    main()
