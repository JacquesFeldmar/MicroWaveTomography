"""TRAITEMENT -- profil et phase du rapport pour John, pics qualifies.

    R_k = S11_plaque(f_k) - S11_fond(f_k)
    P_m = 16 . |IFFT_3216(w_k R_k)_m|          niveau affiche : 20 log10 P_m
    d_m = c.m / (2 . 3216 . df)

La fenetre est une Hann symetrique, le remplissage de zeros vaut 16, et le gain
coherent de la fenetre n'est PAS normalise -- comme dans le rapport, pour que
les niveaux soient comparables aux siens.
La detection qualifie maintenant les maxima par niveau et proeminence.
Le mode explicite ``rapport`` conserve la selection historique pour comparaison.

Aucune dependance a openEMS : ce module traite indifferemment une mesure, une
simulation FDTD ou le modele analytique.
"""
import numpy as np

from banc import C, Acquisition
from donnees import valide_frequences, valide_serie


# ======================================================================
# PROFIL DE DISTANCE
# ======================================================================
def fenetre(n, nom="hann"):
    """Hann symetrique : w_k = 0.5 (1 - cos(2.pi.k/(N-1)))."""
    if nom == "hann":
        return np.hanning(n)
    if nom == "aucune":
        return np.ones(n)
    raise ValueError(f"fenetre inconnue : {nom}")


def profil(s11, acq: Acquisition, fond=None):
    """Rend (distances en m, profil lineaire P_m).

    Si `fond` est fourni, il est retranche AVANT la fenetre, comme dans le
    rapport. Le profil rendu est |P_m|, non converti en dB.
    """
    r = np.asarray(s11, dtype=complex)
    grille = np.linspace(acq.f_min, acq.f_max, acq.points)
    valide_serie(grille, r, "profil")
    if fond is not None:
        _, fond = valide_serie(grille, fond, "fond du profil")
        r = r - fond
    w = fenetre(len(r), acq.fenetre)
    p = acq.zero_padding * np.abs(np.fft.ifft(w * r, n=acq.n_fft))
    d = np.arange(acq.n_fft) * acq.pas_distance
    demi = acq.n_fft // 2
    return d[:demi], p[:demi]


def en_db(p):
    return 20 * np.log10(np.maximum(p, 1e-18))


# ======================================================================
# MAXIMA CANDIDATS : AUCUNE ATTRIBUTION AUTOMATIQUE A UN TRAJET PHYSIQUE
# ======================================================================
def _parabole(y, i):
    """Correction sous-echantillon du sommet, en pas d'axe."""
    if i <= 0 or i >= len(y) - 1:
        return 0.0
    a, b, c_ = y[i - 1], y[i], y[i + 1]
    den = a - 2 * b + c_
    return 0.0 if den == 0 else 0.5 * (a - c_) / den


def _maxima_et_proeminences(p):
    """Maxima (milieu des plateaux) et hauteur au-dessus du contour local.

    De chaque cote, le contour s'arrete au premier echantillon plus haut que
    le sommet; sa base est le plus haut des deux minima. Calcul NumPy seul.
    """
    indices, proeminences = [], []
    i = 1
    while i < len(p) - 1:
        fin = i
        if p[i] > p[i - 1]:
            while fin < len(p) - 1 and p[fin + 1] == p[i]:
                fin += 1
            if fin < len(p) - 1 and p[fin] > p[fin + 1]:
                sommet = (i + fin) // 2
                gauche, droite = i, fin
                while gauche > 0 and p[gauche - 1] <= p[sommet]:
                    gauche -= 1
                while droite < len(p) - 1 and p[droite + 1] <= p[sommet]:
                    droite += 1
                base = max(float(np.min(p[gauche:sommet + 1])),
                           float(np.min(p[sommet:droite + 1])))
                indices.append(sommet)
                proeminences.append(p[sommet] - base)
        i = fin + 1
    return np.asarray(indices, dtype=int), np.asarray(proeminences)


