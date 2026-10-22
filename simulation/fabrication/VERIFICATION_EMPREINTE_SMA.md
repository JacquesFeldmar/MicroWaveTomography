# Vérification de l'implantation SMA femelle

Vérification du 18 octobre 2026 sur la révision courante de [`connectique.py`](../connectique.py). Le connecteur choisi est le **Cinch/Johnson 142-0701-851**, femelle SMA standard 50 Ω, montage bord de carte. Le projet n'utilise pas de RP-SMA.

Les deux documents fabricant conservés localement sont le [catalogue Johnson, page imprimée 58](../references/cinch_catalogue.pdf) et le [plan mécanique de la référence 142-0701-851](../references/sma_cinch_142-0701-851.pdf). La page de catalogue a été lue par extraction du texte et contrôle de l'[image d'implantation](../references/cinch_implantation.png) ; le plan a été contrôlé sur son [rendu](../references/sma_cinch_plan.png). Les conversions utilisent exactement 25,4 mm par pouce.

## Cotes reprises du catalogue

Repère local : `x` transversal, `u` dirigé du bord du PCB vers le radiateur. Le bord d'entrée est `u = 0`. Les coordonnées sont translatées lors de la mise en panneau ; elles ne sont pas agrandies pour le losange ×1,8.

| Élément du catalogue | Pouces | Valeur dans le code, mm | Vérification |
|---|---|---|---|
| B : largeur du pad signal au bord | 0,090 | 2,286 | Conforme |
| C : distance entre bords internes des pattes de masse | 0,250 | 6,350, donc `x = ±3,175` | Conforme |
| D : distance entre bords externes de masse | 0,440 | 11,176, donc `x = ±5,588` | Conforme |
| E : longueur des pads depuis le bord | 0,200 | 5,080 | Conforme |
| Centres des vias, distance à l'axe | 0,170 | `x = ±4,318` | Conforme |
| Retrait des vias après E | 0,035 | 0,889, donc `u = 5,969` | Conforme |
| Diamètre fini des deux trous métallisés | 0,018 | 0,4572 ; export 0,457 | Conforme à l'arrondi de l'Excellon |
| Diamètre extérieur des pastilles | 0,038 | 0,9652 | Conforme ; cercle approché par 48 segments |
| Largeur des cols de liaison aux vias | 0,018 | 0,4572 | Conforme dans la révision courante |

Le dessous de la carte est déjà un plan de masse continu sous l'implantation. Aucun disque supplémentaire n'y est ajouté par `empreinte_mm()` ; le cuivre de masse existant assure l'anneau et le retour des vias. Les Gerbers et la vérification géométrique portent le résultat complet.

## Adaptation de ligne propre au projet

La cote **A du catalogue vaut 0,103 pouce, soit 2,6162 mm**. Elle concerne la ligne après la zone B. Le projet adapte le pad B de 2,286 mm vers sa ligne de **3,1 mm pour les losanges** et **3,0 mm pour la Vivaldi**, avec un raccord incliné à 45°. L'extrémité de l'adaptation est donc à `u = 5,487 mm` pour les losanges et `u = 5,437 mm` pour la Vivaldi. La cote A n'est pas reproduite telle quelle.

Cette différence est une adaptation explicite du projet. Le catalogue indique que les dimensions de transition peuvent demander un ajustement selon le PCB et l'application. Les cotes de contact B/C/D/E et les vias correspondent au dessin ; cela ne garantit pas le S11 de l'ensemble soudé. La qualification de cette transition reste liée aux simulations de la révision et aux mesures après montage.

## Compatibilité mécanique et limites du modèle

La ligne de catalogue associe la référence 142-0701-851 à une épaisseur nominale de **0,062 pouce = 1,5748 mm**. Le plan mécanique donne un logement de **0,068 ± 0,007 pouce**, soit **1,5494 à 1,9050 mm**. La commande nominale 1,6 mm est cohérente avec cette famille ; la tolérance réelle de carte, le cuivre, la finition et la planéité restent à relever avant soudure.

Le calcul porte l'empreinte en cuivre et des vias représentés par des cylindres PEC pleins équivalents. Il utilise un port idéal au bord du PCB. Le corps coaxial, le PTFE, la broche et la soudure ne sont pas entièrement décrits en 3D. La présente vérification valide les conversions de cotes et la cohérence du dessin avec les sources ; elle ne constitue pas une validation électromagnétique du connecteur monté.

Les fichiers source, l'implantation complète et leurs SHA-256 sont repris dans les manifestes des ZIP. Une évolution de `connectique.py` impose leur régénération.
