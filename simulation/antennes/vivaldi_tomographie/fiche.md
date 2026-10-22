# Vivaldi de production pour la tomographie

Cette Vivaldi antipodale est une conception du projet. Les paramètres de départ proviennent des essais historiques ; la révision de production reçoit une implantation SMA documentée, un nominal de matériau commun aux losanges et une garde cuivre/bord. Ses performances sont établies par une nouvelle campagne, distincte des 21 essais antérieurs.

| Élément | Révision de production |
|---|---|
| Contour de carte | 143,668735 × 280,9031025 mm |
| Emprise du cuivre avant garde | 143,068735 × 280,6031025 mm |
| Garde latérale et à la bouche | 0,30 mm ; alimentation au bord |
| Substrat nominal | S1000H, diélectrique de 1,6 mm |
| Matériau simulé | Debye passif, ε′ 4,6 et tan δ 0,011 à 1 GHz |
| Bande visée | 1,4–6,3 GHz ; calcul de comparaison sur 1,0–6,3 GHz |
| Ouverture entre bords intérieurs | 107,068735 mm |
| Ailes à la bouche | 18 mm |
| Ligne principale | Largeur 3,0 mm, longueur initiale 20 mm |
| Transition vers la fente | 100 mm |
| Évasement | 160,6031025 mm, taux 0,013/mm |
| Fente au départ | 0,8 mm |
| Masse à l'alimentation | 40 mm de largeur |
| Fixation | Deux trous non métallisés Ø3 mm, présents dans le modèle |
| Connectique | SMA femelle Cinch Johnson 142-0701-851, pad 2,286 mm et deux vias de masse |
| Finition | Cuivre 1 oz, ENIG, sans masque ni sérigraphie |

La carte rayonne dans l'axe de sa longueur. Dans CSXCAD, elle est posée de chant : largeur en x, longueur en z, épaisseur en y. Les polygones de normale y sont donc fournis en coordonnées `(z,x)`.

Les fonctions `profils()` et `_polygones()` de [geometrie.py](geometrie.py) définissent les bords des deux cuivres. La transition glisse avec une loi de cosinus et l'évasement exponentiel respecte ses deux extrémités. Le contrôle de recouvrement vérifie que la transition ne crée pas une zone excessive de superposition, avec une exception locale explicitement liée à l'implantation SMA.

La ligne de 3,0 mm constitue un choix nominal ; son impédance dépend du matériau et de l'épaisseur réellement livrés. Le modèle conserve l'implantation cuivre et les vias mais pas le corps SMA, le PTFE, la broche ni la soudure. La [procédure de mesure](../../PROTOCOLE_MESURE_PCBWAY.md) distingue le plan idéal du calcul et le plan de connexion réel.

Les anciens chiffres de couverture et les essais de réglage sont disponibles dans [l'archive historique](../../archives/etat_avant_reprise_2026-10-18.zip). Les références de la nouvelle révision sont dans `resultats/pcbway_r1/vivaldi_tomographie/` ; les critères de convergence sont fixés dans [le README principal](../../README.md).