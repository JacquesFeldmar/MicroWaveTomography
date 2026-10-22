"""Construit le PDF de la reponse a l'audit, depuis sa source Markdown.

    python construit_reponse_pdf.py

Ne touche a rien d'autre : lit `reponse_audit_claude_2026-10-18.md` et ecrit
`reponse_audit_claude_2026-10-18.pdf` a cote. Demande pandoc et xelatex.
"""
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

ICI = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(ICI, "reponse_audit_claude_2026-10-18.md")
SORTIE = os.path.join(ICI, "reponse_audit_claude_2026-10-18.pdf")

# Polices Windows a bonne couverture (grec, maths, tirets, guillemets).
# La premiere disponible gagne ; sinon on laisse pandoc choisir.
FAMILLES = [
    ("Cambria", "Calibri", "Consolas"),
    ("Georgia", "Verdana", "Consolas"),
    ("Times New Roman", "Arial", "Courier New"),
]

ENTETE = r"""
\usepackage{booktabs}
\usepackage{longtable}
\let\oldlongtable\longtable
\def\longtable{\small\oldlongtable}
\usepackage{microtype}
\setlength{\emergencystretch}{3em}
\usepackage{xcolor}
\definecolor{lien}{RGB}{0,70,140}
\hypersetup{colorlinks=true,linkcolor=lien,urlcolor=lien,citecolor=lien}
"""


def construit():
    if not shutil.which("pandoc"):
        raise SystemExit("pandoc est introuvable dans le PATH.")
    if not shutil.which("xelatex"):
        raise SystemExit("xelatex est introuvable dans le PATH.")

    entete = os.path.join(ICI, "_entete_reponse.tex")
    with open(entete, "w", encoding="utf-8") as f:
        f.write(ENTETE)

    base = [
        "pandoc", SOURCE, "-o", SORTIE,
        "--pdf-engine=xelatex",
        "--from=markdown+pipe_tables+tex_math_dollars+smart",
        "--toc", "--toc-depth=2",
        "-V", "geometry:margin=2.2cm",
        "-V", "fontsize=10pt",
        "-V", "linkcolor=blue",
        "-V", "colorlinks=true",
        "-V", "lang=fr",
        "-H", entete,
    ]

    erreurs = []
    try:
        for principale, sans, mono in FAMILLES + [(None, None, None)]:
            cmd = list(base)
            if principale:
                cmd += ["-V", f"mainfont={principale}",
                        "-V", f"sansfont={sans}",
                        "-V", f"monofont={mono}"]
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", cwd=ICI)
            if r.returncode == 0:
                quoi = principale or "polices par defaut de pandoc"
                print(f"  OK  {os.path.basename(SORTIE)}  ({quoi})")
                return 0
            erreurs.append((principale or "defaut",
                            (r.stderr or r.stdout or "").strip()[-700:]))
    finally:
        if os.path.exists(entete):
            os.remove(entete)

    print("  ECHEC de toutes les tentatives :")
    for quoi, msg in erreurs:
        print(f"\n  --- {quoi} ---\n{msg}")
    return 1


if __name__ == "__main__":
    raise SystemExit(construit())
