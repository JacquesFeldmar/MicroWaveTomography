"""
VERIFIE QUE LA DOCUMENTATION DECRIT LE CODE REEL.

A relancer apres toute modification du code ou des documents. Il ne juge pas le
fond -- il attrape la derive mecanique, celle qui s'installe sans qu'on la voie :
une option ajoutee et jamais documentee, un programme renomme et cite sous son
ancien nom, une constante changee d'un cote seulement.

    python verifier_doc.py            rapport complet
    python verifier_doc.py --bref     seulement les problemes

Code de retour : 0 si tout va bien, 1 sinon -- utilisable en pre-commit.
"""

import argparse
import io
import os
import re
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

PROGRAMMES = ["calibration.py", "radar.py", "qualification.py"]
BIBLIOTHEQUES = ["noyau.py"]
GUIDE = "GUIDE_UTILISATION.md"
LATEX = ["cours_theorie.tex", "annexe_phase1.tex", "guide_phase1.tex"]

# Options si generiques qu'on ne les documente pas une par une.
BANALES = {"--help", "--start", "--stop", "--points", "--nom", "--cal",
           "--compare", "--sans-graphe", "--autotest"}

_pb = []
_bref = False


def dire(txt=""):
    if not _bref:
        print(txt)


def probleme(txt):
    _pb.append(txt)
    print(f"  [!] {txt}")


def titre(t):
    dire("\n" + "=" * 74)
    dire(f"  {t}")
    dire("=" * 74)


# Les MODES, c est-a-dire ce qui declenche une action et doit donc figurer
# dans le tutoriel. Les reglages fins (--moy, --points...) en sont exclus.
MODES = {
    "calibration.py": ["--sol", "--verifier", "--plan", "--etat", "--rejouer"],
    "radar.py": ["--autotest", "--live", "--mesure", "--enregistre", "--rejeu"],
    "qualification.py": ["--ringing", "--centre-phase"],
}


def lire(nom):
    ch = os.path.join(ICI, nom)
    return io.open(ch, encoding="utf-8").read() if os.path.exists(ch) else None


