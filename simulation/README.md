# simulation — LiteVNA, antennes et plaque métallique

Projet Python/openEMS paramétrable pour simuler le montage du rapport destiné à
John : un port 50 Ω (le LiteVNA calibré au plan SOL), une antenne, et une
plaque métallique parallèle à son plan, à distance variable. Il sert aussi à
**concevoir et faire fabriquer** les antennes du projet.

Trois objectifs, dans cet ordre :

1. **simuler le principe physique** du montage et produire les figures du
   rapport ;
2. **reproduire quantitativement le décalage** observé sur les mesures réelles
   — 20,0 cm le 9 octobre, 36,5 cm le 17 septembre ;
3. **produire les fichiers de fabrication** des antennes, vérifiés par
   simulation avant d'être envoyés chez PCBWay.

## Organisation

```
simulation/
├── banc.py            paramètres : acquisition, plaque, maillage, mesures de référence
├── traitement.py      le traitement du rapport : profil, pics, phase, retard de groupe
├── modele.py          modèle analytique du montage, sans openEMS
├── fdtd.py            la scène openEMS, le maillage, l'exécution, le coût
├── donnees.py         lecture des CSV et Touchstone mesurés
├── figures.py         les figures 2 et 3 du rapport
├── run.py             point d'entrée, tous modes
│
├── apercu.py          dessine une antenne et contrôle son dessin   ─┐
├── export_gerber.py   écrit les Gerbers, le perçage et le ZIP       ├ fabrication
├── verifie_gerber.py  les relit avec gerbonara, qui n'est pas de nous ┘
├── export_dxf.py      l'ancien chemin, par KiCad (plus utilisé)
│
├── test_traitement.py les contrôles de la chaîne (à lancer en premier)
├── BACKLOG.md         les options écartées, et ce qui les ferait revenir
├── fabrication/       les deux commandes PCBWay, prêtes à déposer
└── antennes/
    ├── dipole_reference/     l'étalon du traitement
    ├── diamant_uwb/          l'étalon du modèle électromagnétique
    ├── diamant_uwb_x18/      le même, à l'échelle de notre bande
    ├── vivaldi_tomographie/  l'antenne de travail
    │   └── regle.py          balaie un paramètre et compare les |S11|
    └── uwb_surveyor/         l'antenne du banc
        └── mesures/<AAAA-MM-JJ>_<description>/
```

## État au 18/10/2026

| | |
|---|---|
| `traitement.py` | **vérifié** — `test_traitement.py` passe ses 16 contrôles |
| `modele.py` | **fonctionne** — modèle analytique, sans openEMS, instantané |
| `fdtd.py` | **fonctionne** — openEMS 0.37.0, environnement `openems` |
| **la chaîne de mesure** | **vérifiée** sur le dipôle : écart constant à 0,87 cm près, échelle juste à 1,2 % |
| **le modèle électromagnétique** | **validé** sur le losange publié : 2,30–13,60 GHz simulés contre 2,5–13,5 publiés, 85 % de couverture |
| le losange ×1,8 sur FR4 1,6 mm | **simulé** : −10 dB de 1,27 à 6,00 GHz, 87 % de couverture |
| la Vivaldi | **réglée** sur 21 essais : 71,4 % de la bande sous −10 dB, 94,1 % sous −6 dB, `\|S11\|` moyen −10,6 dB |
| **les fichiers PCBWay** | **écrits et relus par un tiers** — voir `fabrication/README.md` |
| l'UWB Surveyor | géométrie relevée sur la photo de la fiche technique, pas encore simulée |
| objectif (2) | **en attente des fichiers de mesure** |

## Neuf pièges, et ce qui les attrape maintenant

Ils ont dominé la mise au point, et **aucun n'était de la physique**. Chacun a
laissé derrière lui un contrôle automatique, parce qu'aucun ne s'était
signalé : la simulation tournait, rendait une courbe, et la courbe était
fausse.

