"""QA native TEMP : six couts/constructions F2 et 25 archives F1, sans Run."""
import os
for cle in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[cle] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["MPLBACKEND"] = "Agg"
from contextlib import redirect_stdout
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from unittest.mock import patch
import zipfile

sys.dont_write_bytecode = True
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[1]
STAGE = SIM / "chatGPT_critical_review/staging_moteurs_f1_f2"
TAG = "maillage_controle_v2"
F2_SHA = "237510b3702694abb4336b895eb8394015265cfbc18d92e8c1cf86d2eb5b0f84"
ZIP_SHA = "a2d63d75a664b35289a13f3a46747469292b7c52fff1c8a8e3f5cb7461eb56b9"
CATALOGUE = {
    "base": dict(mailles_par_lambda=16, mailles_par_lambda_air=16, maille_min=.15),
    "fin": dict(mailles_par_lambda=24, mailles_par_lambda_air=16, maille_min=.1),
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main():
    sortie = ICI / "rapport_integration.json"
    if sortie.exists():
        raise FileExistsError(sortie)
    ancien = json.loads((STAGE / "avant.json").read_text(encoding="utf-8"))
    sources_avant = {n: sha(SIM / n) for n in ancien["sources_17_sha256"]}
    assert sources_avant == ancien["sources_17_sha256"]
    modifies = {p.name: sha(p) for p in sorted((STAGE / "modifies").glob("*.py"))}
    assert sha(ICI / "fdtd_maille_controlee_2375.py") == F2_SHA
    natif = json.loads((ICI / "preuve_native_f2_grilles_2375.json").read_text(encoding="utf-8"))
    assert natif["F2_sha256"] == F2_SHA
    archive = SIM / "archives/campagne_F1_cloture_2026-10-19.zip"
    assert sha(archive) == ZIP_SHA
    os.environ["CSXCAD_INSTALL_PATH"] = str(SIM.parent / "outils/openEMS")
    cas, archives, marqueurs, constructions = [], [], [], []
    with tempfile.TemporaryDirectory(prefix="mwt_integration_native_f2_") as nom_temp:
        temp = Path(nom_temp).resolve()
        assert temp.parent == Path(tempfile.gettempdir()).resolve()
        assert temp.name.startswith("mwt_integration_native_f2_")
        copie = temp / "simulation"
        copie.mkdir()
        for src in [*SIM.glob("*.py"), *(SIM / "antennes").rglob("*.py")]:
            if src.name == "fdtd_maille_controlee.py" or "__pycache__" in src.parts:
                continue
            dst = copie / src.relative_to(SIM)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        for src in (STAGE / "modifies").glob("*.py"):
            shutil.copy2(src, copie / src.name)
        shutil.copy2(ICI / "fdtd_maille_controlee_2375.py", copie / "fdtd_maille_controlee.py")
        assert all(sha(copie / n) == h for n, h in modifies.items())
        assert sha(copie / "fdtd_maille_controlee.py") == F2_SHA
        sys.path.insert(0, str(copie))
        import numpy as np
        import qualifie_pcbway as Q
        import qualification_adaptative as AP
        import fenetre_sondes as W
        import fdtd_maille_controlee as F2
        import raffine_qualification_plus_pcbway as PLUS
        import openEMS, CSXCAD, scipy, platform
        assert Path(Q.__file__).resolve().parent == copie
        assert Path(AP.__file__).resolve().parent == copie
        assert Path(W.__file__).resolve().parent == copie
        assert Q.module_moteur(TAG) is F2
        assert Q.niveaux_moteur(TAG) == F2.NIVEAUX == CATALOGUE
        assert Q.montage_campagne("base", 12.).maillage.mailles_par_lambda == 10
        assert Q.montage_campagne("fin", 12.).maillage.mailles_par_lambda == 14
        physique9 = Q.F._sources()
        sources10 = F2._sources()
        assert len(physique9) == 9 and len(sources10) == 10
        assert sources10 == {**physique9, "fdtd_maille_controlee.py": F2_SHA}
        assert all(sources_avant[n] == h for n, h in physique9.items())

        original_construit = F2.construit
        class SansRun:
            def __init__(self, natif): self.natif = natif
            def __getattr__(self, nom): return getattr(self.natif, nom)
            def Run(self, *args, **kw):
                raise AssertionError("Run interdit dans cette verification")

        def construit_controle(montage, antenne_mod, *args, **kw):
            fdtd, csx, port, chemin = original_construit(montage, antenne_mod, *args, **kw)
            axes = {a: np.asarray(csx.GetGrid().GetLines(a), dtype="<f8") for a in "xyz"}
            politique = F2.politique_maillage(montage, antenne_mod, csx)
            constructions.append(dict(antenne=antenne_mod.NOM, montage=asdict(montage),
                axes_sha256={a: hashlib.sha256(v.tobytes()).hexdigest() for a, v in axes.items()},
                resume=F2.resume_maillage(csx), politique=politique))
            return SansRun(fdtd), csx, port, chemin

        for nom in Q.ANTENNES:
            for niveau in ("base", "fin"):
                montage = Q.montage_campagne(niveau, 12., moteur=TAG)
                assert {k: getattr(montage.maillage, k) for k in CATALOGUE[niveau]} == CATALOGUE[niveau]
                out = io.StringIO()
                n0 = len(constructions)
                with patch.object(F2, "construit", side_effect=construit_controle), \
                     patch.object(F2, "lance", side_effect=AssertionError("lance interdit pour cout")), \
                     redirect_stdout(out):
                    Q.calcule(nom, niveau, 12., cout=True, base=temp / "jamais_cree", moteur=TAG)
                assert not (temp / "jamais_cree").exists()
                assert len(constructions) == n0 + 1
                courant = constructions[-1]
                reference = next(r for r in natif["resultats"] if r["antenne"] == nom and r["niveau"] == niveau)
                assert courant["axes_sha256"] == reference["axes_sha256_12ns"]
                assert canon(courant["politique"]) == canon(reference["politique"])
                cout = json.loads(out.getvalue())
                assert cout["cellules"] == courant["resume"]["cellules"]
                assert cout["pas_estimes"] > 0 and cout["minutes_indicatives"] > 0
                p = courant["politique"]
                assert p["nom"] == TAG and p["configuration"] == CATALOGUE[niveau]
                assert p["cellules_normales"] == (11 if niveau == "base" else 17)
                assert p["U_x0_primaire_exact"] is True and p["I_dual_hsur2_ecart_mm"] == 0.
                assert all(v["cellules_transversales"] == v["cellules_longitudinales"] == (4 if niveau == "base" else 6) for v in p["vias"])
                cas.append(dict(antenne=nom, niveau=niveau, montage=asdict(montage), cout=cout,
                    axes_sha256=courant["axes_sha256"], politique=p,
                    axes_et_politique_identiques_preuve_native=True))
                print("COUT_NATIF_OK", nom, niveau, cout["cellules"], flush=True)

                # Simulation du controleur seulement : aucune sortie native de solveur.
                etats = []
                def lance_simule(m, module, *, dossier, duree_ns, fils, verbose):
                    assert asdict(m) == asdict(montage) and module.NOM == nom
                    assert duree_ns == 12. and fils == 1
                    path = Path(dossier); path.mkdir(parents=True)
                    (path / "NON_QUALIFICATION_SYNTHETIQUE.txt").write_text("Fixture TEMP ; aucun Run ni sonde physique.\n", encoding="utf-8")
                    for etat in ("prepare", "termine"):
                        manifeste = dict(etat=etat, antenne=nom, montage=asdict(m),
                            sources_sha256=sources10, fixture_synthetique=True)
                        F2._sauve_manifeste(path, manifeste)
                        relu = json.loads((path / "simulation_manifest.json").read_text(encoding="utf-8"))
                        assert relu["moteur"] == TAG
                        etats.append(etat)
                    return np.linspace(1e9, 6.3e9, 213), np.full(213, .2 + 0j)
                base = temp / "marqueurs_synthetiques"
                with patch.object(F2, "lance", side_effect=lance_simule), redirect_stdout(io.StringIO()):
                    Q.calcule(nom, niveau, 12., fils=1, base=base, moteur=TAG)
                dossier = base / nom / f"{niveau}_12ns"
                m = json.loads((dossier / "simulation_manifest.json").read_text(encoding="utf-8"))
                q = json.loads((dossier / "qualification_entree.json").read_text(encoding="utf-8"))
                assert Q.identite_moteur(m, q) == TAG
                # Le lecteur de profils complets n'est jamais appele sur cette fixture.
                assert canon(asdict(montage)) == canon(q["montage"]) == canon(m["montage"])
                assert q["signature_physique"] == Q.signature(Q.G.carte_antenne(nom), montage)
                marqueurs.append(dict(antenne=nom, niveau=niveau, etats=etats,
                    m_moteur=m["moteur"], q_moteur=q["moteur"], montage_exact=True,
                    signature_physique=q["signature_physique"], fixture_sans_qualification=True))

        # Extraction uniquement vers la racine TEMP controlee, jamais vers le projet.
        extraction = temp / "archive_F1"
        extraction.mkdir()
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                rel = PurePosixPath(info.filename)
                assert not rel.is_absolute() and ".." not in rel.parts and "\\" not in info.filename
                dst = extraction.joinpath(*rel.parts).resolve()
                assert dst.is_relative_to(extraction)
                if info.is_dir():
                    dst.mkdir(parents=True, exist_ok=True)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(z.read(info))  # CRC verifie par zipfile.
        PLUS.enregistre(Q)  # Catalogue historique N34, en memoire uniquement.
        assert Q.NIVEAUX["n34"] == dict(mailles_par_lambda=34, mailles_par_lambda_air=22, maille_min=1./14.)
        assert Q.niveaux_moteur(TAG) == CATALOGUE
        profils = sorted((extraction / "simulation/resultats/pcbway_r1").glob("*/*/qualification_entree.json"))
        assert len(profils) == 25
        for fichier in profils:
            dossier = fichier.parent
            f, s, m, q = Q.charge_calcul(dossier, exiger_courant=True)
            niveau, duree = re.fullmatch(r"(.+)_([0-9]+(?:\.[0-9]+)?)ns", dossier.name).groups()
            Q.valide_campagne(m, q, dossier.parent.name, niveau, float(duree))
            assert Q.identite_moteur(m, q) == Q.MOTEUR_F1
            assert "moteur" not in m and "moteur" not in q
            assert m["sources_sha256"] == physique9
            archives.append(dict(antenne=dossier.parent.name, profil=dossier.name,
                etat=m["etat"], moteur=Q.MOTEUR_F1, points=len(f),
                signature_physique=q["signature_physique"],
                manifest_sha256=sha(dossier / "simulation_manifest.json"),
                qualification_sha256=sha(fichier),
                charge_courant_et_valide_campagne=True))
        print("F1_ARCHIVES_OK", len(archives), flush=True)
        versions = dict(python=platform.python_version(), executable=sys.executable,
            numpy=np.__version__, scipy=scipy.__version__, openEMS=openEMS.__version__, CSXCAD=CSXCAD.__version__)
    sources_apres = {n: sha(SIM / n) for n in sources_avant}
    assert sources_apres == sources_avant
    assert modifies == {p.name: sha(p) for p in sorted((STAGE / "modifies").glob("*.py"))}
    bilan = dict(schema="integration_native_F2_2375_v1", utc=datetime.now(timezone.utc).isoformat(),
        reussi=True, aucun_Run=True, aucune_calibration=True, aucun_patch_applique=True,
        nature="QA routage/construction/cout et archives ; aucune qualification electromagnetique F2",
        F2_sha256=F2_SHA, sources10_sha256=sources10, modifies_sha256=modifies,
        sources_17_avant=sources_avant, sources_17_apres=sources_apres,
        catalogue_F2=CATALOGUE, cas_natifs=cas, marqueurs_synthetiques=marqueurs,
        archive_F1=dict(chemin="simulation/archives/campagne_F1_cloture_2026-10-19.zip", sha256=ZIP_SHA,
            profils_lus=archives, nombre_profils=25, catalogue_N34_via_PLUS_en_memoire=True),
        preuve_native_fdtd_sha256=sha(ICI / "preuve_native_f2_grilles_2375.json"),
        script_sha256=sha(__file__), versions=versions,
        limites=["La version2375 est ancree pour cette QA ; une garde de sondes avant CalcPort peut evoluer separement.",
            "Aucun dt operateur ni S11 F2 physique mesure ; les marqueurs sont des fixtures TEMP clairement identifiees.",
            "Q.charge_calcul et Q.valide_campagne ne sont appeles que sur les25 vrais profils F1 clos."])
    with sortie.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(bilan, f, ensure_ascii=True, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps(dict(reussi=True, cas_natifs=len(cas), profils_F1=len(archives),
        sources17_inchangees=True, rapport_sha256=sha(sortie)), indent=2), flush=True)


if __name__ == "__main__":
    main()
