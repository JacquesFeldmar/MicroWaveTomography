# Staging logiciel Q / W / AP pour les moteurs F1 et F2

Ces fichiers sont des propositions isolées. Aucun correctif n'a été appliqué aux sources de production et aucun calcul FDTD réel n'est lu ou lancé par le runner.

`modifies/qualifie_pcbway.py` part exactement de l'intégration Q `5fd159116157bef7191c3b86225cf0524fffd3e700295469fa12604c59482217`, puis ajoute la distinction entre les moteurs. `originaux/` conserve Q `2e6b…`, W `6744…` et AP inchangés ; `Q5fd_avant.py` conserve le point de départ du nouveau correctif. Les différences sont écrites dans chaque dossier d'exécution.

Le registre accepte seulement le moteur historique `fdtd` et le module connu `fdtd_maille_controlee.py`, dont `NOM_MOTEUR` doit être exactement `maillage_controle_v2`. Deux tags `moteur` absents dans manifeste et qualification désignent F1, avec neuf sources et aucun fichier F2 dans l'archive. Deux tags F2 identiques exigent les neuf sources F1 inchangées et la source exacte F2 : dix SHA complets, égaux à `F2._sources()`. Une valeur nulle explicite, un tag manquant ou inconnu et un inventaire incomplet sont refusés.

L'API ajoutée est `Q.calcule(..., moteur=None)` pour F1 ou `moteur="maillage_controle_v2"` pour F2. Le choix s'applique à `charge_antenne`, `estime_cout` et `lance`. La qualification écrit le tag uniquement pour F2. Un cache d'un autre moteur est refusé, même lorsque la géométrie et le montage physique coïncident. La signature CAD/contrat/Montage conserve sa définition historique.

`Q.montage_campagne(niveau, duree_ns, moteur=TAG)` utilise le catalogue explicite `F2.NIVEAUX`, limité à `base` et `fin`, avec paramètres numériques positifs et raffinement monotone. `Q.valide_campagne` compare le montage au catalogue du moteur réellement archivé. L'API historique à deux arguments conserve le catalogue F1. Aucun paramètre F2 n'est caché derrière un montage F1.

W contrôle le couple de tags avant toute écriture. Son sous-processus recharge seulement le module connu sélectionné depuis les sources archivées, après nouvelle vérification des SHA. Il conserve le tag dans le préfixe et les paramètres d'extraction, et vérifie les coordonnées reconstruites octet par octet, les matériaux et la reproduction du S11 parent par le vrai CalcPort.

AP contrôle l'ensemble de la campagne avant de produire les références : aucun mélange F1/F2 entre calculs ou antennes. Le bilan F1 garde sa structure sans tag supplémentaire ; le bilan F2 ajoute `moteur`. Toutes les comparaisons temporelles, y compris les préliminaires, vérifient les axes NPZ en float64 fini et identiques octet par octet, en plus du résumé de grille et du pas temporel.

La voie historique `Q.comparer` sans fichier de sélection applique les mêmes garde-fous : précontrôle des trois antennes avant toute sortie et contrôle des axes temporels via la fonction commune `Q.verifie_grilles_temporelles`. Des tests supplémentaires couvrent explicitement cette voie sans sélection.

Le moteur physique F2 et ses paramètres restent à valider séparément. Les valeurs 16/24 et 0,15/0,10 présentes dans les tests sont des **fixtures logicielles** : le stub F2 délègue la construction au moteur F1 et interdit tout `lance`. Elles ne qualifient aucune nouvelle physique F2, antenne ou courbe.

Pour reproduire les contrôles dans une copie TEMP neuve :

```powershell
python -B -Xutf8 verifie_staging.py --ciblee --sortie nouveau_controle_cible
python -B -Xutf8 verifie_staging.py --sortie nouvelles_regressions
```

Le runner utilise les environnements locaux openems et ph, impose un thread OMP/BLAS et rend les 17 sources et Q/W/AP originaux vérifiables par SHA avant/après. Le stub ne peut être installé que dans la copie temporaire marquée ; aucun moteur physique F2 existant n'est écrasé. Les sorties doivent être neuves. Les tests Q/AP/W/CLI et L restent les régressions existantes ; les tests supplémentaires couvrent les tags, les inventaires, les caches, le catalogue, le préfixe et les campagnes mixtes.

Les résultats des exécutions antérieures sont historiques. Le contrôle complet final est dans `execution_regressions_finales_03/` : 77 tests Q/AP/W/CLI/moteurs et 34 tests L réussis, soit 111 tests distincts sur les trois sources courantes. Le test de collision des caches a ensuite été renforcé pour imposer une signature CAD/contrat/Montage identique dans les deux sens F1/F2 ; les 25 tests ciblés de sa version courante réussissent dans `execution_collision_montage_04/`. Les trois sources n'ont pas changé entre ces deux exécutions. Ces 25 tests recouvrent une partie des 111 et ne s'ajoutent pas au décompte distinct.

`bilan_final_staging.json` relie les SHA courants aux journaux, aux revues indépendantes et à l'invariance des sources originales ; `index_final_sha256.json` inventorie les preuves présentes lors de sa clôture. Ne pas appliquer automatiquement ce staging : le moteur F2 réel doit d'abord être validé et l'application coordonnée par le responsable du projet.