| Origine | Effet | Ce qui l'attrape désormais |
|---|---|---|
| lignes de l'antenne et de l'air à 7 µm l'une de l'autre | pas de temps ÷ 1400 | `_fusionne()` |
| épaisseur de cuivre de 35 µm | cellules de 35 µm | cuivre en feuille d'épaisseur nulle |
| face arrière de plaque entre deux lignes | pas de temps ÷ 4 | épaisseur égale au pas de la grille |
| `SmoothMeshLines` finissant sa progression à 0,28 mm d'une ligne imposée | pas de temps ÷ 4 | `_nettoie_apres_lissage()` |
| grille régulière d'antenne tombant près des lignes fines | 96 min au lieu de 2 | ne donner que les lignes imposées |
| **domaine dimensionné sur la seule distance de plaque** | la PML absorbait le dernier tiers d'une antenne posée de chant | `construit()` déduit l'étendue en z des lignes de l'antenne |
| **polygone de normale y donné en (x, z) au lieu de (z, x)** | antenne simulée transposée, trois fois, sans aucun signe | `fdtd.verifie_emprise()` |
| ligne d'échantillonnage à 0,32 mm d'un bord de matière | pas de temps ÷ 2,4 | la géométrie écarte ses échantillons des bords |
| deux essais de réglage écrits dans le même fichier | le second effaçait le premier en silence | `regle.py` nomme par la configuration entière |

Les deux derniers sont les plus instructifs : ils ne ralentissaient pas la
simulation, ils ne la faisaient pas échouer. Ils rendaient simplement un
mauvais `|S11|`, qu'on pouvait prendre pour un défaut de conception — et deux
« corrections » de la Vivaldi ont été décidées sur ce bruit-là avant qu'on ne
remonte à la cause. D'où la règle qui s'en déduit : **avant de corriger une
conception, vérifier qu'on a bien simulé celle qu'on croit.**

## Installation

openEMS **est installé** sur cette machine :

| | |
|---|---|
| Paquet | `openEMS_x64_v0.37.0_msvc`, décompressé dans `..\outils\openEMS\` |
| Environnement | conda **`openems`**, Python 3.13 |
| Modules | `openEMS 0.37.0`, `CSXCAD 0.7.0` |
| Contrôle des Gerbers | `gerbonara`, dans l'environnement `ph` |

L'environnement `ph` est resté intact : les wheels Windows d'openEMS n'existent
que pour Python 3.13 et 3.14, et `ph` est en 3.12. **Les simulations se lancent
donc avec `conda activate openems`** ; le reste — contrôles, modèle analytique,
traitement des mesures, dessin et export de fabrication — tourne dans `ph`.

Pour refaire l'installation ailleurs :

```powershell
conda create -n openems python=3.13 numpy matplotlib h5py -y
conda activate openems
# ZIP officiel : https://github.com/thliebig/openEMS-Project/releases
python -m pip install --no-index --find-links <dossier>\openEMS\python openEMS
setx CSXCAD_INSTALL_PATH <dossier>\openEMS
```

`CSXCAD_INSTALL_PATH` doit désigner le dossier qui contient `CSXCAD.dll`.
`fdtd.py` le pose tout seul sur `..\outils\openEMS` s'il n'est pas défini.

## Utilisation

```powershell
python test_traitement.py                          # d'abord, toujours

python run.py --mode analytique                    # le principe, instantané
python run.py --mode analytique --derive -0.25 --cote-plaque 30 --bruit -70
python run.py --mode mesures --donnees antennes\uwb_surveyor\mesures\2026-10-09_plaque_50-70cm

python apercu.py --toutes                          # le dessin, avant la machine
python apercu.py --panneau losanges

conda activate openems
cd antennes\dipole_reference && python verifier.py # vérifier le programme
cd ..\.. && python run.py --mode fdtd-antenne --antenne diamant_uwb --fmax 14
python run.py --mode fdtd --antenne uwb_surveyor --distances 50 60 70
cd antennes\vivaldi_tomographie
python regle.py --parametre MARGE_OUVERTURE --valeurs 1.0 1.3

