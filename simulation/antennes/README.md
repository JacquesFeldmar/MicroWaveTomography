# Antennes et campagnes de mesure

Chaque antenne possède un module `geometrie.py`, une fiche descriptive et éventuellement des campagnes dans `mesures/`. Les trois cartes de production partagent la connectique et le nominal de matériau définis dans `../connectique.py` et `../materiaux.py`.

| Dossier | Usage |
|---|---|
| `diamant_uwb/` | Petit monopôle en losange dérivé de la conception publiée, avec implantation SMA de production |
| `diamant_uwb_x18/` | Losange agrandi ×1,8, sur substrat conservé à 1,6 mm et implantation SMA commune |
| `vivaldi_tomographie/` | Vivaldi du projet, avec garde de contour, trous de fixation et implantation SMA |
| `dipole_reference/` | Contrôle partiel du montage et des traitements ; le minimum de S11 seul ne constitue pas une fréquence de résonance de référence exacte |
| `uwb_surveyor/` | Approximation géométrique de la Nooelec du banc, à confronter aux mesures |

Les bandes et essais de réglage antérieurs au 18 octobre 2026 concernent la révision historique, conservée dans `../archives/`. Ils ne qualifient pas les nouvelles cartes. La campagne de production et ses critères sont décrits dans [le README principal](../README.md).

## Interface des géométries

| Élément | Fonction |
|---|---|
| `NOM`, `DESCRIPTION` | Identité |
| `pose(csx, fdtd, acq)` | Construction CSXCAD et lignes physiques nécessaires au maillage |
| `retard_attendu_ns()` | Hypothèse de retard aller simple, ou `None` lorsqu'elle n'est pas justifiée |
| `cotes()` | Dimensions en mm |
| `contours_mm()` | Polygones `F_Cu`, `B_Cu`, contour `Edge_Cuts` |
| `percages_mm()` | Trous non métallisés `(x, y, diamètre)` |
| `vias_mm()` | Trous métallisés `(x, y, diamètre fini)` |
| `controles_fabrication()` | Règles spécifiques au dessin |

Les exports et `pose()` utilisent les mêmes contours. La construction conserve les surfaces métalliques idéales et représente explicitement les vias et les trous de fixation. Le demi-encombrement retourné et les lignes imposées couvrent tous les axes, y compris la longueur en z de la Vivaldi posée de chant. `fdtd.verifie_emprise()` refuse une primitive située hors de cette emprise.

Pour les polygones CSXCAD, les coordonnées tournent avec la normale : normale x → `(y,z)`, normale y → `(z,x)`, normale z → `(x,y)`. La Vivaldi utilise la normale y ; cette permutation doit rester vérifiée lors d'un changement.

## Contrôle avant fabrication

```powershell
python -B apercu.py --toutes
python -B export_gerber.py --tout
python -B verifie_gerber.py fabrication/panneau_losanges/panneau_losanges_pcbway.zip fabrication/vivaldi_tomographie/vivaldi_tomographie_pcbway.zip
```

Le contrôle indépendant relit les surfaces Gerber, la ligne médiane du contour, les coordonnées et le statut de métallisation des perçages. Il compare les formes, pas seulement leurs boîtes englobantes. `export_dxf.py` fournit une copie de travail pour CAO ; le chemin de production reste l'export Gerber direct.

## Campagnes de mesure

Une campagne avec plaque partage la même grille, le même fond et la même calibration. `donnees.charge_dossier()` reconnaît `background.s1p` et `plate_<n>cm.s1p`, avec CSV équivalent. Une recalibration, une autre bande ou un autre montage exige une nouvelle campagne.

Les fichiers Touchstone sont en 50 Ω, paramètres S, représentation RI. Les fréquences sont finies, strictement croissantes et régulièrement espacées. Des doublons CSV/Touchstone identiques sont signalés ; des doublons divergents sont refusés.

La mesure S11 des cartes PCBWay, sans plaque, suit [PROTOCOLE_MESURE_PCBWAY.md](../PROTOCOLE_MESURE_PCBWAY.md). Elle conserve les fichiers complexes, la calibration, l'identifiant de la carte, le stratifié et les dimensions réels, les références de simulation et les photographies du montage.