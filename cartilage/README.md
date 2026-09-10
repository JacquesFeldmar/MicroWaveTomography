# cartilage — épaisseur du cartilage, robot 6 DDL, genou ouvert

Mesure sans contact de l'épaisseur du cartilage articulaire pendant une prothèse
totale de genou. Le système optique donne la surface externe ; la sonde radar,
portée par le robot, retrouve l'interface cartilage/os dans le même repère.

| | |
|---|---|
| `GUIDE_UTILISATION.md` | **le mode d'emploi complet**, dont la séquence en simulation |
| `calibration.py`, `radar.py`, `qualification.py` | les trois programmes |
| `noyau.py` | bibliothèque du projet : modèle stratifié, inversion, simulateur |
| `verifier_doc.py` | contrôle guide ↔ code, à relancer après chaque modification |
| `tutoriel.py`, `tutoriel_contenu.py` | tutoriel vidéo |
| `construire_guide.py`, `guide_style.css` | génèrent `docs/GUIDE_UTILISATION.pdf` et le contrôlent |
| `theorie/` | sources LaTeX du document de théorie et `figures_*.py` |
| `docs/` | PDF livrés, et `docs/ecrans/` : les copies d'écran du guide |

Pour recompiler le document de théorie, se placer dans `theorie/`. Ses images sont
dans `figures/`, produites par `figures_*.py`, et dans `diag_bande/`, qui rassemble
les résultats des essais de bande de juillet.
