# Travaux après la première fabrication

La priorité est la livraison des deux articles PCBWay avec leurs références S11. Les tâches nécessaires à cette livraison sont suivies dans [TACHES_REPRISE_PCBWAY.md](TACHES_REPRISE_PCBWAY.md). Le présent fichier conserve les pistes qui dépendent des prototypes ou d'autres données.

| Travail | Déclencheur et résultat attendu |
|---|---|
| Transition SMA complète | Écart de mesure dépassant la répétabilité ou besoin de phase au même plan : coupon de caractérisation ou modèle 3D incluant connecteur et soudure |
| Matériau large bande du lot | Première mesure dimensionnelle et S11 : comparer le nominal S1000H à des données fournisseur ou à une caractérisation indépendante ; éviter un ajustement uniquement destiné à faire coïncider les courbes |
| Rendement, gain et centre de phase | Besoin de budget de liaison ou de tomographie : calculs de champ lointain et mesures adaptées, car S11 ne suffit pas |
| Vivaldi plus petite ou contour modifié | Encombrement réel du banc ou performances mesurées insuffisantes : nouvelle révision géométrique et nouvelle qualification, sans modifier les références de la première fabrication |
| Substrat à faibles pertes | Pertes ou variabilité du FR-4 incompatibles avec le banc : comparer un stratifié documenté, son coût réel et ses paramètres de fabrication avant décision |
| Campagnes Nooelec historiques | Retrouver les données complexes et calibrations des 17 septembre et 9 octobre : retraitement principal/candidats et confrontation des plans ; aucune borne de retard de carte n'est déduite d'une simple photo |
| Nooelec géométriquement fidèle | Dimensions et empilement disponibles : remplacer l'approximation photographique, puis vérifier sa convergence avant interprétation des distances |
| Quatre paramètres S | Besoin de réciprocité ou d'artefacts d'imagerie : organiser des mesures avec câbles inversés ou un instrument adapté et conserver les calibrations |
| Manifestes de campagnes dans Git | Dès l'ajout d'une campagne réelle, vérifier les règles `.gitignore` pour conserver ses métadonnées et gérer séparément les volumes bruts |

L'absence de vernis épargne est désormais une spécification de fabrication, et les trous de fixation Vivaldi font partie du modèle. Ces deux points ne sont plus des travaux différés. Les anciennes estimations de coût, de bande et de dispersion ne constituent pas des critères de qualification de cette révision.