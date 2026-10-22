# Reprise et livraison PCBWay

Objectif demandé le 18 octobre 2026 : livrer deux archives de production, un panneau comprenant les deux losanges et une Vivaldi seule, avec les simulations et le protocole permettant de comparer les cartes fabriquées aux prédictions.

## État courant

**Décision du 22 octobre : la livraison est qualifiée sur les grandeurs de décision, et la qualification ponctuelle reste en échec, conservée telle quelle.** Les deux verdicts coexistent dans `resultats/pcbway_maille_controlee_v2/` : `qualification_globale.json` répond non à « `S11` est-il prédit point par point ? » et `qualification_grandeurs_decision.json` répond oui à « les niveaux de maillage s'accordent-ils sur ce que l'antenne fait ? ». Le second ne remplace pas le premier et en cite l'empreinte. L'utilisateur a arrêté ce critère après le diagnostic ci-dessous, qui établit qu'un palier de maillage supplémentaire ne ferait pas passer le contrôle ponctuel. Les fichiers des deux articles sont dès lors déposables ; la prochaine information utile vient d'une mesure, pas d'un calcul.

Les six Run longs F2 et leurs neuf préfixes sont terminés. L'analyse automatique s'est achevée le 22 octobre à 06:12:27 à Paris : les trois contrôles temporels passent, les trois contrôles spatiaux échouent. Il s'agit d'une non-convergence numérique, sans échec technique de la campagne. Les quinze profils et les sources exactes sont archivés. Le diagnostic de l'opérateur discret se poursuit ; les dessins de fabrication et les seuils restent inchangés.

### Diagnostic du 22 octobre : la suite de raffinement remonte

Deux faits recalculés indépendamment sur les profils archivés, en lecture
seule, sans toucher aux sources gelées ni à aucun seuil. Voir la
[note](chatGPT_critical_review/convergence_grandeurs_decision_2026-10-22/note.md)
et son [rapport](chatGPT_critical_review/convergence_grandeurs_decision_2026-10-22/rapport.json).

**Premièrement, la suite spatiale du grand losange ne décroît pas.** Les
écarts complexes maximaux des paires consécutives à 12 ns valent 0,0463158,
0,0388005, 0,0249912, puis **0,0317481 et 0,0694264**. Les cinq valeurs
reproduisent exactement celles déjà consignées. La suite décroît sur trois
paliers, remonte sur les deux derniers, et atteint son plus mauvais écart au
maillage le plus fin. Une suite de discrétisation qui converge décroît ;
celle-ci mesure donc autre chose que l'erreur de discrétisation, ce que le
diagnostic des grilles closes avait déjà indiqué en relevant un
grossissement local de 1,69 près du port entre `extreme_fin` et `N30`.
**Conséquence : un palier plus fin ne fera pas passer ce contrôle.** Il
faudrait des grilles emboîtées au port, c'est-à-dire une campagne à concevoir.

**Deuxièmement, les grandeurs de décision s'accordent.** Sur la bande
1,4–6,0 GHz, l'étendue entre tous les niveaux d'une même antenne vaut, pour la
puissance réfléchie moyenne, 0,13 dB (petit losange F2), 0,13 dB (grand
losange F2) et 0,08 dB (Vivaldi F2) ; la part de bande sous −6 dB est
identique entre niveaux pour les deux antennes de travail. Sur les treize
niveaux F1 du grand losange, de 16 à 34 mailles par longueur d'onde dans le
substrat, la puissance moyenne tient dans 0,45 dB. La seule grandeur sensible
est la part sous −10 dB du petit losange, dont le `|S11|` longe ce seuil : un
artefact de comptage, et non un désaccord sur son comportement.

Ce diagnostic ne déclare aucune qualification et ne modifie aucun seuil. Il
pose la question du critère : le contrôle ponctuel en vigueur porte sur le
modèle, les grandeurs ci-dessus portent sur la décision de fabriquer. Le
choix entre les deux appartient à l'utilisateur ; la note en donne le coût.

### Intégration F2 et pilote opérateur

**Clôture du 22 octobre.** La Vivaldi fine est terminée à 06:11:58 à Paris après ses 132 657 pas ; ses deux préfixes sont clos à 06:12:20. Les deux files retournent zéro pour les six Run et neuf préfixes. AP retourne ensuite 2 avec un bilan cohérent `tous_reussis: false` ; l'orchestrateur conclut `non_convergence`, `echec_technique: false`. Le code 1 affiché par l'enveloppe PowerShell de la session native ne remplace pas le code Python 2 conservé dans les preuves. Aucun Run de la campagne ne reste actif.

| Antenne | Spatial : maximum / RMS / P95 module (dB) | Verdict spatial | Temporel : maximum / RMS / P95 module (dB) | Verdict temporel |
|---|---|---|---|---|
| Petit losange | 0,435832887 / 0,109906089 / 5,363894994 | Échec | 0,002477403 / 0,000649159 / 0,038182212 | Réussi |
| Grand losange | 0,412047226 / 0,117608407 / 5,260925393 | Échec | 0,000054704 / 0,000018540 / 0,001238802 | Réussi |
| Vivaldi | 0,365914022 / 0,084711140 / 3,020896434 | Échec | 0,001384749 / 0,000389235 / 0,028778024 | Réussi |

Seuils inchangés : spatial 0,05 / 0,02 / 1 dB ; temporel 0,015 / 0,005 / 0,5 dB. Les références sont passives à la tolérance retenue. La [contrelecture globale](chatGPT_critical_review/contrelecture_globale_F2_2026-10-22/rapport_croise.json) reproduit le bilan AP en lecture seule et confirme la Vivaldi par des formules NumPy indépendantes ; les quinze profils et dix-huit sources sont intacts.

L'[archive complète F2 close](archives/campagne_F2_cloture_non_convergente_2026-10-22.zip) contient 586 membres, avec CRC et chaque SHA vérifiés ; son SHA-256 est `77a54088bde56467fb7ee12ade79f9a222d7cc2983a676c4d4133fbe88a545e7`. Elle préserve l'échec et ne constitue pas une qualification de fabrication.

Après contrelecture du script et du wrapper natif, deux préparations d'opérateur sur les scènes archivées du petit losange ont été exécutées avec `setup_only=True`, sans intégration temporelle : codes 0, environ 14 et 35 secondes, originaux inchangés. Les dumps PEC, coefficients et boîtes de sondes sont produits dans [la préparation 03](chatGPT_critical_review/preparation_operateur_PEC_F2_2026-10-21/preparation_03/). Leur analyse démarre. Les axes NPZ et le pas sont restitués exactement, mais le CAD XML est arrondi : ce diagnostic ne prétend pas récupérer bit à bit l'ancien opérateur en mémoire. Aucun nouveau raffinement global n'est retenu à ce stade.

**Point du 21 octobre à 16:06 à Paris.** La Vivaldi fine atteint 101 265/132 657 pas (76,3 %). Elle est le seul Run actif ; les cinq autres sont terminés. L'orchestrateur ne signale aucun échec technique et attend sa fin avant les deux préfixes puis l'analyse globale. Les variations de vitesse rendent l'heure de fin incertaine ; l'extrapolation des dernières minutes vaut environ seize heures restantes.

La lecture indépendante du grand losange confirme exactement l'échec spatial relevé par Q et son contrôle temporel réussi. Son maximum d'écart apparaît à 4,850 GHz, comme celui du petit losange. L'inspection des géométries et grilles closes n'a démontré ni coupure ni court-circuit CAD de l'implantation SMA ; elle ne représente pas l'opérateur PEC effectif du solveur. L'examen de cet opérateur est la prochaine vérification discriminante à préparer, sans nouveau raffinement global ni modification des sources gelées.

**Point du 20 octobre à 22:53 à Paris.** Cinq Run longs sur six sont terminés. La file des losanges est close avec code 0, préfixes compris, depuis 19:12:55 à Paris. La Vivaldi fine est le seul Run actif : 55 346/132 657 pas (41,7 %). Douze profils sur les quinze prévus sont terminés ; les deux préfixes fins de la Vivaldi suivront son Run. Aucun échec technique n'est signalé par l'orchestrateur.

