# Losange de production de 32 par 40 mm

Ce monopôle reprend le contour rayonnant de la conception publiée en losange, avec une alimentation adaptée à la SMA femelle Cinch Johnson 142-0701-851. La nouvelle révision utilise le nominal diélectrique commun aux trois cartes. Elle doit donc être distinguée de la reproduction historique de l'article.

| Élément | Révision de production |
|---|---|
| Contour de carte | 32 × 40 mm |
| Substrat nominal | FR-4 S1000H, diélectrique de 1,6 mm |
| Matériau simulé | Debye passif, ajusté sur ε′ 4,6 et tan δ 0,011 à 1 GHz |
| Masse arrière | Demi-disque de rayon 15,6 mm, au bord d'alimentation |
| Ligne principale | 3,1 mm ; pad de bord 2,286 mm sur 5,08 mm puis transition |
| Connecteur | SMA femelle standard Cinch Johnson 142-0701-851 |
| Vias de masse | Deux trous métallisés finis Ø0,4572 mm |
| Finition commandée | Cuivre 1 oz, ENIG, sans masque ni sérigraphie |

Les coordonnées complètes, la discrétisation du demi-disque et la transition sont dans [geometrie.py](geometrie.py) et [connectique.py](../../connectique.py). Ces mêmes contours sont exportés en Gerber et construits dans CSXCAD. Le connecteur coaxial complet et la soudure ne sont pas inclus dans le calcul.

La référence de conception est Singhal et al., reprise dans l'exemple MathWorks « Diamond-Shaped Antenna for UWB Applications ». La reproduction et les bandes annoncées avant reprise sont conservées dans [l'archive historique](../../archives/etat_avant_reprise_2026-10-18.zip). Une concordance de bande sur une ancienne configuration est un contrôle partiel ; elle ne valide pas tous les ports, matériaux et configurations du simulateur.

La qualification de production couvre 1,0–6,3 GHz, avec comparaison des maillages et durées. Les résultats et les critères se trouvent dans [le README principal](../../README.md) et `resultats/pcbway_r1/diamant_uwb/`. Mesurer la carte après séparation du panneau en suivant [le protocole](../../PROTOCOLE_MESURE_PCBWAY.md).