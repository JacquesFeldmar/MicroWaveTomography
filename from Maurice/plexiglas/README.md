# Banc plexiglas — méthodes A et B

## Programmes

| Programme | Rôle |
|---|---|
| `progs/s11_cible_A.py` | Méthode A : soustraction complexe du fond, puis profil IFFT avec fenêtre de Hann |
| `progs/s11_cible_B.py` | Méthode B : ajustement direct aux valeurs complexes fréquentielles |
| `progs/ajustement_B.py` | Modèles, optimisation et information de Fisher de B |
| `progs/mesure_cible.py` | Acquisition/lecture commune à A et B |
| `progs/analyse_fond.py`, `progs/calibration_sol.py` | Fond et SOL communs aux deux méthodes |
| `progs/litevna.py`, `progs/tos.py`, `progs/debug_mesures.py` | Pilote, TOS et relecture communs |

L'ancien `s11_cible.py` est remplacé par les deux commandes explicites `_A` et
`_B`. La calibration, le fond et le TOS ne sont pas des estimateurs A ou B :
ils conservent leur nom. Les autres projets du dépôt sont indépendants.

## Utiliser B sur une acquisition existante

Depuis la racine du dépôt, dans l'environnement `env2` :

```sh
source /Users/maurice/envs/env2/bin/activate
python plexiglas/progs/s11_cible_B.py \
  --mesure plexiglas/mesures/cible_20260917T112516_040264Z/cible.npz \
  --modele echos --echos 2
```

Aucun contact avec le VNA en mode `--mesure`. Les anciennes acquisitions sont
compatibles ; leur IFFT sauvegardée n'entre pas dans l'ajustement B.

Pour comparer avec A sur exactement les mêmes données :

```sh
python plexiglas/progs/s11_cible_A.py \
  --mesure plexiglas/mesures/cible_20260917T112516_040264Z/cible.npz
```

## Nouvelle acquisition, puis B

Ces chemins correspondent au fond et à la SOL du montage documenté le 17/09.
Ils ne conviennent que si l'antenne, le câble, les raccords et la scène de fond
correspondent toujours à ces enregistrements.

```sh
python plexiglas/progs/s11_cible_B.py \
  --start-ghz 1 --stop-ghz 6 --points 201 --nombre 10 \
  --sol plexiglas/calibration/sol_20260917T083949_945315Z.npz \
  --fond plexiglas/mesures/fond_20260917T084354_999413Z/fond.npz \
  --modele echos --echos 2
```

Remplacer `_B` par `_A` et retirer `--modele`/`--echos` pour la méthode A.
La mesure commune est sauvegardée **avant** le traitement dans
`mesures/cible_DATE/cible.npz`. Les nouvelles acquisitions ne contiennent plus
le profil A ; celui-ci est enregistré dans le résultat A séparé.

## Modèles B

### Échos : aluminium et recherche de contributions retardées

Le modèle est

`y(f) = somme_j g_j exp[-4 i pi (f-f_c) d_j / c]`.

Les gains `g_j` sont complexes et constants sur la bande. Les distances `d_j`
sont apparentes ; le centrage de fréquence change seulement la convention de
phase du gain. `--echos` choisit explicitement entre 1 et 4 contributions
(défaut : 2). Il n'y a ni IFFT ni recherche de pics IFFT dans cet ajustement.
Une grille de retards sert à l'initialisation, puis les distances sont ajustées
en continu. Plusieurs départs sont essayés, sans garantie de minimum global.

Les bornes `--distance-min-cm 0 --distance-max-cm 150` sont celles des paramètres,
pas une fenêtre appliquée aux données : toutes les contributions présentes
restent dans le signal à ajuster. Un écho ajusté n'identifie pas automatiquement
la plaque, le sol ou un trajet secondaire. Un gain constant peut mal décrire
une antenne large bande et la diffraction d'une plaque finie.

### Plaque diélectrique : épaisseur et facteur d'amplitude

Le modèle du texte `textes/texte1/modele_statistique.tex` est implémenté :

`y(f) = g exp[-4 i pi (f-f_c) d / c] [r + alpha b exp(-4 i pi f n e / c)]`,
avec `r=(1-n)/(1+n)` et `b=-(1-r*r)*r`.

`e` est l'épaisseur ; `alpha` multiplie l'amplitude nominale de l'écho arrière,
et n'est pas une atténuation par mètre. Le gain complexe et le retard externe
sont aussi ajustés. L'indice réel doit être fourni ; aucun indice matériau
n'est déduit de la seule mesure. Par exemple, **si l'on suppose n = 1,61** :

```sh
python plexiglas/progs/s11_cible_B.py --mesure CHEMIN_CIBLE_PLEXIGLAS.npz \
  --modele plaque --indice 1.61 \
  --epaisseur-min-mm 1 --epaisseur-max-mm 40 --alpha-max 2
```

