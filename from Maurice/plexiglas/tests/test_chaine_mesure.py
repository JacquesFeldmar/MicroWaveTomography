"""Contrôles hors matériel de l'axe distance, de la SOL et du protocole USB."""
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "progs"))
from commun import physique, sol
import litevna


class ChaineMesureTests(unittest.TestCase):
    def test_distances_connues_et_independance_du_zoom(self):
        for n, zoom in ((201, 16), (401, 8)):
            f = np.linspace(1e9, 6e9, n)
            for distance_m in (0, .1, .3, .4, .5, .6, 1.5):
                # Retard aller-retour, phase de réflexion métallique et
                # amplitude arbitraires : le pic doit garder sa position.
                echo = -.08 * np.exp(-2j * np.pi * f * (2 * distance_m / physique.c))
                d, a, pas = physique.profil_distance(f, echo, zoom=zoom)
                self.assertLessEqual(abs(d[np.argmax(a)] - 1000 * distance_m), pas / 2)

    def test_grille_non_uniforme_refusee(self):
        with self.assertRaisesRegex(ValueError, "uniforme"):
            physique.profil_distance([1e9, 2e9, 4e9], [1, 1, 1])

    def test_sol_retire_un_retard_de_cable_synthetique(self):
        f = np.linspace(1e9, 6e9, 201)
        directivite = .03 * np.exp(.2j * f / 1e9)
        adaptation = .15 * np.exp(-.3j * f / 1e9)
        suivi = .7 * np.exp(-2j * np.pi * f * 4e-9)

        def instrument(g):
            return directivite + suivi * g / (1 - adaptation * g)

        standards = [np.full(len(f), g, complex) for g in (-1, 1, 0)]
        coefficients, _ = sol.resoudre(standards, [instrument(g) for g in standards])
        cal = dict(freqs=f, **coefficients)
        fond = .2 * np.exp(-2j * np.pi * f * .3e-9)
        for distance_m in (.3, .4, .5, .6):
            echo = .01 * np.exp(-4j * np.pi * f * distance_m / physique.c)
            cible = sol.applique(cal, f, instrument(fond + echo))
            residu = cible - sol.applique(cal, f, instrument(fond))
            np.testing.assert_allclose(residu, echo, atol=1e-14, rtol=1e-12)
            d, a, pas = physique.profil_distance(f, residu)
            self.assertLessEqual(abs(d[np.argmax(a)] - distance_m * 1000), pas / 2)

    def test_decode_indices_et_signes_iq(self):
        # Construction selon le format USB, indépendante du dtype du pilote.
        data = b"".join(struct.pack("<6iH6x", 100, 0, 10 * i, -20 * i, 0, 0, i)
                        for i in (2, 0, 1))
        np.testing.assert_allclose(litevna.decoder(data, 3, "brut"),
                                   np.arange(3) * (.1 - .2j))
        with self.assertRaisesRegex(ValueError, "Indices"):
            litevna.decoder(data[:32] * 3, 3, "brut")

    def test_grille_programmee_apres_sortie_du_mode_usb(self):
        serial = FauxVNA()
        with patch.object(litevna.serial, "Serial", return_value=serial), \
                patch.object(litevna.time, "sleep"):
            s, _, _, identite, _ = litevna.acquisition(
                "FAUX", 1, 6, 201, 1, "brut", silencieux=True)
        self.assertEqual(identite["start_hz"], 1_000_000_000)
        self.assertEqual(identite["step_hz"], 25_000_000)
        self.assertEqual(s.shape, (1, 201))
        self.assertEqual(serial.reg[0x26], 2)

    def test_registre_incorrect_refuse_avant_acquisition(self):
        serial = FauxVNA(corrompre=True)
        with patch.object(litevna.serial, "Serial", return_value=serial), \
                patch.object(litevna.time, "sleep"):
            with self.assertRaisesRegex(ValueError, "Grille USB incorrecte"):
                litevna.acquisition("FAUX", 1, 6, 201, 1, "brut", silencieux=True)
        self.assertEqual(serial.lectures_fifo, 0)
        self.assertEqual(serial.reg[0x26], 2)

    def test_reprise_bloc_invalide_sans_conserver_ses_donnees(self):
        serial = FauxVNA(blocs_invalides=1)
        with patch.object(litevna.serial, "Serial", return_value=serial), \
                patch.object(litevna.time, "sleep"):
            s, temps, paquets, _, _ = litevna.acquisition(
                "FAUX", 1, 6, 201, 2, "brut", silencieux=True)
        self.assertEqual(serial.lectures_fifo, 3)
        self.assertEqual(s.shape, (2, 201))
        self.assertEqual(len(temps), 2)
        for paquet in paquets:
            np.testing.assert_allclose(litevna.decoder(paquet.tobytes(), 201, "brut"),
                                       .1 - .2j)
        self.assertEqual(serial.reg[0x26], 2)

    def test_indices_invalides_persistants_arret_et_retour_mode_normal(self):
        serial = FauxVNA(blocs_invalides=10)
        with patch.object(litevna.serial, "Serial", return_value=serial), \
                patch.object(litevna.time, "sleep"):
            with self.assertRaisesRegex(litevna.IndicesInvalides, "3 tentatives"):
                litevna.acquisition("FAUX", 1, 6, 201, 1, "brut", silencieux=True)
        self.assertEqual(serial.lectures_fifo, 3)
        self.assertEqual(serial.reg[0x26], 2)


class FauxVNA:
    """Firmware simulé rétablissant une autre grille au retour en mode normal."""
    def __init__(self, corrompre=False, blocs_invalides=0):
        self.reg = bytearray(256)
        self.reg[0xf0:0xf5] = bytes([2, 1, 2, 2, 2])
        self.buffer = bytearray()
        self.corrompre = corrompre
        self.lectures_fifo = 0
        self.blocs_invalides = blocs_invalides

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def reset_input_buffer(self):
        self.buffer.clear()

    def read(self, size):
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    def write(self, data):
        i = 0
        while i < len(data):
            cmd = data[i]
            if cmd == 0:
                i += 1
                continue
            addr = data[i + 1]
            if cmd == 0x10:
                self.buffer.append(self.reg[addr])
                i += 2
                continue
            if cmd == 0x18:
                self.lectures_fifo += 1
                for k in range(data[i + 2]):
                    indice = 0 if self.lectures_fifo <= self.blocs_invalides else k
                    self.buffer.extend(struct.pack("<6iH6x", 100, 0, 10, -20, 0, 0, indice))
                i += 3
                continue
            n = {0x20: 1, 0x21: 2, 0x23: 8}[cmd]
            self.reg[addr:addr + n] = data[i + 2:i + 2 + n]
            if addr == 0x26 and self.reg[addr] == 2:
                self.reg[0x10:0x18] = (12_500_000).to_bytes(8, "little")
            if addr == 0x26 and self.reg[addr] == 1 and self.corrompre:
                self.reg[0x10:0x18] = (1).to_bytes(8, "little")
            i += 2 + n
        return len(data)


if __name__ == "__main__":
    unittest.main()
