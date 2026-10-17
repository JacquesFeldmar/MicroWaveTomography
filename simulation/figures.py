"""FIGURES -- les memes que celles du rapport pour John.

  figure_profils  : figure 2 du rapport (zoom sur la cible + profil complet)
  figure_phase    : figure 3 (phase sans le trajet geometrique + ecart a la droite)
  figure_ecarts   : les ecarts en fonction de la distance, compares aux mesures

Les trois prennent le dictionnaire rendu par traitement.bilan().
"""
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from banc import MESURES_9_OCT, DECALAGE_PROCHE_CM, DECALAGE_LOINTAIN_CM
import traitement as tr

COULEURS = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd")


def _couleur(i):
    return COULEURS[i % len(COULEURS)]


def figure_profils(res, chemin, titre="", zoom_cm=(40, 120)):
    """Figure 2 : le profil de distance, zoome puis complet."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.5))
    for i, (d_cm, r) in enumerate(sorted(res.items())):
        db = tr.en_db(r["profil"])
        for ax in (ax1, ax2):
            ax.plot(r["distances"] * 100, db, color=_couleur(i), lw=1.8,
                    label=f"plaque à environ {d_cm:.0f} cm")
        for x_cm, niv in r["pics"]:
            ax1.plot([x_cm], [niv], "o", color=_couleur(i), ms=7)
    ax1.set_xlim(*zoom_cm)
    ax1.set_title("Région de la cible : les deux plus grands maxima locaux "
                  "sont marqués", fontsize=11)
    ax2.set_xlim(0, 250)
    ax2.set_title("Profil complet", fontsize=11)
    for ax in (ax1, ax2):
        ax.set_xlabel("distance équivalente air depuis le plan SOL (cm)")
        ax.set_ylabel("amplitude IFFT (dB réf. 1)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=9)
    if titre:
        fig.suptitle(titre, fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
    else:
        fig.tight_layout()
    fig.savefig(chemin, dpi=120)
    plt.close(fig)
    return chemin


def figure_phase(res, freqs, chemin, titre=""):
    """Figure 3 : phase sans le trajet géométrique, et écart à la droite."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.5))
    for i, (d_cm, r) in enumerate(sorted(res.items())):
        ax1.plot(freqs / 1e9, r["phase_deg"], color=_couleur(i), lw=1.8,
                 label=f"plaque à {d_cm:.0f} cm — pente pondérée : "
                       f"décalage équivalent {r['decalage_phase_cm']:.1f} cm")
        ax1.plot(freqs / 1e9, r["droite_deg"], color=_couleur(i), lw=1,
                 ls="--", alpha=0.7)
        ax2.plot(freqs / 1e9, r["phase_deg"] - r["droite_deg"],
                 color=_couleur(i), lw=1.8, label=f"plaque à {d_cm:.0f} cm")
    ax1.set_title("Phase après retrait du trajet aller-retour géométrique",
                  fontsize=11)
    ax1.set_ylabel("phase déroulée (degrés)")
    ax2.set_title("Écart à une réponse de retard constant", fontsize=11)
    ax2.set_ylabel("écart à la droite ajustée (degrés)")
    for ax in (ax1, ax2):
        ax.set_xlabel("fréquence (GHz)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=9)
    if titre:
        fig.suptitle(titre, fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
    else:
        fig.tight_layout()
    fig.savefig(chemin, dpi=120)
    plt.close(fig)
    return chemin


def figure_ecarts(res, chemin, titre=""):
    """Les écarts simulés, superposés aux mesures du 9 octobre."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    d = sorted(res)
    ax.plot(d, [res[x]["ecart_proche_cm"] for x in d], "o-", color="#1f77b4",
            lw=2, label="simulation — branche proche")
    if not np.isnan(res[d[0]]["ecart_lointain_cm"]):
        ax.plot(d, [res[x]["ecart_lointain_cm"] for x in d], "s-",
                color="#2ca02c", lw=2, label="simulation — branche lointaine")
    dm = sorted(MESURES_9_OCT)
    ax.plot(dm, [MESURES_9_OCT[x][0] - x for x in dm], "o--", color="#1f77b4",
            lw=1.5, alpha=0.55, label="mesure 9 oct. — branche proche")
    ax.plot(dm, [MESURES_9_OCT[x][1] - x for x in dm], "s--", color="#2ca02c",
            lw=1.5, alpha=0.55, label="mesure 9 oct. — branche lointaine")
    ax.axhline(DECALAGE_PROCHE_CM, color="#1f77b4", ls=":", lw=1)
    ax.axhline(DECALAGE_LOINTAIN_CM, color="#2ca02c", ls=":", lw=1)
    ax.set_xlabel("distance vraie de la plaque (cm)")
    ax.set_ylabel("écart = pic − distance (cm)")
    ax.set_title(titre or "Écarts simulés et mesurés", fontsize=12)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(chemin, dpi=120)
    plt.close(fig)
    return chemin


def figure_s11(freqs, s11, chemin, bande_attendue=None, titre="",
               reference=None):
    """|S11| et retard de groupe d'une antenne seule.

    `bande_attendue` : (f_min, f_max) en GHz, surlignee et comparee au seuil
    de -10 dB. C'est le verdict du modele electromagnetique quand l'antenne
    a une reference publiee.
    """
    f = np.asarray(freqs) / 1e9
    s = np.asarray(s11)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)

    ax1.plot(f, 20 * np.log10(np.abs(s)), color="#1f77b4", lw=2,
             label="simulation")
    if reference is not None:
        ax1.plot(reference[0] / 1e9, 20 * np.log10(np.abs(reference[1])),
                 color="#d62728", lw=1.6, ls="--", label="référence")
    ax1.axhline(-10, color="gray", ls=":", lw=1.2)
    ax1.text(f[0], -9.4, "−10 dB", fontsize=9, color="gray")
    if bande_attendue:
        ax1.axvspan(bande_attendue[0], bande_attendue[1], color="#2ca02c",
                    alpha=0.12,
                    label=f"bande annoncée {bande_attendue[0]:.1f}–"
                          f"{bande_attendue[1]:.1f} GHz")
        dans = (f >= bande_attendue[0]) & (f <= bande_attendue[1])
        if dans.any():
            pire = float(np.max(20 * np.log10(np.abs(s[dans]))))
            ax1.set_title(f"{titre} — dans la bande annoncée, le pire |S11| "
                          f"vaut {pire:.1f} dB", fontsize=11)
    if not ax1.get_title():
        ax1.set_title(titre, fontsize=11)
    ax1.set_ylabel(r"$|S_{11}|$ (dB)")
    ax1.set_ylim(-40, 2)
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=9, loc="lower right")

    phase = np.unwrap(np.angle(s))
    tau = -np.gradient(phase, np.asarray(freqs)) / (2 * np.pi)
    ax2.plot(f, tau * 1e9, color="#9467bd", lw=1.8)
    ax2.set_xlabel("fréquence (GHz)")
    ax2.set_ylabel("retard de groupe de $S_{11}$ (ns)")
    ax2.grid(alpha=0.3)
    ax2.set_title("Retard de groupe : les ondulations trahissent les "
                  "réflexions internes", fontsize=10)
    fig.tight_layout()
    fig.savefig(chemin, dpi=120)
    plt.close(fig)
    return chemin


def toutes(res, freqs, dossier, prefixe="", titre=""):
    os.makedirs(dossier, exist_ok=True)
    return [
        figure_profils(res, os.path.join(dossier, f"{prefixe}profils.png"), titre),
        figure_phase(res, freqs, os.path.join(dossier, f"{prefixe}phase.png"), titre),
        figure_ecarts(res, os.path.join(dossier, f"{prefixe}ecarts.png"), titre),
    ]
