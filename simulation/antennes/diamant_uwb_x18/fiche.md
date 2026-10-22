# Losange de production agrandi par un facteur 1,8

La carte de 57,6 × 72 mm agrandit les dimensions planaires du losange de référence par un facteur 1,8. L'épaisseur diélectrique reste de 1,6 mm, la ligne est imposée à 3,1 mm et l'implantation SMA conserve ses dimensions propres. Il ne s'agit donc pas d'une homothétie électromagnétique complète ; une division des fréquences par 1,8 reste une estimation de départ.

Le nominal commun est FR-4 S1000H, deux couches cuivre 1 oz, ENIG, sans masque ni sérigraphie. Le modèle passif de Debye est ajusté sur ε′ = 4,6 et tan δ = 0,011 à 1 GHz. La SMA femelle Cinch Johnson 142-0701-851 utilise un pad de 2,286 mm et deux vias de masse métallisés finis de Ø0,4572 mm.

[geometrie.py](geometrie.py) charge le module du petit losange et lui transmet explicitement échelle, épaisseur, ligne et matériau. Les contours simulés sont ceux exportés. Le connecteur coaxial complet, la soudure et les pertes du cuivre/ENIG ne sont pas inclus dans le modèle.

La qualification de production couvre 1,0–6,3 GHz, indépendamment des anciennes courbes conservées dans [l'archive historique](../../archives/etat_avant_reprise_2026-10-18.zip). Voir [le README principal](../../README.md) et `resultats/pcbway_r1/diamant_uwb_x18/`. Mesurer la carte séparée du panneau selon [le protocole](../../PROTOCOLE_MESURE_PCBWAY.md).