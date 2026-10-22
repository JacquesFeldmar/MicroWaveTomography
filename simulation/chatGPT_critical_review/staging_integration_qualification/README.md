# Intégration finale de la qualification — préparation isolée

Le correctif `integration_qualification.patch` vise uniquement
`simulation/qualifie_pcbway.py`. **Il n'est pas appliqué au projet.** Les sources
et résultats réels de la campagne restent gelés jusqu'à la fin des deux files
de calcul et la levée du gel par le coordinateur.

L'original requis a pour SHA-256 :

```text
2e6b6f7f07b8903acfa6a51eb40bab6f3961dd1af1a95e7b76d9661f0af70ac4
```

Le correctif prépare trois raccordements :

1. Après la définition de `NIVEAUX`, `R.enregistre(Q)` ajoute les copies des
   niveaux complémentaires `ultra_fin` et `extreme_fin`. Les trois définitions
   existantes et tous les seuils numériques sont conservés.
2. `comparer(base, ecrire=True)` délègue à
   `qualification_adaptative.comparer(base, ecrire=ecrire)` si le fichier
   `selection_qualification.json` existe dans cette base. L'import est tardif.
   Une sélection invalide provoque une erreur ; elle ne déclenche aucun retour
   silencieux au protocole initial. Sans sélection, le corps initial est
   conservé intégralement.
3. La CLI est extraite dans `main(argv=None)`. Ses options, valeurs par défaut,
   appels de calcul et codes de retour de comparaison restent identiques.

## Une seule instance du contrôleur

Un script exécuté directement s'appelle `__main__`. Si ce script importe AP,
qui importe `qualifie_pcbway`, Python peut charger deux contrôleurs distincts.
Enregistrer les niveaux dans `sys.modules[__name__]` ne résout pas cette double
instance à lui seul.

L'entrée CLI proposée délègue donc immédiatement au `main` du module canonique
`qualifie_pcbway`, avant les imports locaux et définitions du contrôleur. Ce
module est le même que celui importé par AP et L. La lecture de
`sys.modules[__name__]` sert uniquement à transmettre ce module à
`R.enregistre` ; aucune entrée de `sys.modules` n'est réaffectée. R n'importe
pas Q au niveau module, et Q n'importe AP que dans la branche de comparaison
avec sélection : le cycle d'import est évité.

Un simple import ne déclenche ni comparaison, ni calcul, ni création de
résultats. Le catalogue complémentaire est enregistré dans le processus
appelant, comme prévu par le contrat de R.

Le drapeau historique `sys.dont_write_bytecode = True` est placé **avant**
cette délégation. Ainsi, l'auto-import canonique ne crée pas de cache Python
même si l'utilisateur reprend l'exemple de la docstring sans option `-B`.

## Vérification sur copie

Depuis la racine du projet :

```powershell
& 'C:\Users\jfeld\anaconda3\envs\ph\python.exe' -B -X utf8 simulation/chatGPT_critical_review/staging_integration_qualification/verifie_integration_isolee.py
```

Le runner vérifie le SHA original, crée une copie temporaire des modules,
applique le changement uniquement à cette copie et y exécute :

- Les suites existantes `test_qualification_pcbway`,
  `test_qualification_adaptative` et `test_raffine_qualification_pcbway` dans
  l'environnement openems, avec les vrais CSXCAD/CalcPort et sans `Run`.
- Les tests d'intégration ciblés : identité `AP.Q is Q` et `L.Q is Q`, catalogue,
  options et défauts, absence de résultats à l'import, routage avec/sans
  sélection, erreurs de sélection propagées, vrais sous-processus CLI
  `--help` et `--comparer` sur trois jeux d'archives synthétiques complets.
- La suite existante de livraison `test_livre_pcbway.py` dans l'environnement
  ph, où pytest est disponible.

Le cas CLI avec sélection utilise un fichier valide dans la base temporaire,
sans prolongement physique supposé. La suite AP vérifie séparément les essais
préliminaires échoués conservés et les paires prolongées sur sondes synthétiques.
Une sonde en sous-processus vérifie aussi l'unicité du contrôleur lorsque AP
était déjà importé avant l'exécution du chemin CLI.

Les threads OMP/OpenBLAS/MKL/NumExpr sont limités à un. L'installation native
`outils/openEMS` est désignée explicitement pour les DLL : elle reste une
dépendance en lecture seule, hors de la copie. Aucun programme matériel ni
solveur FDTD n'est exécuté. Aucune sélection n'est créée dans la campagne
réelle. `verification.json` et les journaux stdout/stderr contiennent les
résultats et empreintes de la vérification.

