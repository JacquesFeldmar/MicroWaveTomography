# Compatibilité des CSV John — préparation isolée

Ce dossier prépare uniquement la lecture de l'en-tête réel
`frequency_hz,s11_real,s11_imag`. Le correctif ajoute deux lignes dans
`donnees.lit_csv` : la paire explicite `s11_real,s11_imag` est reconnue comme
réel/imaginaire. La normalisation historique des autres en-têtes reste intacte.
Les valeurs numériques, les grilles, les tolérances et les règles de doublons
ne changent pas. Les préfixes `s21`/`s22`, l'inversion des colonnes et les paires
partiellement préfixées sont refusés.

**Le correctif n'est pas appliqué.** Ne l'appliquer qu'après la fin des deux
files de calcul suivies par les sessions **12178 et 20307**, et après levée
explicite du gel par le coordinateur de la campagne. Ne pas modifier les
sources utilisées par les calculs actifs.

SHA-256 original requis pour `simulation/donnees.py` :

```text
4164aa6d4c0cba4f88592c776592dff79ec5bceeac65f6b65d1a9043a3114237
```

Le lanceur refuse un autre original. Il construit une copie temporaire avec le
correctif, vérifie que son diff correspond exactement au patch fourni, puis
charge cette copie dans un processus Python isolé. Les 10 tests existants de
`simulation/test_donnees.py` et les 7 tests ciblés de ce dossier passent :
**17 tests, zéro échec ou erreur**. Les cinq CSV John sont égaux point par point
aux S1P et à une lecture NumPy indépendante, y compris les parties réelle et
imaginaire. La lecture du dossier signale les quatre doublons identiques et
ignore le SHORT dans la série de plaques.

La vérification confirme aussi le refus des grilles irrégulières, des données
non finies, des en-têtes ambigus et des doublons contradictoires. Les sources
et tous les exports du dossier John sont restés inchangés. Le rapport
`verification.json` donne leurs empreintes et celles du correctif/de la copie.

Pour répéter cette vérification pendant le gel, depuis la racine du projet :

```powershell
& 'C:\Users\jfeld\anaconda3\envs\ph\python.exe' -B -X utf8 simulation/chatGPT_critical_review/staging_import_csv_john/verifie_copie_temporaire.py
```

Le lanceur limite OMP, OpenBLAS, MKL et NumExpr à un thread et n'écrit que son
rapport dans ce dossier. Aucun programme matériel ou FDTD n'est exécuté.

Après la fin des files et la levée du gel seulement, vérifier le SHA original
ci-dessus, puis utiliser depuis la racine :

```powershell
git apply --check simulation/chatGPT_critical_review/staging_import_csv_john/lecteur_csv_john.patch
git apply simulation/chatGPT_critical_review/staging_import_csv_john/lecteur_csv_john.patch
```

Le contrôle `git apply --check` a déjà été réalisé sans appliquer le patch.
Pour vérifier ensuite le lecteur effectivement installé, depuis `simulation/` :

```powershell
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
& 'C:\Users\jfeld\anaconda3\envs\ph\python.exe' -B -X utf8 -m unittest test_donnees
& 'C:\Users\jfeld\anaconda3\envs\ph\python.exe' -B -X utf8 -m unittest discover -s chatGPT_critical_review/staging_import_csv_john -p test_csv_john.py
```

Le lanceur de copie temporaire ne doit plus être utilisé après application :
son verrou SHA de l'original doit alors échouer. Les résultats du staging
attestent uniquement la compatibilité de lecture ; ils ne requalifient aucune
simulation physique et ne suppléent pas les acquisitions/SOL sources absentes.
