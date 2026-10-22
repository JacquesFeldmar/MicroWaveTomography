# Comparer les cartes reçues à leur référence S11

`compare_s11.py` superpose une référence simulée et une ou plusieurs acquisitions. Il conserve les données originales et leurs empreintes SHA-256. Les différences sont descriptives : l’outil n’attribue aucun verdict de qualification physique et n’ajuste ni retard, ni phase, ni amplitude.

Depuis `simulation/`, avec l’environnement `ph` ou `openems` :

```powershell
python -B -X utf8 compare_s11.py `
  --simulation resultats/pcbway_maille_controlee_v2/diamant_uwb/comparaison/reference_simulation.s1p `
  --mesure antennes/diamant_uwb/mesures/2026-11-01_pcbway_L1-01/s11_L1-01_reconnexion01.s1p `
           antennes/diamant_uwb/mesures/2026-11-01_pcbway_L1-01/s11_L1-01_reconnexion02.s1p `
           antennes/diamant_uwb/mesures/2026-11-01_pcbway_L1-01/s11_L1-01_reconnexion03.s1p `
  --sortie comparaisons/L1-01_premiere_serie `
  --plan-mesure "SOL au SMA mâle du câble ; carte L1-01 reconnectée, aucune extension de port"
```

Les chemins et la date d’acquisition sont des exemples à remplacer. La référence F2 ne doit être utilisée qu’après réussite de sa qualification et livraison du fichier correspondant. Utiliser la référence du dessin correspondant : `diamant_uwb`, `diamant_uwb_x18` ou `vivaldi_tomographie`.

Le dossier de sortie doit être neuf ou vide. Un dossier existant contenant des fichiers est refusé. Un nouveau résultat exige un nouveau dossier ; les comparaisons précédentes restent conservées.

## Conditions d’entrée

Chaque fichier doit être un Touchstone un port, complexe RI, référencé à 50 Ω, avec un en-tête explicite comme `# Hz S RI R 50`. Les unités Hz, kHz, MHz et GHz sont acceptées. Les fréquences doivent être finies, croissantes et uniformes, et les valeurs S11 finies.

Les grilles de tous les fichiers doivent être **exactement identiques après conversion en Hz**. Même un décalage de 0,5 Hz entre deux fichiers est refusé. L’outil ne rééchantillonne aucune mesure. Pour la campagne PCBWay, utiliser 1,000–6,300 GHz et 213 points, espacés de 25 MHz, dès l’acquisition.

Un même chemin de mesure fourni plusieurs fois est refusé. Des fichiers distincts peuvent contenir des acquisitions identiques ; leur présence ne prouve pas leur indépendance. Documenter les reconnexions et le montage suivant [le protocole de réception et de mesure](PROTOCOLE_MESURE_PCBWAY.md).

## Plans de référence

`--plan-mesure` est obligatoire et doit décrire le plan réel, la calibration et toute extension de port déjà appliquée. La mesure calibrée originale doit rester disponible.

Par défaut, le plan simulé est le bord du PCB, avec un port idéal 50 Ω. Le corps coaxial, la broche, le PTFE et les soudures ne sont pas résolus en 3D. `--plan-simulation "texte"` permet d’indiquer un autre plan si une future référence utilise effectivement un autre modèle.

Une SOL au connecteur SMA ne rend pas automatiquement son plan équivalent au bord du PCB. Le module, l’impédance et la phase sont affichés aux plans déclarés ; les différences complexes et de phase restent des diagnostics. Un accord quantitatif exige de maîtriser cette différence de transition. Aucune valeur de retard n’est ajustée pour rapprocher les courbes.

## Fichiers produits

| Fichier | Contenu |
|---|---|
| `comparaison_s11.png` | Module en dB, résistance/réactance et phase déroulée ; couleurs communes aux trois panneaux et enveloppe des acquisitions |
| `resultats.json` | Plans, sources et empreintes, bandes disjointes sous −10/−6 dB, couverture, minima descriptifs, écarts et dispersion |
| `resume_comparaisons.csv` | Une ligne par acquisition : écarts complexes, module, percentiles dB/phase, minimum et segments de bande |
| `courbes.csv` | Toutes les fréquences et courbes, S11 complexe, module, phase, impédance et différence complexe à la référence |
| `dispersion_frequentielle.csv` | Produit avec au moins deux acquisitions : moyenne complexe, écarts types et enveloppe de module |
| `entrees/` | Copies exactes de la référence et des acquisitions, avec des noms distincts |
| `manifest_comparaison.json` | SHA-256 des copies d’entrée et de tous les fichiers produits, hors manifeste lui-même |

La couverture porte sur les points de la grille indiquée. La zone utile 1,4–6,0 GHz est aussi décrite lorsque le balayage la couvre. Les bornes des bandes et les minima sont les fréquences échantillonnées, sans interpolation. Les huit minima locaux les plus profonds au maximum sont listés ; ils ne sont pas appariés de force entre simulation et mesure.

Les écarts complexes maximal et RMS utilisent tous les points. Le percentile 95 en dB et celui de la différence de phase principale utilisent uniquement les points où les deux modules sont au moins −20 dB. Un masque vide donne une valeur JSON `null`, sans produire de verdict. La dispersion utilise les écarts types échantillonnaux, avec un dénominateur N−1 ; elle n’est pas estimée avec un seul fichier.

Les valeurs exactement nulles de S11 ont une phase indéfinie : cellule CSV vide et interruption du tracé de phase. Leur module est borné à −360 dB pour l’affichage numérique. L’impédance d’un S11 exactement égal à 1 est également laissée indéfinie. La phase est déroulée séparément par segment non nul, sur sa branche native ; aucun raccord artificiel n’est ajouté à travers un zéro. Le panneau d’impédance emploie une échelle symétrique logarithmique, linéaire entre −100 et +100 Ω.

## Vérification du programme

```powershell
python -B -X utf8 -m unittest discover -s tests -p test_compare_s11.py -v
```

Les tests emploient des signaux de phase connue et des acquisitions synthétiques, vérifient les écarts et la dispersion attendus, la conservation des octets/SHA, le refus des grilles différentes et des sorties non vides, puis produisent une vraie figure dans un dossier temporaire. Ils ne constituent pas une mesure des antennes fabriquées.
