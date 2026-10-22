"""Contrôles de lecture de l'audit du 18 octobre 2026.

À lancer avec Python disposant de NumPy et l'option -B.
N'écrit que preuves_verifications_2026-10-18.json, à côté de ce script.
Ne lance ni solveur ni exportateur et ne modifie pas les sources auditées.
"""
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def ranges(f, mask):
    """Intervalles de points échantillonnés, sans interpolation du seuil."""
    indices = np.flatnonzero(mask)
    if not len(indices):
        return []
    groups = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
    return [[float(f[g[0]] / 1e9), float(f[g[-1]] / 1e9)] for g in groups]


def s11_stats(path, band=None):
    lines = path.read_text(encoding="ascii").splitlines()
    header = next(s for s in lines if s.strip().startswith("#"))
    assert header.strip().lower() == "# hz s ri r 50", header
    data = np.array([[float(t) for t in s.split()]
                     for s in lines if s.strip() and s.lstrip()[0] not in "!#"])
    f, r, i = data.T
    db = 20 * np.log10(np.hypot(r, i))
    selected = np.ones(len(f), dtype=bool) if band is None else (
        (f >= band[0] * 1e9) & (f <= band[1] * 1e9))
    passed = np.flatnonzero(db < -10)
    envelope = (f >= f[passed[0]]) & (f <= f[passed[-1]]) if len(passed) else selected
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "points": len(f), "band_GHz": [float(f[0]/1e9), float(f[-1]/1e9)],
        "evaluation_band_GHz": band,
        "sampled_intervals_below_minus10_GHz": ranges(f, (db < -10) & selected),
        "sampled_intervals_at_or_above_minus10_inside_envelope_GHz": ranges(f, (db >= -10) & envelope),
        "sampled_intervals_above_minus6_GHz": ranges(f, (db > -6) & selected),
        "coverage_minus10_percent_selected": float(100*np.mean(db[selected] < -10)),
        "coverage_minus10_percent_envelope": float(100*np.mean(db[envelope] < -10)),
        "coverage_minus6_percent_selected": float(100*np.mean(db[selected] < -6)),
        "mean_reflected_power_db_selected": float(10*np.log10(np.mean((r*r+i*i)[selected]))),
        "worst_db_selected": float(np.max(db[selected])),
    }


def main():
    result = {"audit_date": "2026-10-18", "python": sys.version,
              "versions": {}, "syntax": [], "s11": [], "zip": [], "svg": []}
    for name in ["numpy", "scipy", "matplotlib", "gerbonara", "pypdf", "PyMuPDF"]:
        try:
            result["versions"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["versions"][name] = None
    for p in sorted(ROOT.rglob("*.py")):
        if HERE not in p.parents:
            ast.parse(p.read_text(encoding="utf-8-sig"), filename=str(p))
            result["syntax"].append(p.relative_to(ROOT).as_posix())
    for name, band in [("diamant_uwb", None), ("diamant_uwb_x18", None),
                       ("vivaldi_tomographie", [1.4, 6.0])]:
        result["s11"].append(s11_stats(ROOT/"resultats"/name/"antenne_seule.s1p", band))
    for p in sorted((ROOT/"fabrication").rglob("*_pcbway.zip")):
        with zipfile.ZipFile(p) as z:
            row = {"path": p.relative_to(ROOT).as_posix(), "crc_error": z.testzip(), "members": []}
            for name in z.namelist():
                original = p.parent/name
                row["members"].append({"name": name, "size": len(z.read(name)),
                    "matches_neighbor": original.exists() and z.read(name) == original.read_bytes()})
            result["zip"].append(row)
    for p in sorted((ROOT/"fabrication").rglob("*_rendu.svg")):
        svg = ET.fromstring(p.read_bytes())
        result["svg"].append({"path": p.relative_to(ROOT).as_posix(),
                              "child_elements": len(list(svg)), "bytes": p.stat().st_size})
    before = json.loads((HERE/"inventaire_avant_audit_2026-10-18.json").read_text(encoding="utf-8"))
    previous = {row["path"]: row for row in before}
    current = {"simulation/"+p.relative_to(ROOT).as_posix(): p
               for p in ROOT.rglob("*") if p.is_file() and HERE not in p.parents}
    result["integrity"] = {
        "before_file_count": len(previous), "after_file_count": len(current),
        "removed": sorted(set(previous)-set(current)), "added_outside_review": sorted(set(current)-set(previous)),
        "content_changed": [name for name in previous.keys() & current.keys()
                            if hashlib.sha256(current[name].read_bytes()).hexdigest() != previous[name]["sha256"]],
        "mtime_changed": [name for name in previous.keys() & current.keys()
                          if current[name].stat().st_mtime_ns != previous[name]["mtime_ns"]],
    }
    out = HERE/"preuves_verifications_2026-10-18.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
