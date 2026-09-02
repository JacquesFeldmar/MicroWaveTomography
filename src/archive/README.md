# Archive

Programmes remplaces par la refonte du 02/08/2026.
Rien n'est perdu : ils restent lisibles, mais ils ne sont plus maintenus
et ne partagent plus les constantes du noyau. **Ne pas les relancer.**

| Fichier | Remplace par |
|---|---|
| `radar_cartilage_online.py` | radar.py --live |
| `radar_cartilage_offline.py` | radar.py --rejeu   (ATTENTION : contenait le bug de 1 % sur l'echelle des distances, time_step = 1/bandwidth au lieu de 1/(n_fft.df) -- ses chiffres etaient faux) |
| `mesure_epaisseur.py` | radar.py --mesure |
| `calibration_sol.py` | calibration.py --sol |
| `qualif_ringing.py` | qualification.py --ringing |
| `qualif_centre_phase.py` | qualification.py --centre-phase, et calibration.py --plan pour la partie plan de reference |
| `erreur_epaisseur.py` | noyau.py (etude en simulation ; l'autotest du noyau couvre le meme terrain) |
| `demo_resolution.py` | aucun -- etude ponctuelle, conservee pour memoire |
| `test_bande_phase.py` | aucun -- campagne de comparaison de bandes, conservee pour memoire |
| `test_superresolution.py` | aucun -- essai ESPRIT, conserve pour memoire |
| `debug_vna.py` | calibration.py --etat |

## L'architecture actuelle

| Programme | Role |
|---|---|
| `noyau.py` | bibliotheque partagee (modele, traitement, acquisition) |
| `calibration.py` | corrections appliquees a chaque mesure |
| `radar.py` | mesure live / quantitative / enregistrement / rejeu |
| `qualification.py` | verdicts sur l'antenne |
