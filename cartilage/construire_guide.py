"""
CONSTRUIT docs/GUIDE_UTILISATION.pdf A PARTIR DE GUIDE_UTILISATION.md

    python construire_guide.py                     genere, controle, remplace
    python construire_guide.py --controle F.pdf    juge un PDF existant

Deux etapes : pandoc ecrit une page HTML AUTONOME -- feuille de style et images
integrees (--self-contained) --, puis Chrome sans interface l'imprime en PDF.

Le titre du PDF est la premiere ligne du guide ("# ..."). Elle est retiree du
corps avant la conversion : sinon le titre apparait deux fois et coiffe toute
la table des matieres.

POURQUOI AUTONOME
    Le 21/08/2026, la page intermediaire a ete ecrite dans un dossier
    temporaire. Ses liens relatifs vers guide_style.css et docs/ecrans/ n'y
    menaient plus nulle part, et Chrome a imprime sans un mot un guide en Times
    New Roman, aux copies d'ecran remplacees par des icones cassees. Il a ete
    livre ainsi.

POURQUOI LE CONTROLE
    Pour que cela ne puisse plus passer inapercu. Le PDF doit employer une
    police de la feuille de style et contenir chaque image citee par le guide.
    Sinon : code de retour 1, et le PDF livre n'est PAS remplace.

Il faut pandoc, Google Chrome, et les copies d'ecran citees dans docs/ecrans/.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
GUIDE = ICI / "GUIDE_UTILISATION.md"
STYLE = ICI / "guide_style.css"
SORTIE = ICI / "docs" / "GUIDE_UTILISATION.pdf"

CHROMES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

# En deca, c'est l'icone d'une image cassee (14 x 16 px), pas une copie d'ecran.
TAILLE_MIN_PX = 64


def echec(msg):
    print(f"  ECHEC : {msg}")
    sys.exit(1)


def titre_et_corps():
    """Rend (titre, guide sans sa premiere ligne '# Titre')."""
    texte = GUIDE.read_text(encoding="utf-8")
    m = re.match(r"\ufeff?#[ \t]+(.+?)[ \t]*\r?\n", texte)
    if not m:
        echec("GUIDE_UTILISATION.md doit commencer par une ligne '# Titre'")
    return m.group(1), texte[m.end():]


def images_citees():
    texte = GUIDE.read_text(encoding="utf-8")
    return re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", texte)


def polices_du_style():
    """Familles de la regle body, dans l'ordre : Segoe UI, Helvetica..."""
    css = STYLE.read_text(encoding="utf-8")
    m = re.search(r"body\s*\{[^}]*?font-family:\s*([^;]+);", css)
    if not m:
        echec("aucune font-family dans la regle body de guide_style.css")
    familles = [f.strip().strip("\"'") for f in m.group(1).split(",")]
    return [f for f in familles if f not in ("serif", "sans-serif", "monospace")]


def analyse_pdf(chemin):
    """Rend (nombre de pages, noms des polices, tailles des images)."""
    from pypdf import PdfReader
    r = PdfReader(str(chemin))
    polices, tailles = set(), []
    for page in r.pages:
        res = page.get("/Resources")
        fontes = res.get_object().get("/Font") if res is not None else None
        if fontes is not None:
            for f in fontes.get_object().values():
                nom = str(f.get_object().get("/BaseFont", ""))
                if nom:                     # les polices Type 3 n'en ont pas
                    polices.add(nom.lstrip("/").split("+")[-1])
        for im in page.images:
            tailles.append(im.image.size)
    return len(r.pages), polices, tailles


def controle(chemin):
    """Vrai si le PDF porte la feuille de style et toutes les images citees."""
    chemin = Path(chemin)
    if not chemin.is_file():
        echec(f"{chemin} introuvable")
    pages, polices, tailles = analyse_pdf(chemin)
    voulues = [v.replace(" ", "").lower() for v in polices_du_style()]
    du_style = sorted(p for p in polices
                      if any(p.lower().startswith(v) for v in voulues))
    vraies = [t for t in tailles if min(t) >= TAILLE_MIN_PX]
    icones = len(tailles) - len(vraies)
    attendues = len(images_citees())

    print(f"  {chemin.name} : {pages} pages")
    print(f"  polices : {', '.join(sorted(polices))}")
    ok = True
    if du_style:
        print(f"  style   : OK ({du_style[0]})")
    else:
        print(f"  style   : ABSENT -- aucune police de guide_style.css "
              f"({', '.join(polices_du_style())}) : la feuille n'a pas ete appliquee")
        ok = False
    if len(vraies) >= attendues:
        print(f"  images  : OK ({len(vraies)} pour {attendues} citees)")
    else:
        print(f"  images  : {len(vraies)} sur {attendues} citees"
              + (f", et {icones} icone(s) d'image cassee" if icones else ""))
        ok = False
    return ok


def trouve_chrome():
    for ch in [shutil.which("chrome")] + CHROMES:
        if ch and os.path.isfile(ch):
            return ch
    echec("Google Chrome introuvable -- c'est lui qui imprime la page en PDF")


def genere():
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        echec("pandoc introuvable")
    manquantes = [i for i in images_citees() if not (ICI / i).is_file()]
    if manquantes:
        print("  Copies d'ecran citees par le guide mais absentes :")
        for i in manquantes:
            print(f"      {i}")
        echec("les remettre dans docs/ecrans/ avant de generer")
    chrome = trouve_chrome()
    titre, corps = titre_et_corps()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        html, pdf = tmp / "guide.html", tmp / "guide.pdf"

        print("  1/3  pandoc : page HTML autonome")
        # Le corps arrive par l'entree standard ; cwd=ICI pour que les images
        # docs/ecrans/... soient trouvees et integrees.
        r = subprocess.run([pandoc, "-f", "markdown", "-s", "--toc",
                            "--toc-depth=2", "--self-contained",
                            "-c", STYLE.name, "--metadata", f"title={titre}",
                            "-o", str(html)],
                           input=corps, cwd=ICI, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0 or "Could not fetch" in r.stderr:
            echec("pandoc :" + chr(10) + r.stderr[-1500:])

        print("  2/3  Chrome : impression en PDF")
        try:
            subprocess.run([chrome, "--headless", "--disable-gpu",
                            "--no-pdf-header-footer",
                            f"--user-data-dir={tmp / 'profil'}",
                            f"--print-to-pdf={pdf}", html.as_uri()],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=180)
        except subprocess.TimeoutExpired:
            echec("Chrome n'a pas termine en trois minutes")
        if not pdf.is_file() or pdf.stat().st_size == 0:
            echec("Chrome n'a produit aucun PDF")

        print("  3/3  controle")
        if not controle(pdf):
            echec(f"{SORTIE.name} n'est PAS remplace")
        shutil.copyfile(pdf, SORTIE)
    print(f"  Ecrit : {SORTIE.relative_to(ICI)}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--controle", metavar="PDF",
                    help="juger un PDF existant, sans rien generer")
    a = ap.parse_args()
    if a.controle:
        sys.exit(0 if controle(a.controle) else 1)
    genere()


if __name__ == "__main__":
    main()
