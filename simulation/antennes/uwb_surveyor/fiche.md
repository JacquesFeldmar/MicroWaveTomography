# Nooelec UWB Surveyor

Antenne biconique planaire, c'est l'antenne du banc.

| | |
|---|---|
| Fiche technique | [`../../uwb_surveyor_datasheet_revision_1.pdf`](../../uwb_surveyor_datasheet_revision_1.pdf), révision 1 du 22/06/2022 |
| Référence | SKU 100840 |
| Bande | 700 MHz – 10 GHz |
| Gain moyen | ~3 dBi (2,0 à 1 GHz ; 1,5 à 2,5 GHz ; 3,4 à 5 GHz) |
| ROS | 1,5 typique, mais ~3 vers 1,7 GHz, et divergent sous 0,8 GHz |
| Dimensions | 120 × 120 × 0,8 mm, 26 g |
| Connecteur | SMA femelle |
| Exemplaire du banc | marqué v1.0b2, 2025-10-15 |

## Ce que la fiche ne donne pas

**Le dessin des conducteurs.** Ni fichiers de fabrication, ni cotes des pétales,
ni largeur de la ligne d'alimentation, ni position exacte de la fente. La
géométrie de [`geometrie.py`](geometrie.py) est donc une **approximation**, dont
les paramètres sont groupés en tête du fichier :

| Paramètre | Valeur posée | |
|---|---|---|
| `RAYON_PETALE` | 46 mm | déduit de l'encombrement |
| `FENTE` | 0,6 mm | choisi |
| `LARGEUR_LIGNE` | 1,5 mm | ligne 50 Ω sur 0,8 mm de FR4 |
| `LONGUEUR_LIGNE` | 38 mm | estimé d'après la photo de la fiche |

**Le seul critère de recalage disponible est la courbe de ROS de la page 3.**
Simuler l'antenne seule, comparer son |S11| à cette courbe, puis ajuster les
quatre paramètres ci-dessus. Tant que ce recalage n'est pas fait, le retard
simulé n'a pas de valeur probante.

## Le retard, qui est la question du projet

`retard_attendu_ns()` ne rend que le retard de la **ligne d'alimentation**,
0,23 ns, soit 6,9 cm de décalage affiché. C'est une **borne basse** : le
rayonnement part plus loin que la fente, et son point de départ dépend de la
fréquence.

Les mesures, elles, donnent 20 cm (campagne du 9 octobre) à 36,5 cm (campagne
du 17 septembre). La géométrie seule ne peut pas produire plus de 24 cm, même
en faisant parcourir à l'onde tout le côté de la carte dans le FR4. **C'est
l'écart entre ces deux chiffres que la simulation doit expliquer.**

## Diagramme de rayonnement

Le diagramme est un tore : maximum dans le plan perpendiculaire à l'axe des
pétales, **nuls dans cet axe**. La plaque doit donc être présentée à la face de
la carte, ce que suppose `geometrie.py` : la carte est dans le plan *xy* et la
plaque est parallèle, à *z = x*.
