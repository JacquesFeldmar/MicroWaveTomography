# Simulation et fabrication des antennes PCBWay

La reprise du 18 octobre 2026 prépare deux articles : un panneau comprenant les deux monopôles en losange, et une Vivaldi seule. Le même dessin de cuivre alimente les simulations et les exports Gerber. La campagne de qualification de cette révision est en cours ; les chiffres de l'ancienne révision ne qualifient pas ces fichiers.

**Qualification globale non acquise : aucune livraison finale validée.** Les six calculs longs F2, les neuf préfixes et l'analyse automatique sont terminés depuis le 22 octobre à 06:12 à Paris. Les trois antennes passent leurs contrôles temporels mais échouent à la convergence spatiale. Les quinze profils sont [archivés avec leurs sources exactes](archives/campagne_F2_cloture_non_convergente_2026-10-22.zip). Le diagnostic de l'opérateur discret se poursuit, sans changement des dessins PCB ni des seuils. Les 25 profils F1 restent un [historique distinct](archives/campagne_F1_cloture_2026-10-19.zip). Voir [le suivi](TACHES_REPRISE_PCBWAY.md#état-courant).

Le suivi et les critères de livraison figurent dans [TACHES_REPRISE_PCBWAY.md](TACHES_REPRISE_PCBWAY.md). Les sources et résultats antérieurs sont conservés dans [l'archive initiale](archives/etat_avant_reprise_2026-10-18.zip), avec les [audits et la réponse de Claude](chatGPT_critical_review/).

Les calculs terminés ne constituent donc pas une qualification de fabrication. Les écarts entre maillages doivent être compris et résolus avant livraison. Deux inspections natives du petit losange sont effectuées sans intégration temporelle ; elles produisent les dumps du cuivre effectif, des coefficients et des boîtes de sondes pour ce diagnostic. Leur CAD XML archivé comporte des arrondis, dont la portée sera explicitée dans l'interprétation.

## Cartes et hypothèses physiques

| Carte individuelle | Dimensions du contour médian | Implantation |
|---|---|---|
| Losange ×1 | 32 × 40 mm | SMA femelle Cinch Johnson 142-0701-851 |
| Losange ×1,8 | 57,6 × 72 mm | Même SMA |
| Vivaldi | 143,668735 × 280,9031025 mm | Même SMA et deux trous de fixation non métallisés |

Les losanges sont réunis dans un panneau de 92,60 × 72,00 mm. Les simulations S11 portent sur les **cartes individuelles après séparation**, sans couplage avec l'autre losange. Voir [fabrication/README.md](fabrication/README.md) pour les paramètres de commande.

Le nominal commun est un FR-4 S1000H de 1,6 mm, deux couches cuivre 1 oz, finition ENIG, sans vernis épargne ni sérigraphie. Le modèle diélectrique de Debye est ajusté sur les valeurs typiques documentées à 1 GHz : ε′ = 4,6 et tan δ = 0,011. Son extrapolation en fréquence est une hypothèse causale, pas une mesure du lot fabriqué. Le cuivre est une feuille PEC ; le nickel, l'or, la rugosité, le corps du connecteur et les soudures ne sont pas résolus en 3D. Ces limites interviennent dans l'interprétation de l'écart simulation/mesure.

La garde cuivre/bord de la Vivaldi est de 0,30 mm hors alimentation. Ses perçages de fixation sont présents dans le modèle. Les vias de masse de l'implantation SMA sont représentés par des cylindres PEC équivalents. La transition du pad SMA vers les lignes de 3,0/3,1 mm est propre à ces cartes. L'épaisseur de 1,6 mm du modèle est celle du diélectrique ; l'épaisseur finie réellement livrée doit être distinguée et relevée à réception.

## Organisation

| Fichier ou dossier | Fonction |
|---|---|
| `antennes/*/geometrie.py` | Contours, perçages et construction CSXCAD |
| `connectique.py`, `materiaux.py` | Implantation SMA commune et matériau dispersif |
| `banc.py`, `fdtd.py` | Paramètres, maillage, exécution, archives et coût |
| `fdtd_maille_controlee.py`, `calcule_maille_controlee.py` | Moteur F2 séparé et lancement avec sources et contrôles archivés |
| `orchestre_f2.py` | Deux files longues, préfixes et analyse globale différée, sans import du solveur |
| `qualifie_pcbway.py` | Campagne S11, comparaison des maillages et des durées |
| `qualification_adaptative.py` | Sélection explicite des comparaisons par antenne et conservation des essais préliminaires |
| `resultats/pcbway_r1/` | Campagne historique F1, incluant l'échec spatial N34 |
| `resultats/validation_maille_controle_v2/` | Pilote opérateur et rejeu F2, sans qualification de convergence |
| `resultats/pcbway_maille_controlee_v2/` | Destination séparée de la campagne longue F2 |
| `export_gerber.py`, `verifie_gerber.py`, `apercu.py` | Génération, relecture indépendante et contrôles géométriques |
| `fabrication/` | Deux articles PCBWay et leurs notices |
| `PROTOCOLE_MESURE_PCBWAY.md` | Acquisition et comparaison aux antennes fabriquées |
| `traitement.py`, `donnees.py`, `run.py`, `figures.py` | Analyse des mesures et du montage avec plaque |
| `modele.py` | Modèle analytique du montage avec plaque |
| `references/` | Fiches techniques du stratifié et de la SMA |
| `chatGPT_critical_review/` | Audit initial, réponse et décisions de reprise |

## Environnements et contrôles

La machine utilise Python 3.13 dans l'environnement conda `openems`, avec openEMS 0.37.0 et CSXCAD 0.7.0. Le dessin, la fabrication et les traitements peuvent tourner sous Python 3.12 dans `ph`. Les dépendances sont consignées dans `requirements_fdtd.txt` et `requirements_fabrication.txt`. `fdtd.py` recherche les bibliothèques dans `../outils/openEMS` si aucun chemin n'est fourni.

Depuis `simulation/` :

```powershell
# Environnement ph
python -B test_traitement.py
python -B -m unittest test_donnees test_run -v
python -B -m pytest -q -p no:cacheprovider test_fabrication.py
python -B apercu.py --toutes
python -B export_gerber.py --tout
python -B verifie_gerber.py fabrication/panneau_losanges/panneau_losanges_pcbway.zip fabrication/vivaldi_tomographie/vivaldi_tomographie_pcbway.zip

# Environnement openems
python -B -m unittest discover -s tests -v
# Estimation F2 uniquement ; la campagne réelle est déjà orchestrée séparément.
python -B calcule_maille_controlee.py --antenne diamant_uwb --niveau base --duree-ns 12 --fils 10 --cout
```

Chaque calcul exige un dossier neuf. Il conserve les sources, XML, grilles, matériaux, sondes temporelles, versions et empreintes SHA-256. Le pas temporel est déterminé par le véritable opérateur openEMS, puis contrôlé sur les sondes. Les paramètres de maillage fixent la résolution dans l'air et le substrat ; les interfaces restent exactes et la graduation finale est bornée à 1,5. Voir [la note technique du moteur](chatGPT_critical_review/note_moteur_fdtd_reprise_2026-10-18.md).

## Qualification et références S11

La campagne couvre 1,000 à 6,300 GHz par pas de 25 MHz, soit 213 points. Elle compare un maillage de base à un maillage fin, puis deux fenêtres de durée sur le même maillage fin. Le préfixe de sondes d'un calcul de 12 ns peut fournir exactement les échantillons d'une fenêtre de 8 ns : cette dérivation est identifiée et conserve sa provenance. Elle ne constitue pas une seconde exécution du solveur.

Les critères sont fixés avant lecture des résultats : écarts complexes maximal/RMS de 0,05/0,02 pour le raffinement spatial et 0,015/0,005 pour le prolongement temporel ; le percentile 95 des écarts de module doit rester sous 1 dB et 0,5 dB respectivement, lorsque les deux modules dépassent −20 dB. Le module doit rester passif à la tolérance numérique près. Une convergence échouée appelle un calcul supplémentaire ; elle ne devient pas une qualification par modification des seuils.

`qualification_adaptative.py` permet de sélectionner explicitement les calculs retenus pour chaque antenne dans `selection_qualification.json` à la racine de sa campagne. La paire spatiale conserve la même durée ; la paire temporelle conserve le même maillage et le même pas, avec un prolongement d’au moins 4 ns. Le calcul fin spatial doit appartenir à la paire temporelle, dont le dernier calcul fournit la référence. Les paires restent ainsi reliées. La référence ne peut être plus courte qu’un calcul préliminaire ; une adaptation restant à la durée initiale de 12 ns doit affiner réellement le niveau fin. Les essais préliminaires, leurs motifs, leurs écarts recalculés et leurs éventuels échecs sont conservés avec toutes les preuves. Aucun seuil n’est assoupli.

La campagne reste en cours : une durée prolongée ne devient une référence de livraison qu’après réussite des comparaisons retenues. Un brouillon peut être préparé **hors du dossier de résultats** puis validé structurellement, sans lancer de FDTD :

```powershell
python -B -X utf8 qualification_adaptative.py --creer-selection brouillons/selection_20ns.json --adapter vivaldi_tomographie --duree-ns 20 --depuis-ns 16 --motif "Sensibilité temporelle à évaluer avec une fenêtre prolongée"
python -B -X utf8 qualification_adaptative.py --valider-selection brouillons/selection_20ns.json
```

Ces durées illustrent une préparation, sans présumer de sa réussite. `--selection-source <ancien_brouillon.json>` conserve aussi les comparaisons d’une sélection précédente. La création exige un fichier neuf ; la validation porte uniquement sur la structure, les profils et le chaînage des paires. La sélection définitive sera figée après les calculs en cours, avec son instantané et son SHA-256.

Les références livrées comprennent S11 complexe en Touchstone, CSV, impédance, phase, bandes disjointes sous −10/−6 dB, sondes et manifestes. Le plan idéal est le bord du PCB. La [procédure de mesure](PROTOCOLE_MESURE_PCBWAY.md) explique la comparaison au plan de connexion SMA réel.

L'outil [compare_s11.py](compare_s11_usage.md) superpose ensuite les S1P mesurés et la référence, conserve les originaux et quantifie les écarts ainsi que la dispersion des reconnexions. Il ne recale pas automatiquement la phase et ne transforme pas ces écarts en verdict physique.

## Montage avec plaque et traitements historiques

`run.py` conserve les modes analytique, mesures, antenne seule et série FDTD avec plaque. Une série FDTD impose un maillage, un pas et une durée communs au fond et à toutes les positions. Les imports exigent des fréquences finies, croissantes et régulièrement espacées, des valeurs complexes finies et une référence de 50 Ω.

Le modèle analytique est un générateur d'échos à amplitudes heuristiques : il peut dépasser |S11| = 1 et ne prédit pas un coefficient de réflexion passif normalisé. Il sert à contrôler les retards et les hypothèses de traitement, séparément des calculs électromagnétiques de production.

Le profil de distance utilise la différence complexe plaque/fond, une fenêtre de Hann et un remplissage de zéros. Le maximum principal est distingué des candidats secondaires ; un lobe secondaire de la fenêtre ne prouve pas la présence d'une seconde surface. Le mode historique de sélection des pics reste accessible explicitement avec `--mode-pics rapport` pour reproduire un ancien rapport. Les comparaisons aux valeurs du 9 octobre sont elles aussi explicites avec `--reference-9-oct`.

Les décalages historiques de 20,0 et 36,5 cm ne sont pas expliqués par la seule géométrie approximative de la Nooelec. Les fichiers bruts, la calibration, les plans de référence et le traitement doivent être confrontés. Cette enquête reste distincte de la qualification S11 des trois cartes à fabriquer. Le dipôle et le losange publié apportent des contrôles partiels ; ils ne démontrent pas, à eux seuls, l'exactitude de toute la chaîne électromagnétique.
