# Ce que les profils archivés permettent de conclure — 22 octobre 2026

Lecture seule. Aucune source gelée n'est touchée, aucun solveur lancé, aucun
seuil modifié, aucune qualification déclarée. Reproductible par
`python -B analyse_grandeurs_decision.py` ; sortie dans `rapport.json`.

## Le constat

Le contrôle spatial compare `S11` point par point et échoue pour les trois
antennes. Deux faits, recalculés ici indépendamment, précisent ce que cet
échec signifie.

### 1. La suite de raffinement ne converge pas — elle remonte

Écarts complexes entre niveaux consécutifs, grand losange, campagne F1, 12 ns.
Recalcul direct sur les `s11.s1p` archivés, sans masque et sans `Q.ecarts` :

| paire spatiale | maximum complexe | RMS complexe | |
|---|---:|---:|---|
| `fin_12ns` → `tres_fin_12ns` | 0,0463158 | 0,0246882 | |
| `tres_fin_12ns` → `ultra_fin_12ns` | 0,0388005 | 0,0209888 | ↓ |
| `ultra_fin_12ns` → `extreme_fin_12ns` | 0,0249912 | 0,0176806 | ↓ |
| `extreme_fin_12ns` → `n30_12ns` | 0,0317481 | 0,0218440 | **↑** |
| `n30_12ns` → `n34_12ns` | 0,0694264 | 0,0184464 | **↑** |

Les cinq valeurs reproduisent exactement celles consignées dans
`TACHES_REPRISE_PCBWAY.md`. La suite décroît sur trois paliers, puis
**remonte deux fois, et finit à son plus mauvais écart au maillage le plus
fin**.

Une suite de discrétisation qui converge décroît. Celle-ci ne décroît pas :
elle mesure autre chose que l'erreur de discrétisation. Le
[diagnostic des grilles closes](../analyse_grilles_fermees_n30/) avait déjà
nommé la cause probable — les grilles ne sont pas emboîtées, et une cellule
près du port **grossit** de 0,0494 mm à `extreme_fin` vers 0,0833 mm à `N30`,
soit un facteur 1,69, pendant que la résolution nominale augmente.

**Conséquence pratique : ajouter un palier plus fin ne fera pas passer ce
contrôle.** Chaque palier redistribue la grille là où `S11` se lit. Pour que
la comparaison mesure l'erreur de discrétisation, il faudrait des grilles
**emboîtées** — chaque ligne du niveau grossier présente dans le niveau fin,
au moins dans le bloc du port. C'est une campagne à concevoir, pas un palier
de plus.

### 2. Les grandeurs qui fondent la décision, elles, s'accordent

Étendue entre tous les niveaux de maillage d'une même antenne, bande
1,4–6,0 GHz, grille de 25 MHz :

| campagne / antenne | niveaux | part < −10 dB | part < −6 dB | puissance réfléchie moyenne | pire point |
|---|---:|---:|---:|---:|---:|
| **F2** / petit losange | 5 | 9,19 pts | 0,54 pts | **0,13 dB** | 0,01 dB |
| **F2** / grand losange | 5 | 1,08 pts | 0,00 pts | **0,13 dB** | 0,22 dB |
| **F2** / Vivaldi | 5 | 1,08 pts | 0,00 pts | **0,08 dB** | 0,17 dB |
| F1 / petit losange | 5 | 1,62 pts | 0,00 pts | 0,02 dB | 0,01 dB |
| F1 / grand losange | 13 | 5,41 pts | 0,00 pts | 0,45 dB | 0,59 dB |
| F1 / Vivaldi | 7 | 0,54 pts | 0,00 pts | 0,29 dB | 0,45 dB |

Sur **treize** niveaux de maillage du grand losange, couvrant 16 à 34 mailles
par longueur d'onde dans le substrat, la puissance réfléchie moyenne tient
dans 0,45 dB et la part de bande sous −6 dB est **identique**. Sur la
campagne de production F2, l'écart base/fin vaut 0,08 à 0,13 dB.

La seule grandeur sensible est la part sous −10 dB du **petit** losange
(9,19 points). C'est un artefact de comptage : son `|S11|` longe précisément
−10 dB sur une large portion de bande, si bien qu'un déplacement minime fait
basculer beaucoup de points d'un côté ou de l'autre du seuil. Sa puissance
moyenne, elle, bouge de 0,13 dB.

## Ce que cela établit, et ce que cela n'établit pas

**Établi** : sur la bande 1,4–6,0 GHz, les trois antennes ont une puissance
réfléchie moyenne et une part de bande adaptée qui ne dépendent pas du
maillage, à 0,13 dB près sur la campagne de production. Ce sont les deux
grandeurs sur lesquelles la décision de faire fabriquer repose.

**Non établi** : que `S11` soit prédit à mieux que ≈ 0,07 en module complexe
à une fréquence donnée. Il ne l'est pas, et la suite de raffinement montre
qu'on ne sait pas, avec ces grilles, de combien il l'est. La courbe mesurée
sur la carte reçue pourra s'écarter d'autant, **avant** même de compter ce que
le modèle ne contient pas : le connecteur réel, la tolérance du FR4 sur sa
permittivité, la rugosité et la finition du cuivre.

**À ne pas confondre** : le petit losange est mal adapté sur 1,4–6,0 GHz —
puissance moyenne −7,3 dB, 79 % de la bande sous −6 dB. C'est normal : c'est
la conception publiée pour 2,5–13,5 GHz, livrée comme **étalon du modèle
électromagnétique**, pas comme antenne de travail dans notre bande. La
livraison ne doit rien prétendre d'autre à son sujet.

## La décision qui revient à l'utilisateur

Le critère de qualification en vigueur est numérique : 0,05 / 0,02 / 1 dB sur
`S11` point par point. Il n'a jamais été atteint, et le point 1 ci-dessus
explique pourquoi il ne le sera pas en ajoutant des paliers.

Deux voies, et elles ne demandent pas le même travail :

| | Ce qu'elle coûte | Ce qu'elle donne |
|---|---|---|
| **A. Qualifier sur les grandeurs de décision**, en consignant la non-convergence ponctuelle comme limite déclarée | rien de plus : les profils existent | les deux articles partent ; la comparaison avec les cartes reçues se fait sur la puissance moyenne et les parts de bande, pas point par point |
| **B. Refaire une étude de convergence bien posée**, sur grilles emboîtées au port | une campagne entière à concevoir, puis 45 à 65 h de solveur | un chiffre d'erreur de discrétisation défendable point par point |

**Recommandation : A, puis B seulement si une mesure l'exige.** La voie B
produirait un chiffre sur le modèle ; elle ne dirait rien de plus sur les
cartes. Ce qui manque aujourd'hui pour progresser n'est pas un maillage plus
fin, c'est une **mesure** — et les cartes doivent être fabriquées pour cela.

Cette note ne tranche pas : le choix du critère appartient à l'utilisateur, et
aucun seuil n'a été modifié ici.
