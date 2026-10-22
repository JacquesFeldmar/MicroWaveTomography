# Revue de la bibliothèque `commun` apportée par Maurice

18 octobre 2026 — comparaison et reprise sélective dans la bibliothèque du projet.

La copie de Maurice apporte des contrôles utiles avant l'IFFT et une clarification importante sur les données USB du LiteVNA. Ces apports sont repris dans `commun` à la racine. Le remplacement intégral aurait supprimé une fonction encore nécessaire à `cartilage` ; il n'a donc pas été effectué. Les sources de Maurice sont conservées intactes.

## Comparaison des six fichiers

| Fichier | Différence observée | Décision appliquée à la racine |
|---|---|---|
| `__init__.py` | Fins de ligne CRLF/LF seulement | Aucun changement |
| `sol.py` | Fins de ligne CRLF/LF seulement ; pas de nouveau calcul SOL | Aucun changement |
| `docs/Lite_VNA.pdf` | Identique octet pour octet | Aucun changement |
| `instrument.py` | Seule la documentation initiale diffère ; code exécutable identique | Documentation corrigée, comportement matériel conservé |
| `physique.py` | Documentation et contrôles d'entrée ajoutés à `profil_distance` ; `cote_plaque_mm` absente de la copie Maurice | Reprise des ajouts, conservation de `cote_plaque_mm` |
| `README.md` | Précisions sur le mode USB corrigé | Texte adapté aux constatations sur le pilote réellement installé ; API conservée documentée |

L'[inventaire complet](revue_commun_maurice_2026-10-18/inventaire_comparaison_complet.json) conserve les SHA-256 de chaque version avant/après et de la copie Maurice. L'égalité du code exécutable d'`instrument.py` est vérifiée sur l'arbre syntaxique, après retrait du seul texte de documentation du module.

## Modifications intégrées

Dans [`commun/physique.py`](../../commun/physique.py), `profil_distance` refuse désormais les entrées non finies, les dimensions ou longueurs incompatibles, une grille comportant moins de deux points, les fréquences non croissantes ou non uniformes et les zooms non entiers positifs. La tolérance de régularité reprise de Maurice est `rtol=1e-9`, `atol=1e-3 Hz`.

La formule IFFT, le pas déduit de `Δf = BW/(N−1)`, les fenêtres et leur normalisation restent identiques pour les données valides. La documentation précise que la distance est équivalente dans l'air depuis le plan de référence, que la réponse de l'antenne reste incluse et que l'amplitude conserve le gain de la fenêtre. Un profil de distance ne devient donc pas une mesure absolue de la position d'une interface par cette seule modification.

`cote_plaque_mm` est conservée : elle est importée dans `cartilage/noyau.py` et utilisée dans `cartilage/calibration.py`. Les constantes, autres fonctions et signatures publiques sont préservées, ainsi que les fins de ligne des fichiers Python existants.

Les originaux exacts, les différences et les empreintes se trouvent dans le [dossier de preuves](revue_commun_maurice_2026-10-18/RESULTATS_REVUE.txt). Les contrôles ajoutés concernent `profil_distance` ; ils ne constituent pas une nouvelle validation générale de toutes les fonctions physiques.

## Correction de l'affirmation sur les données USB

