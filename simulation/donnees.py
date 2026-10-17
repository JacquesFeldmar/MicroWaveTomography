"""DONNEES -- lecture des mesures reelles.

Les fichiers decrits dans le rapport pour John :

    background.csv / .s1p          scene vide
    plate_50cm, plate_60cm, plate_70cm
    independent_short

CSV  : trois colonnes, frequence en Hz, partie reelle, partie imaginaire.
s1p  : Touchstone « # Hz S RI R 50 ».

Les valeurs sont deja calibrees SOL et moyennees, mais NI fenetrees NI
soustraites du fond : c'est bien ce que `traitement.py` attend.
"""
import os
import re

import numpy as np


def lit_csv(chemin):
    d = np.loadtxt(chemin, delimiter=",", comments="#")
    if d.shape[1] < 3:
        raise ValueError(f"{chemin} : trois colonnes attendues (f, re, im)")
    return d[:, 0], d[:, 1] + 1j * d[:, 2]


def lit_s1p(chemin):
    freqs, s = [], []
    mult = 1.0
    for ligne in open(chemin, encoding="utf-8", errors="ignore"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("!"):
            continue
        if ligne.startswith("#"):
            u = ligne.lower().split()
            mult = {"hz": 1, "khz": 1e3, "mhz": 1e6, "ghz": 1e9}.get(u[1], 1.0)
            if "ri" not in u:
                raise ValueError(f"{chemin} : seul le format RI est lu")
            continue
        v = [float(x) for x in re.split(r"[\s,]+", ligne) if x]
        freqs.append(v[0] * mult)
        s.append(complex(v[1], v[2]))
    return np.array(freqs), np.array(s)


def lit(chemin):
    return (lit_s1p if chemin.lower().endswith(".s1p") else lit_csv)(chemin)


def charge_dossier(dossier, motif_fond="background",
                   motif_plaque=r"plate[_-]?(\d+)\s*cm"):
    """Rend (freqs, fond, {distance_cm : S11}) a partir d'un dossier de mesures."""
    fond, mesures, freqs = None, {}, None
    for nom in sorted(os.listdir(dossier)):
        if not nom.lower().endswith((".csv", ".s1p")):
            continue
        chemin = os.path.join(dossier, nom)
        f, s = lit(chemin)
        if freqs is None:
            freqs = f
        elif len(f) != len(freqs) or not np.allclose(f, freqs):
            raise ValueError(f"{nom} : grille de frequences differente")
        if motif_fond in nom.lower():
            fond = s
            continue
        m = re.search(motif_plaque, nom.lower())
        if m:
            mesures[float(m.group(1))] = s
    if fond is None:
        raise FileNotFoundError(f"aucun fichier « {motif_fond} » dans {dossier}")
    if not mesures:
        raise FileNotFoundError(f"aucun fichier de plaque dans {dossier}")
    return freqs, fond, mesures
