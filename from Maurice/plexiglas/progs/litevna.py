"""Interface USB minimale du LiteVNA 64.

Le programme écrit START, le pas et le nombre de points dans les registres USB.
Le mode ``brut``
sert à appliquer une SOL Python ; le mode ``interne`` demande au firmware les
valeurs corrigées par sa calibration active.
"""

from datetime import datetime, timezone
import struct
import time

import numpy as np
import serial
from serial.tools import list_ports


PAQUET = np.dtype([
    ("ondes", "<i4", (6,)),
    ("indice", "<u2"),
    ("reserve", "u1", (6,)),
])


class IndicesInvalides(ValueError):
    """Un bloc USB ne contient pas exactement une fois chaque fréquence."""


def choisir_port(port=None):
    if port:
        return port
    ports = [p.device for p in list_ports.comports()
             if p.vid == 0x04B4 and p.pid == 0x0008]
    if len(ports) != 1:
        raise ValueError("Préciser --port : un seul LiteVNA USB doit être détecté.")
    return ports[0]


def parametres_sweep(debut_ghz, fin_ghz, points=None, delta_mhz=None):
    """Valide START/STOP et calcule points et pas de fréquence.

    Avec ``delta_mhz``, le STOP doit tomber exactement sur la grille. La
    valeur de STOP effectivement envoyée au VNA est alors recalculée à partir
    du pas entier en hertz du registre USB.
    """
    if delta_mhz is None and points is None:
        raise ValueError("Fournir --points ou --delta-mhz.")
    if delta_mhz is not None:
        if not np.isfinite(delta_mhz) or delta_mhz <= 0:
            raise ValueError("--delta-mhz doit être positif.")
        debut_hz = int(round(debut_ghz * 1e9))
        fin_hz = int(round(fin_ghz * 1e9))
        pas_hz = int(round(delta_mhz * 1e6))
        intervalles = (fin_hz - debut_hz) / pas_hz
        n = int(round(intervalles)) + 1
        if n < 2 or not np.isclose(intervalles, n - 1, rtol=0, atol=1e-9):
            raise ValueError("STOP doit être un multiple exact de Δf depuis START.")
        fin_hz = debut_hz + (n - 1) * pas_hz
        return debut_hz / 1e9, fin_hz / 1e9, n, pas_hz
    verifier_spec(debut_ghz, fin_ghz, points, 1)
    pas_hz = int(round((fin_ghz - debut_ghz) * 1e9 / (points - 1)))
    if pas_hz < 1:
        raise ValueError("Le pas de fréquence doit être au moins de 1 Hz.")
    fin_hz = int(round(debut_ghz * 1e9)) + (points - 1) * pas_hz
    return debut_ghz, fin_hz / 1e9, points, pas_hz


def verifier_spec(debut_ghz, fin_ghz, points, nombre):
    if (not np.all(np.isfinite([debut_ghz, fin_ghz])) or
            not 0 < debut_ghz < fin_ghz or
            not isinstance(points, (int, np.integer)) or not 2 <= points <= 65535 or
            not isinstance(nombre, (int, np.integer)) or nombre < 1):
        raise ValueError("Fréquences croissantes, points entre 2 et 65535, nombre >= 1 requis.")


def lire_exact(lien, taille):
    morceaux = []
    restant = taille
    while restant:
        morceau = lien.read(restant)
        if not morceau:
            break
        morceaux.append(morceau)
        restant -= len(morceau)
    donnees = b"".join(morceaux)
    if len(donnees) != taille:
        raise ValueError(f"Transfert incomplet : {len(donnees)}/{taille} octets.")
    return donnees


def lire_registre(lien, adresse):
    lien.write(bytes((0x10, adresse)))
    return lire_exact(lien, 1)[0]


def verifier_grille_usb(lien, debut_hz, pas_hz, points):
    """Relit les registres ; ne constitue pas une mesure de fréquence RF."""
    lus = {}
    for nom, adresse, taille, attendu in (
            ("start_hz", 0x00, 8, debut_hz),
            ("step_hz", 0x10, 8, pas_hz),
            ("points", 0x20, 2, points),
            ("valeurs_par_frequence", 0x22, 2, 1)):
        valeur = int.from_bytes(bytes(lire_registre(lien, adresse + i)
                                      for i in range(taille)), "little")
        if valeur != attendu:
            raise ValueError(f"Grille USB incorrecte : {nom}={valeur}, attendu {attendu}.")
        lus[nom] = valeur
    return lus


def decoder(donnees, points, mode):
    if mode not in ("brut", "interne"):
        raise ValueError(f"Mode inconnu : {mode}")
    if len(donnees) != points * PAQUET.itemsize:
        raise ValueError("Taille de trame incompatible avec le nombre de points.")
    trames = np.frombuffer(donnees, dtype=PAQUET)
    indices = trames["indice"].astype(int)
    if not np.array_equal(np.sort(indices), np.arange(points)):
        uniques, comptes = np.unique(indices, return_counts=True)
        manquants = np.setdiff1d(np.arange(points), uniques)
        raise IndicesInvalides(
            "Indices de fréquence manquants, répétés ou hors plage : "
            f"{len(manquants)} manquants, {np.sum(comptes - 1)} répétés, "
            f"{np.count_nonzero(indices >= points)} hors plage.")
    valeurs = trames["ondes"].astype(np.float64)
    if mode == "interne":
        reference = valeurs[:, 0] + 1j * valeurs[:, 1]
        if not (np.all(reference.real == 2**30) and np.all(reference.imag == 0)):
            raise ValueError("Référence USB du mode corrigé non reconnue.")
        s11 = (valeurs[:, 2] + 1j * valeurs[:, 3]) / 2**30
    else:
        emission = valeurs[:, 0] + 1j * valeurs[:, 1]
        reflexion = valeurs[:, 2] + 1j * valeurs[:, 3]
        if np.any(np.abs(emission) == 0):
            raise ValueError("Référence d'émission nulle dans un sweep brut.")
        s11 = reflexion / emission
    return s11[np.argsort(indices)]


