# Vivaldi antipodale — fiche

Antenne à onde progressive, à fente exponentielle, **conçue ici** pour la
tomographie. Contrairement au losange, elle n'a aucune référence publiée : ses
cotes de départ sont des règles de l'art, et tout le reste a été réglé sur le
`|S11|` simulé.

| | |
|---|---|
| Carte | **143,07 × 280,60 mm**, FR4 1,6 mm, εr 4,4, tanδ 0,02 |
| Bande visée | 1,4 – 6,3 GHz (toute celle du LiteVNA) |
| Alimentation | microruban 3,0 mm = 50 Ω, SMA bord de carte |
| Rayonnement | *end-fire*, dans l'axe de la fente. **La carte est posée de chant.** |

### Les cotes, après réglage

| | mm | d'où elle vient |
|---|---|---|
| Ouverture de la bouche | 107,07 | λ/2 à 1,4 GHz — règle de l'art, confirmée |
| Ailes de cuivre à la bouche | 18,0 | choisie |
| Ligne 50 Ω | 3,0 × 20,0 | largeur imposée par 1,6 mm de FR4 |
| **Transition** | **100,0** | **réglée : c'est le seul levier qui paie** |
| **Évasement** | **160,6** (0,75 λ) | **réglé : raccourci au profit de la transition** |
| **Masse à l'alimentation** | **40,0** | **réglée : optimum net** |
| Fente au départ | 0,8 | réglée (0,4 et 2,0 sont pires) |
| Taux d'évasement | 0,013 /mm | indifférent entre 0,006 et 0,035 |
| Trous de fixation | 2 × Ø3,0 | à 60 mm du ruban, non simulés |

## Les quatre bords, et c'est tout le dessin

| | |
|---|---|
| `a(z)` | bord **intérieur** du cuivre du dessus — il borde la fente |
| `b(z)` | bord **extérieur** du cuivre du dessus |
| `g(z)` | bord **intérieur** du cuivre du dessous |
| `o(z)` | bord **extérieur** du cuivre du dessous |

```
z < z_ligne            a = -w/2, b = +w/2, masse pleine
                       → microruban 50 Ω ordinaire
z_ligne … z_fente      a glisse vers +x, b = a + w, g se retire
                       → le RECOUVREMENT des deux cuivres reste égal à w
z > z_fente            a s'évase en exponentielle, b et o rejoignent
                       le bord de carte, g = −a
                       → fente antipodale, qui rayonne
```

Le point qui n'est pas évident est `b = a + w` dans la transition. Sans lui,
les deux cuivres se recouvrent sur 35 mm au-dessus de 1,6 mm de FR4 : une ligne
de 10 Ω en plein milieu du trajet, et un `|S11|` plat à −4 dB. `apercu.py`
mesure ce recouvrement et refuse au-delà de `RECOUVREMENT_MAX_MM`.

## Ce qu'il a fallu corriger avant de pouvoir régler quoi que ce soit

Quatre fautes, toutes invisibles sur les cotes, toutes fatales — et **aucune
ne s'est signalée** : la simulation tournait et rendait une courbe.

| | Effet |
|---|---|
| L'évasement était écrêté à l'ouverture | passé le point de saturation, les deux bords du cuivre se confondaient : le dernier tiers de chaque aile était un fil |
| L'exponentielle n'était calée que sur son départ | l'ouverture atteinte dépendait du taux |
| La transition était une diagonale droite | rupture de pente aux deux coins |
| **Le domaine de calcul ignorait l'étendue en z de l'antenne** | la PML absorbait le dernier tiers de l'antenne |
| **Polygone de normale y donné en (x, z) au lieu de (z, x)** | antenne simulée **transposée**, 279 mm de large pour 143 de long |

Les deux dernières sont les plus coûteuses : elles ont produit trois
simulations de bruit, sur lesquelles deux « corrections » de conception ont été
décidées. D'où la règle : **avant de corriger une conception, vérifier qu'on a
bien simulé celle qu'on croit.** `fdtd.verifie_emprise()` ferme la seconde pour
de bon ; le calcul de l'étendue en z depuis les lignes de l'antenne ferme la
première.

## Le réglage, paramètre par paramètre

