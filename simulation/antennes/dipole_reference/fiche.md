# Dipôle de référence pour les contrôles du simulateur

Cette antenne de contrôle n'existe pas sur le banc. Elle comprend deux brins de 14 mm, section 2 × 2 mm, séparés par une fente de 2 mm, dans le vide, avec un port localisé de 50 Ω. La longueur totale est de 30 mm.

L'approximation c/(2L), proche de 5 GHz, donne un ordre de grandeur. La fréquence où |S11| est minimal dépend aussi de l'adaptation au port ; elle ne doit pas être confondue avec une résonance définie sur l'impédance. Un minimum vers 4 GHz ne démontre donc pas, par lui-même, une erreur de 20 % du solveur.

## Retard géométrique et réponse électrique

Le dipôle n'a pas de ligne ni de substrat, donc son retard de propagation dans une ligne est nul. Sa réponse électrique rayonnée et reçue peut néanmoins être dispersive et présenter du stockage d'énergie. L'hypothèse historique `retard_attendu_ns() = 0` ne constitue pas une vérité exacte sur le pic de distance après filtrage large bande.

Les contrôles historiques portent surtout sur la constance du décalage et la pente des distances. Ils n'établissent ni l'absence de biais absolu, ni l'exactitude générale de l'extraction S11. L'archive antérieure à la reprise conserve les chiffres historiques, qui ne remplacent pas une nouvelle étude de convergence.

## Commandes et critères historiques

Depuis ce dossier, avec l'environnement openEMS :

```powershell
python verifier.py --cout
python verifier.py
python verifier.py --complet
```

| Contrôle | Critère du script | Portée |
|---|---|---|
| V1 | Minimum du module de S11 entre 3,8 et 5,5 GHz | Plausibilité, sans identification précise de résonance |
| V2 | Étendue du décalage <2 cm et moyenne <10 cm | Constance approximative, sans imposer un biais nul |
| V3 | Pente des distances 1 ±2 % | Échelle approximative des distances |

Ces critères sont des contrôles partiels dans la scène considérée. Ils ne qualifient pas le maillage d'une structure sur FR-4, la soustraction d'un écho très faible, la transition SMA ou la tomographie. La qualification des PCB à fabriquer utilise la campagne dédiée décrite dans [le README principal](../../README.md).
