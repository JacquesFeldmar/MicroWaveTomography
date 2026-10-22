# Décisions après la réponse de Claude

La réponse de Claude du 18 octobre a été lue avec les sources et les preuves de l'audit. Elle corrige certaines formulations de l'audit et confirme les défauts qui empêchaient d'utiliser les anciens résultats comme qualification des fichiers de production. La reprise sépare la fabrication de trois antennes et l'enquête historique sur les pics de distance.

## Observations retenues et corrections

| Sujet | Décision et conséquence |
|---|---|
| Deux pics dans un mono-écho | Défaut reproduit. Le maximum principal et les candidats secondaires sont distingués. Les lobes de Hann ne sont plus assimilés automatiquement à une seconde branche physique ; l'algorithme historique reste explicitement accessible pour reproduction. |
| Imports de mesures | Rejet des grilles invalides, valeurs non finies, référence autre que 50 Ω et doublons divergents. Export puis réimport sont contrôlés. |
| Maillage et séries | Les résolutions demandées ont un effet vérifié. Interfaces et graduation sont contrôlées ; fond et plaques partagent grille, durée et pas temporel. |
| Coût | Le nombre de cellules provient de la grille construite. La symétrie non implémentée n'abaisse plus artificiellement le coût. Les minutes restent une estimation tant que la vitesse réelle n'est pas mesurée. |
| Archives FDTD | XML, grille, sources, propriétés matérielles, sondes et manifeste sont conservés par calcul, sans écrasement silencieux. |
| Troncature temporelle | L'énergie finale seule ne suffit pas. La nouvelle qualification compare le S11 complexe obtenu avec des fenêtres de durées différentes sur le même maillage. |
| Fabrication | Les couches pleines, les perçages PTH/NPTH et les contours sont comparés indépendamment. Tests négatifs et rendus de cuivre complètent les contrôles de dimensions. |
| Produit physique | Le stratifié nominal, l'absence de vernis, les gardes cuivre/bord et une SMA femelle documentée sont communs au dessin et au modèle. Les deux trous de fixation Vivaldi sont simulés. |

## Précisions apportées à l'audit initial

Le défaut du rendu SVG provenait d'une interaction avec l'implémentation de couleur de gerbonara ; la preuve utile reste l'illisibilité du rendu livré. Le nouvel export produit des vues réellement lisibles et des PNG contrôlables.

Les dimensions de fabrication sont celles de la ligne médiane du contour fermé. Une boîte englobante de traits SVG ou Gerber peut dépasser ces dimensions de la largeur de trait ; elle n'est pas la taille finie de la carte. Le contrôle indépendant utilise désormais cette convention explicitement.

La valeur maximale de |S11| analytique de 1,9169, sans unité, correspondait à une configuration sans écho fixe. Les paramètres complets par défaut donnent environ 1,9120. Les deux dépassent l'unité : les amplitudes de ce générateur d'échos sont heuristiques et ne constituent pas une prédiction normalisée d'un réseau passif. La correction porte sur la comparaison entre configurations et ne résout pas le défaut distinct de sélection de pics.

Le facteur analytique `1/(2x)` est dimensionnellement incomplet sans une longueur de référence. La convention de x en mètres fixe les chiffres du générateur, sans leur donner une amplitude physique normalisée. Cette limite est désormais annoncée dans le module et le README ; ce générateur ne participe pas à la qualification des PCB.

Le minimum de |S11| du dipôle vers 4 GHz ne doit pas être directement opposé à l'approximation c/(2L) proche de 5 GHz pour conclure à une erreur de 20 % du solveur. Le point de résonance se juge notamment sur l'impédance, avec les effets de longueur électrique et d'alimentation. Ce contrôle reste partiel.

Les essais de recoupe temporelle de Claude donnent un diagnostic utile sur les anciens calculs, mais pas une borne rigoureuse sur l'erreur de distance. Une petite erreur absolue de S11 peut dépasser un écho de plaque plus faible, puis déplacer un maximum ou le candidat choisi. Le raisonnement approximatif sur la longueur de chemin équivalente ne permet donc pas d'exclure à lui seul une erreur de plusieurs centimètres. La sélection de pics et la convergence doivent être contrôlées séparément.

## Périmètre de la reprise

Les bandes annoncées auparavant pour les losanges et la Vivaldi restent des résultats historiques. L'implantation SMA, le nominal diélectrique et le contour Vivaldi changent ; leur réutilisation comme preuve des nouveaux Gerbers serait incorrecte. Une nouvelle campagne S11 qualifie la révision destinée à PCBWay.

La Nooelec demeure une géométrie approximative. Les fichiers bruts historiques et leurs calibrations sont nécessaires à l'enquête sur les décalages de 20,0 et 36,5 cm ; aucun retard physique unique n'est déduit de ces seuls chiffres. Cette enquête n'empêche pas de produire des prototypes ayant une référence de simulation explicite.

Les connecteurs femelles sont un choix confirmé par l'utilisateur. La référence retenue est Cinch Johnson 142-0701-851 ; son implantation est documentée et adaptée aux lignes des trois cartes. La transition coaxiale complète n'est pas modélisée : le protocole distingue le plan idéal du calcul et le plan de connexion de la mesure.
