# Moteur FDTD repris : méthode et preuves techniques

Date : 18 octobre 2026. Cette note décrit l'infrastructure corrigée. La qualification physique des antennes appartient aux campagnes de convergence ; les essais de quelques centaines de pas cités ici ne la remplacent pas.

## Maillage final contrôlé

Les interfaces de matière, les plans métalliques et les limites du port restent exactement sur des lignes du maillage. Les points d'échantillonnage proposés par les anciennes géométries sont secondaires : ils ne peuvent plus faire disparaître une interface réelle.

`mailles_par_lambda` fixe désormais le pas maximal dans le substrat, à partir de la plus courte longueur d'onde `c / (f_max × sqrt(epsilon_max))`. Pour le modèle dispersif, `epsilon_max` est la permittivité statique, une borne conservative sur toute la bande. `mailles_par_lambda_air` fixe le pas maximal dans l'air. `maille_min` fixe la résolution locale demandée autour du port ; une interface réelle plus petite reste conservée.

Le lissage initial ne suffit pas à garantir le rapport entre cellules voisines. Les positions libres sont donc réparties sous contraintes linéaires : largeur positive, pas maximal par zone, rapport voisin inférieur ou égal à 1,5 et interfaces inchangées. Cela évite de propager un raffinement excessif dans tout l'air. Les tailles dans le substrat et les rapports sont contrôlés à nouveau sur la grille obtenue.

La symétrie n'étant pas implémentée physiquement, le défaut est `symetrie=False`. Demander `True` produit une erreur explicite et ne divise plus artificiellement le coût par quatre.

Pour les séries avec plaque, toutes les faces avant et arrière de toutes les positions, ainsi que les quatre bords latéraux de la plaque, figurent dans le fond et dans chaque cible. Les tableaux de lignes sont identiques bit pour bit.

## Pas de temps déterminé par le vrai opérateur

Le CFL calculé à partir des minima de grille est une estimation préalable. Un essai réel a montré que son emploi direct pouvait dépasser le pas calculé par openEMS pour les éléments localisés et les matériaux de la scène. Cette estimation n'est donc plus imposée au solveur.

Avant chaque calcul, deux itérations avec le pas automatique openEMS sont archivées dans `_calibration_dt`. Le fichier `openEMS_stats.txt` donne le pas de l'opérateur effectivement construit. Le calcul principal emploie 99,9 % de ce pas, avec une borne supplémentaire `tau_min / 4` qui assure que les relaxations de Debye ne sont pas ignorées par le solveur. Pour une série, le minimum des pas calibrés de toutes les scènes devient le pas commun.

La calibration de deux itérations produit volontairement des avertissements de pulse tronqué : elle sert uniquement à construire et inspecter l'opérateur. Les avertissements concernant un pas forcé trop grand, un pôle ignoré ou une primitive importante inutilisée ne doivent pas être assimilés à ces avertissements attendus.

Les sondes du calcul principal sont enregistrées à chaque pas. Leur espacement est comparé au pas imposé, puis leur dernière date à la durée prévue. Un dossier non vide est refusé. Un plafond de nombre de pas insuffisant provoque une erreur au lieu d'une troncature silencieuse.

Une durée explicite de 8, 12 ou 16 ns est acceptée pour l'étude de convergence S11. Il n'est pas nécessaire d'attendre `1/df` pour évaluer une DTFT sur une grille fréquentielle donnée ; l'extinction et la stabilité au prolongement doivent le démontrer. Le manifeste indique séparément si la fenêtre couvre `1/df`. Sans durée explicite, le défaut historique conservatif tient encore compte de cette borne et de la propagation dans le domaine.

## Hypothèse de matériau

`materiaux.py` fournit une somme passive de 13 relaxations de Debye, à pôles fixes entre 1 MHz et 100 GHz. Le modèle est calibré exactement sur la permittivité réelle et la tangente de pertes à une fréquence de référence fixe, indépendante de la bande d'acquisition.

