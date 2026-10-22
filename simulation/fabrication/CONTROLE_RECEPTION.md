# Contrôles à réception des antennes

Cette procédure vise la conformité physique des deux articles commandés. Elle prépare la comparaison aux calculs de la même révision ; elle ne présume ni une bande S11 obtenue ni un accord simulation/mesure.

## Réception avant soudure

1. Conserver la confirmation de commande, la référence du lot, le ZIP réellement envoyé et son SHA-256. Vérifier la quantité : 5 panneaux complets avec deux losanges chacun, et 5 Vivaldi pour les quantités proposées.
2. Photographier chaque face et la tranche, avec une règle et un identifiant d'exemplaire. Utiliser des étiquettes amovibles hors zones rayonnantes ; ne pas ajouter de marquage permanent sur le cuivre ou les fentes.
3. Relever la référence du stratifié **S1000H**, la construction fournie si connue, le cuivre final et les épaisseurs Ni/Au de l'ENIG. Archiver les éventuelles substitutions ou réserves de fabrication. Les valeurs Dk/Df de fiche ne sont pas des mesures du lot.
4. Vérifier visuellement l'absence de masque et de sérigraphie sur les deux faces, y compris les fentes et le FR4 nu. Rechercher rayures, surgravure, cuivre manquant, bavures, délamination et ponts de cuivre. Comparer aux PNG des couches relues dans les dossiers `verification/`.
5. Mesurer au pied à coulisse les dimensions extérieures, puis l'épaisseur finie à plusieurs endroits, surtout au bord SMA. Ne pas déduire exactement l'épaisseur diélectrique d'une mesure globale sans connaître cuivre et finition. Conserver les valeurs, la résolution de l'instrument et les tolérances convenues.

| Mesure nominale | Valeur à retrouver dans les tolérances de la commande |
|---|---|
| Panneau | 92,600 × 72,000 mm |
| Petit losange après séparation | 32,000 × 40,000 mm |
| Grand losange après séparation | 57,600 × 72,000 mm |
| Vivaldi | 143,668736 × 280,903102 mm |
| Fraisage central | 3,000 mm |
| Pontets | Deux zones de 3,000 mm de haut |
| Pad signal SMA, chaque antenne | 2,286 mm de large sur 5,080 mm depuis le bord |
| Ouverture entre bords intérieurs du cuivre, bouche Vivaldi | 107,068736 mm |
| Retrait du cuivre Vivaldi hors bord SMA | 0,300 mm aux côtés et à la bouche |

Au microscope ou à la loupe graduée, relever également les largeurs de lignes et l'alignement des faces. Le chiffre nominal d'une cote n'est pas son critère de réception : utiliser la tolérance acceptée lors de la revue CAM et relever les écarts, même s'ils restent acceptables.

## Perçages et continuité électrique

Le panneau comporte **16 NPTH de 0,600 mm** et **4 PTH de 0,457 mm fini**. La Vivaldi comporte **2 NPTH de 3,000 mm** et **2 PTH de 0,457 mm fini**. Vérifier les perçages ouverts et l'absence de résine. La métallisation concerne uniquement les petits vias de masse SMA.

Avec un multimètre et des pointes adaptées, avant soudure :

1. Chaque patte de masse supérieure doit être reliée au plan de masse inférieur par son via. Contrôler les deux pattes, séparément.
2. Le pad signal supérieur doit rester isolé de ces masses en courant continu. Une continuité indique un pont ou un défaut, à photographier avant toute retouche.
3. Contrôler l'absence de cuivre sur les parois des NPTH. Pour les amorces sur le bord d'un fraisage, une observation au microscope est préférable à une mesure électrique seule.

Les vias finis demandés sont nominalement à `x = ±4,318 mm` et à `u = 5,969 mm` du bord SMA, dans le repère propre de chaque antenne. Le perçage Excellon est arrondi à 0,457 mm, contre 0,4572 mm dans le catalogue.

## Séparation et montage

Séparer les deux losanges hors tension, avec un outil approprié et un maintien qui ne fléchit pas les radiateurs. Protéger les yeux et limiter les poussières de FR4 lors de l'arasage. Araser les restes de pontets au contour nominal rectangulaire, sans mordre le cuivre, puis nettoyer et photographier les deux chants obtenus. Conserver un relevé si des restes de substrat subsistent : la simulation individuelle ne les contient pas.

Présenter à sec le **Cinch/Johnson 142-0701-851 femelle** sur chaque bord SMA. La carte doit se placer dans le logement sans forcer ni soulever la broche centrale. Le catalogue est donné pour un PCB nominal de 0,062 pouce ; le plan mécanique indique un logement de 0,068 ± 0,007 pouce. L'épaisseur locale et la planéité effectivement livrées doivent donc être contrôlées, pas seulement la case « 1,6 mm » de la commande.

Aligner l'axe du connecteur avec le pad central. Souder signal et masses selon les recommandations du fabricant, avec une position reproductible, puis nettoyer le flux. Photographier la jonction et relever la référence du connecteur, l'exemplaire, l'alliage, la méthode et toute retouche. Refaire les contrôles de continuité et d'isolation après soudure.

## Dossier à conserver pour les mesures

Pour chaque exemplaire : identifiant, article/lot, ZIP et SHA-256, dimensions et épaisseurs relevées, photos avant/après montage, contrôle de continuité, référence SMA et remarques de soudure. Joindre le bilan de simulation de **la même révision physique** et les limites de son port idéal. Les campagnes historiques restent des éléments de développement.

Appliquer ensuite le protocole de mesure du projet en conservant les données **complexes** S11, la grille de fréquences, la calibration, les câbles, adaptateurs, orientation et environnement. Le plan coaxial de calibration et le bord PCB du port simulé doivent être explicitement distingués. La comparaison des antennes seules précède l'interprétation des échos avec plaque.

En cas d'écart, conserver d'abord les données brutes et les photos. Une tolérance de matériau, une transition SMA, un écart de gravure et une erreur numérique peuvent se cumuler ; le seul décalage d'une résonance ne permet pas de les départager.
