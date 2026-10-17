# Dipôle de référence — l'étalon du programme

Cette antenne **n'existe pas sur le banc**. Elle sert à vérifier le programme,
et elle est la seule dont la réponse soit connue d'avance.

| | |
|---|---|
| Géométrie | deux brins de 14 mm, section 2 × 2 mm, fente de 2 mm, **dans le vide** |
| Longueur totale | 30 mm |
| Alimentation | port localisé 50 Ω dans la fente |
| Résonance attendue | c/2L = **5,0 GHz**, un peu plus bas à cause de l'épaisseur |
| **Retard attendu** | **0,000 ns** |

## Pourquoi son retard est nul

Il n'y a ni substrat, ni ligne d'alimentation, ni connecteur. Le point d'où
part l'onde est la fente, c'est-à-dire le plan du port, c'est-à-dire le plan de
calibration. Une plaque posée à 50 cm doit donc être **lue à 50 cm**.

C'est le contrôle qui manque sur une antenne réelle. Si la chaîne complète —
géométrie, FDTD, extraction du S11, soustraction du fond, fenêtre, IFFT,
détection de pic — rend autre chose que la distance vraie, alors l'erreur est
dans le programme, et non dans l'antenne.

## Les trois contrôles

```powershell
conda activate openems
cd antennes\dipole_reference
python verifier.py --cout      # l'estimation seule
python verifier.py             # preset rapide : plaque de 30 cm à 20, 30, 40 cm
python verifier.py --complet   # grille du rapport : 201 points, plaque de 60 cm
```

| | Ce qui est vérifié | Critère |
|---|---|---|
| **V1** | le dipôle rayonne et résonne où la théorie le dit | minimum de \|S11\| entre 3,8 et 5,5 GHz |
| **V2** | **l'écart est le même à toutes les distances** | étendue < 2 cm, moyenne < 10 cm |
| **V3** | l'échelle des distances est juste | pente = 1,000 ± 2 % |

**V2 ne teste pas que l'écart soit nul, et c'est voulu.** Un dipôle résonne,
donc il stocke de l'énergie, donc il retarde sa réponse de l'ordre de Q/(πf) :
quelques centimètres, inévitables. Ce qui doit être vrai — et qui porte tout
le projet — c'est qu'un **retard s'ajoute sans se multiplier**, donc que
l'écart ne dépende pas de la distance de la plaque. La première version de ce
fichier affirmait un retard nul : c'était faux, et la simulation l'a montré.

V2 et V3 sont exactement ce qui a échoué sur le banc réel, où l'écart valait 20
à 36 cm et la pente 0,880. Les voir corrects ici établit que ni le traitement
ni l'extraction du S11 n'en sont responsables.

## Ce que cette antenne ne prouve pas

Elle ne valide **ni le modèle de l'UWB Surveyor, ni le maillage d'une structure
sur FR4**. Un dipôle dans le vide est le cas le plus facile pour un solveur
FDTD. Qu'il passe les trois contrôles ne dit rien de la finesse de maillage
nécessaire autour d'une fente de 0,6 mm sur un substrat.
