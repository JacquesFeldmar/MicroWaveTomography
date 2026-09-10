"""
INSTRUMENT -- le LiteVNA, et rien que lui.

Ouverture, balayage, moyennage vectoriel, enregistrement et relecture des
balayages BRUTS. Aucun modele physique, aucun dossier de donnees : la bande et
les chemins sont fournis par l'appelant.

L'USB du LiteVNA renvoie TOUJOURS des donnees non calibrees, quelle que soit la
calibration faite dans son menu : la correction est l'affaire de sol.py.
"""

import os

import numpy as np

PORT_VNA = "ASRL6::INSTR"


def ouvrir_reel(start_ghz, stop_ghz, points, port=PORT_VNA):
    """Ouvre le LiteVNA (protocole NanoVNA V2) et regle son balayage."""
    from skrf.vi.vna.nanovna import NanoVNAv2
    import skrf as rf
    vna = NanoVNAv2(port, backend="@py")
    vna.frequency = rf.Frequency(start=start_ghz, stop=stop_ghz,
                                 npoints=points, unit="GHz")
    return vna


def balayage(vna):
    """Un balayage brut. Rend (freqs, s11)."""
    s11, _ = vna.get_s11_s21()
    return s11.f, s11.s[:, 0, 0]


def acquiert(vna, n_moy=16, n_jetes=2, silencieux=False):
    """Moyennage VECTORIEL : abaisse le plancher de 10.log10(N) dB."""
    for _ in range(n_jetes):
        vna.get_s11_s21()
    acc, freqs = None, None
    for k in range(n_moy):
        f, s = balayage(vna)
        if freqs is None:
            freqs, acc = f.copy(), np.zeros(len(f), dtype=complex)
        acc += s
        if not silencieux:
            print(f"      balayage {k + 1}/{n_moy}", end="\r", flush=True)
    if not silencieux:
        print(" " * 32, end="\r")
    if hasattr(vna, "avance"):     # simulateur : scene suivante
        vna.avance()
    return freqs, acc / n_moy


class ReseauSimule:
    """Imite juste ce que le code utilise d'un objet skrf.Network."""
    def __init__(self, f, s):
        self.f = f
        self.s = s.reshape(-1, 1, 1)


# ======================================================================
# ENREGISTREMENT / RELECTURE
# ======================================================================
def enregistre(chemin, freqs, sweeps, temps=None, **meta):
    """Un ou plusieurs balayages BRUTS, avec leurs instants.

    Format unique pour une mesure isolee comme pour une sequence : sweeps est
    toujours un tableau (n_balayages, n_frequences). Les donnees enregistrees
    sont NON CALIBREES, pour pouvoir etre recalculees plus tard avec une
    meilleure calibration.
    """
    sweeps = np.atleast_2d(np.asarray(sweeps))
    if temps is None:
        temps = np.zeros(len(sweeps))
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    np.savez_compressed(chemin, freqs=freqs, sweeps=sweeps,
                        temps=np.asarray(temps), **meta)
    return chemin


def relit(chemin):
    """Rend (freqs, sweeps, temps). Accepte l'ancien format a un balayage."""
    z = np.load(chemin, allow_pickle=True)
    freqs = z["freqs"]
    if "sweeps" in z:
        return freqs, np.atleast_2d(z["sweeps"]), z["temps"]
    return freqs, np.atleast_2d(z["s11"]), np.zeros(1)   # ancien format
