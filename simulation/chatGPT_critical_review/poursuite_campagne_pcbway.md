# Reprise automatique des calculs PCBWay

Le script `simulation/poursuit_campagne_pcbway.py` enchaîne les calculs sur exactement deux voies, avec dix threads openEMS par worker. Il ne livre aucun paquet de fabrication et ne prononce aucun avis de commande.

```powershell
& 'C:\Users\jfeld\anaconda3\envs\openems\python.exe' -B -X utf8 simulation/poursuit_campagne_pcbway.py --adopter-en-cours --fils 10
```

La première voie contrôle le petit losange base 8 ns, attend son calcul fin 12 ns s'il est en cours, dérive fin 8 ns, puis effectue ces trois étapes pour le grand losange. La seconde attend la Vivaldi base 8 ns, lance fin 12 ns, puis dérive fin 8 ns. Les neuf dossiers achevés sont relus et passés à `qualifie_pcbway.comparer`.

Chaque worker nouveau est un processus Python distinct. Les threads du script ne font qu'attendre et lire les preuves ; ils n'appellent jamais `Run`, qui change le répertoire courant du processus. Les journaux sont créés dans `resultats/pcbway_r1/journaux`, hors des dossiers de calcul dont les empreintes sont figées.

`--adopter-en-cours` permet l'adoption d'un worker existant après contrôle de son PID, exécutable, arguments, répertoire courant, date de création, configuration, versions et sources physiques. Un handle Windows conserve l'identité du processus jusqu'à sa sortie. Le script attend son code de sortie nul ainsi que le manifeste terminé, la qualification et les indicateurs lisibles. Il réapplique les contrôles de qualification et recalcule les indicateurs avant de libérer la voie. Un dossier partiel dépourvu de manifeste adoptable est refusé ; un préfixe en cours de dérivation doit finir avant une reprise du script.

Les calculs terminés sont réutilisés après lecture du cache durci. Une différence de géométrie, de moteur, de contrat de production, d'environnement ou d'indicateurs provoque un arrêt. Les sources physiques et les scripts de traitement/qualification sont surveillés pendant le pipeline.

Le délai d'inactivité par défaut est de dix minutes et la limite globale de six heures, avec une veille toutes les cinq secondes. Les tailles, dates de modification et derniers pas des sondes sont lus sans modifier les calculs. Un échec ou un dépassement arrête les nouveaux lancements ; **aucun worker déjà lancé n'est tué**. Son PID et son journal restent dans les traces pour permettre la reprise.

Un verrou système exclusif empêche deux orchestrateurs de poursuivre simultanément la même campagne. Le fichier `pipeline_pcbway.lock` reste présent, avec l'état `libere` après une fin normale. Après interruption brutale, `--adopter-en-cours` permet de reprendre le verrou abandonné ; un verrou encore détenu reste bloquant. Aucun effacement récursif n'est effectué.

Le statut courant est dans `pipeline_pcbway_statut.json`, et les événements dans `journaux/pipeline_trace.jsonl`. Un code de sortie 0 indique que les calculs et les critères de comparaison ont réussi ; le code 2 signale un arrêt ou des critères non atteints. La fabrication et la validation physique du lot restent une étape distincte.

Seize tests unitaires avec workers factices vérifient l'adoption sans lancement, l'attente des preuves et de la sortie réelle, les caches, le refus des mauvaises sources/PID/répertoires, les deux watchdogs, les échecs sans destruction de worker, le verrou, les deux voies jusqu'à la comparaison des neuf dossiers et les incidents d'écriture du statut. Ces tests n'exécutent aucun solveur. Une revue indépendante a également vérifié en lecture seule les deux workers réels déjà actifs.

Sous Windows, le remplacement atomique du statut réessaie pendant deux secondes au maximum, par pauses de 50 ms, si un lecteur ou un antivirus détient momentanément le fichier. Une erreur persistante est propagée et le JSON temporaire complet est conservé. Les lecteurs de suivi emploient le partage de lecture, écriture et suppression/remplacement. L'incident réel du 18 octobre est archivé dans `journaux/pipeline_statut_incident_verrou_windows_2026-10-18.json` ; les solveurs ont continué et ont été réadoptés.

La seule dépendance supplémentaire du pilote est psutil 7.2.2, installé dans l'environnement `openems` et consigné dans `requirements_poursuite.txt`.

La comparaison des indicateurs conserve les structures, comptes, booleens et classifications exacts. Les seules valeurs flottantes admettent rtol=2e-11 et atol=2e-12 pour couvrir la quantification du Touchstone, ecrit apres le calcul des indicateurs en double precision. Une modification relative de S11 de 1e-6 est refusee. Le cache reel diamant_uwb/base_8ns a ete relu et valide sans solveur ni modification des archives.
