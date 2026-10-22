"""Lecture stricte des S11 complexes, sans interpolation ni renormalisation.

CSV : trois colonnes (Hz, reel, imaginaire), en-tete facultatif.
Touchstone 1 port : ``# Hz|kHz|MHz|GHz S RI R 50`` uniquement.
Les grilles doivent etre finies, croissantes et uniformes pour l'IFFT.
Les noms natifs sont background et plate_50cm (decimales autorisees).
Les anciens noms antenne_seule et plaque_50cm restent acceptes.
"""
import csv
import os
import re
import warnings

import numpy as np


FREQUENCE_ATOL_HZ = 1.0


def valide_frequences(freqs, contexte="frequences", atol_hz=FREQUENCE_ATOL_HZ):
    """Refuse une grille incompatible avec l'IFFT (tolerance absolue en Hz).

    1 Hz tolere l'arrondi des exports, pas une variation relative de plusieurs
    dizaines de kHz a 6 GHz comme le ferait np.allclose par defaut.
    """
    f = np.asarray(freqs, dtype=float)
    if f.ndim != 1 or len(f) < 3:
        raise ValueError(f"{contexte} : au moins trois frequences attendues")
    if not np.all(np.isfinite(f)) or np.any(f < 0):
        raise ValueError(f"{contexte} : frequences non finies ou negatives")
    if np.any(np.diff(f) <= 0):
        raise ValueError(f"{contexte} : frequences strictement croissantes requises")
    if not np.allclose(f, np.linspace(f[0], f[-1], len(f)), rtol=0, atol=atol_hz):
        raise ValueError(f"{contexte} : grille de frequences non uniforme")
    return f


def valide_serie(freqs, s11, contexte="S11"):
    f = valide_frequences(freqs, contexte)
    s = np.asarray(s11, dtype=complex)
    if s.ndim != 1 or s.shape != f.shape or not np.all(np.isfinite(s)):
        raise ValueError(f"{contexte} : S11 de meme taille que la grille, fini, requis")
    return f, s


def _sans_commentaire(ligne):
    return re.split(r"[!#]", ligne, maxsplit=1)[0].strip()


def lit_csv(chemin):
    valeurs = []
    with open(chemin, encoding="utf-8-sig") as fichier:
        for numero, ligne in enumerate(fichier, 1):
            ligne = _sans_commentaire(ligne)
            if not ligne:
                continue
            colonnes = next(csv.reader([ligne]))
            if len(colonnes) != 3:
                raise ValueError(f"{chemin}:{numero} : exactement trois colonnes (Hz,re,im)")
            try:
                valeurs.append([float(x) for x in colonnes])
            except ValueError as exc:
                entete = [re.sub(r"[^a-z]", "", x.lower()) for x in colonnes]
                if not valeurs and entete[0] in ("f", "freq", "frequency", "frequence", "freqhz", "frequencyhz", "frequencehz") and entete[1] in ("re", "real", "reel") and entete[2] in ("im", "imag", "imaginaire"):
                    continue
                raise ValueError(f"{chemin}:{numero} : ligne CSV non numerique") from exc
    if not valeurs:
        raise ValueError(f"{chemin} : aucune donnee")
    d = np.asarray(valeurs)
    if not np.all(np.isfinite(d)):
        raise ValueError(f"{chemin} : donnees non finies")
    return valide_serie(d[:, 0], d[:, 1] + 1j * d[:, 2], str(chemin))


def lit_s1p(chemin):
    freqs, s = [], []
    options = None
    unites = {"hz": 1., "khz": 1e3, "mhz": 1e6, "ghz": 1e9}
    with open(chemin, encoding="utf-8-sig") as fichier:
        for numero, ligne in enumerate(fichier, 1):
            ligne = ligne.split("!", 1)[0].strip()
            if not ligne:
                continue
            if ligne.startswith("#"):
                u = ligne[1:].lower().split()
                try:
                    correct = len(u) == 5 and u[0] in unites and u[1:4] == ["s", "ri", "r"] and float(u[4]) == 50.
                except ValueError:
                    correct = False
                if not correct:
                    raise ValueError(f"{chemin}:{numero} : en-tete # UNIT S RI R 50 requis")
                if options is not None and u != options:
                    raise ValueError(f"{chemin}:{numero} : en-tetes contradictoires")
                options = u
                continue
            if options is None:
                raise ValueError(f"{chemin}:{numero} : en-tete Touchstone explicite requis")
            try:
                v = [float(x) for x in re.split(r"[\s,]+", ligne)]
            except ValueError as exc:
                raise ValueError(f"{chemin}:{numero} : donnees RI invalides") from exc
            if len(v) != 3:
                raise ValueError(f"{chemin}:{numero} : trois valeurs par ligne requises (un port)")
            freqs.append(v[0] * unites[options[0]])
            s.append(complex(v[1], v[2]))
    return valide_serie(freqs, s, str(chemin))


def lit(chemin):
    return (lit_s1p if str(chemin).lower().endswith(".s1p") else lit_csv)(chemin)


def charge_dossier(dossier, motif_fond=r"(?:background|antenne_seule)",
                   motif_plaque=r"(?:plate|plaque)[_-]?(\d+(?:[.,]\d+)?)\s*cm",
                   tolerance_frequence_hz=FREQUENCE_ATOL_HZ):
    """Rend (freqs, fond, {distance_cm: S11}).

    Les doublons identiques (par exemple CSV et S1P) sont signales et admis.
    Toute contradiction de donnees ou de grille est une erreur, jamais un
    remplacement silencieux. Les fichiers non reconnus (SHORT, etc.) sont ignores.
    """
    donnees, sources, freqs = {}, {}, None
    for nom in sorted(os.listdir(dossier)):
        if not nom.lower().endswith((".csv", ".s1p")):
            continue
        est_fond = re.search(motif_fond, os.path.splitext(nom.lower())[0]) is not None
        plaque = re.search(motif_plaque, nom.lower())
        if est_fond and plaque:
            raise ValueError(f"{nom} : nom ambigu (fond et plaque)")
        if not est_fond and not plaque:
            continue
        cle = "fond" if est_fond else float(plaque.group(1).replace(",", "."))
        f, s = lit(os.path.join(dossier, nom))
        if freqs is None:
            freqs = f
        elif f.shape != freqs.shape or not np.allclose(f, freqs, rtol=0, atol=tolerance_frequence_hz):
            raise ValueError(f"{nom} : grille de frequences differente (tolerance {tolerance_frequence_hz:g} Hz)")
        if cle in donnees:
            if not np.allclose(s, donnees[cle], rtol=1e-9, atol=1e-12):
                raise ValueError(f"{nom} et {sources[cle]} : doublons contradictoires pour {cle}")
            warnings.warn(f"{nom} et {sources[cle]} : doublon identique pour {cle}, conserve une seule fois", RuntimeWarning, stacklevel=2)
        else:
            donnees[cle], sources[cle] = s, nom
    if "fond" not in donnees:
        raise FileNotFoundError(f"aucun fichier de fond ({motif_fond}) dans {dossier}")
    fond = donnees.pop("fond")
    if not donnees:
        raise FileNotFoundError(f"aucun fichier de plaque dans {dossier}")
    return freqs, fond, donnees