L'ancienne phrase « l'USB renvoie toujours des données brutes » était trop générale. Le [manuel officiel LiteVNA](https://nanovna.com/wp-content/uploads/2021/11/LiteVNA_User-Guide.pdf), page PDF 28, décrit un mode 3 corrigé dans le registre `rawSamplesMode` à l'adresse `0x26`. Page PDF 30, le paragraphe FIFO affirme pourtant encore l'absence de correction USB. Cette contradiction impose d'identifier le mode effectif du firmware du banc.

L'inspection du code installé **scikit-rf 1.12.0** apporte une précision supplémentaire : `NanoVNAv2` définit l'adresse `0x26`, mais ne la lit ni ne l'écrit explicitement dans l'initialisation et l'acquisition examinées. Il lit la FIFO et forme les rapports d'ondes. Ce calcul ne prouve pas à lui seul que le firmware a transmis des valeurs brutes. La documentation de Maurice ne doit donc pas être reprise comme une garantie automatique du pilote. Les [sources exactes et le relevé d'inspection](revue_commun_maurice_2026-10-18/inspection_pilote_skrf_sans_materiel.json) sont conservés.

Le pilote distinct [`from Maurice/plexiglas/progs/litevna.py`](../../from%20Maurice/plexiglas/progs/litevna.py) sélectionne les modes brut/interne, relit le registre et contrôle les paquets et la grille. Le chemin `plexiglas/progs/mesure_s11.py` cité dans le README Maurice n'existe pas dans le paquet reçu ; il n'est pas recopié dans la documentation du projet. Aucun nouveau pilote matériel n'est intégré sur la seule base de cette revue.

Le [`README` commun](../../commun/README.md), la documentation initiale d'[`instrument.py`](../../commun/instrument.py) et le [protocole de mesure PCBWay](../PROTOCOLE_MESURE_PCBWAY.md) décrivent maintenant les deux voies :

- acquisition effectivement brute, conservation des étalons/coefficient de calibration, puis SOL en Python ;
- acquisition déjà corrigée en interne, conservation de cet état et de sa calibration, sans deuxième SOL.

Firmware, mode USB, calibration et plan de référence doivent accompagner les futures mesures. Le comportement du matériel n'a pas été testé pendant cette revue ; les doubles logiciels ne le démontrent pas. Cette vérification au banc concerne la comparaison expérimentale et ne conditionne pas la fabrication des PCB.

## Vérifications réalisées

| Vérification | Résultat | Preuve |
|---|---|---|
| Tests ciblés de `commun.physique` | **8 tests réussis** | [Journal](revue_commun_maurice_2026-10-18/tests_physique_8.txt) |
| Non-régression sur données valides | **135 profils strictement identiques** à l'original archivé, dont 45 calculés depuis les cinq exports John | [Détail](revue_commun_maurice_2026-10-18/RESULTATS_REVUE.txt) |
| Suite Maurice avec bibliothèque **racine** imposée avant découverte des tests | **19 tests réussis** ; chemins/modules vérifiés avant et après | [Preuve JSON](revue_commun_maurice_2026-10-18/tests_maurice_19_commun_root.json) et [journal](revue_commun_maurice_2026-10-18/tests_maurice_19_commun_root.txt) |
| Auto-test synthétique `cartilage` | **10 cas réussis** : sept épaisseurs et trois inversions de permittivité | [Preuve JSON](revue_commun_maurice_2026-10-18/autotest_cartilage_root_10.json) et [journal](revue_commun_maurice_2026-10-18/autotest_cartilage_root_10.txt) |
| Imports/API `cartilage` | `noyau`, `calibration`, `qualification` et fonction de dimensionnement conservés | Même preuve JSON |
| Documentation du pilote | AST exécutable identique à l'original ; aucun changement de conduite matérielle | [Manifeste documentaire](revue_commun_maurice_2026-10-18/reprise_documentaire.json) |
| Sources Maurice | Six SHA-256 inchangés | [Inventaire](revue_commun_maurice_2026-10-18/inventaire_comparaison_complet.json) |

Les essais utilisent l'environnement `ph`, les bibliothèques NumPy/SciPy du projet et des instruments simulés. Les tests croisés sont isolés, avec backend graphique `Agg`, parallélisme numérique limité et ouverture réelle des ports interdite. Aucun LiteVNA n'a été contacté.

## Suite du projet

Les améliorations utiles de cette copie sont maintenant reprises sans retirer les API existantes. Aucun changement de SOL ni de pilote matériel n'est justifié par la comparaison des deux `commun` : leurs calculs correspondants étaient déjà identiques.

L'identification du mode USB restera un contrôle explicite lors des premières mesures des antennes produites. L'exposition de S21 dans l'API commune demeure un travail distinct pour la tomographie en transmission.

Cette intégration ne modifie aucune source physique ou contrôleur des simulations PCBWay en cours. La qualification électromagnétique des trois antennes reste suivie dans [les tâches de reprise](../TACHES_REPRISE_PCBWAY.md) ; les tests présentés ici ne valent pas validation de leurs performances radiofréquences.
