"""Preuves d'audit : lecture des sorties et construction openEMS en memoire.

Executer avec le Python de l'environnement openems et l'option -B.
N'appelle jamais Run, ne cree aucun repertoire et n'ecrit aucun resultat.
La sortie JSON peut etre redirigee par l'auditeur vers son dossier de revue.
Les bornes des bandes sont des points echantillonnes, sans interpolation.
"""
import sys
sys.dont_write_bytecode = True

import dataclasses
import hashlib
import json
import pathlib

import numpy as np

SIM = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
import fdtd as F
from banc import Acquisition, C, Montage


def intervals(f, mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return [[float(f[a]), float(f[b])] for a, b in
            zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1)]


def grid_summary(csx):
    answer = {}
    for ax in "xyz":
        lines = np.asarray(csx.GetGrid().GetLines(ax))
        delta = np.diff(lines)
        ratios = np.maximum(delta[1:] / delta[:-1], delta[:-1] / delta[1:])
        answer[ax] = dict(lines=len(lines), minimum_mm=float(delta.min()),
                          maximum_mm=float(delta.max()),
                          bounds_mm=[float(lines[0]), float(lines[-1])],
                          max_adjacent_ratio=float(ratios.max()),
                          sha256=hashlib.sha256(lines.tobytes()).hexdigest())
    answer["cells"] = int(np.prod([answer[ax]["lines"] - 1 for ax in "xyz"]))
    answer["dt_estimate_ps"] = F.verifie_maillage(csx, 1)[1] * 1e12
    return answer


def main():
    output = {"scope": "read-only, no FDTD Run", "s11": {}, "meshes": {}}
    # construit() has one directory-creation side effect; suppress it in this
    # process while retaining the real CSXCAD/openEMS construction and meshing.
    original_makedirs = F.os.makedirs
    F.os.makedirs = lambda *args, **kwargs: None
    owners = []  # FDTD owns C++ CSX; keep it alive while reading the grid.
    try:
        for nom in ("diamant_uwb", "diamant_uwb_x18", "vivaldi_tomographie"):
            path = SIM / "resultats" / nom / "antenne_seule.s1p"
            data = np.loadtxt(path, comments=("!", "#"))
            freq, saved = data[:, 0], data[:, 1] + 1j * data[:, 2]
            f, db = freq / 1e9, 20 * np.log10(abs(saved))
            mask = db < -10
            selected = np.flatnonzero(mask)
            lo, hi = selected[[0, -1]]
            note = dict(points=len(freq), envelope_10_GHz=[float(f[lo]), float(f[hi])],
                        envelope_coverage_percent=float(100 * mask[lo:hi + 1].mean()),
                        intervals_under_10_GHz=intervals(f, mask),
                        intervals_over_6_GHz=intervals(f, db >= -6),
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            if nom == "vivaldi_tomographie":
                within = (f >= 1.4) & (f <= 6.0)
                note["metrics_1p4_to_6"] = dict(
                    under_10_percent=float(100 * np.mean(db[within] < -10)),
                    under_6_percent=float(100 * np.mean(db[within] < -6)),
                    worst_db=float(db[within].max()),
                    mean_power_db=float(10 * np.log10(np.mean(abs(saved[within]) ** 2))))
            ant = F.charge_antenne(nom)
            montage = Montage(acquisition=Acquisition(f_min=freq[0], f_max=freq[-1],
                                                     points=len(freq)))
            obj = F.construit(montage, ant, dossier=str(SIM / "chatGPT_critical_review"))
            owners.append(obj)
            port = obj[2]
            probe_dir = SIM / "resultats" / "fdtd" / nom / "antenne_seule"
            port.CalcPort(str(probe_dir), freq, ref_impedance=50)
            rebuilt = port.uf_ref / port.uf_inc
            note["max_complex_difference_from_raw_probes"] = float(np.max(abs(rebuilt - saved)))
            probe = np.loadtxt(probe_dir / "port_ut_1", comments="%")
            note["recorded_port_duration_ns"] = float(probe[-1, 0] * 1e9)
            output["s11"][nom] = note
            output["meshes"][nom] = grid_summary(obj[1])

        ant, montage = F.charge_antenne("vivaldi_tomographie"), Montage()
        individual, common = {}, {}
        for dist in (None, 50.0, 60.0, 70.0):
            key = "background" if dist is None else str(dist)
            obj = F.construit(montage, ant, x_cm=dist,
                             dossier=str(SIM / "chatGPT_critical_review"))
            owners.append(obj)
            individual[key] = grid_summary(obj[1])
            obj = F.construit(montage, ant, x_cm=dist, x_domaine=70.0,
                             dossier=str(SIM / "chatGPT_critical_review"))
            owners.append(obj)
            common[key] = grid_summary(obj[1])
            if dist is not None:
                z = np.asarray(obj[1].GetGrid().GetLines("z"))
                common[key]["distance_from_plate_faces_to_mesh_mm"] = [
                    float(np.min(abs(z - face))) for face in (dist * 10, dist * 10 + 5)]
        output["individual_calls"] = individual
        output["common_domain_calls"] = common

        settings = {}
        for name, value in (("symetrie", False), ("mailles_par_lambda", 80), ("maille_min", 0.05)):
            m = dataclasses.replace(montage, maillage=dataclasses.replace(montage.maillage, **{name: value}))
            obj = F.construit(m, ant, dossier=str(SIM / "chatGPT_critical_review"))
            owners.append(obj)
            summary = grid_summary(obj[1])
            settings[name] = dict(value=value, same_grid_as_default=all(
                summary[ax]["sha256"] == individual["background"][ax]["sha256"] for ax in "xyz"),
                advertised_cost=F.estime_cout(m))
        output["parameter_effects"] = settings

        grid = owners[2][1].GetGrid()  # third nominal antenna = Vivaldi
        substrate = {}
        d = ant.cotes()
        for ax, lo, hi in (("x", -d["demi_x"], d["demi_x"]), ("z", 0.0, d["z_total"])):
            lines = np.asarray(grid.GetLines(ax))
            delta = np.diff(lines[(lines >= lo) & (lines <= hi)])
            substrate[ax] = dict(maximum_step_mm=float(delta.max()),
                                  cells_per_substrate_wavelength_6GHz=float(
                                      C / 6e9 / np.sqrt(ant.EPS_R) * 1e3 / delta.max()))
        output["vivaldi_substrate"] = substrate
    finally:
        F.os.makedirs = original_makedirs
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
