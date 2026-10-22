"""Deux PDF strictement synthetiques dans TEMP ; jamais un bilan final reel."""
import os
os.environ["MPLBACKEND"] = "Agg"
for cle in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[cle] = "1"
import copy
from dataclasses import asdict
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[2]
BUILDER = SIM / "chatGPT_critical_review/construit_bilan_qualification_pcbway.py"
sys.path.insert(0, str(SIM))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    if (ICI / "qa_pdf.json").exists():
        raise FileExistsError("Une execution QA doit rester immuable")
    spec = importlib.util.spec_from_file_location("builder_pdf_fixture_qa", BUILDER)
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)
    import export_gerber as G
    import qualifie_pcbway as Q
    import livre_pcbway as L
    import numpy as np
    import matplotlib.pyplot as plt
    from pypdf import PdfReader
    import pdfplumber

    avant = json.loads((ICI / "avant.json").read_text(encoding="utf-8"))
    assert all(sha(SIM / n) == h for n, h in avant["sources_root_sha256"].items())
    temp = Path(tempfile.mkdtemp(prefix="mwt_qa_pdf_f1_f2_")).resolve()
    assert temp.parent == Path(tempfile.gettempdir()).resolve()
    natif = json.loads((SIM / "chatGPT_critical_review/integration_native_f2_2375/rapport_integration.json").read_text(encoding="utf-8"))
    sources9 = Q.F._sources()
    sources10 = {**sources9, "fdtd_maille_controlee.py": sha(SIM / "fdtd_maille_controlee.py")}
    controles = []

    def refuse(label, fonction):
        try:
            fonction()
        except (ValueError, FileNotFoundError):
            controles.append(dict(controle=label, reussi=True))
        else:
            raise AssertionError("Refus attendu : " + label)

    def fixture(moteur):
        base = temp / ("pcbway_controle_v2_SYNTHETIQUE" if moteur else "pcbway_r1_SYNTHETIQUE")
        base.mkdir()
        bilan = dict(schema="qualification_pcbway_r1", tous_reussis=True, antennes={})
        if moteur:
            bilan["moteur"] = moteur
            bilan["configuration_sha256"] = {"selection_qualification.json": "c" * 64}
        calculs, references = {}, {}
        f = np.linspace(1e9, 6.3e9, 213)
        for i, nom in enumerate(Q.ANTENNES):
            profils = (["base_8ns", "fin_8ns", "fin_12ns", "base_16ns", "fin_16ns"]
                       if moteur else ["base_8ns", "fin_8ns", "fin_12ns"])
            z = .28 + .07 * np.cos(2 * np.pi * f / 2.1e9 + i * .3)
            s = z * np.exp(-2j * np.pi * f * (.13e-9 + i * .02e-9))
            resultat = dict(indicateurs=Q.indicateurs(f, s),
                spatial=Q.ecarts(f, s, f, s + .008),
                temporel=Q.ecarts(f, s, f, s + .001, temporel=True),
                hypothese_plan=G.carte_antenne(nom)["simulation_contract"])
            if moteur:
                preliminaires = [
                    dict(type="spatial", calculs=["base_8ns", "fin_8ns"], motif="Fixture : essai spatial non retenu.", ecarts=Q.ecarts(f, s, f, s + .07)),
                    dict(type="temporel", calculs=["fin_8ns", "fin_12ns"], motif="Fixture : essai temporel non retenu.", ecarts=Q.ecarts(f, s, f, s + .02, temporel=True)),
                    dict(type="temporel", calculs=["base_8ns", "base_16ns"], motif="Fixture : diagnostic temporel conserve.", ecarts=Q.ecarts(f, s, f, s + .001, temporel=True)),
                ]
                resultat.update(selection_effective=dict(spatial=["base_16ns", "fin_16ns"],
                    temporel=["fin_12ns", "fin_16ns"], reference="fin_16ns", preliminaires=[]),
                    calculs_utilises=profils, essais_preliminaires=preliminaires)
            bilan["antennes"][nom] = resultat
            calculs[nom] = {}
            for profil in profils:
                niveau, duree = re.fullmatch(r"(base|fin)_([0-9]+)ns", profil).groups()
                duree = float(duree)
                montage = Q.montage_campagne(niveau, duree, moteur=moteur)
                dt = 1.5e-13 if niveau == "base" else 1e-13
                n = int(np.ceil(duree * 1e-9 / dt)) + 1
                m = dict(antenne=nom, etat="termine", montage=asdict(montage),
                    sources_sha256=sources10 if moteur else sources9,
                    maillage=dict(cellules=(3000000 if niveau == "base" else 7500000) * (i + 1)),
                    execution=dict(dt_s=dt, n_pas=n, duree_demandee_s=duree * 1e-9),
                    sondes=dict(port_ut_1=dict(debut_s=0., fin_s=n * dt)))
                if moteur:
                    m["moteur"] = moteur
                    m["politique_maillage"] = copy.deepcopy(next(v["politique"] for v in natif["cas_natifs"]
                        if v["antenne"] == nom and v["niveau"] == niveau))
                calculs[nom][profil] = m
            fig, axes = plt.subplots(3, 1, figsize=(8, 8), sharex=True)
            for j, profil in enumerate(profils):
                axes[0].plot(f / 1e9, 20 * np.log10(np.abs(s) + j * .003), label=profil)
            axes[0].set(ylabel="S11 synthetique (dB)")
            axes[0].legend(fontsize=7, ncol=2)
            impedance = 50 * (1 + s) / (1 - s)
            axes[1].plot(f / 1e9, impedance.real, label="R")
            axes[1].plot(f / 1e9, impedance.imag, label="X")
            axes[1].set(ylabel="Z synthetique (ohms)"); axes[1].legend()
            axes[2].plot(f / 1e9, np.unwrap(np.angle(s)) * 180 / np.pi)
            axes[2].set(xlabel="Frequence (GHz)", ylabel="Phase (degres)")
            for ax in axes: ax.grid(alpha=.3)
            fig.suptitle("FIXTURE SYNTHETIQUE - NON LIVRABLE\n" + nom, color="#ac2532")
            fig.tight_layout()
            figure = base / (nom + "_SYNTHETIQUE.png")
            fig.savefig(figure, dpi=120); plt.close(fig)
            reference = base / (nom + "_SYNTHETIQUE.s1p")
            Q.F.ecrit_s1p(reference, f, s, commentaire="FIXTURE SYNTHETIQUE NON LIVRABLE")
            references[nom] = dict(s1p=reference, figure=figure, sha256=sha(reference),
                profil="fin_16ns" if moteur else "fin_12ns")
        articles = [dict(numero=i, chemin=base / f"FIXTURE_SYNTHETIQUE_ARTICLE{i}.zip",
            sha256=hashlib.sha256(f"FIXTURE{i}".encode()).hexdigest(),
            dimensions_mm=[92.6, 72.] if i == 1 else [143.668735, 280.9031025],
            manifeste=dict(fabrication=dict(material_datasheet="https://www.pcbway.com/img/images/product/TDS-S1000H-S1000HB.pdf")))
            for i in (1, 2)]
        return dict(base=base, bilan=bilan, sha_bilan=hashlib.sha256(G.json_octets(bilan)).hexdigest(),
            calculs=calculs, references=references, articles=articles,
            creation=datetime.now(ZoneInfo("Europe/Paris")), qualification_verifiee=True,
            fixture_test=True)

    f1, f2 = fixture(None), fixture(B.MOTEUR_F2)
    assert B.moteur_rapport(f1) is None and B.moteur_rapport(f2) == B.MOTEUR_F2
    controles.append(dict(controle="F1 historique et F2 explicite acceptes", reussi=True))
    for tag in (None, "fdtd", "inconnu"):
        mauvais = copy.deepcopy(f2); mauvais["bilan"]["moteur"] = tag
        refuse("tag du bilan refuse : " + repr(tag), lambda d=mauvais: B.moteur_rapport(d))
    mauvais = copy.deepcopy(f2); mauvais["bilan"].pop("moteur")
    refuse("tags de calcul F2 sans tag global refuses", lambda: B.moteur_rapport(mauvais))
    for label, mutation in (
        ("sourceF2 absente", lambda m: m["sources_sha256"].pop("fdtd_maille_controlee.py")),
        ("catalogue incoherent", lambda m: m["montage"]["maillage"].update(maille_min=.25)),
        ("normales incoherentes", lambda m: m["politique_maillage"].update(cellules_normales=12)),
        ("PMLdifferent", lambda m: m["politique_maillage"]["pml8"]["x"]["gauche_mm"].__setitem__(0, -999.)),
    ):
        mauvais = copy.deepcopy(f2)
        mutation(mauvais["calculs"][Q.ANTENNES[0]]["base_8ns"])
        refuse(label, lambda d=mauvais: B.moteur_rapport(d))
    mauvais = copy.deepcopy(f2); mauvais["bilan"]["tous_reussis"] = False
    refuse("rendu refuse sans PASS global", lambda: B.construit_rapport(mauvais, temp / "NE_DOIT_PAS_EXISTER.pdf"))
    assert not (temp / "NE_DOIT_PAS_EXISTER.pdf").exists()
    with patch.object(L, "_verifie_qualification", side_effect=AssertionError("Ne pas revalider une campagne deja refusee")):
        refuse("charge_dossier absent refuse", lambda: B.charge_dossier(temp / "absent"))
        dossier_false = temp / "campagne_globale_false"; dossier_false.mkdir()
        (dossier_false / "qualification_globale.json").write_text(json.dumps(dict(
            schema="qualification_pcbway_r1", tous_reussis=False, antennes={})), encoding="utf-8")
        refuse("charge_dossier globalFalse refuse", lambda: B.charge_dossier(dossier_false))

    rendus = []
    for nom, dossier in (("F1", f1), ("F2", f2)):
        pdf = temp / f"FIXTURE_SYNTHETIQUE_{nom}_NON_LIVRABLE.pdf"
        resultat = B.construit_rapport(dossier, pdf)
        lecteur = PdfReader(pdf)
        pages_texte = [page.extract_text() for page in lecteur.pages]
        texte = re.sub(r"\s+", " ", " ".join(pages_texte))
        assert all("FIXTURE SYNTHÉTIQUE DE TEST - NON LIVRABLE" in t for t in pages_texte)
        if nom == "F1":
            assert "Les grilles sont reconstruites sans emboîtement" in texte
            assert "Le voisinage fin du port varie aussi" in texte
            assert "9 dossiers de calcul contrôlés" in texte
        else:
            assert "Les grilles sont reconstruites sans emboîtement" not in texte
            assert "Le voisinage fin du port varie aussi" not in texte
            for attendu in ("maillage_controle_v2", "15 dossiers de calcul contrôlés", "11 puis 17 cellules normales",
                            "4 puis 6 subdivisions", "soit dix sources", "0,15 mm", "0,10 mm"):
                assert attendu in texte, attendu
            assert "resultats/pcbway_r1/vivaldi" not in texte
        with pdfplumber.open(pdf) as analyse:
            for page in analyse.pages:
                for mot in page.extract_words():
                    assert mot["x0"] >= 0 and mot["x1"] <= page.width + .1
                    assert mot["top"] >= 0 and mot["bottom"] <= page.height + .1
        prefixe = temp / ("page_FIXTURE_" + nom)
        commande = ["pdftoppm", "-r", "90", "-png", str(pdf), str(prefixe)]
        rendu = subprocess.run(commande, capture_output=True)
        assert rendu.returncode == 0, rendu.stderr.decode(errors="replace")
        pngs = sorted(temp.glob(prefixe.name + "-*.png"))
        assert len(pngs) == len(lecteur.pages)
        rendus.append(dict(fixture=nom, resultat=resultat, pdf_sha256=sha(pdf),
            nombre_profils=sum(len(c) for c in dossier["calculs"].values()),
            rendu_toutes_pages=True, pages_png=[dict(chemin=str(p), sha256=sha(p)) for p in pngs],
            controle_texte_et_limites_page=True))
    apres = {n: sha(SIM / n) for n in avant["sources_root_sha256"]}
    assert apres == avant["sources_root_sha256"]
    bilan = dict(schema="qa_builder_pdf_F1_F2_synthetique_v1", reussi=True,
        script_sha256=sha(__file__), builder_sha256=sha(BUILDER),
        racine_TEMP=str(temp), aucun_Run=True, aucune_qualification_reelle=True,
        aucune_creation_pdf_final=True, controles=controles, rendus=rendus,
        inspection_visuelle_a_faire=True, sources_root_inchangees=True,
        sources_root_sha256=apres)
    with (ICI / "qa_pdf.json").open("x", encoding="utf-8") as f:
        json.dump(bilan, f, ensure_ascii=True, indent=2); f.write("\n")
    print(json.dumps(dict(reussi=True, controles=len(controles),
        rendus=[dict(fixture=r["fixture"], pages=r["resultat"]["pages"], profils=r["nombre_profils"]) for r in rendus],
        racine_TEMP=str(temp), rapport_sha256=sha(ICI / "qa_pdf.json")), indent=2), flush=True)


if __name__ == "__main__":
    main()
