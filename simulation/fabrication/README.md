# fabrication — les deux commandes PCBWay

Deux articles, deux dépôts séparés sur le site. Chaque dossier contient **un
ZIP prêt à déposer tel quel** et une notice qui donne les options à cocher.

```powershell
conda activate ph
python export_gerber.py --tout          # réécrit les deux jeux depuis la géométrie
python verifie_gerber.py fabrication\panneau_losanges\panneau_losanges_pcbway.zip `
                         fabrication\vivaldi_tomographie\vivaldi_tomographie_pcbway.zip
```

| | À déposer | Carte |
|---|---|---|
| **Article 1** | `panneau_losanges/panneau_losanges_pcbway.zip` | 92,60 × 72,00 mm |
| **Article 2** | `vivaldi_tomographie/vivaldi_tomographie_pcbway.zip` | 143,07 × 280,60 mm |

Options communes aux deux : **FR-4, 2 couches, 1,6 mm, cuivre 1 oz, 5 pièces,
finition ENIG, pas de sérigraphie**, et la couleur de vernis est indifférente
— voir plus bas.

## Article 1 — le panneau des deux losanges

Deux monopôles planaires en losange sur une même plaque, reliés par deux
pontets sécables de 3 mm percés d'amorces de rupture.

| | |
|---|---|
| Petit losange, 32 × 40 mm | la **conception publiée** (Singhal 2013 / MathWorks), cotes inchangées |
| Grand losange, 57,6 × 72 mm | le même losange à l'échelle 1,8, pour la bande du LiteVNA |
| Fraisage de séparation | 3,00 mm de large, deux pontets de 3,0 mm, seize trous de 0,6 mm |

**Pourquoi un panneau.** PCBWay facture le nombre de *dessins*, pas le nombre
de cartes : deux losanges sur une plaque, c'est un dessin, donc un article.

**Pourquoi des pontets et pas une rainure en V.** Une rainure doit traverser le
panneau de bord à bord, et les deux cartes n'ont pas la même hauteur. Les
pontets, eux, tombent sur le côté, à 4 mm du cuivre le plus proche. Et surtout
**les deux bords d'alimentation sont sur le bord extérieur du panneau** : ils
sortent fraisés, pas cassés. C'est sur eux que se sertit le SMA, et c'est le
plan où se trouve le port de la simulation.

**Ce qui ne suit pas l'échelle sur le grand losange**, et c'est une décision,
pas un oubli :

| | |
|---|---|
| L'épaisseur reste 1,6 mm | 2,88 mm n'est pas une épaisseur de catalogue, et deux épaisseurs ne tiennent pas sur un même panneau |
| La ligne reste 3,1 mm de large | les 50 Ω d'un microruban tiennent au rapport largeur/épaisseur. À 5,58 mm sur 1,6 mm de FR4, la ligne ferait 28 Ω, et ses 18 mm agiraient en transformateur quart d'onde vers 2,5 GHz — en plein dans la bande visée. |

Conséquence : le grand losange **n'est plus l'homothétique exact** de la
conception publiée, et sa bande n'est pas celle de l'article divisée par 1,8.
C'est pour cela qu'il est simulé à part.

**Une cote serrée, à ne pas corriger** : la masse semi-circulaire du petit
losange arrive à **0,40 mm du bord de carte** — rayon 15,6 mm sur une carte de
32 mm, c'est la cote publiée. PCBWay accepte 0,3 mm de cuivre au bord fraisé,
donc cela passe, mais sans marge. S'ils le signalent, la réponse est : ne pas
reculer la masse, c'est elle qu'on veut comparer à l'article. Le grand losange,
lui, a 0,72 mm. Les deux bords de rupture, eux, sont à 2,9 mm du cuivre le plus
proche au minimum.

### Ce que la simulation dit

| | Simulé | Attendu |
|---|---|---|
| Petit losange (×1) | −10 dB de **2,30 à 13,60 GHz**, 85 % de couverture | 2,5–13,5 GHz publiés |
| Grand losange (×1,8 sur 1,6 mm) | −10 dB de **1,27 à 6,00 GHz**, 87 % de couverture | prédiction 1,39–7,50 GHz |

Le premier est l'**étalon du modèle électromagnétique** : il retrouve la bande
publiée à 0,2 GHz près aux deux bouts. C'est lui qui donne du poids au second,
dont personne n'a publié le résultat. Les 6,00 GHz du grand losange sont la
borne de la simulation, pas celle de l'antenne.

## Article 2 — la Vivaldi antipodale

Antenne à onde progressive, à fente exponentielle, conçue ici pour la
tomographie : directive sans l'être trop, continue en fréquence.

| | |
|---|---|
| Carte | 143,07 × 280,60 mm, FR4 1,6 mm |
| Ouverture de la bouche | 107,07 mm entre les deux bords intérieurs du cuivre |
| Ailes de cuivre à la bouche | 18 mm de chaque côté |
| Ligne d'alimentation | 3,00 mm — c'est elle qui fait les 50 Ω |
| Masse à l'alimentation | 40 mm de large |
| Transition / évasement | 100 mm / 160,6 mm |
| Perçages | deux trous de 3,0 mm, à 60 mm du ruban, pour la fixer |

**Elle n'a aucune référence publiée**, contrairement au losange. Ses cotes de
départ sont des règles de l'art — ouverture ≥ λ/2, longueur ≥ λ à la fréquence
basse — et le reste a été réglé sur le `|S11|` simulé, avec `regle.py`.

### Ce que la simulation dit, et ce qu'elle ne dit pas

Vingt-et-un essais, consignés dans
[`../antennes/vivaldi_tomographie/fiche.md`](../antennes/vivaldi_tomographie/fiche.md).
Sur 1,4–6,0 GHz :

| | |
|---|---|
| sous −10 dB | **71,4 %** de la bande |
| sous −6 dB | **94,1 %** de la bande |
| `\|S11\|` moyen | **−10,6 dB** |
| seule zone au-dessus de −6 dB | **5,45 – 5,85 GHz** |

La coupure basse est **sous 1,0 GHz**, c'est-à-dire sous la borne de la
simulation et non au-dessus de la bande visée.

Ce qui a fait le résultat n'était pas ce qu'on attendait : ni le taux
d'évasement, ni l'ouverture de la bouche, ni la longueur de l'évasement
n'améliorent quoi que ce soit — **agrandir la carte la dégrade**. Le seul
levier est la longueur de la **transition** micro-ruban / fente, et elle
s'achète sur l'évasement : la carte livrée fait la même taille que la première,
pour 2,4 dB de mieux en moyenne.

**Le défaut qui reste est localisé et chiffré, pas caché** : 400 MHz vers
5,6 GHz, soit 8 % de la bande utile, à son extrémité haute — là où la
pénétration dans les tissus est de toute façon la plus faible. Les deux
remèdes classiques — dentelures sur les ailes, substrat trapézoïdal — sont à
l'entrée 9 du `BACKLOG.md`, avec ce qui les ferait revenir. Aucun n'est tenté
ici : **la prochaine itération doit partir d'une mesure.**

**La Vivaldi est dispersive par construction**, et c'est à retenir pour la
mesure de distance : le rayonnement ne part pas d'un point fixe mais de
l'endroit où la fente vaut environ λ/2, lequel se déplace avec la fréquence.
Son retard n'est donc pas constant. Pour la tomographie, où l'image est
reconstruite par inversion, ce n'est pas un défaut ; pour lire une distance sur
un pic, ç'en serait un.

## Le vernis épargne, et pourquoi il est ouvert sur tout le cuivre

Les couches `.GTS` et `.GBS` ne sont pas celles d'une carte ordinaire :
**elles reprennent exactement les formes du cuivre**. Le vernis est donc retiré
partout où il y a du cuivre, et ne subsiste que sur le FR4 nu — les fentes.

Deux raisons. La simulation suppose du cuivre nu ; et le connecteur SMA doit
pouvoir se souder n'importe où sur la tranche, ce qui exige du cuivre
accessible et une finition qui le protège.

Ce qui reste de vernis, dans les fentes, déplace la fréquence de **moins de
1 %** — vingt micromètres contre 1,6 mm de substrat, soit dix fois moins que la
tolérance du FR4 sur sa permittivité. On aurait pu demander « pas de vernis du
tout », ce qui collerait encore mieux à la simulation, mais ce n'est pas une
option sûre du formulaire PCBWay : voir l'entrée 8 du `BACKLOG.md`.

La **couleur** du vernis est donc indifférente. La **finition**, non : ENIG est
le choix robuste. Sa couche de nickel est un peu plus dissipative en
hyperfréquence que l'argent chimique, ce qui se discute sur les 20 mm de ligne
d'alimentation et nulle part ailleurs ; l'argent chimique est meilleur en radio
et se ternit en quelques mois à l'air libre.

## Le connecteur n'est pas sur la carte

Aucune empreinte de connecteur n'est posée, et c'est volontaire : le SMA est un
modèle **bord de carte** (*edge-launch*), qui se sertit sur la tranche et se
soude d'un côté sur le ruban, de l'autre sur la masse. C'est exactement ce que
suppose la simulation, dont le port localisé occupe le plan de cette tranche.

| Antenne | Où se sertit le SMA |
|---|---|
| Losanges | bord inférieur, centré sur la ligne de 3,1 mm |
| Vivaldi | bord inférieur, centré sur la ligne de 3,0 mm |

## Trois contrôles, et aucun ne fait confiance au précédent

| | |
|---|---|
| `apercu.py` | dessine les contours et mesure le cuivre par tranche. Il attrape ce qu'aucune relecture de code n'attrape : un conducteur qui se pince jusqu'à disparaître, un cuivre hors carte, un recouvrement des deux faces trop large. |
| `export_gerber.py` | écrit le RS-274X et l'Excellon directement depuis la géométrie simulée. Pas d'étape KiCad — c'était le seul endroit où les cotes fabriquées pouvaient diverger de celles qui ont été simulées. |
| `verifie_gerber.py` | relit le ZIP avec `gerbonara`, qui n'est pas de nous, compare les encombrements et produit un rendu SVG. |

Les encombrements relus se recoupent avec la géométrie simulée :

| | Gerber relu | Géométrie simulée |
|---|---|---|
| Vivaldi, cuivre dessus | 73,03 × 279,14 mm | ligne en x = −1,50 → aile en x = +71,53 |
| Vivaldi, cuivre dessous | 143,07 × 279,14 mm | masse pleine, toute la largeur |
| Panneau, cuivre dessus | 88,40 × 61,20 mm | les deux losanges posés à 0 et 35 mm |

## À faire en recevant les cartes

1. Mesurer `|S11|` de chaque antenne **seule**, au LiteVNA calibré SOL, au
   plan exact de la tranche.
2. Le comparer à `resultats/<antenne>/s11_antenne_seule.png`.

C'est ce qui ferme la boucle. Le losange publié dit déjà que le modèle
électromagnétique est juste ; la mesure dira si la **fabrication** l'est, et
c'est la seule chose que la simulation ne peut pas savoir.
