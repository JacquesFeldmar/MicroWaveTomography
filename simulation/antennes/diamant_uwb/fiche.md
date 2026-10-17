# Monopôle planaire en losange — l'antenne de référence cotée

| | |
|---|---|
| Origine | Singhal et al. (2013), repris par MathWorks, [*Diamond-Shaped Antenna for UWB Applications*](https://www.mathworks.com/help/antenna/ug/diamond-shaped-antenna-for-uwb-applications.html) |
| Type | monopôle planaire, cuivre en losange sur une face, masse semi-circulaire sur l'autre |
| Carte | 32 × 40 mm, FR4 **1,6 mm**, εr 4,8, tanδ 0,026 |
| Masse | demi-disque de rayon 15,6 mm, bord droit en y = −20 mm |
| Alimentation | au bord y = −20 mm, largeur 3,1 mm |
| **Résultat publié** | **\|S11\| < −10 dB de 2,5 à 13,5 GHz** |

## Pourquoi cette antenne est dans le projet

Elle est le **second étalon**, et le plus important des deux :

| Étalon | Ce qu'il vérifie |
|---|---|
| `dipole_reference` | la chaîne de **traitement** : une plaque à 30 cm doit être lue à 30 cm |
| `diamant_uwb` | le modèle **électromagnétique** : notre S11 doit retrouver la bande publiée |

Si notre S11 simulé colle à la courbe de l'article, alors le maillage, le port,
le substrat et les conditions aux limites sont justes — et le jour où le même
programme donnera un retard pour l'UWB Surveyor, ce retard vaudra quelque
chose. C'est exactement ce que la Nooelec ne permet pas, faute de fichiers.

## Les douze sommets du cuivre rayonnant

En millimètres, dans l'ordre, z = 1,6 mm :

| | x | y | | x | y |
|---|---|---|---|---|---|
| 1 | −1,55 | −20 | 7 | 11,00 | 14 |
| 2 | −1,55 | −10 | 8 | 14,50 | 9 |
| 3 | −0,60 | −4 | 9 | 6,50 | −2 |
| 4 | −6,50 | −2 | 10 | 0,60 | −4 |
| 5 | −14,50 | 9 | 11 | 1,55 | −10 |
| 6 | −11,00 | 14 | 12 | 1,55 | −20 |

Paramètres de l'article : Wf 3,1 · Wf1 1,2 · W1 22 · W2 29 · W3 13 ·
Lf 10 · Lf1 6 · L1 5 · L2 11 · L3 2.

## La mise à l'échelle, pour descendre à 1,4 GHz

Une antenne planaire multipliée par *k* voit ses fréquences divisées par *k*.
La constante `ECHELLE` de [`geometrie.py`](geometrie.py) applique ce facteur à
toutes les cotes.

| Échelle | Bande attendue | Carte |
|---|---|---|
| 1,0 (publiée) | 2,5 – 13,5 GHz | 32 × 40 mm |
| **1,8** | **1,4 – 7,5 GHz** | **58 × 72 mm** |

**Réserve, et elle est sérieuse :** le FR4 ne se met pas à l'échelle. Sa
permittivité descend d'environ 4,5 à 1 GHz à 4,2 à 6 GHz, et ses pertes
montent avec la fréquence. La version agrandie doit donc être re-simulée, et
sans doute retouchée — le rayon de la masse semi-circulaire est le paramètre
le plus efficace pour rattraper l'adaptation en bas de bande.

## Fabrication

Deux couches, FR4 1,6 mm, cuivre 35 µm, finition ENIG de préférence. Le
connecteur SMA se soude au bord de carte en y = −20 mm : pin central sur le
cuivre du dessus, masse sur le demi-disque du dessous.
