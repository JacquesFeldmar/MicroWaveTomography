"""Acquisition et lecture communes aux traitements A et B du banc plexiglas."""
import argparse
from pathlib import Path
import sys

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
PROJET = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
from commun import sol
import litevna


def charger(chemin):
    with np.load(chemin, allow_pickle=False) as z:
        return {k: z[k].copy() for k in z.files}


def arguments(description):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--mesure", type=Path, help="Retraiter un cible.npz sans contacter le VNA")
    ap.add_argument("--port")
    ap.add_argument("--debut-ghz", "--start-ghz", dest="debut_ghz", type=float)
    ap.add_argument("--fin-ghz", "--stop-ghz", dest="fin_ghz", type=float)
    ap.add_argument("--points", type=int)
    ap.add_argument("--delta-mhz", type=float)
    ap.add_argument("--nombre", type=int, default=20)
    ap.add_argument("--fond", type=Path)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--sol", type=Path)
    mode.add_argument("--interne", action="store_true")
    ap.add_argument("--sortie", type=Path, default=PROJET)
    return ap


def meme_grille(a, b):
    return np.shape(a) == np.shape(b) and np.allclose(a, b, rtol=1e-9, atol=1e-3)


def obtenir_mesure(args):
    if args.mesure:
        if any(x is not None for x in (args.port, args.debut_ghz, args.fin_ghz,
                                      args.points, args.delta_mhz, args.sol)) or args.interne:
            raise ValueError("Avec --mesure, ne pas fournir les réglages d'acquisition/SOL.")
        chemin = args.mesure.resolve()
        data = charger(chemin)
        for k in ("freqs", "residu"):
            if k not in data:
                raise ValueError(f"La mesure ne contient pas {k}.")
        return chemin, data
    if (args.debut_ghz is None or args.fin_ghz is None or args.fond is None
            or (args.sol is None and not args.interne)):
        raise ValueError("Acquisition : --start-ghz, --stop-ghz, --fond et --sol (ou --interne) requis.")
    debut, fin, points, delta = litevna.parametres_sweep(
        args.debut_ghz, args.fin_ghz, args.points, args.delta_mhz)
    litevna.verifier_spec(debut, fin, points, args.nombre)
    ref = charger(args.fond)
    f = litevna.frequences(debut, fin, points)
    if not meme_grille(ref.get("freqs", []), f):
        raise ValueError("La grille cible ne correspond pas au fond.")
    fond = np.asarray(ref["fond"], complex)
    if fond.shape != f.shape or not np.all(np.isfinite(fond)):
        raise ValueError("Fond invalide.")
    mode = "interne" if args.interne else "brut"
    if str(ref.get("correction_mode", "interne")) != mode:
        raise ValueError("Le fond et la cible doivent utiliser la même correction.")
    cal = None if args.interne else charger(args.sol)
    if cal is not None:
        if not meme_grille(cal["freqs"], f):
            raise ValueError("La grille de mesure ne correspond pas à la calibration SOL.")
        for k in ("freqs", "e00", "e11", "e10e01"):
            if "sol_" + k not in ref or np.shape(ref["sol_" + k]) != np.shape(cal[k]) or not np.allclose(
                    ref["sol_" + k], cal[k], rtol=1e-9, atol=1e-12):
                raise ValueError("La SOL de la cible diffère de celle du fond ou n'est pas documentée.")
    print("Avec cible : ne pas déplacer antenne, câbles ou support.")
    print(f"START={debut:g} GHz, STOP={fin:g} GHz, Δf={delta/1e6:g} MHz, {points} points.")
    s, temps, paquets, identite, port = litevna.acquisition(
        args.port, debut, fin, points, args.nombre, mode, delta_hz=delta)
    brut = s.copy() if cal is not None else None
    if cal is not None:
        s = sol.applique(cal, f, s)
    cible = s.mean(axis=0)
    data = dict(freqs=f, sweeps_calibres=s, cible=cible, fond=fond, residu=cible-fond,
                temps=temps, simulation=False, correction_mode=mode, port=port,
                fichier_fond=str(args.fond.resolve()),
                **{"usb_" + k: v for k, v in identite.items()})
    if brut is not None:
        data.update(sweeps_bruts=brut, fichier_sol=str(args.sol.resolve()))
        data.update({"sol_"+k: cal[k] for k in ("freqs", "e00", "e11", "e10e01")})
    if "sigma_complexe" in ref and "sweeps_calibres" in ref:
        data["variance_moyenne_fond"] = ref["sigma_complexe"]**2 / len(ref["sweeps_calibres"])
    dossier = args.sortie.resolve() / "mesures" / litevna.nom_utc("cible_")
    dossier.mkdir(parents=True, exist_ok=False)
    chemin = dossier / "cible.npz"
    # Sauvegarder l'acquisition avant tout traitement susceptible d'échouer.
    np.savez_compressed(chemin, **data, paquets_usb=paquets)
    np.savetxt(dossier / "s11_soustrait.csv",
               np.column_stack((f, cible.real, cible.imag, fond.real, fond.imag,
                                (cible-fond).real, (cible-fond).imag,
                                20*np.log10(np.maximum(abs(cible-fond), 1e-15)))),
               delimiter=",", comments="",
               header="frequence_hz,cible_reel,cible_imag,fond_reel,fond_imag,residu_reel,residu_imag,residu_db")
    print(f"Mesure cible enregistrée : {chemin}")
    return chemin, data


def variance_moyenne(data, fond_explicite=None):
    """Var(mean(cible)-mean(fond)), sweeps indépendants ; None si inconnue."""
    s = data.get("sweeps_calibres")
    if s is None or s.ndim != 2 or len(s) < 2:
        return None
    vf = data.get("variance_moyenne_fond")
    if vf is None or fond_explicite is not None:
        chemin = fond_explicite or str(data.get("fichier_fond", ""))
        if not chemin or not Path(chemin).is_file():
            return None
        ref = charger(chemin)
        if not meme_grille(ref["freqs"], data["freqs"]) or not np.allclose(
                ref["fond"], data["fond"], rtol=1e-9, atol=1e-12):
            raise ValueError("Le fond utilisé pour le bruit ne correspond pas à la mesure.")
        sf = ref.get("sweeps_calibres")
        if sf is None or len(sf) < 2:
            return None
        vf = sf.var(axis=0, ddof=1) / len(sf)
    v = s.var(axis=0, ddof=1) / len(s) + vf
    if v.shape != data["freqs"].shape or not np.all(np.isfinite(v)) or np.any(v <= 0):
        return None
    return v


def chemins_resultats(sortie, mesure, suffixe):
    nom = mesure.parent.name if mesure.name == "cible.npz" else mesure.stem
    dossier = sortie.resolve() / "analyses" / (nom + "_" + suffixe)
    dossier.mkdir(parents=True, exist_ok=True)
    figures = sortie.resolve() / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    return dossier, figures / (nom + "_" + suffixe + ".png")