La passe complète consignée dans `verification.json` a réussi : **54 tests
Q/AP/R/intégration et 34 tests L**. Son patch est conservé sous
`integration_qualification_avant_controle_cache.patch`. La revue du point
d'entrée a ensuite déplacé le seul drapeau `dont_write_bytecode` avant la
délégation ; le raccordement et les seuils numériques restent identiques.
La passe ciblée du patch final a réussi : **7 tests**, consignés séparément dans
`verification_ciblee.json`, avec les tests CLI/import repris et un test
supplémentaire sans `-B`, sans variable `PYTHONDONTWRITEBYTECODE` et sans
`__pycache__`. La suite L déjà réussie n'est pas relancée pour ce déplacement.

Pour répéter seulement cette dernière passe :

```powershell
& 'C:\Users\jfeld\anaconda3\envs\ph\python.exe' -B -X utf8 simulation/chatGPT_critical_review/staging_integration_qualification/verifie_integration_isolee.py --ciblee
```

## Application après levée du gel seulement

Contrôler à nouveau le SHA original ci-dessus, puis depuis la racine :

```powershell
git apply --check simulation/chatGPT_critical_review/staging_integration_qualification/integration_qualification.patch
git apply simulation/chatGPT_critical_review/staging_integration_qualification/integration_qualification.patch
```

Le premier contrôle a été exécuté sans appliquer le patch. Avant modification,
archiver l'original et les preuves de ce staging avec les contrôleurs de la
campagne. La sélection finale devra rester explicite et ne sera installée
qu'après les calculs requis ; ce correctif ne crée aucune sélection et ne
déclare aucune antenne qualifiée.

Après application, depuis la racine du projet, vérifier une fois la source
intégrée par une nouvelle copie isolée :

```powershell
& 'C:\Users\jfeld\anaconda3\envs\ph\python.exe' -B -X utf8 simulation/chatGPT_critical_review/staging_integration_qualification/verifie_integration_isolee.py --source-integree
```

Ce mode accepte uniquement le SHA final attendu de Q :

```text
5fd159116157bef7191c3b86225cf0524fffd3e700295469fa12604c59482217
```

Il copie les sources actuelles dans TEMP **sans réappliquer le correctif**,
puis y exécute les sept checks. Les résultats de campagne et caches existants
ne sont pas copiés. La source sélectionnée, ses résultats et son cache restent
intacts. Ce mode ne crée aucun journal ou rapport dans le dépôt : les journaux
temporaires sont retransmis sur stdout/stderr et le bilan JSON est imprimé
après le repère `RAPPORT_INTEGRATION_JSON`. Aucun fichier de la campagne réelle
n'est ouvert par les comparaisons synthétiques.

**Ne pas copier les checks dans `simulation/tests/`.** Ils supposent une base
neuve et l'absence de cache, conditions valides uniquement dans leur copie
temporaire. Leur nom `checks_...` dans le staging évite une collecte contre
les sources installées et la campagne réelle.

Pour prouver cette voie avant application réelle, `--source-integree` accepte
un chemin optionnel vers un répertoire de sources déjà intégrées au même SHA
strict. `prouve_mode_integre.py` fabrique ce témoin dans TEMP, avec une campagne
et un cache existants à préserver, vérifie le refus d'un SHA inconnu, puis
reprend les sept checks de la voie originale sur copie. Il n'intègre rien dans
le projet et conserve ses preuves uniquement dans ce staging :

```powershell
& 'C:\Users\jfeld\anaconda3\envs\ph\python.exe' -B -X utf8 simulation/chatGPT_critical_review/staging_integration_qualification/prouve_mode_integre.py
```

La voie sans `--source-integree` reste réservée au SHA original avant
application. La voie intégrée refuse tout autre SHA que le SHA final ci-dessus.

La preuve `preuve_deux_voies.json` a réussi : sept checks sur une source déjà
intégrée dans TEMP, puis sept checks de la voie originale sur copie. La
campagne et le cache existants de la source témoin sont restés inchangés ; le
mode intégré n'a écrit aucun fichier dans le staging. Une source de SHA
inconnu a été refusée avant toute copie ou exécution. Aucun test n'a été
installé dans `simulation/tests/` et Q réel conserve son SHA original.
