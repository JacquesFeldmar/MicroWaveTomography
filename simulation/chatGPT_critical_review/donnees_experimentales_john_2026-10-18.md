# Données expérimentales du rapport pour John

Information fournie par l'utilisateur le 18 octobre 2026 : le dossier `from Maurice/plexiglas` accompagne `from Maurice/report_john.pdf`. Lecture et contrôles effectués sans modifier les sources de ce dossier ni contacter le VNA. Les simulations PCBWay restent une campagne distincte, en cours.

## Correspondance et provenance

Les trois copies du rapport sont identiques octet pour octet :

- [Rapport fourni par Maurice](<../../from Maurice/report_john.pdf>).
- [Rapport dans le paquet de données](<../../from Maurice/plexiglas/textes/texte3_john/report_john.pdf>).
- [Copie déjà présente dans simulation](../report_john.pdf).

Leur SHA-256 commun est `1a922ffd7fae750a369d8d6fbf162f05f4de786759f09769243cc47e169da742`. Le rapport compte six pages et est daté du 9 octobre 2026. Les empreintes des 55 fichiers du dossier et des trois copies du rapport sont conservées dans [l'inventaire de lecture](inventaire_donnees_john_2026-10-18.json).

Le [paquet technique](<../../from Maurice/plexiglas/textes/texte3_john/README.md>) donne accès aux [exports numériques](<../../from Maurice/plexiglas/textes/texte3_john/data/>), au [manifeste des acquisitions](<../../from Maurice/plexiglas/textes/texte3_john/data/manifest.json>), au source LaTeX et au [programme des figures](<../../from Maurice/plexiglas/textes/texte3_john/build_figures.py>).

Malgré le nom du dossier, le jeu du rapport concerne une **plaque d'aluminium** devant une Nooelec UWB Surveyor bleue. Le rapport précise que le panneau transparent était absent de ces mesures. L'instrument est un LiteVNA 64. La photo est explicitement présentée comme retouchée par IA : elle ne fournit pas de référence dimensionnelle ni de preuve d'absence de trajets parasites.

## Données effectivement disponibles

| Export | Contenu | Balayages annoncés dans le manifeste |
|---|---|---:|
| `background` | Fond sans cible | 100 |
| `plate_50cm` | Plaque à environ 50 cm | 10 |
| `plate_60cm` | Plaque à environ 60 cm | 10 |
| `plate_70cm` | Plaque à environ 70 cm | 10 |
| `independent_short` | Nouvelle acquisition du SHORT | 10 |

Chaque export existe en CSV et Touchstone S1P. Les cinq couples sont strictement égaux en fréquence et en S11 complexe : 201 points de 1 à 6 GHz, avec un pas de 25 MHz, référencés à 50 ohms. Ce sont les moyennes complexes annoncées comme corrigées par SOL, avant fenêtre et soustraction du fond.

L'inventaire complet, fichiers cachés et ignorés compris, ne contient **aucun des cinq NPZ sources référencés par le manifeste**, ni les acquisitions individuelles, ni le fichier de calibration SOL. Les étiquettes de distance, les nombres de balayages et l'utilisation d'une même SOL restent donc des déclarations du paquet. Leur vérification à partir des acquisitions originales n'est pas possible avec ces seuls exports.

## Reproduction numérique

Les résultats ont été recalculés indépendamment depuis les valeurs complexes, puis comparés au [traitement actuel](../traitement.py). La chaîne historique est : soustraction complexe cible moins fond, Hann symétrique, IFFT sur 3 216 points et facteur d'amplitude 16, sans correction du gain cohérent de Hann.

| Distance annoncée, cm | Premier maximum historique, cm | Second maximum historique, cm | Offset de pente de phase, cm |
|---:|---:|---:|---:|
| 50 | 69,914286 | 75,880305 | 21,337934 |
| 60 | 79,609067 | 86,320838 | 22,651894 |
| 70 | 90,422476 | 96,574934 | 22,567955 |

Les positions et niveaux du fichier `peak_summary.csv` sont reproduits exactement. Les offsets du fichier `echo_phase_slopes.csv` sont reproduits à moins de 1e-14 cm. Le traitement actuel reproduit aussi les profils à l'arrondi numérique ; il ne s'agit pas d'une incertitude expérimentale de cet ordre.

La phase est dépliée après retrait du trajet aller-retour géométrique. Les ajustements pondérés par la puissance donnent des retards résiduels de 1,423514, 1,511172 et 1,505572 ns. Le calcul utilise les radians ; les graphiques utilisent les degrés. Ces valeurs décrivent l'écho plaque moins fond, et non le S11 de l'antenne seule.

Pour retrouver les deux maxima du tableau historique, utiliser la règle du rapport (`mode_pics='rapport'`, sans interpolation). Leurs secondes proéminences sont seulement de 1,17 / 2,73 / 1,71 dB : elles ne passent pas le critère courant de 3 dB. Le maximum dominant change de branche entre 50 et 60 cm. Ces observations ne démontrent pas deux interfaces ou deux trajets physiques.

Le SHORT exporté présente un maximum de profil signé à 0 cm. Son module S11 varie d'environ -0,2166 à +0,0438 dB ; le pic IFFT proche de -6 dB provient de la Hann non normalisée. Il s'agit d'une nouvelle acquisition du standard utilisé pour la calibration, pas d'un standard métrologique indépendant. Acquis plus de cinq heures avant les plaques, il ne prouve pas la stabilité ultérieure du montage.

## Ce que ces données permettent de vérifier

Le paquet permet de reproduire les figures et tableaux du rapport, de contrôler la soustraction complexe et les conventions IFFT, et de conserver un cas expérimental réel pour le traitement. Les distances géométriques sont annoncées depuis la face avant du PCB, tandis que l'axe apparent est référencé au plan SOL : la différence de convention doit rester explicite.

Les dimensions de la plaque, les distances précises, les coefficients SOL et les caractéristiques du kit d'étalons manquent. La calibration du programme emploie des étalons idéaux. Les moyennes seules ne permettent pas de retrouver les dispersions entre balayages, les biais du kit ou les effets des reconnexions. Les observations de septembre et de l'antenne verte sont séparées dans le rapport et ne sont pas les acquisitions exportées ici.

La méthode B du dossier ajuste directement un modèle fréquentiel à gains complexes constants. Elle n'est pas la méthode des tableaux reproduits ci-dessus et ne retire pas automatiquement le retard de l'antenne. Une pente commune d'écho ne suffit pas à attribuer tout l'offset à la Nooelec.

## Intégration au projet PCBWay

Les exports S1P sont immédiatement lisibles avec [donnees.py](../donnees.py). Les en-têtes CSV `s11_real` et `s11_imag` ne sont pas encore acceptés par son lecteur CSV ; utiliser les S1P associés pendant le gel des sources. Une extension des alias CSV pourra être faite après les calculs, avec une vérification dédiée.

La campagne PCBWay utilise 213 points de 1 à 6,3 GHz. Le jeu historique s'arrête à 6 GHz : ne pas prolonger ou interpoler silencieusement ses mesures, son fond ou sa SOL. Les futures antennes demanderont de nouvelles acquisitions et une calibration couvrant la bande du [protocole PCBWay](../PROTOCOLE_MESURE_PCBWAY.md).

**Conclusion : ces fichiers fournissent un cas expérimental reproductible pour la chaîne de traitement du rapport. Ils ne constituent pas une mesure des nouvelles antennes, ni une validation de leur modèle électromagnétique.** Leur disponibilité complète utilement la reprise, sans remplacer la convergence des simulations de production et les mesures à venir.
