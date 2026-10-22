"""Ce qu'on s'apprete a deposer est-il bien ce qui a ete simule ?

    python verifie_coherence_livraison.py --campagne resultats/pcbway_maille_controlee_v2

C'est la seule question que ni `verifie_gerber.py` ni la qualification ne
posent. Le premier compare un ZIP a la geometrie Python COURANTE ; la seconde
qualifie des profils calcules a une date donnee. Entre les deux, rien ne
garantit que la geometrie courante soit celle qui a ete simulee -- il suffit
d'avoir retouche un `geometrie.py` apres la campagne pour que les deux
controles passent separement en decrivant deux cartes differentes.

Cinq maillons, et il faut les cinq :

    1. le ZIP vaut son empreinte, et celle de son fichier `.sha256` voisin,
       et celle inscrite dans l'inventaire de livraison ;
    2. le manifeste inscrit DANS le ZIP porte la meme empreinte de geometrie
       que l'inventaire ;
    3. les sources citees par ce manifeste sont, aujourd'hui, celles de
       l'arbre de travail ;
    4. les sources GELEES avec la campagne sont, elles aussi, celles de
       l'arbre de travail ;
    5. les deux fichiers de qualification s'accordent sur l'empreinte de
       geometrie de chaque antenne.

Les maillons 3 et 4 se rejoignent sur l'arbre courant : c'est par la que la
chaine se ferme. Si les deux y concordent, alors la geometrie simulee et la
geometrie exportee sont la meme, sans avoir a comparer deux empreintes qui ne
decrivent pas le meme objet -- un panneau n'a pas l'empreinte des antennes
qu'il porte.

Lecture seule. Aucun fichier n'est ecrit sans `--rapport`.
"""
import argparse
import hashlib
import json
import os
import sys
import zipfile

ICI = os.path.dirname(os.path.abspath(__file__))


def sha256_octets(donnees):
    return hashlib.sha256(donnees).hexdigest()


def sha256_fichier(chemin):
    with open(chemin, "rb") as f:
        return sha256_octets(f.read())


def _manifeste(chemin_zip):
    with zipfile.ZipFile(chemin_zip) as z:
        noms = [n for n in z.namelist() if n.endswith("_manifest.json")]
        if len(noms) != 1:
            raise ValueError(f"{os.path.basename(chemin_zip)} : "
                             f"{len(noms)} manifeste(s), il en faut un")
        return json.loads(z.read(noms[0]).decode("utf-8"))


