"""MODELE ANALYTIQUE -- le montage sans openEMS.

Il sert a trois choses :

  1. valider la chaine de traitement de bout en bout, avec une verite connue ;
  2. montrer le principe physique : pourquoi un retard d'antenne produit un
     decalage CONSTANT, et ce qui le fait deriver avec la distance ;
  3. tester des hypotheses sur l'origine des deux branches de pics observees
     dans le rapport, avant de payer le prix d'une simulation FDTD.

Le modele n'est pas une simulation electromagnetique : il compose des echos.
C'est volontaire. Chaque terme y porte un nom physique et une valeur reglable.

    S11_fond(f)    = Gamma_connecteur(f) + echos internes de l'antenne
    S11_plaque(f)  = S11_fond(f) + H(f)^2 . Gamma_plaque(f, x) . e^(-j.4.pi.f.x/c)

H(f) est la fonction de transfert aller simple de l'antenne. Elle est traversee
DEUX fois, d'ou H^2 : c'est ce qui fait apparaitre plusieurs branches de pics
quand H contient plusieurs trajets internes.
"""
from dataclasses import dataclass

import numpy as np

from banc import C


@dataclass
class ModeleAntenne:
    """Antenne vue comme une somme de trajets internes.

    tau1  : retard aller simple du trajet principal (connecteur -> rayonnement)
    tau2  : retard d'un second trajet interne (reverberation dans la structure)
    a1,a2 : leurs amplitudes
    derive_ns : dispersion. tau1 varie lineairement sur la bande de cette
                quantite. NEGATIF = plus de retard en bas de bande, ce qui est
                le comportement habituel d'une antenne large bande.
    desadaptation_db : |Gamma| du connecteur, vu a distance nulle

    ATTENTION a l'aller-retour. L'antenne est traversee deux fois, donc
    H(f)^2 contient TROIS termes : 2.tau1, tau1+tau2 et 2.tau2. Sur l'axe des
    distances ils tombent a c.tau1, c.(tau1+tau2)/2 et c.tau2, regulierement
    espaces de c.(tau2-tau1)/2. Les valeurs par defaut ci-dessous placent les
    deux premiers a 20,0 et 26,3 cm : les deux branches du rapport pour John.
    Le troisieme, en a2^2, reste 30 dB plus bas, donc invisible.
    """
    tau1_ns: float = 0.6671       # c.tau1 = 20,0 cm
    tau2_ns: float = 1.0873       # c.(tau1+tau2)/2 = 26,3 cm
    a1: float = 1.0
    a2: float = 0.20
    derive_ns: float = 0.0
    desadaptation_db: float = -12.0

    def transfert(self, freqs):
        """H(f), aller simple, sans dimension."""
        f = np.asarray(freqs, dtype=float)
        tau1 = self.tau1_ns * 1e-9
        if self.derive_ns:
            u = (f - f[0]) / (f[-1] - f[0])
            tau1 = tau1 + self.derive_ns * 1e-9 * (u - 0.5)
        h = self.a1 * np.exp(-2j * np.pi * f * tau1)
        if self.a2:
            h = h + self.a2 * np.exp(-2j * np.pi * f * self.tau2_ns * 1e-9)
        return h

    def fond(self, freqs, echos_fixes=()):
        """S11 sans cible : desadaptation + echos internes + echos du montage.

        echos_fixes : iterable de (amplitude_lineaire, distance_affichee_cm).
        """
        f = np.asarray(freqs, dtype=float)
        g = 10 ** (self.desadaptation_db / 20) * np.ones_like(f, dtype=complex)
        # l'echo propre de l'ouverture : vu a c.tau1 sur l'axe
        g = g + 0.25 * np.exp(-2j * np.pi * f * 2 * self.tau1_ns * 1e-9)
        for amp, d_cm in echos_fixes:
            g = g + amp * np.exp(-2j * np.pi * f * 2 * (d_cm / 100) / C)
        return g


def gamma_plaque(freqs, x_m, cote_m=0.60, f_min_utile=None):
    """Reflexion d'une plaque finie, vue depuis l'antenne.

    Deux effets, les seuls qui comptent pour la forme de l'echo :

      - decroissance en 1/(2x) : la plaque se comporte en miroir, donc l'image
        est a 2x ;
      - troncature de Fresnel : la plaque ne reflechit « en miroir » que si son
        demi-cote couvre le rayon de la premiere zone de Fresnel,
        sqrt(lambda.x/2). En dessous, sa contribution chute -- et comme ce
        rayon grandit avec lambda, c'est le BAS de la bande qui est tronque,
        d'autant plus que la plaque est loin.
    """
    f = np.asarray(freqs, dtype=float)
    lam = C / f
    r_fresnel = np.sqrt(lam * x_m / 2)
    couverture = np.clip((cote_m / 2) / r_fresnel, 0, 1) ** 2
    return -couverture / (2 * x_m) * np.ones_like(f, dtype=complex)


def simule(freqs, x_cm, antenne: ModeleAntenne = None, cote_plaque_m=0.60,
           echos_fixes=((0.05, 95.0),), bruit_db=None, germe=0):
    """Rend (S11_fond, S11_plaque) pour une plaque a x_cm.

    echos_fixes : echos du montage (table, support), en (amplitude, distance cm).
    bruit_db    : si donne, bruit complexe gaussien a ce niveau, en dB.
    """
    antenne = antenne or ModeleAntenne()
    f = np.asarray(freqs, dtype=float)
    x = x_cm / 100
    fond = antenne.fond(f, echos_fixes)
    h = antenne.transfert(f)
    echo = h ** 2 * gamma_plaque(f, x, cote_plaque_m) * np.exp(
        -2j * np.pi * f * 2 * x / C)
    plaque = fond + echo
    if bruit_db is not None:
        rng = np.random.default_rng(germe)
        sigma = 10 ** (bruit_db / 20)
        for s in (fond, plaque):
            s += sigma * (rng.normal(size=f.size) + 1j * rng.normal(size=f.size))
    return fond, plaque


def verite_terrain(x_cm, antenne: ModeleAntenne = None):
    """Ou les pics DOIVENT tomber, d'apres le modele : utile pour les tests.

    Le trajet traverse l'antenne deux fois, donc les retards internes
    s'additionnent deux a deux : 2.tau1, tau1+tau2, 2.tau2.
    """
    antenne = antenne or ModeleAntenne()
    t1, t2 = antenne.tau1_ns * 1e-9, antenne.tau2_ns * 1e-9
    return {
        "proche": x_cm + C * t1 * 100,
        "milieu": x_cm + C * (t1 + t2) / 2 * 100,
        "lointain": x_cm + C * t2 * 100,
    }