def candidats_maxima(d, p, fenetre_cm=(40.0, 120.0), interpoler=True,
                     seuil_relatif_db=-25.0, prominence_min_db=3.0):
    """Maxima classes par amplitude, avec niveau et proeminence explicites.

    La proeminence en dB est le rapport amplitude / niveau du contour local.
    Le seuil relatif par defaut ecarte les
    lobes secondaires d'une Hann pure (-31,5 dB). Ces seuils qualifient des
    candidats numeriques, jamais des trajets physiques.
    """
    d_cm, p = np.asarray(d, dtype=float) * 100, np.asarray(p, dtype=float)
    if d_cm.ndim != 1 or p.shape != d_cm.shape or len(p) < 3:
        raise ValueError("profil : axes de meme taille, au moins trois points requis")
    if not np.all(np.isfinite(d_cm)) or not np.all(np.isfinite(p)) or np.any(p < 0) or np.any(np.diff(d_cm) <= 0):
        raise ValueError("profil : valeurs finies, amplitudes positives et axe croissant requis")
    if not np.isfinite(seuil_relatif_db) or seuil_relatif_db > 0 or not np.isfinite(prominence_min_db) or prominence_min_db < 0:
        raise ValueError("seuil relatif <= 0 et proeminence >= 0 requis")
    indices, proeminences = _maxima_et_proeminences(p)
    dans = (d_cm[indices] >= fenetre_cm[0]) & (d_cm[indices] <= fenetre_cm[1])
    indices, proeminences = indices[dans], proeminences[dans]
    if not len(indices):
        return []
    ordre = np.argsort(-p[indices], kind="stable")
    reference = p[indices[ordre[0]]]
    sortie = []
    for rang, j in enumerate(ordre, 1):
        i = int(indices[j])
        niveau = float(en_db(p[i]))
        relatif = float(20 * np.log10(p[i] / reference))
        base = max(float(p[i] - proeminences[j]), 1e-300)
        prominence_db = float(20 * np.log10(max(p[i], 1e-300) / base))
        dec = float(np.clip(_parabole(p, i), -.5, .5)) if interpoler else 0.
        pas = (d_cm[i + 1] - d_cm[i - 1]) / 2
        sortie.append(dict(distance_cm=float(d_cm[i] + dec * pas),
                           niveau_db=niveau, relatif_db=relatif,
                           rang_amplitude=rang, prominence_db=prominence_db,
                           qualifie=relatif >= seuil_relatif_db and prominence_db >= prominence_min_db,
                           indice=i))
    return sortie


def maxima_locaux(d, p, fenetre_cm=(40.0, 120.0), combien=2, interpoler=True,
                  seuil_relatif_db=-25.0, prominence_min_db=3.0, mode="qualifies"):
    """Paires (distance_cm, niveau_dB) classees par amplitude.

    ``mode='rapport'`` reproduit la selection historique des deux plus grands
    maxima, y compris les lobes de fenetrage. Reserve a la relecture du rapport.
    """
    if mode not in ("qualifies", "rapport"):
        raise ValueError("mode de pics inconnu")
    if mode == "rapport":
        # Definition historique exacte, y compris l'exclusion des deux
        # echantillons aux bords de la fenetre et le debut des plateaux.
        d_cm, p = np.asarray(d) * 100, np.asarray(p)
        idx = np.flatnonzero((d_cm >= fenetre_cm[0]) & (d_cm <= fenetre_cm[1]))
        pics = [i for i in idx[1:-1] if p[i] > p[i - 1] and p[i] >= p[i + 1]]
        pics.sort(key=lambda i: p[i], reverse=True)
        return [(float(d_cm[i] + (_parabole(p, i) if interpoler else 0.) * (d_cm[1] - d_cm[0])),
                 float(en_db(p[i]))) for i in pics[:combien]]
    candidats = candidats_maxima(d, p, fenetre_cm, interpoler,
                                seuil_relatif_db, prominence_min_db)
    retenus = [x for x in candidats if x["qualifie"]]
    return [(x["distance_cm"], x["niveau_db"]) for x in retenus[:combien]]