def controle(campagne, racine=None):
    """Rend (liste de (ok, maillon, detail), tout_bon).

    `racine` est resolue a l'APPEL et non a la definition : une valeur par
    defaut figee rendrait la fonction intestable, puisque les tests doivent
    pouvoir la faire porter sur une arborescence temoin.
    """
    racine = racine or ICI
    constats = []

    def note(ok, maillon, detail=""):
        constats.append((bool(ok), maillon, detail))
        return bool(ok)

    inventaire = os.path.join(racine, "fabrication",
                              "inventaire_livraison_courante.json")
    with open(inventaire, encoding="utf-8") as f:
        inv = json.load(f)

    for article in inv["articles"]:
        nom = article["produit"]
        base = os.path.join(racine, "fabrication", nom)
        chemin_zip = os.path.join(base, f"{nom}_pcbway.zip")

        # 1 -- le ZIP vaut son empreinte, partout ou elle est inscrite
        calcule = sha256_fichier(chemin_zip)
        with open(chemin_zip + ".sha256", encoding="ascii") as f:
            voisin = f.read().split()[0]
        note(calcule == voisin == article["zip_sha256"],
             f"1. empreinte du ZIP {nom}",
             calcule if calcule == voisin == article["zip_sha256"]
             else f"calculee {calcule}, voisine {voisin}, "
                  f"inventaire {article['zip_sha256']}")

        manif = _manifeste(chemin_zip)

        # 2 -- le manifeste interne porte la meme geometrie que l'inventaire
        note(manif.get("geometrie_sha256") == article["geometrie_sha256"],
             f"2. geometrie du manifeste {nom}",
             str(manif.get("geometrie_sha256")))

        # 3 -- les sources citees par le manifeste sont celles d'aujourd'hui
        derive = []
        for rel, attendu in sorted(manif.get("sources_sha256", {}).items()):
            chemin = os.path.join(racine, rel.replace("/", os.sep))
            if not os.path.isfile(chemin):
                derive.append(f"{rel} absent")
            elif sha256_fichier(chemin) != attendu:
                derive.append(f"{rel} modifie")
        note(not derive, f"3. sources du manifeste {nom}",
             f"{len(manif.get('sources_sha256', {}))} sources"
             if not derive else "; ".join(derive))

    # 4 -- les sources gelees avec la campagne valent celles d'aujourd'hui
    gelees = os.path.join(campagne, "controle_orchestration", "sources")
    derive, nombre = [], 0
    for dossier, _, fichiers in os.walk(gelees):
        for fichier in fichiers:
            chemin = os.path.join(dossier, fichier)
            rel = os.path.relpath(chemin, gelees)
            nombre += 1
            courant = os.path.join(racine, rel)
            if not os.path.isfile(courant):
                derive.append(f"{rel} absent de l'arbre")
            elif sha256_fichier(courant) != sha256_fichier(chemin):
                derive.append(f"{rel} modifie depuis la campagne")
    note(nombre > 0 and not derive, "4. sources gelees de la campagne",
         f"{nombre} sources identiques a l'arbre courant"
         if not derive else "; ".join(derive))

    # 5 -- les deux qualifications s'accordent sur chaque antenne
    chemins = {
        "ponctuelle": os.path.join(campagne, "qualification_globale.json"),
        "grandeurs": os.path.join(campagne,
                                  "qualification_grandeurs_decision.json"),
    }
    if all(os.path.isfile(c) for c in chemins.values()):
        with open(chemins["ponctuelle"], encoding="utf-8") as f:
            ponctuelle = json.load(f)
        with open(chemins["grandeurs"], encoding="utf-8") as f:
            grandeurs = json.load(f)
        desaccords = [
            antenne for antenne, bilan in grandeurs["antennes"].items()
            if bilan.get("geometrie_sha256")
            != ponctuelle["antennes"].get(antenne, {}).get("geometrie_sha256")]
        note(not desaccords, "5. accord des deux qualifications",
             f"{len(grandeurs['antennes'])} antennes"
             if not desaccords else "desaccord : " + ", ".join(desaccords))
        note(grandeurs["qualification_ponctuelle_conservee"]["sha256"]
             == sha256_fichier(chemins["ponctuelle"]),
             "5b. verdict ponctuel cite sans alteration")
    else:
        note(False, "5. accord des deux qualifications",
             "un fichier de qualification manque")

    return constats, all(ok for ok, _, _ in constats)


def principal():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--campagne", required=True)
    p.add_argument("--rapport", default=None)
    p.add_argument("--racine", default=None,
                   help="arbre de travail a confronter ; par defaut celui de "
                        "ce fichier")
    args = p.parse_args()

    constats, tout_bon = controle(args.campagne, racine=args.racine)
    print()
    for ok, maillon, detail in constats:
        print(f"  {'OK ' if ok else '!! '} {maillon:46s} {detail}")
    print("\n  " + ("LA CHAINE EST FERMEE : ce qui part est ce qui a ete "
                    "simule" if tout_bon
                    else "CHAINE ROMPUE : ne pas deposer en l'etat"))
    if args.rapport:
        with open(args.rapport, "w", encoding="utf-8") as f:
            json.dump({"tout_bon": tout_bon,
                       "constats": [{"reussi": o, "maillon": m,
                                     "detail": d} for o, m, d in constats]},
                      f, indent=2, ensure_ascii=False)
        print("  rapport : " + args.rapport)
    return 0 if tout_bon else 2


if __name__ == "__main__":
    sys.exit(principal())