def options_declarees(prog):
    """Options que le programme accepte reellement, lues dans son --help."""
    r = subprocess.run([PYTHON, os.path.join(ICI, prog), "--help"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        probleme(f"{prog} : --help echoue ({r.stderr.strip()[:80]})")
        return set()
    return set(re.findall(r"(--[a-z][a-z0-9-]*)", r.stdout))


def documentee(opt, texte):
    """Vrai si l'option est citee, y compris via une plage '--x-c0 ... --x-c3'."""
    if opt in texte:
        return True
    m = re.match(r"^(--.*?)(\d)$", opt)          # famille numerotee
    if m:
        base, n = m.group(1), int(m.group(2))
        chiffres = [int(x) for x in
                    re.findall(rf"{re.escape(base)}(\d)", texte)]
        if chiffres and min(chiffres) <= n <= max(chiffres):
            return True
    return False


# ======================================================================
def verifie_guide(guide):
    titre("1. GUIDE contre CODE -- les options")
    reelles = {p: options_declarees(p) for p in PROGRAMMES}

    for m in re.finditer(r"(calibration|radar|qualification)\.py"
                         r"((?:\s+--?[\w.\-]+|\s+[\d.]+)*)", guide):
        prog, suite = m.group(1) + ".py", m.group(2)
        for opt in re.findall(r"(--[a-z][a-z0-9-]*)", suite):
            if opt not in reelles[prog]:
                probleme(f"{prog} {opt} : cite dans le guide, n'existe pas")

    for p in PROGRAMMES:
        for opt in sorted(reelles[p] - BANALES):
            if not documentee(opt, guide):
                probleme(f"{p} {opt} : existe, non documentee")
    dire("   (options croisees dans les deux sens)")


def verifie_milieux(guide):
    titre("2. NOMS DE MILIEUX employes dans les commandes")
    sys.path.insert(0, ICI)
    import noyau
    cites = set(re.findall(r"--(?:milieu|substrat)\s+([a-z_]+)", guide))
    for nom in sorted(cites):
        if nom in noyau.MILIEUX:
            dire(f"   {nom:14s} connu")
        else:
            probleme(f"--milieu/--substrat {nom} : inconnu de noyau.MILIEUX")
    if not cites:
        dire("   aucun")


def verifie_fichiers(guide):
    titre("3. FICHIERS CITES et PROGRAMMES PRESENTS")
    for f in sorted(set(re.findall(r"`?([a-z_]+\.py)`?", guide))):
        if os.path.exists(os.path.join(ICI, f)):
            dire(f"   {f:26s} racine")
        elif os.path.exists(os.path.join(ICI, "archive", f)):
            probleme(f"{f} : cite par le guide mais ARCHIVE")
        else:
            probleme(f"{f} : cite par le guide, introuvable")

    for f in sorted(os.listdir(ICI)):
        if (f.endswith(".py") and not f.startswith("figures_")
                and f != os.path.basename(__file__) and f not in guide):
            probleme(f"{f} : present a la racine, absent du guide")


def verifie_latex():
    titre("4. DOCUMENTS LATEX -- programmes cites")
    archive = set(os.listdir(os.path.join(ICI, "archive"))) \
        if os.path.isdir(os.path.join(ICI, "archive")) else set()
    for doc in LATEX:
        s = lire(doc)
        if s is None:
            dire(f"   {doc} : absent")
            continue
        # \texttt{nom\_fichier.py} -- l'underscore y est echappe
        cites = set(x.replace("\\_", "_") for x in
                    re.findall(r"\\texttt\{([a-z\\_]+\.py)\}", s))
        if not cites:
            dire(f"   {doc:24s} aucun programme cite")
            continue
        for f in sorted(cites):
            if os.path.exists(os.path.join(ICI, f)):
                dire(f"   {doc:24s} {f:26s} OK")
            elif f in archive:
                probleme(f"{doc} cite {f}, qui est ARCHIVE")
            else:
                probleme(f"{doc} cite {f}, introuvable")


def verifie_constantes(guide):
    titre("5. CONSTANTES -- code contre guide")
    sys.path.insert(0, ICI)
    import noyau
    res = noyau.resolution_mm([noyau.BANDE_DEFAUT[0] * 1e9,
                               noyau.BANDE_DEFAUT[1] * 1e9])
    controles = [
        ("resolution", f"{res:.0f} mm", f"{res:.0f} mm" in guide),
        ("points par defaut", str(noyau.POINTS_DEFAUT),
         f"{noyau.POINTS_DEFAUT} points" in guide),
    ]
    for nom, val, ok in controles:
        if ok:
            dire(f"   {nom:22s} {val:10s} coherent")
        else:
            probleme(f"{nom} = {val} dans le code, introuvable dans le guide")
    dire(f"   {'plan d antenne':22s} {noyau.plan_antenne():.0f} mm"
         "   (mesure, non verifiable ici)")


def verifie_autotest():
    titre("6. AUTOTEST DU NOYAU")
    r = subprocess.run([PYTHON, os.path.join(ICI, "radar.py"), "--autotest"],
                       capture_output=True, text=True)
    if "REUSSI" in r.stdout:
        dire("   REUSSI")
    else:
        probleme("l'autotest du noyau ECHOUE -- le code est casse, "
                 "la documentation est le moindre souci")


# ======================================================================
def verifie_tutoriel():
    """Le tutoriel video montre-t-il les MODES des trois programmes ?

    Ce controle existe parce que six commandes -- --live, --sol, --verifier,
    --plan, --ringing et --centre-phase -- avaient disparu du tutoriel sans
    que rien ne le signale : le spectateur voyait l outil sans savoir le
    lancer. On ne verifie que les MODES, c est-a-dire ce qui ouvre une
    action ; les reglages fins n ont pas a figurer dans une video.
    """
    titre("7. TUTORIEL VIDEO -- les modes sont-ils montres")
    try:
        import tutoriel_contenu as tc
    except Exception as e:
        probleme("tutoriel_contenu illisible : " + str(e)[:80])
        return
    texte = []
    for seg in tc.SEGMENTS:
        texte.append(seg["titre"])
        for pl in seg["plans"]:
            for cle in ("titre", "sous", "texte", "n"):
                if cle in pl:
                    texte.append(str(pl[cle]))
            if pl["t"] == "tableau":
                texte += [str(x) for x in pl["entetes"]]
                texte += [str(x) for l in pl["lignes"] for x in l]
    blob = chr(10).join(texte)
    for prog, modes in MODES.items():
        reelles = options_declarees(prog)
        for m in modes:
            if m not in reelles:
                probleme(f"{prog} {m} : liste comme mode, n existe plus")
                continue
            etat = "montre" if m in blob else "ABSENT du tutoriel"
            dire(f"   {prog:<18} {m:<16} {etat}")
            if m not in blob:
                probleme(f"{prog} {m} : mode absent du tutoriel video")


def main():
    global _bref
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bref", action="store_true",
                    help="n'afficher que les problemes")
    _bref = ap.parse_args().bref

    guide = lire(GUIDE)
    if guide is None:
        print(f"  [!] {GUIDE} introuvable")
        sys.exit(1)

    verifie_guide(guide)
    verifie_milieux(guide)
    verifie_fichiers(guide)
    verifie_latex()
    verifie_constantes(guide)
    verifie_autotest()
    verifie_tutoriel()

    print("\n" + "=" * 74)
    if _pb:
        print(f"  {len(_pb)} PROBLEME(S)")
        for x in _pb:
            print(f"    - {x}")
    else:
        print("  TOUT EST COHERENT")
    print("=" * 74)
    sys.exit(1 if _pb else 0)


if __name__ == "__main__":
    main()