Mesuré sur 1,4–6,0 GHz (la borne haute est celle de la simulation, pas de
l'antenne). `couverture` = part de la bande sous −10 dB ; `moyen` = moyenne en
puissance de `|S11|`, ramenée en dB — c'est elle qui compte pour la tomographie,
puisqu'elle mesure la part de puissance qui n'entre pas dans l'antenne.

Reproduire : `python regle.py --parametre <NOM> --valeurs <...>`
Renoter sans resimuler : `python bilan_reglage.py` — tous les `.s1p` sont
gardés, précisément pour que changer de critère ne coûte pas une machine.

Vingt-et-un essais, du moins bon au meilleur. Carte de 143,07 mm de large
partout sauf mention contraire.

| essai | carte (mm) | <−10 dB | <−6 dB | pire | moyen |
|---|---|---|---|---|---|
| TRANSITION 25 | 143 × 259 | 24,3 % | 63,8 % | −1,1 | −6,4 |
| MARGE_OUVERTURE 1,3 | 175 × 279 | 26,5 % | 73,5 % | −3,9 | −7,3 |
| FENTE 0,4 | 143 × 279 | 28,1 % | 76,2 % | −3,8 | −7,7 |
| FENTE 2,0 | 143 × 279 | 20,0 % | 82,7 % | −4,8 | −7,7 |
| LARGEUR_MASSE 20 | 143 × 279 | 47,0 % | — | −1,2 | −7,8 |
| TAUX 0,022 | 143 × 279 | 28,1 % | 85,9 % | −4,2 | −7,9 |
| MARGE_LONGUEUR 1,4 | 143 × 365 | 30,3 % | 81,6 % | −4,2 | −7,9 |
| TRANSITION 70 | 143 × 304 | 40,0 % | 75,1 % | −2,9 | −8,0 |
| AILE 35 | 177 × 279 | 38,9 % | 77,8 % | −3,6 | −8,0 |
| TR 100 + MASSE 20 | 143 × 334 | 51,9 % | 80,5 % | −1,3 | −8,0 |
| **départ** (TR 45, ML 1,0) | 143 × 279 | 36,2 % | 82,2 % | −4,9 | −8,2 |
| TAUX 0,006 | 143 × 279 | 37,3 % | 82,2 % | −4,5 | −8,4 |
| TAUX 0,035 | 143 × 279 | 38,9 % | 85,4 % | −5,0 | −8,5 |
| TRANSITION 140 | 143 × 374 | 60,0 % | 80,0 % | −2,2 | −8,5 |
| LARGEUR_MASSE 40 | 143 × 279 | 53,0 % | — | −3,4 | −8,9 |
| TR 140 + ML 0,6 | 143 × 289 | 56,8 % | 85,4 % | −2,2 | −9,0 |
| TRANSITION 100 | 143 × 334 | 49,7 % | 88,6 % | −2,7 | −9,2 |
| TR 100 + ML 0,6 | 143 × 249 | 64,3 % | 90,8 % | −2,8 | −9,6 |
| TR 100 + ML 0,75 | 143 × 281 | 60,5 % | 91,9 % | −2,7 | −9,9 |
| TR 100 + ML 0,9 | 143 × 313 | 58,9 % | 90,3 % | −3,8 | −10,1 |
| TR 100 + ML 0,75 + MASSE 60 | 143 × 281 | 68,6 % | 93,5 % | −2,8 | −10,4 |
| TR 100 + ML 0,75 + MASSE 30 | 143 × 281 | 67,6 % | 93,5 % | −3,0 | −10,5 |
| **TR 100 + ML 0,75 + MASSE 40** | **143 × 281** | **73,0 %** | **93,5 %** | **−4,4** | **−10,8** |

### Ce que ce tableau dit, et qui n'était pas prévisible

1. **Les trois leviers « évidents » ne servent à rien.** Le taux d'évasement,
   l'ouverture de la bouche et la longueur de l'évasement sont les trois cotes
   que toute la littérature met en avant. Les faire varier déplace le `|S11|`
   de moins d'un décibel en moyenne — et l'agrandir le dégrade : à ouverture
   1,3 (carte de 175 mm), le `moyen` tombe de −8,2 à −7,3 dB.
2. **Le levier est la TRANSITION micro-ruban / fente.** De 25 à 100 mm, le
   `moyen` passe de −6,4 à −9,2 dB. C'est là que l'impédance passe de 50 Ω à
   celle de la fente, et c'est la seule cote dont la longueur achète vraiment
   quelque chose.
3. **Elle s'achète sur l'évasement, pas sur la carte.** Transition 100 avec
   l'évasement ramené à 0,75 λ donne une carte de 281 mm — la taille de
   départ — pour −9,9 dB au lieu de −8,2. La règle de l'art « évasement ≥ λ »
   suppose une transition courte ; ce qui compte est la longueur ÉLECTRIQUE
   totale, et la répartir autrement vaut mieux que l'allonger.
4. **La masse de l'alimentation a un optimum net à 40 mm.** Pleine largeur
   (143 mm), elle résonne en travers ; trop étroite (20 mm), elle ne fait plus
   un micro-ruban propre. À 40 mm, et seulement combinée aux deux autres, elle
   fait gagner un décibel de plus.

Les quatre dimensions de carte essayées — 249, 281, 304, 334, 365, 374 mm de
long, 143, 175, 177 mm de large — donnent toutes un résultat **moins bon** que
la carte de 143 × 281 mm retenue. Ce n'est pas un hasard de réglage : agrandir
une antenne à onde progressive sans redistribuer ses longueurs ne fait
qu'allonger le trajet de l'écho de bouche.

## Ce qu'elle vaut, et ce qu'elle ne vaut pas

Chiffres de la simulation de confirmation, `resultats/vivaldi_tomographie/
s11_antenne_seule.png`, sur 1,4–6,0 GHz :

| | |
|---|---|
| sous −10 dB | **71,4 %** de la bande |
| sous −6 dB | **94,1 %** de la bande |
| `\|S11\|` moyen | **−10,6 dB**, soit 9 % de la puissance réfléchie |
| pire | −2,9 dB |
| **seule zone au-dessus de −6 dB** | **5,45 – 5,85 GHz** |

**Elle vaut** donc : adaptée de 1,0 à 5,4 GHz presque sans trou — la coupure
basse est sous la borne de la simulation, pas au-dessus — avec des creux à
−25 dB et un fond à −10 dB.

**Elle ne vaut pas** : un `|S11|` sous −10 dB partout. Le défaut n'est plus
l'ondulation large de la première version ; c'est **une bande unique de
400 MHz vers 5,6 GHz**. Pour la tomographie, cela se contourne : c'est 8 % de
la bande utile, à son extrémité haute, là où la pénétration dans les tissus
est de toute façon la plus faible.

**Un chiffre à ne pas sur-interpréter** : le `pire` dépend du maillage. Entre
deux discrétisations qui donnent la même couverture à 1 % près, il passe de
−4,4 à −2,9 dB. Les grandeurs robustes sont la couverture et la moyenne ; la
pointe la plus haute ne l'est pas, et c'est la mesure qui tranchera.

**Les deux remèdes classiques sont au `BACKLOG.md`** (entrée 9), avec ce qui
les ferait revenir : les dentelures sur les ailes, qui demandent une carte plus
large, et le substrat trapézoïdal, qui ne coûte qu'un contour et une
simulation. Aucun des deux n'est tenté ici : la prochaine itération doit partir
d'une **mesure**, pas d'une vingt-deuxième simulation.

## La réserve à ne pas oublier pour la mesure de distance

Une Vivaldi est **dispersive par construction** : le rayonnement ne part pas
d'un point fixe, mais de l'endroit où la fente vaut environ λ/2, lequel se
déplace vers la bouche quand la fréquence baisse. Son retard n'est donc pas
constant, et `retard_attendu_ns()` n'en donne qu'une borne haute — celle du
trajet complet, 1,53 ns, soit 45,9 cm de décalage affiché.

Pour la **tomographie**, où l'image est reconstruite par inversion du champ
complet, ce n'est pas un défaut : la dispersion fait partie du modèle direct.
Pour lire une distance sur un pic de profil, comme dans le projet cartilage,
ç'en serait un — et c'est une raison de plus de garder les losanges, dont le
retard est presque constant.
