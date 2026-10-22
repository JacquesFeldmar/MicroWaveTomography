"""Ajustement fréquentiel complexe (B), sans IFFT ni correction empirique du zéro.

Deux modèles : somme d'échos à gains constants, ou plaque air/diélectrique/air
à deux faces avec indice fixé. Projection linéaire des gains complexes puis
moindres carrés bornés sur les distances et, pour la plaque, (e, alpha).
"""
import numpy as np
from scipy.optimize import least_squares
from scipy.signal import find_peaks

C = 299_792_458.


def verifier(f, y, bornes, variance=None):
    f, y = np.asarray(f, float), np.asarray(y, complex)
    if f.ndim != 1 or y.shape != f.shape or len(f) < 8 or not np.all(np.isfinite(f)) or not np.all(np.isfinite(y)):
        raise ValueError("B : au moins huit fréquences et valeurs complexes finies requises.")
    if np.any(np.diff(f) <= 0) or np.any(f <= 0):
        raise ValueError("B : fréquences positives strictement croissantes requises.")
    lo, hi = bornes
    if not np.isfinite([lo, hi]).all() or not 0 <= lo < hi:
        raise ValueError("B : intervalle de distance invalide (cm).")
    df = np.diff(f)
    if np.allclose(df, df[0], rtol=1e-9, atol=1e-3) and hi-lo >= C/(2*df[0])*100:
        raise ValueError("B : intervalle dépassant la période d'ambiguïté de la grille.")
    if np.linalg.norm(y) == 0:
        raise ValueError("B : signal nul, retard non identifiable.")
    if variance is not None:
        v = np.asarray(variance, float)
        if v.shape != f.shape or np.any(v <= 0) or not np.all(np.isfinite(v)):
            raise ValueError("B : variances strictement positives et finies requises.")
    return f, y


def base_echos(f, distances_cm):
    # Centrer f améliore le conditionnement. Le gain libre porte la phase à fc.
    return np.exp(-4j*np.pi*(f-f.mean())[:, None]*np.asarray(distances_cm)[None, :]/(100*C))


def base_plaque(f, distance_cm, epaisseur_mm, alpha, indice):
    r = (1-indice)/(1+indice)
    b = -(1-r*r)*r
    z = np.exp(-4j*np.pi*f*indice*epaisseur_mm/(1000*C))
    return base_echos(f, [distance_cm])[:, 0]*(r+alpha*b*z)


def reel(z):
    return np.r_[z.real, z.imag]


def projection(a, y, poids):
    gains = np.linalg.lstsq(a*poids[:, None], y*poids, rcond=None)[0]
    return gains, a@gains


def grille_retards(f, bornes):
    # Huit échantillons par c/(2B) pour INITIALISER le modèle continu.
    n = int(np.ceil((bornes[1]-bornes[0])/(100*C/(2*np.ptp(f))/8)))+1
    if n > 20000:
        raise ValueError("B : intervalle trop large ; réduire les bornes.")
    return np.linspace(*bornes, max(n, 16))


def candidats(score, grille, nombre):
    indices = np.unique(np.r_[0, find_peaks(score)[0], len(score)-1])
    return grille[indices[np.argsort(score[indices])[::-1][:nombre]]]


def information(jac, variance):
    """FIM réelle pour CN(0,diag(v)), covariance complète incluant les nuisances.

    Rang évalué après normalisation des colonnes ; pas de pseudo-inverse qui
    présenterait une direction non identifiable comme précisément estimée.
    """
    if variance is None:
        return None, None, 0, None
    jw = jac/np.sqrt(variance)[:, None]
    fim = 2*(jw.conj().T@jw).real
    norms = np.sqrt(np.maximum(np.diag(fim), 0))
    if np.any(norms == 0):
        return fim, None, int(np.linalg.matrix_rank(fim)), None
    normalisee = fim / norms[:, None] / norms[None, :]
    valeurs = np.linalg.eigvalsh(normalisee)
    rang = int(np.count_nonzero(valeurs > max(valeurs[-1], 1)*1e-10))
    condition = float(valeurs[-1]/valeurs[0]) if valeurs[0] > 0 else None
    covariance = None
    if rang == len(norms):
        covariance = np.linalg.inv(normalisee)/norms[:, None]/norms[None, :]
    return fim, covariance, rang, condition


