# antennes — une antenne, un dossier

```
antennes/
└── <nom_de_l_antenne>/
    ├── fiche.md          ce qu'on sait d'elle, et d'où on le sait
    ├── geometrie.py      sa géométrie openEMS, et son retard attendu
    └── mesures/
        └── <AAAA-MM-JJ>_<description>/    une campagne d'acquisition
            ├── manifeste.md               ce qui a été mesuré, et comment
            ├── background.s1p             la scène vide
            └── plate_50cm.s1p …           une position de plaque par fichier
```

**Une campagne = un dossier.** Le critère est celui du rapport pour John : les
fichiers d'une même campagne partagent la **même grille de fréquences**, le
**même fond** et les **mêmes coefficients SOL**. Dès que l'un des trois change
— recalibration, autre bande, autre jour — c'est une autre campagne, donc un
autre dossier. Mélanger deux campagnes, c'est comparer des distances mesurées
depuis deux plans de référence différents.

`donnees.charge_dossier()` lit un dossier de campagne : il y cherche un fichier
dont le nom contient `background`, et des fichiers `plate_<n>cm`. Les formats
acceptés sont le CSV (`f_Hz, réel, imaginaire`) et le Touchstone `.s1p`
(`# Hz S RI R 50`).

```powershell
python run.py --mode mesures --donnees antennes\uwb_surveyor\mesures\2026-10-09_plaque_50-70cm
```

## Le module `geometrie.py`

Chaque antenne expose la même interface, pour que `fdtd.py` n'ait rien à savoir
d'elle :

| | | |
|---|---|---|
| `NOM`, `DESCRIPTION` | identité | obligatoire |
| `pose(csx, fdtd, acq)` | construit la géométrie, rend `(port, lignes_x, lignes_y, lignes_z, demi_étendue_xy_mm)` | obligatoire |
| `retard_attendu_ns()` | le retard aller simple attendu, ou `None` s'il est inconnu | obligatoire |
| `cotes()` | toutes les cotes, en mm | facultatif |
| `bande_attendue_ghz()` | la bande annoncée, tracée sur la figure | facultatif |
| `s11_fiche()` | `(freqs, S11)` relevé sur une fiche technique, pour recalage | facultatif |
| `contours_mm()` | `{"F_Cu": [...], "B_Cu": [...], "Edge_Cuts": [...]}`, polylignes de `(x, y)` en mm | pour fabriquer |
| `percages_mm()` | `[(x, y, diamètre), ...]` | pour fabriquer |
| `controles_fabrication()` | les cotes à vérifier avant de commander | pour fabriquer |
| `RECOUVREMENT_MAX_MM` | recouvrement toléré entre les deux cuivres | facultatif |

`retard_attendu_ns()` est ce qui rend la vérification possible : c'est la
valeur que la mesure simulée doit retrouver.

`pose()` rend son demi-encombrement **en x et en y seulement**. L'étendue en z
se déduit des lignes qu'elle impose, parce qu'une antenne posée de chant —
une Vivaldi — s'étend de 280 mm le long de l'axe de rayonnement. Tant que
`construit()` déduisait l'étendue en z de la seule distance de plaque, la PML
tombait sur la bouche de l'antenne et en absorbait le dernier tiers.

### Un piège de CSXCAD, qui n'est écrit nulle part

Pour un polygone de normale `n`, **les deux coordonnées sont lues dans les axes
`(n+1, n+2) modulo 3`** :

| normale | coordonnées attendues |
|---|---|
| `norm_dir=0` (x) | `(y, z)` |
| `norm_dir=1` (y) | **`(z, x)`** |
| `norm_dir=2` (z) | `(x, y)` |

Les antennes planaires du projet sont toutes en normale z, donc en `(x, y)`,
ce qui est l'ordre naturel : elles n'ont jamais été touchées. La Vivaldi, posée
de chant, est en normale y — et a été simulée **trois fois transposée**,
279 mm de large pour 143 de long. Rien ne le signalait : ni openEMS, ni le
maillage, ni le `|S11|`, qui était seulement mauvais. Deux corrections de
conception ont été décidées sur ce bruit-là.

D'où `fdtd.verifie_emprise()`, appelé juste après `pose()` : il refuse toute
matière posée hors du volume que l'antenne annonce. Le contrôle coûte une
milliseconde et ferme la faute pour de bon.

## Les antennes présentes

| Dossier | |
|---|---|
| `dipole_reference/` | **l'étalon du traitement** : un dipôle dans le vide, sans substrat ni ligne, dont le retard est nul par construction. Il vérifie que la chaîne lit une plaque là où elle est. |
| `diamant_uwb/` | **l'étalon du modèle électromagnétique** : monopôle en losange, conception publiée et entièrement cotée, dont le S11 est connu (−10 dB de 2,5 à 13,5 GHz). |
| `diamant_uwb_x18/` | le même, à l'échelle 1,8, pour la bande du LiteVNA. Ne recopie aucune cote : il charge le précédent et n'en change que l'échelle. |
| `uwb_surveyor/` | l'antenne du banc, Nooelec UWB Surveyor. Géométrie approximative, à recaler. |

## De la simulation à la fabrication

Les cotes n'existent qu'à **un** endroit, le `geometrie.py` de l'antenne.
Trois outils en dérivent tout le reste, et chacun contrôle le précédent :

```powershell
python apercu.py --toutes                       # le dessin, et ses pièges
python export_gerber.py --tout                  # les fichiers PCBWay
python verifie_gerber.py fabrication\*\*_pcbway.zip   # relus par un tiers
```

| | |
|---|---|
| `apercu.py` | dessine les contours et mesure le cuivre par tranche. Une simulation coûte des minutes, un dessin une seconde : c'est là qu'on attrape un conducteur qui se pince, un cuivre hors carte, un recouvrement de trop. |
| `export_gerber.py` | écrit directement le jeu RS-274X + Excellon + le ZIP. Pas d'étape KiCad : c'était le seul endroit où les cotes fabriquées pouvaient diverger de celles qui ont été simulées. |
| `verifie_gerber.py` | relit le ZIP avec `gerbonara`, qui n'est pas de nous, compare les encombrements aux cotes annoncées et produit un rendu SVG. |

`export_dxf.py` reste disponible pour qui veut reprendre le dessin dans KiCad,
mais ce n'est plus le chemin de production.
