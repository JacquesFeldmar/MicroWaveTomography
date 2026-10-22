# Décision après le contrôle N34 — 19 octobre 2026

La campagne F1 ne qualifie pas les deux articles PCBWay : les contrôles du petit losange et de la Vivaldi passent, mais le grand losange échoue encore au contrôle spatial N30/N34. Ses critères temporels et sa passivité passent. Le maximum complexe spatial vaut 0,069426408 à 4,250 GHz et le percentile 95 du module 1,076518714 dB ; les limites restent 0,05 et 1 dB. Les rapports et les 25 profils F1 sont conservés.

## Constats et portée

Les grilles N30/N34 sont reconstruites indépendamment. Certaines cellules proches du port grossissent malgré le raffinement nominal. La grille ne préserve pas toutes les coordonnées des arêtes internes du cuivre : les boîtes englobantes des primitives sont fixes, tandis que des indications de maillage issues des contours peuvent être déplacées par la redistribution. Les vias de 0,4572 mm restent décrits par deux cellules dans chaque direction du plan. Le point de tension nominal x = 0 est échantillonné à des positions transverses différentes ; il ne s'agit pas d'un déplacement du plan VNA le long de la ligne.

Ces observations établissent des limites du contrôle spatial actuel. Elles n'isolent pas à elles seules la cause de chaque variation de S11. Les constructions diagnostiques N38/N42 gardant l'air et la cible locale constants laissent encore varier des cellules critiques. Elles n'ont pas été exécutées par le solveur.