def terminer(f, y, modele, jac, noms, variance, optimum, solutions, bornes, parametres):
    residu = y-modele
    erreur_relative = float(np.linalg.norm(residu)/np.linalg.norm(y))
    ddl = 2*len(f)-len(noms)
    chi2 = float(2*np.sum(abs(residu)**2/variance)/ddl) if variance is not None else None
    fim, cov, rang, condition = information(jac, variance)
    bord = bool(np.any(np.isclose(parametres, bornes[0], atol=1e-5, rtol=0)) or
                np.any(np.isclose(parametres, bornes[1], atol=1e-5, rtol=0)))
    avertissements = ["Distances apparentes depuis le plan SOL ; réponse de l'antenne non déconvoluée."]
    if erreur_relative > .2:
        avertissements.append("Plus de 20 % de résidu RMS relatif : modèle incomplet (seuil descriptif).")
    if chi2 is not None and chi2 > 3:
        avertissements.append("Résidu supérieur au bruit estimé : modèle/bruit iid incompatible (chi2 réduit > 3).")
    if not optimum.success:
        avertissements.append("Optimisation non convergée.")
    if bord:
        avertissements.append("Un paramètre atteint une borne : élargir ou justifier le domaine.")
    if variance is None:
        avertissements.append("Bruit de la moyenne inconnu : FIM et bornes statistiques non calculées.")
    elif cov is None:
        avertissements.append("FIM singulière ou mal conditionnée : paramètres non identifiables localement.")
    valide = variance is not None and cov is not None and chi2 <= 3 and optimum.success and not bord
    return dict(modele_complexe=modele, erreur_complexe=residu, fim=fim, covariance_conditionnelle=cov,
                noms_parametres=noms, erreur_rms_relative=erreur_relative, chi2_reduit=chi2,
                rang_fim=rang, condition_fim_normalisee=condition, convergence=bool(optimum.success),
                borne_atteinte=bord, crlb_interpretable_sous_modele=bool(valide),
                avertissements=avertissements,
                minima=[dict(cout=float(s.cost), parametres=s.x.tolist(), convergence=bool(s.success))
                        for s in sorted(solutions, key=lambda s: s.cost)[:8]])


def ajuster_echos(f, y, nombre=2, bornes=(0., 150.), variance=None, ponderation="uniforme"):
    f, y = verifier(f, y, bornes, variance)
    if not isinstance(nombre, (int, np.integer)) or not 1 <= nombre <= 4:
        raise ValueError("Choisir entre 1 et 4 échos.")
    poids = poids_fit(variance, ponderation, len(f))
    echelle = np.sqrt(np.mean(abs(y)**2))
    yn = y/echelle
    grille = grille_retards(f, bornes)
    dictionnaire = base_echos(f, grille)
    def scores(residu):
        return abs((dictionnaire*poids[:, None]).conj().T@(residu*poids))
    premiers = candidats(scores(yn), grille, 8)
    depart = []
    for premier in premiers:
        ds = [premier]
        for _ in range(nombre-1):
            _, prediction = projection(base_echos(f, ds), yn, poids)
            sc = scores(yn-prediction)
            for d in ds:
                sc[abs(grille-d) < 100*C/(2*np.ptp(f))*.5] = -np.inf
            ds.append(grille[np.argmax(sc)])
        depart.append(ds)
    rng = np.random.default_rng(0)
    depart.extend(rng.uniform(*bornes, size=(4, nombre)))
    def fun(ds):
        _, prediction = projection(base_echos(f, ds), yn, poids)
        return reel((prediction-yn)*poids)
    solutions = [least_squares(fun, x, bounds=bornes, ftol=1e-11, xtol=1e-11,
                               gtol=1e-11, max_nfev=500) for x in depart]
    best = min(solutions, key=lambda s: s.cost)
    ds = np.sort(best.x)
    a = base_echos(f, ds)
    gains, modele = projection(a, y, poids)
    jac = np.column_stack([a, 1j*a, a*gains[None, :]*(-4j*np.pi*(f-f.mean())[:, None]/(100*C))])
    noms = ([f"gain_reel_{j+1}" for j in range(nombre)] + [f"gain_imag_{j+1}" for j in range(nombre)] +
            [f"distance_cm_{j+1}" for j in range(nombre)])
    result = terminer(f, y, modele, jac, noms, variance, best, solutions, bornes, ds)
    result.update(modele="echos", distances_cm=ds, retards_ns=2*ds/(100*C)*1e9, gains=gains)
    return result