Ce modèle suppose deux faces, une incidence normale, un indice et un alpha
constants. Il néglige les réflexions internes multiples, les bords et les
trajets parasites. Il ne s'applique pas à une plaque d'aluminium. Les deux
traits du graphique sont la face avant et la face arrière à distance optique :
leur écart vaut `n*e`, pas l'épaisseur géométrique `e`.

## Résultats et qualité du modèle

- Figures : `figures/cible_DATE_A.png`, `cible_DATE_B_echos2.png` ou
  `cible_DATE_B_plaque.png`.
- Résultats : `analyses/cible_DATE_A/` et `analyses/cible_DATE_B_MODELE/`.
- B produit un NPZ (valeurs complexes), un CSV et un JSON (paramètres, FIM,
  covariance conditionnelle complète, diagnostics, bornes et minima essayés).
- Une relance du même modèle sur le même fichier remplace son analyse ; utiliser
  `--sortie AUTRE_DOSSIER` pour conserver des variantes. La mesure source est
  conservée.

L'ajustement est uniforme par défaut. `--ponderation bruit` minimise la somme
`|y-modele|² / v(f)`, lorsque les variances sont disponibles. Le bruit de la
moyenne est estimé comme `var(cible)/N_cible + var(fond)/N_fond`, en supposant
les balayages indépendants. Un `--fond` explicite avec `--mesure` permet de
retrouver un fichier de fond déplacé ; ses fréquences et sa moyenne sont vérifiées.

La FIM vaut `2 Re(Jᴴ diag(1/v) J)` et inclut les gains et retards auxiliaires.
Son inverse complet, lorsqu'il existe, tient donc compte de ces inconnues ;
le bloc d'épaisseur/alpha est la borne marginale. Les unités des paramètres
sont documentées dans le JSON (cm, mm, gains sans dimension). Aucune précision
n'est annoncée lorsque le bruit est inconnu ou la FIM singulière. Même lorsque
la FIM est inversible, les bornes sont conditionnelles au modèle et aux
hypothèses de bruit ; elles ne mesurent pas les erreurs systématiques.

Le résidu RMS relatif est `norme(y-modele)/norme(y)`, pas une fraction de
puissance. Le seuil de 20 % est descriptif. Le chi² réduit compare l'erreur au
bruit estimé ; une valeur supérieure à 3 déclenche un avertissement, sans
constituer un test statistique exact pour des données corrélées. Les solutions
aux bornes et les échecs de convergence sont également signalés.

**B ne corrige pas automatiquement l'offset de 37–38 cm.** La réponse de l'antenne
reste incluse. Un mauvais ajustement ne doit pas être interprété comme une
localisation fiable ou une preuve de trajet secondaire.

Le premier traitement de la mesure `cible_20260917T112516_040264Z` avec deux
échos laisse environ **80 % de résidu RMS relatif** et atteint une borne :
ce modèle simple est insuffisant pour cette acquisition.

## Vérification

```sh
python -m unittest discover -s plexiglas/tests -v
```

Tests de distances connues, deux trajets d'intensités différentes, plaque avec
bruit, FIM avec nuisances, dégénérescence, variance des moyennes, relecture hors
matériel et chaîne SOL/USB existante. Dépendances : NumPy, SciPy, Matplotlib,
pyserial (disponibles dans `env2`). Optimisation par
[SciPy least_squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html),
en empilant les parties réelle et imaginaire du résidu.

## Comparer une sous-bande sans nouvelle acquisition

```sh
python plexiglas/progs/ifft_sous_bande.py --start-ghz 1 --stop-ghz 4
```

Sans `--mesure`, le programme utilise le dernier `mesures/cible_*/cible.npz`
selon sa date de modification, et affiche le chemin retenu. Pour choisir une
acquisition, ajouter `--mesure chemin/vers/cible.npz`. Ajouter éventuellement
`--distance-cm 45` pour calculer les offsets apparents des maxima globaux.

Le résidu complexe enregistré (cible moins fond, déjà corrigé par SOL) est
sélectionné sans interpolation. Les IFFT complète et partielle utilisent
chacune une fenêtre de Hann et un facteur de suréchantillonnage de 16.
Les originaux sont conservés ; le programme ne contacte pas le VNA.
La figure comparative est enregistrée dans `figures/`, les profils et les pics
CSV dans `analyses/`, avec le suffixe `ifft_1-4GHz` pour cette bande.
Les bornes effectives et le nombre de points sont affichés.

La bande réduite élargit les pics et modifie la pondération fréquentielle :
un changement de maximum ne prouve pas à lui seul l'origine d'un offset.