# ======================================================================
# PHASE : LE TRAJET GEOMETRIQUE RETIRE
# ======================================================================
def phase_sans_trajet(freqs, r, distance_m):
    """H(f) = R(f).exp(+j.4.pi.f.x/c), puis phase deroulee en degres.

    Ce que trace la figure 3 du rapport : il ne reste que la phase
    supplementaire theta(f), c'est-a-dire tout ce qui n'est pas le trajet
    aller-retour dans l'air.
    """
    h = np.asarray(r, dtype=complex) * np.exp(
        1j * 4 * np.pi * np.asarray(freqs) * distance_m / C)
    return np.unwrap(np.angle(h)) * 180 / np.pi, h


def pente_ponderee(freqs, phase_deg, poids=None):
    """Ajustement lineaire pondere de la phase (degres) -> (retard, decalage).

    Rend (tau_aller_retour en s, decalage equivalent en cm, droite ajustee).
    Le decalage equivalent est c.tau/2 : c'est la grandeur que le rapport
    appelle « equivalent offset ».
    """
    f = np.asarray(freqs, dtype=float)
    y = np.asarray(phase_deg, dtype=float)
    w = np.ones_like(f) if poids is None else np.asarray(poids, dtype=float)
    valide_frequences(f)
    if y.shape != f.shape or w.shape != f.shape or not np.all(np.isfinite(y)) or not np.all(np.isfinite(w)) or np.any(w < 0):
        raise ValueError("phase et poids finis de meme taille que les frequences requis")
    if w.sum() <= 0:
        return np.nan, np.nan, np.full_like(f, np.nan)
    w = w / w.sum()
    fm, ym = (w * f).sum(), (w * y).sum()
    variance = (w * (f - fm) ** 2).sum()
    if variance <= 0:
        return np.nan, np.nan, np.full_like(f, np.nan)
    pente = (w * (f - fm) * (y - ym)).sum() / variance
    droite = ym + pente * (f - fm)
    tau = -(pente * np.pi / 180) / (2 * np.pi)     # s, aller-retour
    return tau, C * tau / 2 * 100, droite