La relecture Q des cinq profils clos du grand losange montre aussi un **échec spatial F2** : maximum complexe 0,412047226, RMS 0,117608407, percentile 95 du module 5,260925393 dB. Son contrôle temporel fin 12/16 ns passe très largement (0,000054704 / 0,000018540 / 0,001238802 dB) et sa référence est passive. Les deux losanges échouent donc aux critères spatiaux des niveaux sélectionnés, malgré des fenêtres temporelles suffisamment stables selon les seuils retenus. L'analyse globale automatique attend toujours la Vivaldi ; ces résultats intermédiaires ne valident pas les ZIP. Le diagnostic des entrées et de la discrétisation continue sans toucher aux dix-huit sources gelées.

**Point du 20 octobre à 18:59 à Paris.** Les quatre Run précédemment terminés restent clos avec code 0. Le grand losange fin atteint 130 601/132 657 pas (98,5 %) ; la Vivaldi fine 44 756/132 657 (33,7 %). Les deux moteurs progressent et l'orchestrateur n'a signalé aucun échec technique. La lecture indépendante des cinq profils du petit losange confirme exactement les valeurs Q et son échec spatial, avec écart maximal à 4,850 GHz ; le contrôle temporel et la passivité passent. Voir le [rapport indépendant](chatGPT_critical_review/controle_petit_losange_F2_2026-10-20/lecture_independante.json). Les derniers Run ne sont pas encore terminés et l'analyse globale n'est pas lancée.

**Point du 20 octobre à 10:39 à Paris.** Quatre Run longs sur six sont terminés avec code 0 : les deux du petit losange et les niveaux de base du grand losange et de la Vivaldi. Les neuf profils dérivés ou complets correspondants sont présents. Les deux Run fins restants progressent : grand losange 51 931/132 657 pas (39,1 %), Vivaldi 24 732/132 657 (18,6 %). Ces pourcentages portent sur les itérations de chaque Run ; les coûts des antennes sont différents. Les statistiques natives et les sondes évoluent, même si les journaux stdout des deux Run fins restent en tampon. Les dix-huit sources gelées sont toujours exactes.

La relecture Q des cinq profils clos du petit losange révèle un **échec spatial F2** : base 12/fin 12 ns donnent un maximum complexe de 0,435832887, un RMS de 0,109906089 et un percentile 95 de module de 5,363894994 dB, au-delà des limites 0,05 / 0,02 / 1 dB. Le contrôle temporel fin 12/16 ns passe (0,002477403 / 0,000649159 / 0,038182212 dB) et la référence est passive. Le fait d'avoir terminé ses calculs ne qualifie donc pas le petit losange. Une lecture indépendante est en cours ; aucune cause physique de cet écart n'est encore démontrée et aucun seuil n'est modifié. Les deux autres Run continuent ; la livraison reste non validée.

La [décision de maillage](chatGPT_critical_review/decision_maillage_controle_2026-10-19.md) retient les grilles de la variante 10 : paramètres base 16/16/0,15 mm et fin 24/16/0,10 mm, vias quatre/six cellules, normales onze/dix-sept cellules, positions effectives U/I et PML contrôlées. Les douze constructions natives reproduisent les six NPZ retenus octet par octet, sans solveur. La compatibilité de Q/W/AP est étayée par 111 tests distincts, 25 contrôles ciblés de provenance et la relecture des 25 vrais profils F1. Ces contrôles logiciels ne qualifient aucune antenne F2.