def acquisition(port, debut_ghz, fin_ghz, points, nombre, mode,
                silencieux=False, delta_hz=None):
    """Programme START/Δf/points puis acquiert ``nombre`` sweeps."""
    verifier_spec(debut_ghz, fin_ghz, points, nombre)
    if mode not in ("brut", "interne"):
        raise ValueError("Mode d'acquisition attendu : brut ou interne.")
    port = choisir_port(port)
    sweeps, paquets, temps = [], [], []
    identite = {}
    with serial.Serial(port, 115200, timeout=10, write_timeout=2,
                       exclusive=True) as lien:
        lien.write(bytes(8))
        lien.reset_input_buffer()
        for nom, adresse in (("variante", 0xf0), ("protocole", 0xf1),
                             ("materiel", 0xf2), ("firmware_majeur", 0xf3),
                             ("firmware_mineur", 0xf4)):
            identite[nom] = lire_registre(lien, adresse)
        if identite["variante"] != 2 or identite["protocole"] != 1:
            raise ValueError("L'appareil n'est pas un LiteVNA au protocole attendu.")
        debut_hz = int(round(debut_ghz * 1e9))
        pas_hz = (int(round(delta_hz)) if delta_hz is not None else
                  int(round((fin_ghz - debut_ghz) * 1e9 / (points - 1))))
        if debut_hz < 50_000 or pas_hz < 1:
            raise ValueError("START ou Δf invalide pour le registre du LiteVNA.")
        # Revenir au mode normal AVANT de programmer la grille : certains
        # firmwares rétablissent leurs paramètres locaux en quittant l'USB.
        lien.write(bytes((0x20, 0x26, 2)))
        time.sleep(.05)
        if lire_registre(lien, 0x26) != 2:
            raise ValueError("Le LiteVNA n'est pas en mode normal USB.")
        # Registres USB NanoVNA/LiteVNA : START et STEP sur 64 bits,
        # POINTS et valeurs par fréquence sur 16 bits.
        lien.write(
            struct.pack("<BBQ", 0x23, 0x00, debut_hz) +
            struct.pack("<BBQ", 0x23, 0x10, pas_hz) +
            struct.pack("<BBH", 0x21, 0x20, points) +
            struct.pack("<BBH", 0x21, 0x22, 1))
        time.sleep(.1)
        code_mode = 1 if mode == "brut" else 3
        lien.write(bytes((0x20, 0x26, code_mode)))
        try:
            time.sleep(.05)
            if lire_registre(lien, 0x26) != code_mode:
                raise ValueError(f"Le firmware refuse le mode USB {code_mode}.")
            identite.update(verifier_grille_usb(lien, debut_hz, pas_hz, points))
            debut = time.monotonic()
            echecs = 0
            while len(sweeps) < nombre:
                # Le FIFO est alimenté en continu ; on retire les points anciens.
                lien.write(bytes((0x20, 0x30, 0)))
                time.sleep(.05)
                # Le troisième octet est un compteur sur 8 bits. Un zéro ne
                # signifie pas « tous les points » sur tous les firmwares ;
                # lire par paquets de 255 rend le transfert compatible avec
                # le LiteVNA 64 et les firmwares NanoVNA-V2.
                morceaux = []
                restant = points
                while restant:
                    n = min(restant, 255)
                    lien.write(bytes((0x18, 0x30, n)))
                    morceaux.append(lire_exact(lien, n * PAQUET.itemsize))
                    restant -= n
                paquet = b"".join(morceaux)
                try:
                    sweep = decoder(paquet, points, mode)
                except IndicesInvalides as exc:
                    echecs += 1
                    if echecs >= 3:
                        raise IndicesInvalides(
                            f"{exc} Échec après 3 tentatives du balayage "
                            f"{len(sweeps) + 1}/{nombre}.") from exc
                    if not silencieux:
                        print(f"{exc} Balayage rejeté ; nouvelle tentative "
                              f"{echecs + 1}/3.", flush=True)
                    continue
                echecs = 0
                sweeps.append(sweep)
                paquets.append(np.frombuffer(paquet, dtype=np.uint8).copy())
                temps.append(time.monotonic() - debut)
                if not silencieux:
                    print(f"Sweep {len(sweeps)}/{nombre}", flush=True)
        finally:
            # Même en cas d'erreur, rendre l'affichage au VNA.
            lien.write(bytes((0x20, 0x26, 2)))
    return (np.asarray(sweeps), np.asarray(temps), np.asarray(paquets), identite,
            port)


def frequences(debut_ghz, fin_ghz, points):
    return np.linspace(debut_ghz * 1e9, fin_ghz * 1e9, points)


def nom_utc(prefix):
    return prefix + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