conda activate ph                                  # fabrication
python export_gerber.py --tout
python verifie_gerber.py fabrication\panneau_losanges\panneau_losanges_pcbway.zip
```

Tous les modes de `run.py` écrivent les trois mêmes figures — profils, phase,
écarts — et impriment le tableau du rapport, pour que modèle, simulation et
mesure se comparent ligne à ligne.

## Le traitement est celui du rapport, au chiffre près

```
R_k = S11_plaque(f_k) − S11_fond(f_k)
P_m = 16 · |IFFT_3216(w_k R_k)_m|          niveau affiché : 20 log10 P_m
d_m = c · m / (2 · 3216 · Δf)
```

Bande 1–6 GHz, 201 points, Δf = 25 MHz, Hann symétrique, remplissage 16, gain
cohérent **non** normalisé, 50 Ω. Pas d'axe 1,86 mm ; ce n'est pas la
résolution, qui vaut c/2B ≈ 3 cm.

`test_traitement.py` vérifie que la chaîne rend la distance qu'on y injecte à
2 mm près, et le retard injecté à 10⁻³ ns près.

## Ce que le modèle analytique montre déjà

1. **Un retard d'antenne produit un décalage rigoureusement constant.** Avec
   τ₁ = 0,667 ns, l'écart vaut 19,91 cm aux trois distances — la valeur mesurée
   le 9 octobre à 50 cm.
2. **Les deux branches de pics peuvent venir d'une seule antenne.** Traversée
   deux fois, elle produit trois échos à c·τ₁, c·(τ₁+τ₂)/2 et c·τ₂. Avec
   τ₂−τ₁ = 0,42 ns, les deux premiers tombent à 20,0 et 26,3 cm ; le troisième
   reste 30 dB plus bas. **Deux branches n'impliquent pas deux surfaces.**
3. **La dispersion seule n'explique pas la dérive de l'écart.** Elle élargit
   l'écho (5,8 → 8,2 cm à mi-hauteur) mais laisse le décalage constant. La
   dérive n'apparaît qu'avec une pondération qui change avec la distance :
   troncature de Fresnel d'une plaque trop petite, ou échos parasites.

## L'ordre de marche

1. `test_traitement.py` — la chaîne de traitement.
2. `antennes/dipole_reference/verifier.py` — **le traitement de bout en bout**,
   sur une antenne dont le retard est nul par construction. Si une plaque posée
   à 30 cm n'est pas lue à 30 cm, inutile d'aller plus loin.
3. `run.py --mode fdtd-antenne --antenne diamant_uwb --fmax 14` — **le modèle
   électromagnétique**, sur une conception publiée : notre |S11| doit retrouver
   la bande 2,5–13,5 GHz de l'article.
4. `apercu.py` avant toute simulation d'une antenne dessinée ici — une
   simulation coûte des minutes, un dessin une seconde.
5. `run.py --mode fdtd-antenne --antenne uwb_surveyor` — l'antenne du banc
   seule, à comparer à la courbe de ROS de sa fiche technique.
6. `run.py --mode fdtd` — avec la plaque, puis confrontation aux mesures.

**Une série se simule d'un bloc.** `fdtd.serie()` impose à toutes les
simulations d'une campagne le même maillage et le même nombre de pas. Sans
cela, chaque simulation s'arrête sur son propre critère d'énergie, et la
différence `S11_plaque − S11_fond` n'est plus que l'écart entre deux
troncatures. C'est la transposition de la règle de mesure : un fond ne vaut que
pris dans la même configuration.

## Les limites à garder en tête

- **La géométrie de l'UWB Surveyor est approximative.** Reproduire 20 cm en
  ajustant un retard ne prouverait rien : c'est leur origine physique qu'on
  cherche.
- **L'environnement n'est pas modélisé.** Les mesures ont été faites sur une
  table, sans absorbant. Le modèle analytique accepte des échos fixes ; la FDTD
  ne verra qu'un montage idéal.
- **Le câble n'est pas simulé**, et c'est volontaire : la calibration SOL le
  retire. Un tronçon resté en aval du plan de calibration est une hypothèse à
  écarter côté mesure, pas côté simulation.
- **Les deux campagnes ne donnent pas le même décalage** — 20,0 et 36,5 cm pour
  la même antenne. Aucune simulation ne peut expliquer les deux à la fois : la
  différence est en aval du plan de calibration, ou dans le traitement d'un de
  ces jours-là.
- **Les trous de fixation ne sont pas simulés.** Ceux de la Vivaldi traversent
  le plan de masse à 60 mm du ruban : l'effet est nul à ces fréquences, mais
  c'est une différence entre la carte simulée et la carte commandée.
