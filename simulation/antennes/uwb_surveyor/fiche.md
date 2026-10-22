# Nooelec UWB Surveyor du banc

L'UWB Surveyor est l'antenne commerciale utilisée sur le banc. La [fiche Nooelec révision 1](../../uwb_surveyor_datasheet_revision_1.pdf) documente l'encombrement de 120 × 120 × 0,8 mm, une bande annoncée de 700 MHz à 10 GHz et une SMA femelle standard. L'exemplaire décrit dans le projet porte le marquage v1.0b2, 2025-10-15.

## Géométrie approximative

La fiche ne fournit pas les cotes détaillées des conducteurs ni l'empilement diélectrique complet. [geometrie.py](geometrie.py) conserve un modèle relevé sur photo : disque tronqué de rayon 83,5 mm, centre à y = 92,7 mm, ligne de 1,5 mm et longueur d'alimentation dérivée de 69,2 mm. Les anciennes valeurs de 46 et 38 mm présentes dans la fiche précédente ne correspondent plus au code. Ces valeurs restent des estimations, pas des cotes Nooelec certifiées. Le matériau de ce module historique conserve εr = 4,4 et une conductivité ajustée au centre de la bande ; il n'utilise pas le nouveau contrat S1000H des PCB de production.

Une confrontation au S11 et aux dimensions de l'exemplaire est nécessaire avant d'interpréter les retards simulés. Une courbe de ROS seule ne détermine pas de façon unique cette géométrie ni sa phase. La scène actuelle place la carte dans le plan xy et une plaque parallèle à une distance en z ; l'orientation doit être confrontée au montage et au diagramme réels.

## Retards historiques

Le retard calculé pour la seule ligne approximative est de 0,421 ns, soit environ 12,62 cm sur l'axe de distance. Il ne fournit ni une borne inférieure rigoureuse du pic large bande, ni une borne supérieure du retard total. Résonances, couplages, centre de phase, environnement et traitement peuvent intervenir ; deux traversées de la largeur de la carte ne bornent pas ces effets.

Les décalages de 20,0 cm et 36,5 cm rapportés dans les deux campagnes historiques doivent être examinés à partir des données complexes, des calibrations, de la sélection des pics et des plans de référence. Il n'est pas établi qu'un même mécanisme physique explique ces deux chiffres. Les campagnes sont distinctes et ne doivent pas être mélangées.

La première fabrication concerne les deux losanges et la Vivaldi, pas une copie de cette Nooelec. La qualification de ces cartes et leur [protocole de mesure](../../PROTOCOLE_MESURE_PCBWAY.md) sont indépendants de l'enquête historique.