La documentation openEMS distingue l'alignement exact du **plan** d'une feuille métallique de la résolution de ses **arêtes dans le plan**, pour lesquelles elle recommande un placement de mailles adapté aux singularités. Cette distinction guide le prototype ; elle ne constitue pas une validation de ses résultats. [Documentation officielle du maillage](https://docs.openems.de/en/latest/concepts/mesh.html).

## Maillage retenu pour la nouvelle campagne

Un moteur distinct, `fdtd_maille_controlee.py`, est préparé à partir d'une copie contrôlée de F1. Les neuf sources physiques historiques, les contours PCB, le matériau nominal et le modèle de connecteur restent inchangés. Le moteur F2 sera lui-même la dixième source physique archivée. L'identifiant `maillage_controle_v2` devra être présent dans le manifeste et dans l'entrée de qualification.

Avant tout calcul long, les six grilles base/fin des trois antennes doivent démontrer :

- des dimensions physiques constantes du bloc fin entourant le port et du domaine extérieur, avec limites PML définies ;
- un échantillonnage de tension centré et une position effective de courant contrôlée sur la grille duale ;
- une résolution explicitement croissante des vias et des zones critiques du cuivre ;
- un maillage déterministe, identique entre les fenêtres temporelles d'un même niveau, avec rapports de cellules et pas admissibles vérifiés ;
- un coût calculé sur les grilles réelles, puis un petit essai opérateur et un préfixe réellement extrait et rejoué.

La variante 10 est retenue après construction native des six grilles et contrôle exhaustif des intervalles. Les configurations sont `base = 16/16/0,15 mm` et `fin = 24/16/0,10 mm` (résolution par longueur d'onde substrat/air, puis cible locale). Les vias passent de quatre à six cellules et l'épaisseur du substrat de onze à dix-sept cellules. La tension est échantillonnée sur la primaire x = 0 ; la sonde de courant reste centrée à h/2 sur la grille duale. Les arêtes rectilignes retenues sont des primaires exactes ; il ne s'agit pas d'une application générale de la règle des tiers.

Les lignes primaires de base sont conservées dans les projections du PCB hors des blocs SMA. Dans ces blocs, les interpolations non physiques peuvent être redistribuées, tandis que les interfaces, les vias et la zone uniforme du port restent fixes. Aucun intervalle ne grossit dans les projections du PCB ni dans les blocs SMA. L'air extérieur peut redistribuer ses cellules ; les huit cellules de chaque PML et leurs coordonnées restent identiques entre niveaux. Ce contrôle porte sur le maillage et ne démontre encore aucune convergence de S11.

| Antenne | Cellules base | Cellules fines |
|---|---:|---:|
| Petit losange | 3 005 640 | 7 566 780 |
| Grand losange | 3 722 400 | 10 030 398 |
| Vivaldi | 9 548 352 | 27 169 776 |

Une copie complète du moteur a reproduit les six NPZ de la variante 10 octet par octet, pour des fenêtres de 12 et 16 ns. Ces douze constructions n'exécutent pas le solveur. La Vivaldi fine est estimée à 28–40 heures pour 16 ns ; les six calculs longs représentent environ 46–65 heures de solveur cumulées. Ces estimations doivent être rapprochées du pas opérateur et de la vitesse réellement observés. Voir la [preuve native](staging_moteur_controle_v2/preuve_native_f2_grilles.json).

Le schéma de campagne envisagé comporte, par antenne, un calcul base de 12 ns et un calcul fin de 16 ns. Les préfixes base 8 ns et fin 8/12 ns donneraient cinq profils, soit quinze au total. La comparaison spatiale porterait sur base 12/fin 12 ns et la comparaison temporelle sur fin 12/16 ns. Les deux comparaisons initiales de 8/12 ns resteraient des préliminaires explicites. Cette sélection reste conditionnelle aux résultats ; tous les seuils existants sont conservés.

## Provenance, relecture et livraison

Q devra reconnaître uniquement les deux moteurs connus, contrôler leurs marqueurs et comparer l'intégralité de leurs sources. La voie de calcul F1 devra refuser une archive F2 et réciproquement. L'extracteur de préfixe devra utiliser le moteur archivé déclaré, puis vérifier les grilles reconstruites, les matériaux et la reproduction du S11 parent.

La qualification contrôlera directement les tableaux de maillage des paires temporelles et refusera de mélanger les moteurs entre les trois antennes. Les résultats F1 demeurent un historique distinct ; ils ne seront pas présentés comme des résultats F2. Le PDF et la livraison finale seront produits après la réussite de la campagne retenue et des vérifications de fabrication et de portabilité.

La campagne F1 complète est fermée dans [son archive](../archives/campagne_F1_cloture_2026-10-19.zip) : 25 profils, sources et preuves, SHA-256 `a2d63d75a664b35289a13f3a46747469292b7c52fff1c8a8e3f5cb7461eb56b9`. Le CRC et les empreintes de chaque membre ont été vérifiés avant la promotion des outils F2. Les anciens helpers qui imposent les 17 anciens SHA doivent être rejoués avec ces sources archivées.

## Mise en œuvre et état au lancement

Ces exigences sont intégrées dans Q/W/AP. Le moteur final F2 porte le SHA-256 `3906a789d3dc69439c5ef354c4d65e394a3e35c2a36ed092acc675b18cde1da1` ; ses fonctions de construction restent exactes à celles vérifiées sur les six NPZ. Une garde avant CalcPort refuse les statistiques ou sondes tronquées sans modifier les équations, le pas ou les grilles.

Le pilote réel de 3,5 ns est terminé avec code 0, 19 347 pas et dt = 1,8091917271563098 × 10⁻¹³ s. Son préfixe de 2 ns et son rejeu déplacé sont validés ; les fichiers S1P du préfixe sont identiques octet par octet. Cette vérification porte sur l'opérateur et le rejeu, pas sur la convergence d'une antenne.

La campagne longue est lancée le 19 octobre à 17:21:29 UTC (19:21:29 à Paris) dans `resultats/pcbway_maille_controlee_v2/`. Deux files produiront les quinze profils retenus ; l'analyse se déclenchera automatiquement après la réussite technique des deux files. Les dix sources physiques et huit contrôles sont gelés. Le [suivi courant](../TACHES_REPRISE_PCBWAY.md#état-courant) indique les preuves, processus et tâches restantes.

Les Gerbers existants restent les dessins candidats. Aucune commande n'a été passée sur PCBWay.