Pour l'hypothèse nominale de production `epsilon'=4,6`, `tan(delta)=0,011` à 1 GHz, toutes les contributions et toutes les constantes de temps sont positives. Cette réalisation causale représente des pertes approximativement constantes avec une dispersion associée. Elle ne constitue pas une mesure large bande du lot de FR-4 que livrera le fabricant. La confirmation du stratifié et la comparaison aux mesures restent nécessaires.

La borne supérieure de 100 GHz évite les relaxations excessivement rapides qui étaient ignorées par openEMS avec une borne de 1 THz. L'alternative explicite `modele="constant"` reste disponible pour reproduire une permittivité et une conductivité constantes : dans ce cas la tangente de pertes varie comme `1/f`, ce qui est annoncé dans le manifeste.

## Archives de chaque calcul

Le dossier contient notamment :

- `entree_openems.xml`, `maillage.npz` et `geometrie.json` ;
- les copies des sources dans `sources/`, dont les géométries, la connectique et les matériaux ;
- les sondes originales `port_ut_1` et `port_it_1`, les statistiques du solveur et `s11.s1p` ;
- `simulation_manifest.json` : montage, matériaux et pôles, lignes et empreintes, durée, pas, versions, état du calcul et empreintes SHA-256 des fichiers présents à sa clôture.

Les fichiers ajoutés ensuite par un orchestrateur doivent être couverts par son propre inventaire de qualification. Le manifeste FDTD n'atteste que les fichiers disponibles lorsqu'il a été clos.

`estime_cout` construit la vraie grille sans lancer openEMS. Le nombre de cellules est exact pour cette grille ; les minutes reposent encore sur une vitesse indicative de 30 millions de cellules par seconde et un pas préalable estimé. Le pas et la vitesse réels proviennent ensuite des statistiques de l'opérateur et du calcul. openEMS compte ses points de mise à jour tandis que le résumé compte les cellules de Yee `(Nx-1)(Ny-1)(Nz-1)` : ces deux nombres diffèrent légèrement et ne désignent pas un changement de géométrie.

## Vérifications réalisées

Les sept contrôles de `tests/test_fdtd_reprise.py` passent avec CSXCAD réel, sans exécution FDTD : passivité et référence du matériau, maillage commun et faces exactes, résolution du substrat et graduation finale, effet des paramètres, indépendance du matériau vis-à-vis de la bande, coût réel et absence de symétrie fictive, refus de troncature et d'écrasement.

Commande :

```powershell
& 'C:\Users\jfeld\anaconda3\envs\openems\python.exe' -B -X utf8 -m unittest discover -s simulation/tests -p test_fdtd_reprise.py -v
```

L'essai réel `verification_moteur_2026-10-18/mini_calibre_debye` confirme le chargement des matériaux dispersifs, le pas effectif de **0,315119 ps**, l'enregistrement par pas et les archives. Il ne dure que **200 pas, soit 0,063 ns** ; son S11 ne doit pas être utilisé comme résultat d'antenne. Le premier dossier `mini_debye` conserve l'essai antérieur qui a révélé les défauts de pas forcé et de relaxations trop rapides ; il n'est pas qualifié non plus.

SciPy 1.18.1 a été ajouté à l'environnement `openems` pour la répartition linéaire du maillage. Les versions employées sont consignées dans `requirements_fdtd.txt` et dans les manifestes.

Sources officielles consultées : [maillage et CFL openEMS](https://docs.openems.de/en/latest/concepts/mesh.html), [matériaux dispersifs openEMS](https://docs.openems.de/en/latest/concepts/dispersive.html), [définition Debye et enregistrement de propriété Python](https://github.com/thliebig/openEMS-Project/discussions/366). L'API effectivement installée a également été inspectée et exécutée.

## Comparaison temporelle sans recalculer le préfixe

`fenetre_sondes.py` peut dériver la fenêtre de 8 ns depuis les sondes d'un calcul terminé de 12 ns. Cette comparaison teste la sensibilité de S11 à la troncature de la **même trajectoire discrète** ; elle ne constitue ni une seconde simulation indépendante ni une étude de convergence du pas temporel.

```powershell
python -B -X utf8 fenetre_sondes.py --source resultats/pcbway_r1/vivaldi_tomographie/fin_12ns --sortie resultats/pcbway_r1/vivaldi_tomographie/fin_8ns --duree-ns 8
```

Les fichiers originaux restent intacts. L'outil vérifie les empreintes, le nombre d'itérations effectivement achevées, les nombres réels d'échantillons, leur cadence, la géométrie, le matériau et l'excitation gaussienne complète. Le code officiel fixe sa longueur à `ceil(9/(pi*fc*dt))` ; une durée qui la tronquerait est refusée. Voir [l'excitation du solveur openEMS 0.37.0](https://github.com/thliebig/openEMS/blob/v0.37.0/FDTD/excitation.cpp#L145-L170).

Une précision terminale est établie par les sondes réelles : avec cette version, `NrTS=200` produit **201 échantillons**, U de `0` à `200*dt`, I de `0,5*dt` à `200,5*dt`. Le commentaire initial du moteur annonçant une dernière sonde à `(NrTS-1)*dt` est donc conservatif d'un pas ; la durée effectivement couverte dépasse légèrement celle demandée. Les manifestes dérivés donnent séparément les deux fins réelles. Le préfixe qui reproduit le runner à T ns conserve les indices `0..NrTS_court`, avec `NrTS_court=ceil(T/dt)+1`.

L'extraction conserve les octets des lignes et leurs horodatages, puis charge les sources archivées du calcul parent dans un processus Python isolé. Elle reconstruit le même port, vérifie la grille et le matériau, et emploie le vrai `CalcPort`. Sa DTFT tient déjà compte du décalage temporel U/I ; aucune seconde rotation de phase n'est ajoutée. Une relecture intégrale du parent doit reproduire son S11 à moins de `2e-10` avant d'accepter le préfixe.

Le manifeste annonce explicitement `derive_sondes=true`, `calcul_fdtd_execute=false` et les empreintes des preuves parentes. L'XML copié se nomme `origine_entree_openems.xml` et reste identifié comme entrée du calcul **parent**, jamais comme une nouvelle entrée courte. La signature de qualification est recalculée avec la durée courte. Le niveau incident minimal et relatif est conservé dans `relecture_calcport.json`.

Cinq tests sans solveur vérifient cette opération avec le vrai `CalcPort` et des sondes synthétiques : identité exacte du S11 arrondi pour 12→12 ns, identité des octets des sondes complètes, indices et demi-pas pour 12→8 ns, compatibilité du lecteur de qualification, préservation des originaux, refus d'écrasement, de pulse tronqué, de source altérée et de nombre de lignes incohérent. Une revue scientifique indépendante a confirmé le protocole. Les mêmes vérifications de relecture intégrale sont répétées automatiquement lors de l'utilisation sur les calculs physiques.

## Sélection adaptative des comparaisons

Une fenêtre initiale peut échouer au contrôle temporel. `qualification_adaptative.py` permet alors de déclarer, par antenne, d’autres profils et une référence prolongée, sans modifier les seuils de `qualifie_pcbway.ecarts`. Cette sélection ne change ni le moteur ni les sources physiques des calculs. La campagne reste en cours ; aucune durée particulière n’est acquise comme référence par cette note.

Le raffinement spatial compare deux maillages à la même durée. Le prolongement temporel compare un même niveau, un même maillage et un même pas à deux durées séparées d’au moins 4 ns, comme l’intervalle initial 8→12 ns. Son dernier profil est la référence ; le profil fin spatial doit être l’un des deux profils temporels. Ce chaînage empêche d’associer un raffinement à une fenêtre courte et une comparaison temporelle sans profil commun. La référence doit couvrir au moins la durée maximale des préliminaires. Une adaptation restant à 12 ns exige un niveau fin plus résolu que le niveau fin initial.

La sélection conserve les essais initiaux et les comparaisons antérieures déclarées comme préliminaires, y compris lorsqu’ils échouent. Leurs écarts sont recalculés et leurs archives restent couvertes par les preuves. Tous les profils doivent partager géométrie, contrat, sources et environnement ; l’instantané et le SHA-256 de `selection_qualification.json` accompagnent le bilan. Une validation structurelle du brouillon ne remplace pas la lecture des résultats et ne produit aucun verdict de convergence. Les commandes de préparation hors du dossier de résultats figurent dans le [README](../README.md#qualification-et-références-s11).

La relecture d’une copie déplacée ne réécrit pas les preuves. Pour comparer les JSON individuel et global, seul l’ancien préfixe local du champ `reference` est neutralisé ; son nom de profil doit correspondre à la sélection. Les empreintes, les courbes, la configuration et tous les autres champs restent strictement vérifiés.