La [preuve d'intégration](chatGPT_critical_review/integration_finale_f2/integration_appliquee.json) conserve les dix SHA physiques et les huit SHA de contrôle. Les neuf sources physiques F1 restent exactes ; le nouveau moteur ajoute sa propre source. Sa garde avant CalcPort impose les statistiques natives, NrTS+1 lignes et les abscisses U/I correctes ; neuf tests ciblés couvrent notamment les sorties tronquées. L'ajout du niveau historique N34 dans R et l'import CSV John sont intégrés ; leurs 25 tests passent dans l'arbre réel.

Le pilote est distinct de la production : `resultats/validation_maille_controle_v2/`, ancienne session native `53453`, PID initial `36668`. Il est terminé avec code natif 0 le 19 octobre à 15:11:36 UTC (17:11:36 à Paris). Il a exécuté 19 347 pas avec un pas opérateur de 1,8091917271563098 × 10⁻¹³ s. Les sondes U/I, le préfixe de 2 ns et son rejeu déplacé sont validés. CalcPort reproduit le S11 parent avec un écart complexe maximal de 6,77 × 10⁻¹⁴ ; les fichiers S1P du préfixe et du rejeu ont aussi été comparés directement et sont identiques octet par octet. Voir la [preuve du pilote](resultats/validation_maille_controle_v2/journaux/fin_pilote.json) et sa [contrelecture root](chatGPT_critical_review/integration_finale_f2/contrelecture_pilote_root.json). Les dix sources physiques et huit contrôles sont restés exacts. Ce pilote court ne constitue pas une étude de convergence.

La campagne longue est séparée dans `resultats/pcbway_maille_controlee_v2/` : deux Run par antenne (base 12 ns, fin 16 ns), puis les préfixes base 8 ns et fin 8/12 ns. Les contrôles finaux compareront base 12/fin 12 ns dans l'espace et fin 12/16 ns dans le temps. Les quinze profils et les essais préliminaires resteront conservés. La session `18488` suit l'orchestrateur PID `28980` ; ses premiers calculs sont le petit losange et la Vivaldi base 12 ns. Les [commandes et empreintes de lancement](chatGPT_critical_review/integration_finale_f2/lancement_campagne.json), les queues, la sélection et les dix-huit sources ont été archivées avant le lancement. Le [statut courant](resultats/pcbway_maille_controlee_v2/etat_orchestration.json) reste non qualifié pendant les calculs.

`orchestre_f2.py` enchaîne les calculs et préfixes sans écrasement, au plus deux à la fois. Après la réussite technique des deux files, il déclenchera automatiquement AP. Le code natif de chaque processus est conservé ; un code 2 d'analyse ne sera qualifié d'échec numérique qu'en présence d'un bilan F2 cohérent. Un échec technique arrête les étapes suivantes, laisse terminer le calcul actif de l'autre file et interdit l'analyse globale. Neuf tests avec sous-processus factices couvrent ces cas, la mutation des sources et le refus d'un pilote absent ou altéré. La preuve complète sera `fin_orchestration.json` ; aucun succès global n'est présumé.

Le [checkpoint de lancement F2](chatGPT_critical_review/integration_finale_f2/point_reprise_F2_2026-10-19.json) conserve les PID, leurs dates et les paramètres opérateur réellement observés. Les deux premiers Run ont un pas de 1,8091917271563098 × 10⁻¹³ s et 66 329 itérations demandées pour 12 ns ; ils sont encore en cours dans cet instantané. Ne pas relancer ces profils existants pour obtenir un statut.

Les [preuves du pilote](chatGPT_critical_review/verification_finale_reprise/pilote_maille_controlee_v2_preuves.zip) (97 membres) et les [preuves d'intégration F1/F2](chatGPT_critical_review/verification_finale_reprise/integration_moteurs_F1_F2_preuves.zip) (169 membres) sont fermées, avec CRC et chaque SHA vérifiés. Les calculs longs actifs en sont exclus. Le préparateur de livraison conserve maintenant aussi `controle_orchestration/`, le statut et les codes finaux : ses 35 tests passent. Les fonctions de validation numérique restent identiques.

Le générateur PDF est adapté au moteur indiqué par le bilan. Douze contrôles et deux rapports **synthétiques**, de sept et neuf pages, vérifient les refus, les textes F1/F2 et la mise en page ; toutes les pages sont rendues et inspectées. Une coupure entre tableau et explication a été corrigée. L'[archive de QA PDF](chatGPT_critical_review/verification_finale_reprise/pdf_moteur_controle_v2_preuves.zip) conserve ces essais explicitement non livrables. Le vrai PDF reste absent et devra être généré et inspecté à nouveau après réussite des résultats réels.

L'[archive complète F1](archives/campagne_F1_cloture_2026-10-19.zip), vérifiée membre par membre, conserve 25 profils et les sources exactes antérieures à cette intégration. Son SHA-256 est `a2d63d75a664b35289a13f3a46747469292b7c52fff1c8a8e3f5cb7461eb56b9`.

### Clôture N34 et décision du 19 octobre

La file `77627` s'est terminée avec code 0 le 19 octobre à 13:48:19 UTC (15:48:19 à Paris), préfixe de 8 ns et validation PLUS compris. L'observateur a déclenché l'analyse indépendante ; sa contrelecture par Q concorde exactement. Le contrôle spatial N30/N34 échoue sur le maximum complexe (0,069426408 > 0,05) et le percentile 95 en dB (1,076518714 > 1) ; le RMS passe (0,017957379 < 0,02). Le contrôle temporel N34 8/12 ns passe : 0,009388069 / 0,002406589 / 0,118247938 dB. Les treize profils sont passifs. Le plus grand écart spatial apparaît à 4,250 GHz.

Les [résultats N34](resultats/pcbway_r1/diamant_uwb_x18/bilan_intermediaire_n34.json), les [courbes inspectées](chatGPT_critical_review/controle_extreme_fin/comparaison_n34/) et l'[archive de preuves](chatGPT_critical_review/verification_finale_reprise/controle_n34_preuves.zip) conservent cet échec. Les 360 fichiers des treize profils et les 17 sources ont été vérifiés inchangés. La [preuve de fin](resultats/pcbway_r1/journaux/fin_grand_n34_resultats_2026-10-19.json) distingue les codes du solveur, de l'analyse numérique et du wrapper PowerShell.

Les constructions diagnostiques N38/N42 ne sont pas lancées : elles laissent les vias à deux cellules et déplacent encore des cellules critiques. La prochaine campagne devra contrôler le bloc d'alimentation, les arêtes du cuivre, les vias et les limites du domaine. Les anciens calculs restent un historique distinct ; aucun succès ne sera transféré automatiquement à la nouvelle stratégie.

Point de reprise : [checkpoint courant](resultats/pcbway_r1/journaux/reprise_grand_n34_vivaldi_ultra_fin_lancement.json).

Le [point après clôture de la Vivaldi](resultats/pcbway_r1/journaux/point_reprise_vivaldi_terminee_2026-10-19.json) conserve les preuves et l'état du grand au 19 octobre à 11:21 à Paris. La file N34 reste la session `77627`. L'observateur `26841` attend le vrai code terminal de son parent, puis déclenchera uniquement l'analyse indépendante des treize profils si la file termine avec code 0 et si les 17 sources sont inchangées. Son [script](resultats/pcbway_r1/journaux/surveille_fin_n34_et_analyse.ps1) ne lance aucun nouveau FDTD ; sa [revue préalable](chatGPT_critical_review/verification_finale_reprise/controle_observateur_n34_avant.json) est conservée. Le résultat différé sera dans `controle_extreme_fin/controle_final_n34/`, avec les attestations `journaux/fin_queue_n34_observee_automatiquement.json` et `journaux/fin_analyse_n34_automatique.json`.

Un [brouillon de sélection](chatGPT_critical_review/preparation_selection_n34_ultra_fin/selection_conditionnelle_n34_ultra_fin.json) conserve les 25 profils et 17 comparaisons préliminaires prévus. Sa structure est validée, sans lecture des résultats FDTD. Il reste hors de la campagne et ne sera installé qu'après réussite des contrôles N34 et intégration finale des outils.

La [contrelecture N34](chatGPT_critical_review/controle_extreme_fin/revue_croisee_n34/controle_croise.py) est préparée et relue statiquement, sans exécution ni accès aux profils N34. Après fin de l'observateur, elle vérifiera les attestations, les treize profils fermés et l'accord exact avec le helper, avant toute modification de R/Q/CSV. Elle conserve aussi un éventuel échec numérique (code 2) ; sa préparation ne présume aucun résultat.

Restent la campagne de convergence F2 et les contrôles finaux sur ses résultats réels, puis la qualification globale. Q/CSV sont intégrés et leurs tests passent. Les références finales, le PDF et la livraison des deux articles seront produits seulement si la qualification réussit. Les checkpoints et les sections suivantes conservent l'historique des étapes et lancements antérieurs ; leurs mentions de processus actifs décrivent ces instants passés.

Les deux audits du 18 octobre constituent l'état initial. Ils sont conservés comme documents historiques ; les chiffres de cet état ne seront pas présentés comme ceux de la nouvelle révision. Les sources et résultats d'origine sont archivés dans `archives/etat_avant_reprise_2026-10-18.zip`.

## Vivaldi : contrôles réussis le 19 octobre 2026

La file `81046` est terminée avec code 0, préfixe de 12 ns compris, le 19 octobre à 09:06:36 UTC (11:06:36 à Paris). Le calcul de 16 ns a exécuté 88 450 pas ; son préfixe causal en conserve 66 338. Les grilles et le pas temporel sont identiques bit à bit entre les deux fenêtres. Les sept profils sont passifs, avec un maximum de référence de 0,591672488.

| Comparaison | Maximum complexe | RMS complexe | Percentile 95 du module | Résultat |
|---|---:|---:|---:|---|
| Spatial : `tres_fin_16ns` → `ultra_fin_16ns` | 0,035163522 | 0,015978709 | 0,987341105 dB | Réussi |
| Temporel : `ultra_fin_12ns` → `ultra_fin_16ns` | 0,006451027 | 0,001720170 | 0,127713569 dB | Réussi |

L'analyse NumPy indépendante et la contrelecture par `Q.ecarts` donnent exactement les mêmes valeurs, seuils, masques, indicateurs et verdicts. Les 17 sources gelées et les 195 fichiers des sept profils ont été revérifiés sans changement. Les quatre comparaisons préliminaires, y compris leurs échecs, restent conservées. Voir la [preuve de fin de file](resultats/pcbway_r1/journaux/fin_vivaldi_ultra_fin_resultats_2026-10-19.json), le [rapport indépendant](chatGPT_critical_review/controle_vivaldi/controle_final_vivaldi_ultra/rapport.json) et la [contrelecture](chatGPT_critical_review/controle_vivaldi/revue_croisee_ultra_fin/rapport_croise.json).

Les deux courbes de contrôle et le bilan individuel sont dans [le dossier de comparaison](chatGPT_critical_review/controle_vivaldi/comparaison_ultra_fin_16ns/). L'[archive de preuves Vivaldi](chatGPT_critical_review/verification_finale_reprise/controle_vivaldi_ultra_fin_preuves.zip) conserve les rapports, figures, journaux, scripts et empreintes : ses 55 membres et 51 origines ont été revérifiés, CRC et SHA-256 compris. Les données brutes restent dans les sept profils d'origine ; cette archive ne constitue pas un ZIP de fabrication.

Sur la grille de 25 MHz entre 1,4 et 6,0 GHz, cette référence donne 160 points sur 185 sous −10 dB (86,49 %) et 185 sur 185 sous −6 dB. La moyenne de puissance réfléchie vaut −13,0822 dB et le pire point −7,14787 dB. Ces résultats concernent le modèle au port idéal en bord de PCB ; ils ne sont pas des mesures d'antennes fabriquées. La livraison globale attend toujours le grand losange et les contrôles finaux.

## Tâches et critères de fin

| ID | Tâche | État actuel | Critère de fin |
|---|---|---|---|
| T01 | Préserver sources, sondes brutes et audits | Fait | Archive intègre et inventoriée, antérieure aux corrections |
| T02 | Lire et trier les observations de la réponse Claude | Fait | Défauts avérés intégrés ; voir `chatGPT_critical_review/decisions_reprise_2026-10-18.md` |
| T03 | Définir le produit physique commun aux exports et au solveur | Fait | S1000H nominal, cuivre/ENIG, sans masque, SMA femelle Cinch documentée ; plans et limites explicites |
| T04 | Corriger maillage, temps, série commune et coût | Fait, convergence en T08 | Contrôles initiaux et série F1 conservés ; maillage F2 contrôlé en T12 et pilote opérateur/rejeu réussi en T14 |
| T05 | Fiabiliser pics, imports et compte rendu S11 | Fait | Contrôles de traitement et quatorze tests imports/CLI passent ; bandes disjointes explicites |
| T06 | Fiabiliser génération et contrôle indépendants des Gerbers | Fait | 21 tests passent ; surfaces, contours et PTH/NPTH comparés, rendus SVG/PNG lisibles |
| T07 | Supprimer les particularités de fabrication évitables | Fait | Garde cuivre/bord, trous et vias simulés ; guides commande, réception et implantation SMA écrits |
| T08 | Exécuter et archiver les simulations de la révision retenue | **Fait** sur le critère retenu | Quinze profils archivés ; qualification acquise sur les grandeurs de décision, échec ponctuel conservé et expliqué |
| T09 | Produire les références pour comparaison avec les cartes | **Fait** | Protocole écrit ; trois `reference_simulation.s1p` émises sur la grille de mesure (213 points, 1,000–6,300 GHz), différence de plans explicitée |
| T10 | Générer et contrôler les deux articles finaux | **Fait** | Deux ZIP conformes à leurs empreintes, relus par gerbonara : surfaces, contours, PTH/NPTH et rendus tous valides |
| T11 | Relecture indépendante et livraison | **Fait** | Chaîne fermée par `verifie_coherence_livraison.py` : neuf maillons, dont les 18 sources gelées identiques à l'arbre courant ; 93 tests `ph` et 98 tests `openems` (plus 85 sous-tests) passent |
| T12 | Contrôler le maillage du port, des arêtes et des vias | Fait, construction et pilote | Six grilles base/fin relues, positions effectives des sondes et raffinement local vérifiés, domaines/PML contrôlés, coûts construits conservés ; chaque Run long calibre encore son propre opérateur |
| T13 | Séparer et tracer les moteurs F1/F2 | Fait | Sources exactes archivées, marqueurs stricts, ancien lecteur compatible, moteurs mélangés refusés, axes temporels contrôlés directement |
| T14 | Valider un petit essai réel F2 et son préfixe | Fait | Opérateur, durée, reconstruction depuis sources archivées et S11 parent reproduits ; fichiers du rejeu déplacé identiques |
| T15 | Orchestrer les deux files et l'analyse différée | Fait | Six Run et neuf préfixes code 0 ; AP code 2 non-convergence conservé ; dix-huit sources exactes |

## Périmètre

La livraison prépare les fichiers à déposer et la comparaison expérimentale. Elle ne comprend ni achat ni dépôt sur le compte PCBWay. L'explication des décalages historiques de l'UWB Surveyor reste un travail séparé et ne conditionne pas la fabrication de ces trois antennes. Les propriétés GHz d'un FR4 générique et la transition réelle d'un connecteur ne seront pas présentées comme mesurées.

## Décisions de départ

- Deux couches, substrat de 1,6 mm, cuivre 1 oz, finition ENIG, absence de vernis et de sérigraphie.
- Panneau client contenant deux dessins différents, livré en cinq panneaux ; Vivaldi seule, cinq cartes.
- Nominal de production S1000H documenté à 1 GHz, identique pour les trois cartes ; extrapolation Debye explicitement hypothétique.
- SMA femelle standard Cinch Johnson 142-0701-851, choix confirmé par l'utilisateur ; câble SMA mâle–mâle vers le LiteVNA.
- Les courbes de l'ancienne révision restent disponibles dans l'archive, distinctes des simulations de production.
- La comparaison au LiteVNA porte sur la bande effectivement calculée et sur un plan de référence défini. Les modèles de transition et leurs limites seront documentés.

## Contrôle intermédiaire du petit losange

Le raffinement spatial à 8 ns passe : écart complexe maximal 0,01564, RMS 0,00720 et percentile 95 du module 0,4846 dB, sous les limites 0,05 / 0,02 / 1 dB.

La comparaison temporelle de 8 à 12 ns échoue : maximal 0,02134 pour une limite de 0,015 et RMS 0,005340 pour une limite de 0,005. Le percentile 95 en dB passe, à 0,2322 dB. Une faible énergie finale ne suffit donc pas à conclure à elle seule.

La vérification est prolongée à 16 ns sur les deux maillages. Le contrôle final du petit losange comparera les maillages de base et fin à 16 ns, puis les fenêtres fines de 12 et 16 ns, avec les mêmes seuils. Les premiers calculs et leur échec restent conservés. Les autres antennes suivent encore la campagne de départ, sous réserve de leurs résultats.

**Résultat petit losange : les deux contrôles finaux passent.** À 16 ns, le raffinement donne maximum complexe 0,016207, RMS 0,007257 et percentile 95 du module 0,4863 dB. De 12 à 16 ns sur le maillage fin : 0,006909 / 0,001730 / 0,07385 dB. Les coordonnées des grilles et le pas temporel sont identiques pour cette seconde comparaison. La référence retenue est `diamant_uwb/fin_16ns`.

Le diagnostic supplémentaire base 8 ns/base 16 ns échoue aussi (0,02657 / 0,005315 / 0,2160 dB), ce qui confirme l'insuffisance de 8 ns. Il sera conservé parmi les essais préliminaires avec les premières paires. Les valeurs de la référence fine restent passives et donnent deux intervalles sous −10 dB : 2,475–3,325 GHz et 4,525–6,300 GHz, sur la grille de 25 MHz. La qualification globale attend les deux autres antennes.

La première batterie logicielle complète compte 114 tests et 39 contrôles de traitement réussis ; les journaux sont dans `chatGPT_critical_review/verification_finale_reprise/`. Ils ne remplacent pas la qualification électromagnétique en cours. Les nouveaux contrôles de sélection et de suivi seront inclus dans la vérification finale.

La batterie enrichie vient de passer : **143 tests et 39 contrôles**, avec les nouvelles protections de sélection, de portabilité et de suivi Windows. Le fichier `validation_logicielle_intermediaire_143.json` conserve leurs journaux et empreintes de sources. L'intégration finale du routage adaptatif sera contrôlée après la fin des calculs déjà lancés.

## Contrôle intermédiaire du grand losange

La durée de 12 ns est suffisante par rapport à 8 ns sur le maillage fin : maximum complexe 0,008496, RMS 0,002183 et percentile 95 du module 0,1013 dB, sous 0,015 / 0,005 / 0,5 dB.

Le raffinement de base vers fin à 8 ns échoue : maximum 0,05552, RMS 0,03841 et percentile 95 du module 2,1967 dB, au-dessus des limites 0,05 / 0,02 / 1 dB. Un calcul au niveau `tres_fin` est nécessaire. La qualification prévue comparera `fin_12ns` à `tres_fin_12ns`, puis les fenêtres de 8 et 12 ns sur ce dernier maillage. Les essais initiaux et leurs résultats seront conservés.

## Incident de suivi Windows

Le fichier de statut a rencontré un verrou Windows transitoire pendant son remplacement atomique. Le suivi a suspendu les nouveaux lancements et laissé les deux solveurs actifs continuer. Le statut de cet incident est conservé dans `resultats/pcbway_r1/journaux/pipeline_statut_incident_verrou_windows_2026-10-18.json`.

Le suivi réessaie désormais le remplacement pendant deux secondes au maximum ; les lectures de surveillance partagent aussi le droit de remplacement. Les deux processus ont été réadoptés après vérification de leur identité. La reprise conserve les calculs terminés et les données déjà écrites. Les contrôles transitoire/permanent et la lisibilité du JSON sont testés.

## Controle intermediaire de la Vivaldi

Les trois calculs initiaux sont termines et leurs archives ont ete relues. Les deux criteres de convergence echouent : spatial base8/fin8, maximum complexe 0,094265, RMS 0,041793 et percentile 95 du module 2,5985 dB ; temporel fin8/fin12, 0,031724 / 0,008299 / 0,5811 dB. La passivite numerique de la reference provisoire fin12 passe (maximum |S11| = 0,585665). Elle ne suffit pas a qualifier ce calcul.

Le raffinement prevu utilise un calcul `tres_fin_16ns`, dont une fenetre causale `tres_fin_12ns` sera extraite. Le controle spatial comparera `fin_12ns` a `tres_fin_12ns` et le controle temporel comparera `tres_fin_12ns` a `tres_fin_16ns`, sur la meme grille et avec le meme pas reel. Cette selection reste conditionnelle aux ecarts effectivement mesures ; les seuils sont inchanges. Les deux comparaisons initiales echouees seront conservees parmi les preliminaires.

La comparaison initiale des neuf dossiers (8/12 ns), ses courbes et ses references sont archivees dans `resultats/pcbway_r1/journaux/comparaison_initiale_8_12ns.zip`, avec un index SHA-256 relu. Les six scripts de controle et le statut final initial sont figes dans `journaux/controle_initial/`. Le suivi initial est termine ; il ne constitue pas la qualification finale adaptee.

Le calcul Vivaldi `tres_fin_16ns` est lance le 18 octobre a 12:42:31 UTC (PID initial 35652), suivi automatiquement de l'extraction causale a 12 ns ; file d'attente `journaux/raffine_vivaldi_tres_fin_16ns.ps1`. Les trois benchmarks isoles a 2/4/10 fils donnent 17,83 / 20,81 / 23,51 millions de cellules par seconde ; 10 fils est retenu. Leurs grilles sont identiques et leurs XML/statistiques sont conserves sous `journaux/benchmark_vivaldi_tres_fin/`. Ils servent uniquement a choisir les ressources et sont exclus des preuves de convergence. La projection du calcul complet est d'environ 15 heures avec le grand losange simultane ; elle est indicative. Les sources restent figees jusqu'a la fin des deux files. Aucun de ces nouveaux resultats n'est encore declare reussi.

## Deuxieme controle spatial du grand losange

Le calcul `tres_fin_12ns` et son prefixe causal de 8 ns sont termines le 18 octobre a 13:22:31 UTC, file initiale achevee avec code 0. Les cinq dossiers du grand losange ont ete relus et leurs geometries, sources, environnement et durees revalides. Le controle temporel tres_fin8/tres_fin12 passe : maximum complexe 0,009481, RMS 0,002432 et percentile 95 du module 0,1068 dB.

Le controle spatial fin12/tres_fin12 echoue encore : maximum complexe 0,046316 (sous 0,05), RMS 0,025816 (au-dessus de 0,02) et percentile 95 du module 1,1858 dB (au-dessus de 1 dB). Un niveau supplementaire `ultra_fin` est prepare : 22 mailles par longueur d'onde dans le substrat, 16 dans l'air et cible locale 0,125 mm. Les niveaux existants et toutes les sources physiques restent inchanges pendant la Vivaldi. Le nouveau lancement passe par un module de controle distinct pour respecter ce gel.

La selection conditionnelle du grand devient spatiale tres_fin12/ultra_fin12 et temporelle ultra_fin8/ultra_fin12. Les deux essais initiaux et les deux nouveaux essais tres_fin restent dans l'historique : sept dossiers grand au total. Avec les cinq petits et les cinq Vivaldi vises, la livraison conserverait 17 dossiers, sous reserve de reussite effective. Le bilan reel est dans `resultats/pcbway_r1/diamant_uwb_x18/bilan_intermediaire_tres_fin.json` ; son graphique provisoire ne vaut pas qualification finale.

Le calcul grand `ultra_fin_12ns` est lance le 18 octobre a 13:26:40 UTC, PID initial 3720, file `journaux/raffine_grand_losange_ultra_fin.ps1` ; le prefixe de 8 ns suivra automatiquement apres un nouveau controle des empreintes. Le pas calibre reel est 0,176224649 ps et 68 096 iterations sont imposees. Le module de controle complementaire est teste (7/7) et son script exact, le Q exact et les parametres sont archives avant Run, hors du dossier physique. Le point de reprise est `journaux/reprise_grand_ultra_fin_lancement.json`. La Vivaldi et ce grand calcul sont les deux seuls solveurs actifs. La qualification finale reste en attente.

Les sept tests du controleur de raffinement complementaire passent (`journaux/tests_raffine_qualification_pcbway.txt`). Les 34 tests de livraison passent ensemble, dont une fixture integree de 17 profils et neuf essais preliminaires avec le niveau ultra_fin (`chatGPT_critical_review/verification_finale_reprise/livraison_34_ultra.txt`). La fixture reste separee de la campagne reelle : elle ne presume aucun resultat electromagnetique. Le constructeur PDF accepte maintenant les niveaux du catalogue Q via AP, avec refus des noms inconnus et des chemins sortants. L'integration finale dans Q et sa verification complete attendent toujours la fin des deux calculs et de leurs prefixes.

## Donnees experimentales apportees par Maurice

L'utilisateur a indique le paquet `from Maurice/plexiglas`. Les trois copies du rapport John sont identiques et les 55 fichiers de ce paquet ont ete inventories sans modification. Les exports complexes du 9 octobre permettent de reproduire exactement les pics historiques et, a l'arrondi numerique, les pentes de phase ; les NPZ et la SOL sources ne sont pas inclus. Le contexte est Nooelec + plaque aluminium, distinct des antennes PCBWay et des essais dielectriques. Voir `chatGPT_critical_review/donnees_experimentales_john_2026-10-18.md` et son inventaire SHA-256. Les S1P sont utilisables immediatement ; les alias CSV s11_real/s11_imag pourront etre ajoutes apres le gel. Aucun source physique ni pilote n'a ete modifie, aucun VNA contacte.

## Troisieme controle spatial du grand et niveau suivant

La file ultra s'est terminee avec code 0 le 18 octobre a 14:45:45 UTC. Les sept dossiers sont integres et les calculs independants confirment : spatial tres_fin12/ultra_fin12, maximum 0,038800 et percentile 95 du module 0,9309 dB passants, mais RMS 0,021624 encore au-dessus de 0,02 ; temporel ultra_fin8/ultra_fin12 passant a 0,009981 / 0,002564 / 0,1272 dB. Le bilan intermediaire est conserve sans qualification dans `diamant_uwb_x18/bilan_intermediaire_ultra_fin.json`.

Le nouveau niveau `extreme_fin` ajoute 26 mailles par longueur d'onde dans le substrat, 18 dans l'air et une cible locale de 0,10 mm ; aucune definition existante ne change. R a ete etendu seulement apres la fin de sa file ultra, avec sa version precedente conservee. Il n'est ni charge ni hashe par le Q utilise pour la Vivaldi deja en cours ; ses sources physiques et ses scripts controles restent inchanges. Huit tests R passent.

Le calcul `extreme_fin_12ns` est lance a 14:48:37 UTC, PID initial 62652, file `journaux/raffine_grand_losange_extreme_fin.ps1`, session8645. Grille4 884 256 cellules, pas calibre reel0,104572997 ps,114 754 iterations. Un prefixe8ns suivra automatiquement. Les comparaisons conditionnelles seront ultra_fin12/extreme_fin12 et extreme_fin8/extreme_fin12 ; tous les sept dossiers precedents restent conserves, soit neuf grand et19 au total avec cinq petits et cinq Vivaldi. Les onze essais preliminaires restent traces. Aucun seuil n'est modifie. Le point de reprise est `journaux/reprise_grand_extreme_fin_lancement.json`.

Le correctif minimal des alias CSV John est prepare et teste sur copie isolee sous `chatGPT_critical_review/staging_import_csv_john/` (17 tests, dont10 imports existants et7 cibles). Son application aux sources et les tests finaux attendent toujours la fin des deux files actives.

## Reprise selective de la bibliotheque commun de Maurice

Les six fichiers de `from Maurice/commun` ont ete compares a la racine. Les controles d'entree et la documentation de `profil_distance` sont repris ; ses calculs pour les donnees valides restent strictement identiques sur 135 profils. La fonction `cote_plaque_mm`, absente de la copie Maurice mais requise par cartilage, est conservee. Huit tests cibles, 19 tests Maurice visant explicitement la bibliotheque racine et dix cas synthetiques cartilage passent, sans acces au VNA. Les originaux, differences et SHA sont archives. Voir `chatGPT_critical_review/revue_commun_maurice_2026-10-18.md`.

Le README commun, la documentation du module instrument et le protocole de mesure corrigent l'affirmation « USB toujours brut ». Le manuel decrit un mode3 corrige mais garde un paragraphe FIFO contradictoire ; scikit-rf1.12.0 ne selectionne ni ne verifie explicitement le mode0x26. Le mode effectif, le firmware et la calibration devront etre identifies au banc avant les mesures T09, afin d'eviter une SOL absente ou double. Aucun comportement du pilote ni source de la campagne FDTD n'est modifie. Les sources Maurice restent intactes ; aucune fusion complete de repertoire n'a ete faite.


## Raccordement final prepare hors des sources gelees

Le correctif Q est prepare sous `chatGPT_critical_review/staging_integration_qualification/` : enregistrement du catalogue R, comparaison AP en presence d'une selection et entree CLI deleguant au meme module canonique que les imports AP/L. Les options, defauts et comparaisons initiales sans selection restent conserves. La preparation a passe 54 tests Q/AP/R/integration et34 tests L sur copie ; apres deplacement du drapeau anti-cache avant delegation, les sept controles cibles CLI/import passent. Une contre-relecture independante confirme le patch.

Les checks demeurent exclusivement sur copie temporaire : ils supposent une campagne neuve et ne doivent pas etre installes directement dans les tests du projet reel. Le runner offre maintenant `--source-integree` pour verifier une copie du Q final apres application, sans reappliquer le patch ni ecrire dans le depot. Cette voie est testee avec une campagne et un cache temoins existants preserves ; une source au SHA inconnu est refusee. Les preuves et le patch final sont archives dans `verification_finale_reprise/staging_integration_qualification_preuves.zip`.

Le correctif n'est pas encore applique. Q reel reste au SHA2e6b6f7f07b8903acfa6a51eb40bab6f3961dd1af1a95e7b76d9661f0af70ac4, seize sources gelees sont recontrolees identiques, aucune selection reelle ni livraison finale n'est creee. L'application de ce patch et de l'import CSV John, puis la suite logicielle finale, attendent toujours la fin des deux files physiques et de leurs prefixes.


## Contre-verification independante du niveau extreme preparee

Un analyseur reproductible en lecture seule est prepare dans `chatGPT_critical_review/controle_extreme_fin/analyse_extreme_fin.py`. Il recalcule les metriques directement avec NumPy sans Q.ecarts, apres controle Q des neuf profils, des sources/environnement/contrats communs et de l'identite binaire des grilles et dt de la paire temporelle. Sa verification sur les sept profils precedents retrouve exactement RMS spatial0,02162359892061181 et maximum temporel0,009980515944572232 ;195 fichiers des profils restent identiques. Les fonctions numeriques et toute la branche de calcul finale sont ensuite confirmees identiques par AST apres ajout du lecteur Windows partage et de la precondition de coordination.

Le precontrole des manifestes actifs utilise FILE_SHARE_READ|WRITE|DELETE. L'outil attend toutes les preuves et la confirmation explicite par le coordinateur de la sortie0 de la file avant d'appeler Q.charge_calcul. Apres constat de fin0 de la session8645 et de son prefixe8ns, executer depuis la racine avec Python openems : `python -B -X utf8 simulation/chatGPT_critical_review/controle_extreme_fin/analyse_extreme_fin.py --queue-sortie-zero-confirmee --sortie controle_final_extreme`. Le dossier de rapport doit etre neuf sous controle_extreme_fin. Ce rapport independant ne cree aucune selection ni qualification officielle. Seize sources gelees sont de nouveau confirmees inchangées.


## Quatrieme controle spatial du grand et lancement n30

La file extreme s'est terminee avec code0 le18octobre a18:14:35UTC, prefixe8ns compris. Les neuf profils sont relus et deux calculs independants concordent exactement. Spatial ultra12/extreme12 : maximum0,024991 et RMS0,017770 passent, mais percentile95du module1,125231dB depasse1dB sur191points admissibles. Temporel extreme8/12 :0,009746 /0,002500 /0,112086dB, passant ; grille etdt identiques bitabit, passivite maximale0,830719. Le bilan et le graphique restent explicitement provisoires et refuses. Rapport NumPy et contrelecture Q.ecarts sont archives sous `chatGPT_critical_review/controle_extreme_fin/`, avec paquet SHA relu dans verification_finale_reprise.

Un niveau `n30` ajoute30mailles par longueur d'onde substrat,20dans l'air et cible locale1/12mm. Le R precedent et ses huit tests sont archives dans `journaux/controle_extension_n30/`. Seules deux lignes de definition sont ajoutees ; anciens niveaux, Q et tous les seuils restent inchanges. Huit tests passent et une revue independante valide la filePS1 sans execution.

Le calcul n30_12ns est lance a18:17:31UTC, PID39188, session14137, file `journaux/raffine_grand_losange_n30.ps1`, suivie automatiquement du prefixe n30_8ns. La calibration operateur donne dt reel0,082036696ps et146278iterations sur6611829cellules Yee. Le R533c2678aba6219073601fc0101682bc82ae52c5b221ce66bfecfac323f859fb est a nouveau gele pendant cette file. La Vivaldi35652/session20307 reste l'autre seul solveur actif.

Les paires conditionnelles deviennent extreme12/n30_12 et n30_8/n30_12, avec les huit comparaisons precedentes du grand conservees. Cela viserait onze profils grand et21au total, avec13comparaisons preliminaires (petit3/grand8/V2), uniquement si les prochains controles passent. Aucune selection reelle n'est creee. Le point de reprise est `journaux/reprise_grand_n30_lancement.json`.


## Verification independante du palier n30 preparee

L'analyseur hors sources physiques accepte maintenant `--n30` : onze profils grand, espace extreme12/n30_12 et temps n30_8/n30_12, reference provisoire n30_12. Les modes precedents sept/neuf profils sont conserves, les quatre fonctions numeriques et les lectures partagees Windows sont inchangees par AST. La nouvelle version retrouve exactement toutes les metriques du bilan extreme ;250fichiers des neuf profils termines conservent leurs SHA. Le mode n30 sans attestation de sortie0 retourne proprement les preconditions manquantes sans charger les calculs. L'ancienne version et son contrat sont preserves dans extension_n30_avant ; preuve et usage sont dans controle_extreme_fin.

Apres confirmation de la sortie0 de session14137, prefixe8ns compris, executer avec Python openems depuis la racine : `python -B -X utf8 simulation/chatGPT_critical_review/controle_extreme_fin/analyse_extreme_fin.py --n30 --queue-sortie-zero-confirmee --sortie controle_final_n30`. Le dossier de sortie doit etre neuf. SHA analyseur actuel d31fd9e40b7b4c6bc4d9549244c13a31457d6392007fd8c2167c0248d78d81a2. Ce controle ne produit toujours aucune selection ni qualification officielle. Les seize sources gelees de la campagne sont de nouveau confirmees inchangées.


## Contre-verification Vivaldi preparee

L'outil `chatGPT_critical_review/controle_vivaldi/analyse_vivaldi.py` reutilise les metriques et lecteurs partages du controle grand, sans dupliquer leurs algorithmes. Il attend les cinq profils Vivaldi et l'attestation de fin0 de session20307, prefixe tres_fin_12ns compris. Il comparera fin12/tresfin12 dans l'espace et tresfin12/tresfin16 dans le temps, avec reference tresfin16. La preuve separee sur les trois profils initiaux retrouve exactement les six valeurs d'ecart deja archivees ;les deux echecs attendus sont conserves. Elle ne pretend pas que la file globale initiale etait sortie0 :celle-ci s'etait terminee en echec numerique. Les85fichiers de ces profils et16sources gelees sont confirmes identiques.

Apres fin confirmee de la file, executer depuis la racine avec Python openems : `python -B -X utf8 simulation/chatGPT_critical_review/controle_vivaldi/analyse_vivaldi.py --queue-sortie-zero-confirmee --sortie controle_final_vivaldi`. Le dossier de sortie doit etre neuf sous controle_vivaldi. SHA outil3dce54db99c768a48b479e845e1ad9ea52ba1e6f4d2cc6c6231beaf2c947c5f8 ;utilitaire partage d31fd9e40b7b4c6bc4d9549244c13a31457d6392007fd8c2167c0248d78d81a2. Aucun calcul final ni selection officielle n'est cree par cette preparation.


## Deuxieme controle Vivaldi et lancement ultra_fin

La file Vivaldi tres_fin s'est terminee avec code0 le18octobre a21:19:08UTC, prefixe12ns compris. Les cinq profils ont ete relus et deux methodes independantes donnent exactement les memes ecarts. Spatial fin12/tres_fin12 : maximum0,0716368965, RMS0,0316621924 et percentile95du module2,5289229576dB ; les trois limites0,05/0,02/1dB sont depassees. Temporel tres_fin12/16 passe a0,0075183392 /0,0019619897 /0,1354810273dB ; grille etdt identiques bitabit. Les cinq profils sont passifs. Le rapport, sa contrelecture et le graphique restent provisoires et spatialement refuses. Ils sont archives avec le helper exact dans `verification_finale_reprise/controle_vivaldi_tres_fin_preuves.zip` (SHA c102b09a0a3e2f55b111f8e067702ec64c8dc41118dc60c4aee6f8ee0ae6a20b).

Le niveau ultra_fin EXISTANT de R533c est utilise sans aucune edition de source :22mailles par longueur d'onde substrat,16dans l'air et ciblelocale0,125mm. Son cout et sa memoire avec N30 deja actif ont ete controles ; reserve proposee4Gio avec plusde6,26Gio disponibles au lancement. La filePS1 a passe une seconde revue AST/empreintes/commandes/absence de collisions. Le calcul ultra_fin_16ns est lance a21:23:32UTC, PID13052, session81046,10fils, sur17933482cellules Yee. Un prefixe causal12ns suivra automatiquement seulement apres code0 et recontrole des empreintes. Le dt reel et les iterations seront releves apres calibration operateur ; le cout prealable de12,66heures a30Mcellules/s n'est pas une echeance garantie.

Les paires V conditionnelles deviennent tres_fin16/ultra_fin16 dans l'espace et ultra_fin12/16 dans le temps, reference ultra_fin16. Les quatre comparaisons precedentes restent dans l'historique. Avec petit5/grand11/V7, cela viserait23profils et15comparaisons preliminaires (petit3/grand8/V4), uniquement apres reussite effective. Le grand N30 PID39188/session14137 et cette Vivaldi sont les deux seuls solveurs actifs. Les seize sources restent gelees, R compris ; aucun patchQ/CSV, aucune selection reelle ni livraison finale n'est creee. Point de reprise courant : `journaux/reprise_grand_n30_vivaldi_ultra_fin_lancement.json`.


La calibration operateur V ultra_fin impose finalement dt reel1,8089657413612908e-13s et88450iterations, sur18156096points operateur (17933482cellules Yee). Le solveur complet est observe actif apres la pre-calibration de deux pas, dont les avertissements de duree sont attendus et ne concernent pas la duree88450pas finale.

L'analyseur V dispose maintenant de `--ultra-fin`, avec les sept profils et les paires TF16/UF16 etUF12/UF16. Son mode precedent reproduit exactement tous les champs numeriques des cinq profils, code2 attendu ; le mode nouveau actif rend code3sans appeler Q.charge_calcul ni attester de sortie0. Ancien helper3dce etcontrat conserves avant edition ; les140fichiers termines et16sources sont inchanges. Root a revu la difference et les preuves. Apres fin0 effective de session81046 avec prefixe12, executer avec Python openems : `python -B -X utf8 simulation/chatGPT_critical_review/controle_vivaldi/analyse_vivaldi.py --ultra-fin --queue-sortie-zero-confirmee --sortie controle_final_vivaldi_ultra`. Nouveau SHA f985d19ecd6d8c876691f9417f4d6df3e656c95ca5a75b8941c7b57ebee150e3.

La relecture L/AP/PDF confirme leur compatibilite avec23profils et15preliminaires, sous reserve du raccordementQ apresgel. Les helpers etendus f985 et sa dependance numerique d31, avec usages/contrats/snapshots/preuves, sont archives dans `verification_finale_reprise/controle_helpers_n30_vivaldi_ultra_preuves.zip` (SHA97f71bce5935169316e12a0171ec3b29be7b6b44cbe2bf306370b27b85faa1d4). Ses58membres plats ont ete relus avecCRC/SHA, les autres ZIP historiques restent inchanges. Cet ajout comble la dependance d31 citee par le precedent rapport V ; il ne pretend pas etre un projet autonome sans sources/profils.


## Cinquieme controle spatial du grand : resultat N30

La file N30 a termine avec code0 le19octobre a02:02:57UTC, prefixe8ns compris. Le solveur a effectue146278iterations sur6721440points operateur en27876,94s ; le prefixe causal contient97519pas. Les onze profils ont ete relus et valides ; deux implementations independantes donnent exactement les memes valeurs. Spatial extreme12/n30_12 : maximum0,0317480931 sous0,05, RMS0,0212988281 au-dessus de0,02 et percentile95du module1,4211171777dB au-dessus de1dB sur185points admissibles. C'est un echec spatial, sans modification de seuil. Temporel n30_8/12 :0,0097155380 /0,0024884228 /0,1284848879dB, passant. Coordonnees etdt sont identiques bitabit (dt8,203669576847067e-14s), passivite des onze profils reussie, maximum final0,8324793906.

Rapport NumPy et controle Q.ecarts sont sous `chatGPT_critical_review/controle_extreme_fin/controle_final_n30/` et `revue_croisee_n30/`. Le bilan `diamant_uwb_x18/bilan_intermediaire_n30.json` reste explicitement refuse et provisoire. Les seize sources gelees sont confirmees inchangees. La file Vivaldi81046/PID13052 reste active, autour de41pourcent au constat de fin N30.

La preparation suivante emploie un NOUVEAU controleur autonome `raffine_qualification_plus_pcbway.py`, hors des seize fichiers geles, pour le niveau n34 :34mailles par longueur d'onde substrat,22dans l'air et cible locale1/14mm. Ce controleur et ses controles/cout/relecture sont en cours de preparation. Aucun calcul n34 n'est encore lance : les tests, le cout et la revue du controleur restent a finaliser. L'etude du mecanisme et ses garde-fous sont conserves dans `journaux/point_suivi_2026-10-19_0132.json` ; le constat de fin est `journaux/fin_grand_n30_resultats_2026-10-19.json`. Le prochain controle spatial prevu comparera n30_12/n34_12 et le temporel n34_8/n34_12, avec tous les echecs precedents conserves. Si ces prochains controles passent, cela viserait13profils grand,25au total et17preliminaires (petit3/grand10/V4). Ces nombres restent conditionnels ; aucune selection officielle ni livraison finale n'est creee.


## Lancement N34 par controleur distinct

Le nouveau controleur PLUS et sa file PS ont passe deux relectures,14tests isoles (code0, aucunFDTD) et le cout/memoire. Les305fichiers des onze profils grand et les seize sources existantes gardent leurs SHA. PLUS15fe2ef41de4c4c3c4da0954dc2396fa652f3b75ba18d0f373824a4aab39d3c3 est scelle ; les preuves exactes sont sous `journaux/controle_n34_plus_avant/`. La filePSa882257a59d5d856fe950e724deab93e5039084ef51542152c5dad86ba035e62 refuse toute collision des deux profils, de l'archive Run et de ses six journaux. Elle impose codes0 et controles des17sources entre les phases.

Le calcul n34_12ns est lance le19octobre a02:14:01UTC, PID532, session77627,10fils. Il utilise8539020cellules Yee ; le cout avant calibration est136157pas et645,915minutes indicatives a30Mcellules/s. Le dt reel et le nombre de pas seront releves apres calibration ; aucune echeance de fin n'est garantie. Le precontrole mesure9,84Gio de RAM et8,20Gio de commit libres avec la seule Vivaldi active ; la memoire est compatible avec deux solveurs. L'archive avant Run est `journaux/controle_raffinement_plus/diamant_uwb_x18/n34_12ns/`.

La sequence est PLUS12avec validation puisWprefix8 puisPLUSverificationseule8, avec verificationsSHA entre et apres les phases. Dix-sept sources sont desormais gelees : les seize precedentes et PLUS15fe. La Vivaldi13052/session81046 reste l'autre solveur actif ; aucun ajoutn34 dansR533c, aucun patchQ/CSV ni selection reelle n'est applique pendant ces files. Apres TOUTES fins seulement, la definition Python n34 devra etre copiee exactement dansRfinal avant le raccordementQ/AP et les controles globaux. Le point courant est `journaux/reprise_grand_n34_vivaldi_ultra_fin_lancement.json`.


La calibration N34 donne finalement dt reel7,7350114375119956e-14s et155140iterations, avec8669808points operateur (grille252/244/141lignes et8539020cellules Yee). Le solveur complet est constate actif apres les deux pas de precalibration. Les avertissements de deux pas trop courts et de timestep faible sont coherents avec cette precalibration et le maillage fin ; la duree reelle finale est bien12ns, sans arret sur energie.

Le helper grand hors17sources est etendu a `--n34`, SHA2d5215a9e388d2c8cfd6f075eafde1776246d9de3bfe84461a9eda06d94e3b9b. AncienD31 etcontrat sont preserves dans extension_n34_avant ; six fonctions numeriques/lecteurs restent identiques parAST. Les replays des onze grands et cinq Vivaldi termines retrouvent exactement tous les champs horsprovenance ;17sources et445fichiers termines gardent leursSHA. Le mode n34 actif rend code3sansattestation0 et sansQ.charge_calcul. Les preuves sont sous controle_extreme_fin/verification_extension_n34/ ; root a revu la difference et une contrelecture independante ne trouve pas de defaut.

Apres FIN0 REELLE de session77627 (prefixe8 ETvalidationPLUS compris), executer avec Python openems : `python -B -X utf8 simulation/chatGPT_critical_review/controle_extreme_fin/analyse_extreme_fin.py --n34 --queue-sortie-zero-confirmee --sortie controle_final_n34`. Le dossier doit etre neuf. Aucune attestation de fin n'est encore fournie pour77627 ni81046. Ce helper ne cree ni selection ni qualification officielle.

Les preuves N30 refusees, courbes et controles sont archivees dans `verification_finale_reprise/controle_n30_preuves.zip` (SHAf2992757544c969fe198dd12d440b38a077648998e69488f5aead0c80893a88f),16membres relusCRC/SHAparagentetroot. Les copies prealables du controleurPLUS, des14tests, du PS et des controles/cout/memoire sont dans `verification_finale_reprise/controle_n34_plus_avant_preuves.zip` (SHA4a439a8eb72530812b13e7d93446b56db022605c6a951b966c34165df6f3bff6),13membres relusCRC/SHA. Les anciennes archives demeurent inchangees ; l'archive RunN34 vivante n'est pas copiee avant sa fermeture.

La contrelecture et les replays du helper N34 sont également scellés dans `verification_finale_reprise/controle_helper_n34_preuves.zip` (SHA76584fda25af11f7d518c5261a8ccf22846879b02847ac018a4a2330fffbc03f),21membres. La relecture binaire root des deux nouvelles archives confirme tous les CRC, tous les SHA et la complétude des index ; preuve `verification_finale_reprise/controle_archives_n34_root.json`. Les17sources gelées sont à nouveau identiques ; aucun profil vivant n'est lu ni déclaré terminé par ce contrôle.

## Diagnostic des grilles closes après N30

Un diagnostic reproductible des onze profils grand terminés est conservé dans `chatGPT_critical_review/analyse_grilles_fermees_n30/`. Les maillages ne sont pas emboîtés ; ce fait ordinaire ne constitue pas une erreur. Un grossissement local effectif est toutefois mesuré près du port, à y=−35,975mm : .04938271604935096mm à extreme_fin puis .08333333333341386mm à N30 (rapport1,6875). Root le retrouve directement dans les deux NPZ. Au point x=−5,23367mm enregistré, les largeurs sont égales et aucun grossissement x n'est revendiqué. La projection fine autour du port se rétrécit avec maille_min ; les distances résolues PCB→entréePML restent supérieures à75mm. Aucune contribution de ces changements à S11 n'est isolée. Il ne s'agit ni d'un nouveau jugement de qualification ni d'une modification des seuils.

La note corrigée, le scriptf909, le rapport et une copie figée du checkpoint sont scellés dans `verification_finale_reprise/diagnostic_grilles_n30_preuves.zip` (SHAf6f0faadab879e4c471e189f7555efeb54e09167f1fef2ad46f333c2e6185ecb),8membres relusCRC/SHA par agent et root. Preuve root `controle_diagnostic_grilles_n30_root.json`. Si N34 échoue, examiner ses cellules locales avant de choisir la suite ; toute modification du moteur exigera une campagne séparée. Les deux files actuelles et les17sources restent inchangées.

Point de suivi 2026-10-19T02:33:18.0738591Z : les deux sessions77627/81046 restent actives, avec GrandN34 4159/155140 pas et Vivaldiultra 40053/88450 pas. Le point resultats/pcbway_r1/journaux/point_suivi_2026-10-19_0233_utc.json conserve les17SHA, les nouvelles archives et la suite exacte. Aucune sortie0, sélection réelle ni livraison finale n'est déclarée.

## Préparation du rapport et vérification de son environnement

Le constructeur PDF courant68b9f6d3756e71c645dce8f55a530a5d2436198a3962fcfccd380cc2a7eee7fc précise les grilles reconstruites sans emboîtement, les grossissements locaux possibles et la variation du voisinage fin du port. Une seule constante textuelle change ; ancien2d130 et nouveau sont conservés dans `verification_finale_reprise/portee_grilles_pdf_preuves.zip` (SHAb8caa952c76a050125080386ad97e76ea684e1c0ab613287909227e277b7b887),9membres relusCRC/SHA et AST par root. Le vrai PDF et sa QA visuelle de toutes les pages restent à produire après qualification.

La revue du cuivre et du port confirme2,286mm au bord des trois cartes, puis taper vers3,1/3,0mm. Les anciens sommets du feed sont remplacés ; aucun ruban plus large ne contourne le port. Les deux XML clos grandN30 etVtrès_fin concordent. Coordonnées, sources et contrelecture sondes attribuée à FDTD sont conservées dans `controle_port_signal_2p286.json`. Le connecteur SMA complet reste hors modèle.

Une relecture réelle sous phPython3.12.13/NumPy2.4.4 accepte21profils clos et reproduit EXACTEMENT les champs des six paires natives (valeurs, seuils et booléens). Les17sources et590fichiers clos gardent leursSHA, relus indépendamment par root. Preuvesplates `controle_lecture_ph_profils_fermes.py/.json` ; synthèse root `controle_finalisation_preparee_root.json`. Les échecs spatiaux grandN30 etVtrès_fin restent refusés ; il s'agit de compatibilité du lectorat, sans nouvelle qualification.

Point courant 2026-10-19T03:06:19.2475384Z : GrandN34 11597/155140pas ; Vivaldiultra 44329/88450pas. Les sessions77627 et81046 sont de nouveau confirmées actives, sans code terminal. Point `resultats/pcbway_r1/journaux/point_suivi_2026-10-19_0306_utc.json`. Aucune sélection réelle ni livraison finale n'est créée.

Attente vérifiée au 2026-10-19T04:09:18.3402094Z : processus532/N34 25823/155140pas, processus13052/Vivaldi 52536/88450pas, compteurs progressant régulièrement. Les sessions77627/81046 sont confirmées actives par poll direct, sans code terminal. Les17sources et le builder68b9 sont inchangés. Aucun nouveau résultat de convergence, sélection réelle ou livraison finale. Preuve : `resultats/pcbway_r1/journaux/point_suivi_2026-10-19_0409_utc.json`.

Attente vérifiée au 2026-10-19T05:12:05.4978526Z : GrandN34 39326/155140pas ; Vivaldi 60309/88450pas. Les sessions77627/81046 restent actives par poll direct. Les17sources, le builder68b9 et les deux ZIP de fabrication sont inchangés. La cadence a diminué en fin de suivi mais les compteurs avancent, sans redémarrage. Aucun verdict nouveau de convergence ni livraison finale. Preuve `resultats/pcbway_r1/journaux/point_suivi_2026-10-19_0512_utc.json`.

Attente vérifiée au 2026-10-19T06:15:15.5890942Z : GrandN34 52786/155140pas ; Vivaldi 68047/88450pas. Sessions77627/81046 actives par poll direct ;17sources inchangées. La vérification de ressources ne démontre aucun ancien solveur du projet à arrêter ; les autres processus récemment observés sont conservés, sans attribution abusive. Aucun réglage système modifié. Aucune sélection réelle, livraison finale ni nouveau verdict de convergence. Preuve `resultats/pcbway_r1/journaux/point_suivi_2026-10-19_0615_utc.json`.