# ======================================================================
# BILAN D'UNE SERIE
# ======================================================================
def bilan(freqs, fond, mesures, acq: Acquisition, fenetre_cm=(40.0, 120.0),
          seuil_relatif_db=-25.0, prominence_min_db=3.0, mode_pics="qualifies",
          continuite_cm=None):
    """Resultats par distance, principal stable par rang d'amplitude.

    ``pic_principal`` est le maximum retenu le plus fort; sa definition ne
    change jamais quand un lobe passe de l'autre cote. ``pic_proche/lointain``
    restent des alias de positions des candidats tries par distance; un seul
    candidat ne produit pas de pic lointain. Ce ne sont pas des branches
    physiques. Le suivi rapproche les ecarts des candidats qualifies entre
    positions voisines, avec une tolerance c/2B par defaut; il n'invente pas
    de pic absent et ne change pas le principal. Le mode rapport reproduit
    explicitement l'ancienne selection et peut donc reproduire son artefact.
    """
    freqs, fond = valide_serie(freqs, fond, "fond")
    grille = np.linspace(acq.f_min, acq.f_max, acq.points)
    if freqs.shape != grille.shape or not np.allclose(freqs, grille, rtol=0, atol=1.):
        raise ValueError("grille des donnees differente de l'acquisition")
    if mode_pics not in ("qualifies", "rapport"):
        raise ValueError("mode de pics inconnu")
    tolerance = acq.resolution * 100 if continuite_cm is None else continuite_cm
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance de continuite finie et positive requise")
    out = {}
    precedents, numero_suivi = [], 0
    for d_cm, s11 in sorted(mesures.items()):
        _, s11 = valide_serie(freqs, s11, f"plaque {d_cm} cm")
        r = np.asarray(s11, dtype=complex) - np.asarray(fond, dtype=complex)
        d, p = profil(s11, acq, fond=fond)
        candidats = candidats_maxima(d, p, fenetre_cm, seuil_relatif_db=seuil_relatif_db,
                                    prominence_min_db=prominence_min_db)
        qualifies = [x for x in candidats if x["qualifie"]]
        disponibles = list(precedents)
        for candidat in qualifies:
            ecart = candidat["distance_cm"] - d_cm
            proche = min(disponibles, key=lambda x: abs(x["ecart_cm"] - ecart), default=None)
            if proche is not None and abs(proche["ecart_cm"] - ecart) <= tolerance:
                candidat["suivi_id"] = proche["suivi_id"]
                disponibles.remove(proche)
                candidat["suivi_continu"] = True
            else:
                numero_suivi += 1
                candidat["suivi_id"], candidat["suivi_continu"] = numero_suivi, False
            candidat["ecart_cm"] = ecart
        precedents = qualifies
        pics = (maxima_locaux(d, p, fenetre_cm, mode="rapport") if mode_pics == "rapport"
                else [(x["distance_cm"], x["niveau_db"]) for x in qualifies[:2]])
        pics_tries = sorted(pics, key=lambda t: t[0])
        ph, h = phase_sans_trajet(freqs, r, d_cm / 100)
        tau, dec_cm, droite = pente_ponderee(freqs, ph, poids=np.abs(r) ** 2)
        out[d_cm] = dict(
            distances=d, profil=p, residu=r, pics=pics,
            candidats=candidats, mode_pics=mode_pics,
            pic_principal=pics[0][0] if pics else np.nan,
            niveau_principal_db=pics[0][1] if pics else np.nan,
            pic_proche=pics_tries[0][0] if pics_tries else np.nan,
            pic_lointain=pics_tries[1][0] if len(pics_tries) > 1 else np.nan,
            phase_deg=ph, droite_deg=droite, tau=tau, decalage_phase_cm=dec_cm)
        out[d_cm]["ecart_proche_cm"] = out[d_cm]["pic_proche"] - d_cm
        out[d_cm]["ecart_lointain_cm"] = out[d_cm]["pic_lointain"] - d_cm
        out[d_cm]["ecart_principal_cm"] = out[d_cm]["pic_principal"] - d_cm
    return out


def table_bilan(res):
    """Principal par amplitude et positions de candidats, sans interpretation physique."""
    lig = [f"{'plaque':>8s}{'principal':>12s}{'ecart princ.':>14s}"
           f"{'cand. proche':>14s}{'cand. lointain':>16s}{'pente phase':>13s}"]
    lig.append("-" * len(lig[0]))
    for d_cm, r in sorted(res.items()):
        lig.append(f"{d_cm:>6.1f} cm{r['pic_principal']:>10.2f} cm"
                   f"{r['ecart_principal_cm']:>12.2f} cm"
                   f"{r['pic_proche']:>12.2f} cm"
                   f"{r['pic_lointain']:>14.2f} cm"
                   f"{r['decalage_phase_cm']:>11.1f} cm")
    lig.append("Candidats numeriques seulement ; nan = aucun candidat retenu.")
    if any(r["mode_pics"] == "rapport" for r in res.values()):
        lig.append("ATTENTION : selection historique rapport, lobes secondaires inclus.")
    return "\n".join(lig)


def bandes_adaptees(freqs, s11, seuil_db=-10.):
    """Segments contigus sous le seuil, bornes echantillonnees (pas interpolees).

    La couverture porte sur toute la grille, pas sur l'enveloppe entre premiere
    et derniere reussite. Un resultat vide est normal pour une antenne inadaptee.
    """
    f, s = valide_serie(freqs, s11)
    if not np.isfinite(seuil_db):
        raise ValueError("seuil S11 fini requis")
    sous = en_db(np.abs(s)) < seuil_db
    groupes = np.split(np.flatnonzero(sous), np.flatnonzero(np.diff(np.flatnonzero(sous)) > 1) + 1)
    segments = [(float(f[g[0]]), float(f[g[-1]])) for g in groupes if len(g)]
    return dict(seuil_db=float(seuil_db), segments_hz=segments,
                couverture=float(sous.mean()), points_sous_seuil=int(sous.sum()),
                points_total=len(f))
