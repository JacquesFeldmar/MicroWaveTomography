"""BANC -- les parametres du montage, en un seul endroit.

Tout le projet lit ses reglages ici : la bande et le traitement (identiques a
ceux du rapport pour John), la geometrie de l'antenne, celle de la plaque, et
le maillage FDTD. Rien dans ce fichier ne depend d'openEMS.

Convention de distance, valable partout dans le projet : l'axe est en ALLER
SIMPLE depuis le plan de calibration SOL. Une cible a la distance d y apparait
a d, et un retard aller simple tau_a de l'antenne decale l'axe de c.tau_a.
"""
from dataclasses import dataclass, field

C = 299792458.0


# ======================================================================
# ACQUISITION ET TRAITEMENT  (rapport pour John, 9 octobre 2026)
# ======================================================================
@dataclass(frozen=True)
class Acquisition:
    f_min: float = 1.0e9          # Hz
    f_max: float = 6.0e9          # Hz
    points: int = 201             # grille uniforme
    zero_padding: int = 16        # IFFT sur 16 x 201 = 3216 points
    fenetre: str = "hann"         # Hann symetrique, w_k = 0.5(1-cos(2.pi.k/(N-1)))
    z_ref: float = 50.0           # ohms

    @property
    def df(self) -> float:
        return (self.f_max - self.f_min) / (self.points - 1)

    @property
    def n_fft(self) -> int:
        return self.zero_padding * self.points

    @property
    def pas_distance(self) -> float:
        """Pas de l'axe des distances, en m. 1,86 mm avec les reglages du rapport."""
        return C / (2.0 * self.n_fft * self.df)

    @property
    def resolution(self) -> float:
        """c/2B, en m. Ce n'est PAS le pas d'interpolation ci-dessus."""
        return C / (2.0 * (self.f_max - self.f_min))


# ======================================================================
# ANTENNE  (Nooelec UWB Surveyor, biconique planaire)
# ======================================================================
@dataclass(frozen=True)
class Antenne:
    """Geometrie approximative, en mm. La datasheet ne donne que l'encombrement.

    La carte fait 120 x 120 x 0,8 mm, connecteur SMA sur un bord. Le reste
    (rayon des petales, fente d'alimentation, largeur de ligne) est ajustable :
    c'est precisement ce que l'etape de recalage sur le S11 mesure doit fixer.
    """
    cote: float = 120.0           # cote de la carte
    epaisseur: float = 0.8        # epaisseur du substrat
    eps_r: float = 4.4            # FR4
    tan_delta: float = 0.02
    rayon_petale: float = 46.0    # rayon du disque rayonnant
    fente: float = 0.6            # fente d'alimentation entre les deux petales
    largeur_ligne: float = 1.5    # ligne 50 ohms sur 0,8 mm de FR4
    longueur_ligne: float = 38.0  # du connecteur a la fente
    cuivre: float = 0.035

    @property
    def retard_ligne_ns(self) -> float:
        """Retard ALLER SIMPLE de la seule ligne d'alimentation, en ns.

        eps_eff approche par la formule classique du microruban large.
        """
        eps_eff = (self.eps_r + 1) / 2 + (self.eps_r - 1) / 2 * (
            1 + 12 * self.epaisseur / self.largeur_ligne) ** -0.5
        return self.longueur_ligne * 1e-3 * eps_eff ** 0.5 / C * 1e9

    @property
    def decalage_ligne_cm(self) -> float:
        """Decalage affiche qu'elle produit a elle seule, en cm."""
        return C * self.retard_ligne_ns * 1e-9 * 100


# ======================================================================
# PLAQUE
# ======================================================================
@dataclass(frozen=True)
class Plaque:
    cote: float = 600.0           # mm -- la plaque de 60 x 60 cm
    # Une plaque PEC est opaque des le premier millimetre : son epaisseur n'a
    # aucun effet physique. On la prend egale au pas de la grille d'air pour
    # que sa face arriere tombe SUR une ligne de maillage. Sinon elle en cree
    # une a quelques dixiemes de millimetre, ce qui divise le pas de temps --
    # et donc multiplie la duree de calcul -- pour rien.
    epaisseur: float = 5.0        # mm
    distances_cm: tuple = (50.0, 60.0, 70.0)   # celles du rapport


# ======================================================================
# MAILLAGE ET EXECUTION FDTD
# ======================================================================
@dataclass(frozen=True)
class Maillage:
    """Le maillage decide du cout. Trois presets sont proposes dans run.py."""
    mailles_par_lambda: int = 20      # pres de l'antenne, a f_max
    mailles_par_lambda_air: int = 10  # dans l'espace libre
    maille_min: float = 0.2           # mm, taille visee autour du port
    marge_pml: float = 8              # cellules de PML
    marge_air_mm: float = 60.0        # air entre l'objet et la PML
    n_pas_max: int = 250000
    critere_fin: float = -40.0        # dB d'energie residuelle
    symetrie: bool = False            # reserve : aucun plan n'est actuellement implemente
    rapport_max: float = 1.5          # borne VERIFIEE sur les cellules finales
    facteur_courant: float = 0.95     # marge sous le CFL vide anisotrope
    duree_ns: float | None = None     # None : max(1/df, propagation + extinction)

    def __post_init__(self):
        if min(self.mailles_par_lambda, self.mailles_par_lambda_air,
               self.maille_min, self.n_pas_max) <= 0:
            raise ValueError("les resolutions et n_pas_max doivent etre positifs")
        if not 1 < self.rapport_max <= 1.5:
            raise ValueError("rapport_max doit etre dans ]1, 1.5]")
        if not 0 < self.facteur_courant < 1:
            raise ValueError("facteur_courant doit etre dans ]0, 1[")
        if self.duree_ns is not None and self.duree_ns <= 0:
            raise ValueError("duree_ns doit etre positive")


# ======================================================================
# MESURES DE REFERENCE  (rapport pour John, tableau page 3)
# ======================================================================
MESURES_9_OCT = {
    # distance_cm : (pic proche_cm, pic lointain_cm)
    50.0: (69.91, 75.88),
    60.0: (79.61, 86.32),
    70.0: (90.42, 96.57),
}
DECALAGE_PROCHE_CM = 20.0      # moyenne des trois
DECALAGE_LOINTAIN_CM = 26.3
PENTES_PHASE_CM = {50.0: 21.3, 60.0: 22.7, 70.0: 22.6}   # figure 3 du rapport


@dataclass(frozen=True)
class Montage:
    """Le montage complet."""
    acquisition: Acquisition = field(default_factory=Acquisition)
    antenne: Antenne = field(default_factory=Antenne)
    plaque: Plaque = field(default_factory=Plaque)
    maillage: Maillage = field(default_factory=Maillage)

    def resume(self) -> str:
        """Acquisition et cible. L'antenne, elle, se decrit dans son module."""
        a = self.acquisition
        return "\n".join([
            f"  bande            {a.f_min/1e9:.1f} - {a.f_max/1e9:.1f} GHz, "
            f"{a.points} points, pas {a.df/1e6:.1f} MHz",
            f"  IFFT             {a.n_fft} points, pas d'axe "
            f"{a.pas_distance*1e3:.2f} mm, resolution c/2B "
            f"{a.resolution*1e2:.1f} cm",
            f"  plaque           {self.plaque.cote/10:.0f} x "
            f"{self.plaque.cote/10:.0f} cm a "
            f"{', '.join(f'{d:.0f}' for d in self.plaque.distances_cm)} cm",
        ])