def poids_fit(variance, ponderation, n):
    if ponderation not in ("uniforme", "bruit"):
        raise ValueError("Pondération inconnue.")
    if ponderation == "bruit":
        if variance is None:
            raise ValueError("Pondération bruit demandée mais variance de moyenne indisponible.")
        return np.sqrt(np.median(variance)/variance)
    return np.ones(n)


def ajuster_plaque(f, y, indice, bornes=(0., 150.), epaisseurs=(1., 40.),
                   alpha_max=2., variance=None, ponderation="uniforme"):
    f, y = verifier(f, y, bornes, variance)
    if not np.isfinite(indice) or indice <= 1:
        raise ValueError("Plaque : indice réel connu > 1 requis.")
    if not np.isfinite([*epaisseurs, alpha_max]).all() or not 0 < epaisseurs[0] < epaisseurs[1] or alpha_max <= 0:
        raise ValueError("Plaque : bornes d'épaisseur/alpha invalides.")
    poids = poids_fit(variance, ponderation, len(f))
    echelle = np.sqrt(np.mean(abs(y)**2))
    yn = y/echelle
    grille = grille_retards(f, bornes)
    dictionnaire = base_echos(f, grille)
    depart = []
    # Recherche de minima concurrents en épaisseur, alpha et retard externe.
    for e in np.linspace(*epaisseurs, 9):
        for alpha in (.25*alpha_max, .75*alpha_max):
            forme = base_plaque(f, 0., e, alpha, indice)
            a = dictionnaire*forme[:, None]
            sc = abs((a*poids[:, None]).conj().T@(yn*poids)) / np.sqrt(np.sum(abs(a*poids[:, None])**2, axis=0))
            depart.extend([[d, e, alpha] for d in candidats(sc, grille, 2)])
    bornes_fit = ([bornes[0], epaisseurs[0], 0.], [bornes[1], epaisseurs[1], alpha_max])
    def fun(p):
        a = base_plaque(f, *p, indice)[:, None]
        _, prediction = projection(a, yn, poids)
        return reel((prediction-yn)*poids)
    solutions = [least_squares(fun, x, bounds=bornes_fit, x_scale=[30., 10., 1.],
                               ftol=1e-11, xtol=1e-11, gtol=1e-11, max_nfev=800) for x in depart]
    best = min(solutions, key=lambda s: s.cost)
    d, e, alpha = best.x
    forme = base_plaque(f, d, e, alpha, indice)
    gains, modele = projection(forme[:, None], y, poids)
    g = gains[0]
    r = (1-indice)/(1+indice)
    b = -(1-r*r)*r
    arriere = base_echos(f, [d])[:, 0]*b*np.exp(-4j*np.pi*f*indice*e/(1000*C))
    jac = np.column_stack([forme, 1j*forme, modele*(-4j*np.pi*(f-f.mean())/(100*C)),
                           g*alpha*arriere*(-4j*np.pi*f*indice/(1000*C)), g*arriere])
    noms = ["gain_reel", "gain_imag", "distance_cm", "epaisseur_mm", "alpha"]
    result = terminer(f, y, modele, jac, noms, variance, best, solutions, bornes_fit, best.x)
    result.update(modele="plaque", distances_cm=np.array([d, d+indice*e/10]),
                  retards_ns=np.array([2*d/(100*C), 2*d/(100*C)+2*indice*e/(1000*C)])*1e9,
                  gains=gains, epaisseur_mm=float(e), alpha=float(alpha), indice=float(indice))
    result["avertissements"].append("Plaque : deux faces, incidence normale, indice fixé, gain constant ; réflexions internes multiples négligées.")
    return result
