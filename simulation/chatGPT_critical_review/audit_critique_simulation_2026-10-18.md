# Audit critique du simulateur et des fichiers de fabrication

18 octobre 2026 — Projet MicroWaveTomography — Répertoire `simulation`

**Conclusion générale : je dispose des éléments nécessaires pour reprendre le développement du projet. Je ne dispose pas encore de tous les éléments nécessaires pour valider quantitativement le banc réel ni pour considérer les deux commandes PCBWay comme entièrement qualifiées.**

L'architecture est compréhensible, les équations principales du traitement correspondent au rapport pour John, et les fichiers S11 des trois antennes sont cohérents avec les sondes openEMS conservées. En revanche, la commande FDTD publique contourne un garde-fou essentiel, la validation par le losange est présentée trop favorablement, et la vérification des fichiers de fabrication est incomplète. Les corrections et travaux décrits ci-dessous sont proposés pour une reprise ultérieure ; ils n'ont pas été appliqués.

## 1 Périmètre et méthode

L'audit porte sur les 20 fichiers Python du répertoire et de ses sous-répertoires, les README et fiches d'antennes, le backlog, les manifestes de campagnes, les trois PDF et la source LaTeX de faisabilité, les résultats présents localement, les DXF, les Gerbers, les perçages, les notices et les ZIP PCBWay. Les résultats et manifestes ignorés par Git ont été inclus : une simple lecture des fichiers suivis aurait manqué une partie importante des preuves.

État Git de référence : `14aab7d1a83ec1f5ebaecc461ee226783fb6ce8b`. Le dossier audité contient initialement **266 fichiers, pour 9 299 246 octets**, caches existants compris. Un inventaire SHA-256 et des dates de modification a été pris avant les contrôles. La comparaison finale confirme **266 fichiers conservés, aucun contenu modifié, aucune date de modification changée, aucun fichier ajouté ou supprimé hors `chatGPT_critical_review`**. Les autres fichiers non suivis déjà présents ailleurs dans le dépôt ont été laissés intacts.

Vérifications effectuées :

- analyse syntaxique des 20 fichiers Python, sans produire de bytecode ;
- exécution des tests existants et sondes supplémentaires sur des tableaux ou lecteurs simulés en mémoire ;
- construction de véritables objets openEMS et inspection de leurs grilles, sans lancer le solveur ;
- recalcul des statistiques des S11 enregistrés et extraction indépendante des S11 à partir des sondes brutes ;
- relecture des Gerbers et Excellon avec gerbonara, contrôle des archives et confrontation des contours ;
- lecture des PDF et examen visuel des pages pertinentes, notamment les figures et conventions du rapport pour John ;
- consultation des documentations officielles openEMS, MathWorks et PCBWay.

**Aucune nouvelle campagne FDTD complète n'a été exécutée.** Cet audit vérifie le code, les données conservées et la construction des scènes ; il n'établit pas à lui seul une convergence électromagnétique ni une performance mesurée des cartes.

Dans la suite, les chemins sont relatifs à `simulation`, sauf indication contraire. Les numéros de ligne désignent l'état audité. Les priorités signifient : **P1**, à traiter avant d'exploiter quantitativement la chaîne concernée ou de lancer une commande en confiance ; **P2**, défaut ou limite substantielle à corriger pendant la reprise ; **P3**, documentation ou robustesse secondaire.

## 2 Synthèse des décisions

| Sujet | Verdict de l'audit | Conséquence |
|---|---|---|
| Architecture Python | Base exploitable et assez bien séparée | Reprise possible sans réécriture générale |
| IFFT et phase du rapport | Formules principales correctes, tests existants réussis | Conserver le cœur du traitement, renforcer les entrées et l'interprétation des pics |
| Commande `run.py --mode fdtd` | Maillages et arrêts non harmonisés entre fond et cibles | Corriger avant une comparaison quantitative fond/cible |
| Validation par le petit losange | Accord partiel, avec deux interruptions au-dessus de −10 dB | Retirer l'idée de validation globale acquise |
| Chiffres Vivaldi | Statistiques principales confirmées | Les conserver comme résultats de cette simulation, sous réserve de convergence |
| Géométries et ZIP Gerber | Correspondance des contours actuels confirmée | Base de fabrication récupérable |
| Vérification Gerber annoncée | Comparaison automatique non raccordée, rendus SVG vides | Compléter les contrôles avant commande |
| DXF Vivaldi | Ancienne géométrie | Ne pas les utiliser pour fabriquer la version actuelle |
| UWB Surveyor et décalage réel | Géométrie approximative, mesures complexes absentes des campagnes locales | Explication quantitative des 20 cm encore ouverte |

## 3 Ce qui est solide dans le projet

Le découpage entre `banc.py`, `traitement.py`, `modele.py`, `fdtd.py`, `donnees.py` et les modules d'antennes facilite la reprise. Les unités sont généralement explicites. La distinction entre pas d'interpolation en distance et résolution physique est correcte. La géométrie du grand losange est dérivée du petit, avec des exceptions documentées pour l'épaisseur et la largeur de ligne. Le passage direct des contours Python aux Gerbers limite les ressaisies.

Les équations utilisées dans `traitement.py:31–44,85–112` correspondent aux pages 2 et 4 de `report_john.pdf` : soustraction complexe avant fenêtrage, Hann symétrique, IFFT de 3216 points pour 201 fréquences avec remplissage 16, absence de normalisation du gain cohérent, distance aller simple et retrait de la phase géométrique avant déroulement. La régression de phase pondérée par la puissance est cohérente avec le rapport.

Les **20 contrôles actuels de `test_traitement.py` passent** avec Python `-B`. Le README en annonce encore 16. Ces succès vérifient les cas effectivement testés ; les défauts d'import et d'orchestration ci-dessous ne sont pas couverts.

Une vérification supplémentaire importante relie les trois fichiers `antenne_seule.s1p` aux sondes temporelles conservées : `CalcPort` reproduit leurs valeurs complexes avec un écart maximal inférieur à **6,6 × 10⁻¹¹**, compatible avec l'arrondi d'écriture. Les courbes sont donc traçables jusqu'à ces sondes. Cette vérification ne prouve pas que la scène initiale, les matériaux ou le maillage étaient suffisamment précis.

## 4 Défaut prioritaire dans la simulation avec plaque

### P1 La commande publique ne passe pas par la série commune

**Sources :** `run.py:103–110,130–134`, `fdtd.py:220–305,352–392`, `README.md:189–194`.

Le README impose à juste titre de comparer le fond et les cibles avec une configuration numérique commune. `fdtd.serie()` prévoit un domaine commun et un nombre de pas imposé. Pourtant, `run.py --mode fdtd` appelle directement `F.lance()` pour chaque plaque, puis pour l'antenne seule, sans transmettre `x_domaine` ni `n_pas` communs.

La construction réelle des grilles pour la Vivaldi, avec les réglages par défaut, donne :

| Scène | Lignes x × y × z | Cellules |
|---|---|---|
| Fond, antenne seule | 92 × 84 × 133 | 996 996 |
| Plaque à 50 cm | 184 × 175 × 186 | 5 890 770 |
| Plaque à 60 cm | 184 × 175 × 203 | 6 432 084 |
| Plaque à 70 cm | 184 × 175 × 226 | 7 164 450 |

Le domaine, les grilles et parfois le pas temporel estimé diffèrent. L'arrêt par énergie est également indépendant. La différence calculée contient donc potentiellement des différences numériques et de frontières en plus de l'effet physique recherché. L'ampleur de cette contamination reste à mesurer ; son mécanisme et l'absence de protection dans la commande recommandée sont établis.

**Reprise proposée :** raccorder la commande à une série commune, puis comparer explicitement les grilles et les durées réellement produites. Vérifier ensuite la stabilité du résidu complexe et des distances lorsque l'on raffine le maillage et prolonge le calcul.

Le programme du dipôle utilise bien `F.serie()` (`antennes/dipole_reference/verifier.py:88–97`). Son succès ne couvre donc pas cette régression du point d'entrée général.

### P2 La grille commune ne place exactement que la plaque la plus éloignée

**Source :** `fdtd.py:283–287,364–375`.

Avec `x_domaine=70`, les quatre grilles deviennent identiques, ce qui est un progrès. Mais seules les faces de la plaque à 70 cm sont explicitement imposées. Dans la construction inspectée, les faces avant à 50 et 60 cm sont respectivement à environ **0,346 mm et 0,415 mm** de la ligne de grille la plus proche.

Cela ajoute une incertitude de discrétisation sur la distance physique. La correction future doit construire une grille commune incluant les faces de **toutes** les plaques, ou quantifier la position effective retenue par la discrétisation. Cette question est distincte du défaut du point d'entrée.

## 5 Maillage matériaux et niveau de validation

### P1 La finesse annoncée ne suffit pas à établir la convergence

**Sources :** `banc.py:103–112`, `fdtd.py:206–214,264–296`, `antennes/vivaldi_tomographie/geometrie.py:302–324`.

La grille est principalement lissée vers un pas calculé sur la longueur d'onde **dans l'air**. Pour la Vivaldi à 6 GHz, des cellules inspectées dans le substrat atteignent environ **4,72 mm en x et 5,00 mm en z**. Avec εr = 4,4, cela représente environ **5,05 et 4,77 cellules par longueur d'onde dans le matériau**. Le contrôle `verifie_maillage()` reçoit une taille cible mais ne l'utilise pas pour refuser une grille trop grossière ; il ne contrôle que les minima et calcule un pas temporel approximatif.

La documentation officielle rappelle que la longueur d'onde dans le milieu, les petits détails et la variation progressive des cellules doivent guider le maillage. Ici, certains rapports de cellules voisines atteignent **6,27** pour la Vivaldi et **7,20** pour le grand losange, malgré le `ratio=1.4` passé au lissage. Il faut donc contrôler la grille finale après sa construction et son nettoyage. Ces observations signalent une précision à démontrer ; elles ne permettent pas de chiffrer l'erreur S11 sans étude de convergence. Voir la [documentation openEMS sur le maillage](https://docs.openems.de/en/latest/concepts/mesh.html).

Une convergence utile comparerait le S11 **complexe**, les franchissements de seuil, le résidu fond/cible et le retard entre plusieurs grilles et durées. Une couverture S11 voisine entre deux essais ne suffit pas à qualifier la phase ni le retard.

### P2 Plusieurs réglages ne pilotent pas le calcul annoncé

**Sources :** `banc.py:103–112`, `fdtd.py:79–100,239–245,264–296`, `run.py:25–33,164–165`.

Les essais en mémoire montrent que changer `mailles_par_lambda` de 20 à 80, `maille_min` de 0,2 à 0,05 mm, ou `symetrie` de vrai à faux ne change aucune ligne de la grille Vivaldi. La symétrie ne modifie que l'estimation du coût, divisée par quatre ; le solveur reçoit toujours six frontières `PML_8`. Le paramètre `--sans-symetrie` ne désactive donc aucune symétrie physique effectivement appliquée.

L'estimation par défaut de la Vivaldi seule annonce environ **57 603 cellules**, contre **996 996** dans la scène construite. Le commentaire indique déjà que l'estimation est un plancher, mais la réduction pour une symétrie inexistante et l'encombrement d'antenne incomplet aggravent son optimisme. La durée affichée ne doit pas servir à planifier une campagne en confiance.

### P2 Les pertes FR4 ne correspondent pas à une tangente de pertes constante

**Sources :** `antennes/diamant_uwb/geometrie.py:138–142`, `antennes/vivaldi_tomographie/geometrie.py:265–270`, `antennes/uwb_surveyor/geometrie.py:111–115`.

Le code transforme `TAN_DELTA` en une conductivité constante calculée à la fréquence centrale `f0`. Avec une permittivité réelle constante, cela produit une tangente effective proportionnelle à `f0/f`, et non la valeur constante annoncée sur toute la bande.

Exemple Vivaldi, bande 1–6 GHz : une valeur nominale 0,02 à 3,5 GHz devient environ **0,070 à 1 GHz** et **0,0117 à 6 GHz**. Pour le petit losange simulé sur 1–14 GHz, la valeur 0,026 à 7,5 GHz correspond à environ 0,195 à 1 GHz et 0,0139 à 14 GHz. Les chiffres aux extrémités illustrent le modèle implémenté, pas un matériau mesuré.

Changer seulement les bornes de l'acquisition change ainsi la conductivité attribuée au même PCB. Il faut choisir et documenter un modèle diélectrique adapté à la bande et indépendant de cette acquisition, puis étudier la sensibilité à εr, aux pertes et à l'épaisseur. La documentation MathWorks consultée utilise désormais un modèle fréquentiel de substrat ; comparer les seuls noms « FR4 » et les dimensions ne garantit donc pas l'identité électromagnétique des deux modèles. La signification de la conductivité κ est donnée dans les [propriétés de matériaux openEMS](https://docs.openems.de/en/latest/concepts/properties.html).

### P2 Les sondes conservées ne remplacent pas une preuve de convergence

Les durées des enregistrements de tension relus sont d'environ **1,566 ns**, **2,742 ns** et **7,164 ns** pour les trois antennes seules. Une réponse éteinte peut être transformée sur une grille fréquentielle fine sans imposer systématiquement une durée égale à `1/Δf`. Ces durées ne constituent donc pas, isolément, une preuve d'erreur. Elles justifient de conserver les critères d'arrêt, l'énergie résiduelle et une comparaison avec un calcul prolongé. Les commentaires du projet qui présentent toute différence de troncature comme nécessairement dominante sont trop absolus. Les [critères d'arrêt openEMS](https://docs.openems.de/en/latest/concepts/simulation.html) distinguent bien seuil d'énergie et limites de durée ou de pas.

## 6 Vérification des trois antennes annoncées

### P1 Les bandes des losanges sont des enveloppes avec interruptions

**Sources :** `run.py:120–124`, `resultats/diamant_uwb/antenne_seule.s1p`, `resultats/diamant_uwb_x18/antenne_seule.s1p`, README général et de fabrication.

Le code prend la première et la dernière fréquence sous −10 dB, puis affiche « de … à … ». Cette phrase ne décrit pas une bande continue. Le recalcul donne :

| Antenne | Intervalles de points effectivement sous −10 dB | Interruptions dans l'enveloppe | Couverture dans l'enveloppe |
|---|---|---|---|
| Petit losange | 2,30–5,80 ; 6,60–9,50 ; 10,55–13,60 GHz | 5,85–6,55 et 9,55–10,50 GHz | 84,58 % |
| Grand losange | 1,275–1,600 ; 2,225–6,000 GHz | 1,625–2,200 GHz | 87,37 % |

Ces limites sont les fréquences échantillonnées, sans interpolation des franchissements. Les pas sont de 50 MHz pour le petit losange et de 25 MHz pour le grand. **6 GHz est la borne du calcul du grand losange, pas une coupure haute identifiée.** Les pourcentages de 85 % et 87 % sont bien retrouvés, mais ils sont calculés sur deux enveloppes différentes ; ils ne signifient pas une couverture de toute la bande d'acquisition.

L'exemple [MathWorks du losange](https://www.mathworks.com/help/antenna/ug/diamond-shaped-antenna-for-uwb-applications.html) annonce un S11 sous −10 dB sur 2,5–13,5 GHz et renvoie à Singhal et al., DOI `10.1109/INDCON.2013.6726048`. Le code reprend ses principales dimensions. Toutefois, les interruptions observées et les différences de modèle de matériau empêchent de déclarer que la bande de référence a été reproduite intégralement.

**Réponse à l'argument « l'étalon donne du poids au reste » : oui, comme premier contrôle de plausibilité ; non, comme validation acquise de tout le modèle.** La proximité des deux bornes extrêmes ne valide ni le comportement intérieur de la bande, ni la phase, ni le rayonnement, ni le retard de l'UWB Surveyor, ni une Vivaldi orientée différemment.

### Les principaux chiffres de la Vivaldi sont confirmés

**Source :** `resultats/vivaldi_tomographie/antenne_seule.s1p`, évalué sur les 185 points de 1,4 à 6,0 GHz inclus.

| Indicateur | Valeur recalculée | Valeur annoncée |
|---|---|---|
| Points sous −10 dB | 71,351 % | 71,4 % |
| Points sous −6 dB | 94,054 % | 94,1 % |
| Moyenne de puissance réfléchie, en dB | −10,5929 dB | −10,6 dB |
| Pire S11 | −2,8982 dB | −2,9 dB |

La moyenne est `10 log10(moyenne(|S11|²))`, pas la moyenne arithmétique des valeurs en dB. Elle correspond à environ **8,7 % de puissance réfléchie** en moyenne sur ces points. Le reste de la puissance acceptée comprend les pertes et le rayonnement ; il ne constitue pas une efficacité de rayonnement de 91,3 %.

La zone « 5,45–5,85 GHz au-dessus de −6 dB » est également une enveloppe : les points concernés forment deux groupes, **5,45–5,65 GHz** et **5,825–5,85 GHz**. La bande entre ces groupes redescend sous le seuil. La documentation surestime donc l'étendue continue du défaut. Inversement, les 71,4 % sous −10 dB impliquent plusieurs interruptions de ce seuil ailleurs dans la bande.

Une valeur acceptable à la première fréquence de 1 GHz ne caractérise pas précisément une coupure basse située hors du balayage. Les affirmations sur la bande inférieure à 1 GHz doivent rester conditionnelles. Enfin, le gain, la directivité, le rendement et la fidélité temporelle ne sont pas qualifiés par le seul S11. Les 21 fichiers d'essais S1P retrouvés sont utiles, mais ne décrivent pas un espace d'optimisation exhaustif ; le tableau de la fiche comprend 23 lignes, dont la configuration de départ et des variantes absentes de cet ensemble S1P. Certaines sondes brutes supplémentaires subsistent.

## 7 Traitement des mesures et interprétation des résultats

### P2 Une grille fréquentielle non uniforme donne une distance fausse sans refus

**Sources :** `donnees.py:54–74`, `run.py:70–76`, `traitement.py:31–44`.

Le lecteur vérifie que les fichiers partagent la même grille, mais ne vérifie pas que cette grille est uniforme, strictement croissante, finie et compatible avec l'IFFT. `mode_mesures()` reconstruit ensuite un pas unique à partir des seules bornes et du nombre de points.

Sonde reproductible : sur `np.geomspace(1e9, 6e9, 201)`, un écho pur de cible à **50 cm** est accepté et son maximum est placé à **40,46 cm**. Il faut refuser une grille incompatible, ou proposer explicitement un rééchantillonnage complexe adapté. Vérifier seulement l'égalité des grilles entre fichiers ne suffit pas.

### P2 Un maximum secondaire devient automatiquement un pic lointain

**Sources :** `traitement.py:63–79,118–134`.

Le programme sélectionne les deux maxima les plus forts dans une fenêtre, sans seuil de bruit ou de proéminence. Avec un modèle à **un seul trajet** (`ModeleAntenne(a2=0)`), il rapporte un pic à **70,00 cm** et un « pic lointain » à **77,08 cm**. Le second est un lobe secondaire de la réponse fenêtrée, environ **31,5 dB** sous le principal.

La sélection de deux maxima reproduit une convention graphique du rapport, qui précise justement qu'elle n'identifie pas deux surfaces physiques. Elle doit rester descriptive. Pour suivre des branches, il faut autoriser une seule détection, définir une confiance et vérifier la continuité avec la distance. La fenêtre fixe de 40–120 cm du bilan général doit également être adaptée si l'utilisateur choisit d'autres distances.

### P2 Les sorties simulées ne se réimportent pas par la commande par défaut

**Sources :** `run.py:108–110,130–133`, `donnees.py:51–72`.

Le simulateur écrit `plaque_50cm.s1p` et `antenne_seule.s1p`. Le lecteur attend `plate_50cm` et un nom contenant `background`. Le dossier exporté ne peut donc pas être rejoué directement avec `--mode mesures`. Les motifs sont paramétrables dans la fonction Python, mais ne sont pas exposés par cette commande.

Le lecteur reste limité à un sous-ensemble de Touchstone. Il refuse par exemple un commentaire `!` en fin de ligne de données, et ne contrôle pas explicitement que l'en-tête décrit des paramètres S avec la référence attendue. Il faut aussi définir la conduite à tenir en présence de plusieurs fonds, de doublons CSV/S1P divergents et de distances décimales.

### P2 Une antenne non adaptée fait échouer le résumé après simulation

**Source :** `run.py:120–124`.

Si aucun point n'est sous −10 dB, `sous` est vide et `sous.min()` lève une `ValueError`. Une sonde avec `S11=0,9` le reproduit. Le compte rendu doit pouvoir annoncer qu'aucune bande n'est détectée, même si le solveur a terminé normalement.

### Limites du modèle analytique

**Sources :** `modele.py:54–64,80–120`, `run.py:61–64`.

Le modèle est utile comme générateur d'échos et outil d'hypothèses. Ses amplitudes absolues ne sont pas une prédiction physique normalisée : avec les réglages par défaut à 50 cm, il produit **max |S11| = 1,9169**, incompatible avec un coefficient de réflexion passif normalisé. Le facteur heuristique `1/(2x)` et la fonction de transfert doivent être traités comme tels.

Les échos fixes sont identiques dans le fond et dans la scène avec plaque ; ils s'annulent dans la soustraction à l'arrondi près. Ils ne démontrent donc pas l'effet d'un parasite modifié par le déplacement de la cible. Le bruit utilise par défaut le même tirage à chaque distance, tandis que le fond construit par la commande analytique est sans bruit.

Enfin, `derive_ns` modifie un retard de **phase** dans l'exponentielle. Le retard de groupe devient `τ(f) + f dτ/df`. Avec `derive_ns=-0,25`, le décalage du pic passe d'environ **20,00 à 14,75 cm**. Il reste constant entre les distances dans le cas testé, mais ne conserve pas sa valeur initiale. La phrase « la dispersion élargit l'écho mais ne le déplace pas » est donc trop générale. Le test qui évoque un écart expérimental décroissant ne correspond pas non plus au tableau du 9 octobre embarqué, dont les écarts augmentent globalement entre la première et la dernière position.

## 8 Fichiers de fabrication contrôlés

### Les deux ZIP sont cohérents avec les contours actuels

| Article | ZIP | Dimensions du contour |
|---|---|---|
| Panneau des deux losanges | `fabrication/panneau_losanges/panneau_losanges_pcbway.zip` | 92,60 × 72,00 mm |
| Vivaldi | `fabrication/vivaldi_tomographie/vivaldi_tomographie_pcbway.zip` | 143,068736 × 280,603102 mm |

Chaque ZIP contient **cinq Gerbers**, un fichier Excellon et une notice : sept membres au total. Les cinq Gerbers sont les deux cuivres, les deux masques et le contour. L'absence de sérigraphie explique qu'il n'y ait pas six Gerbers. Les contrôles CRC réussissent et chaque membre est identique au fichier homonyme voisin.

Les polygones cuivre et masque relus correspondent aux contours Python actuels, à l'arrondi d'export près, inférieur à **0,000001 mm**. Le panneau porte deux losanges, deux pontets et **16 trous de 0,6 mm**. La Vivaldi comporte **deux trous de 3 mm**. Les dimensions globales et le contenu technique des archives sont donc récupérables et cohérents. Cette correspondance géométrique ne remplace pas l'accord de fabrication ni la qualification RF.

### P1 Le vérificateur ne réalise pas les comparaisons annoncées

**Source :** `verifie_gerber.py:7–14,38–85,88–119`.

La fonction `compare()` existe, mais le programme principal ne l'appelle jamais. Le booléen de succès accepte les couches graphiques rencontrées si elles ne sont pas vides et exige un fichier de perçage. Il n'impose pas la présence de toutes les couches attendues, ne confronte pas automatiquement leurs contours à la source, ne vérifie pas les surfaces annoncées et ne compare pas les trous à une référence.

Les dimensions et les perçages sont imprimés, ce qui aide une lecture humaine, mais une sortie « OK » n'a pas la portée revendiquée par le texte introductif. Il faut relier les attentes à la géométrie et faire échouer le contrôle sur une couche absente, une mauvaise échelle, un mauvais contour ou un perçage divergent.

### P1 Les deux rendus SVG conservés sont vides

**Sources :** les deux fichiers `fabrication/*/*_rendu.svg`, `verifie_gerber.py:79–83`.

Les fichiers de **244 et 247 octets** ne contiennent que l'élément racine SVG, sans dessin. Le contrôle d'image annoncé ne fournit donc aucune preuve visuelle. Avec la version locale de gerbonara, l'appel à `to_svg()` sans couleurs explicites laisse les couches sans couleur utilisable ; une génération en mémoire avec couleurs explicites produit bien un contenu graphique.

C'est un défaut de rendu et de vérification, pas une preuve que les Gerbers sont vides. Leur relecture et la comparaison des polygones donnent au contraire des objets cohérents.

### P2 Le statut de métallisation inconnu est affiché comme non métallisé

**Source :** `verifie_gerber.py:64–71`.

La relecture locale des DRL conserve un statut de métallisation inconnu (`None`). Le code fait `bool(o.plated)`, transformant cet état en `False`. Il affiche donc une confirmation de non-métallisation que l'analyseur n'a pas réellement établie.

Le suffixe `-NPTH.DRL` et la notice expriment l'intention correcte. Il faut cependant conserver les trois états — métallisé, non métallisé, inconnu — dans le contrôle et faire confirmer les perçages non métallisés dans la revue fabricant, notamment les amorces de rupture.

### P2 Les DXF de la Vivaldi sont obsolètes

**Sources :** `antennes/vivaldi_tomographie/dxf/*`, `fabrication/README.md:175–178`.

Les DXF s'arrêtent à **279,1375 mm**, contre **280,603102 mm** pour les contours actuels. Le cuivre inférieur conserve une ancienne masse pleine largeur ; le dessin actuel limite la masse au pied à 40 mm. Les écarts entre certains points des cuivres dépassent largement un simple arrondi. Le tableau de dimensions cuivre du README correspond à l'ancienne version : il annonce notamment 143,07 mm de largeur pour le cuivre inférieur, contre **91,534368 mm** dans le Gerber actuel.

Les DXF des losanges concordent avec leurs contours. La voie DXF est documentée comme secondaire ; il faut néanmoins retirer l'ambiguïté de version avant toute réutilisation. `export_dxf.py` annonce aussi R12 tout en écrivant des `LWPOLYLINE` et sans déclaration complète des unités/version ; une importation CAO demande un contrôle d'échelle.

### P2 Le contrôle de dessin reste approximatif

`apercu.py` fournit un contrôle préalable utile des contours et des recouvrements. Il travaille cependant avec un raster de 0,2 mm et une tolérance de débordement de 1 mm². Il ne remplace pas un contrôle complet des distances cuivre/bord, des pontets, des trous et des règles de gravure ; `GRAVURE_MINI` n'est pas utilisé. Les trous sont contrôlés contre la boîte globale, ce qui ne suffit pas à vérifier leur rapport au cuivre et au contour réel.

## 9 Points à résoudre avant une commande PCBWay

### P1 La notice du panneau indique un mauvais type de livraison

**Sources :** `export_gerber.py:121–122,218–231,277`, notice du panneau.

La notice demande `Board Type: Single pieces` et garantit `Different Design: 1` au motif que deux cartes sur un panneau formeraient un seul dessin. Le panneau contient pourtant deux conceptions d'antenne distinctes, reliées par pontets et fraisage.

L'[aide officielle PCBWay sur les panneaux](https://www.pcbway.com/helpcenter/panel_issues/Confirm_the_panel_way_of_the_boards.html) demande de choisir **Panel by customer** lorsqu'un panneau client contient des tab-routes. Il faut déclarer clairement les deux cartes et faire confirmer la valeur de `Different Design`, le prix et la quantité de panneaux livrés. Le dépôt de deux ZIP comme deux articles reste cohérent ; la promesse commerciale d'un seul dessin facturé pour le panneau ne l'est pas suffisamment.

### P1 La Vivaldi présente du cuivre au bord de plusieurs contours

**Sources :** `antennes/vivaldi_tomographie/geometrie.py:198–226`, Gerbers actuels.

Le cuivre rejoint le contour à la bouche et sur certaines portions latérales, avec une distance nominale de **0 mm**. Ce n'est pas limité au bord de connexion SMA. Les [capacités PCBWay publiées](https://www.pcbway.com/capabilities.html) donnent des distances usuelles de cuivre au fraisage de 0,25/0,20 mm selon le niveau de difficulté. Ces parties doivent donc être signalées et acceptées explicitement, avec les tolérances et le procédé retenus.

Il ne faut pas reculer automatiquement le cuivre pour satisfaire une règle générique : cela changerait l'antenne simulée. Ce point nécessite une décision conjointe de conception et de fabrication. Pour le petit losange, la marge latérale de masse de **0,40 mm** est bien retrouvée hors du bord d'alimentation.

Les marges annoncées près des pontets sont en revanche surestimées : au point le plus proche du petit losange, le cuivre est à environ **1,5 mm de la ligne de rupture**, et **1,2 mm du bord d'un trou de 0,6 mm**, plutôt que 2,9 ou 4 mm. Cela ne prouve pas une impossibilité de fabrication, mais la documentation doit refléter le dessin réel.

### P1 Le connecteur SMA reste à définir

**Sources :** notices et `fabrication/README.md`, ports dans les modules `geometrie.py`.

Aucune référence fabricant de connecteur, empreinte validée ou nomenclature de montage n'est fournie. « SMA bord de carte pour 1,6 mm » ne garantit pas le bon contact de masse, la largeur de broche, la longueur de recouvrement ni le maintien mécanique. Certains connecteurs demandent des masses sur la face supérieure ; les dessins fournis n'en proposent pas autour du ruban au pied.

Un modèle compatible avec une masse sur la face opposée peut convenir. Il faut le choisir et confronter son plan de montage aux trois cartes. Le port localisé idéal n'est pas un modèle complet de sa transition. Une calibration SOL au plan d'accouplement du SMA ne place pas automatiquement le plan électrique à la tranche du PCB : l'adaptateur et la transition en aval peuvent rester dans la mesure.

### P2 Le matériau et le traitement de surface ne sont pas qualifiés quantitativement

Le panneau utilise le matériau simulé des losanges, εr = 4,8 et tanδ nominale 0,026 ; la Vivaldi utilise 4,4 et 0,02. Une commande générique « FR4, TG130 ou TG150, 1,6 mm » ne spécifie pas ces propriétés fréquentielles. Un panneau physique n'aura qu'un seul stratifié : la référence réelle et ses tolérances doivent être consignées. Une piste de 3,0 ou 3,1 mm n'est qu'une approximation de ligne 50 Ω avec des matériaux et épaisseurs donnés, pas une garantie d'impédance contrôlée.

L'affirmation d'un déplacement inférieur à 1 % dû au masque restant dans les fentes repose sur un rapport d'épaisseurs, sans calcul de champs ni essai de sensibilité. Les champs ne sont pas répartis uniformément ; cette borne n'est pas établie. L'effet « nul » des trous et les limites d'effet de l'ENIG sont également trop catégoriques. Le solveur emploie du métal idéal, sans rugosité, résistivité du cuivre, empilement ENIG ni connecteur.

Le [formulaire PCBWay consulté le 18 octobre 2026](https://www.pcbway.com/QuickOrderOnline.aspx) propose explicitement `Solder mask: None`. La justification du backlog selon laquelle cette option ne serait pas disponible de manière sûre doit être réexaminée. Le choix final de masque et de finition doit être explicite ; les archives existantes n'ont pas été modifiées.

**Verdict fabrication : les archives sont techniquement lisibles et leurs contours correspondent aux sources actuelles. Elles ne constituent pas encore un dossier entièrement qualifié pour une commande sans questions.** Les priorités sont le panneau client, le cuivre affleurant, le connecteur et une vraie revue visuelle des couches.

## 10 Données expérimentales et cohérence documentaire

Les deux dossiers de campagne UWB Surveyor ne contiennent que leurs manifestes. Les S11 complexes de fond, de plaques et de SHORT qui permettraient de recalculer les figures du rapport n'y sont pas. Les valeurs embarquées dans `banc.py` sont des tableaux de résultats publiés, pas des mesures complexes exploitables pour recaler l'antenne.

La fiche UWB et `banc.Antenne` conservent des paramètres anciens : rayon 46 mm, ligne 38 mm, retard 0,23 ns et décalage 6,9 cm. La géométrie réellement chargée utilise un rayon **83,5 mm**, un centre de disque **92,7 mm** et une ligne déduite de **69,2 mm**, donnant environ **0,421 ns et 12,62 cm** pour la seule ligne. `Montage.antenne` n'est pas la source effective de ces cotes dans la FDTD. L'idée « tous les paramètres sont centralisés dans banc.py » ne correspond donc plus à l'architecture actuelle.

`report_john.pdf` constitue une référence plus prudente que certains README : il distingue retard commun observé et attribution à l'antenne, décrit le multipath et les incertitudes de distance. Il précise que les dimensions de la plaque expérimentale n'ont pas été fournies. La plaque de **60 × 60 cm** du simulateur est une spécification de la faisabilité, pas une dimension confirmée pour cette acquisition.

Le « retard attendu » des modules d'antennes doit également être distingué du biais de distance lu sur une cible. Pour la Vivaldi, `geometrie.py:131–142` estime un temps de trajet interne complet, puis la commande le convertit en distance par `cτ`. Or la distance de plaque est définie depuis `z=0` ; un lieu de rayonnement situé à `z_r > 0` raccourcit le trajet dans l'air. Dans une approximation à un point d'émission, le biais serait **`cτ_interne − z_r`**. En supposant une émission à la bouche, le trajet interne estimé équivaudrait à environ 46,1 cm, mais son excès sur le trajet aérien serait environ **18,0 cm** après retrait des 28,1 cm jusqu'à la bouche. Ce calcul illustre une convention ; le modèle distribué réel demande une analyse de phase ou de champ, et ces estimations ne sont pas des bornes étalonnées.

Le rapport pour John mentionne aussi des observations du **22 septembre** et une ancienne antenne verte avec un autre décalage ; le manifeste séparé décrit le **17 septembre** comme une campagne de la même UWB Surveyor. Sans les fichiers et l'historique d'acquisition, il faut garder ces campagnes distinctes et vérifier leur attribution. Les phrases qui excluent définitivement toute explication des deux campagnes par la simulation sont prématurées : supports, couplages, calibration, traitement et géométrie peuvent changer.

Autres incohérences documentaires à corriger pendant la reprise :

- la fiche du dipôle annonce encore un retard strictement nul puis explique correctement qu'un dipôle résonant peut retarder la réponse ; le script affiche également une conclusion « antenne sans retard » malgré un écart moyen conservé d'environ **4 cm** ;
- les contrôles historiques du dipôle donnent une étendue d'écart de **0,87 cm** et une pente **0,9877** : ce sont des contrôles utiles de stabilité et d'échelle, pas une validation absolue à zéro retard ;
- la limite prétendue de **24 cm** de retard pour l'UWB Surveyor, déduite de la seule taille de carte, n'est pas une borne générale sur le retard d'un système rayonnant résonant ;
- les figures et le rappel des mesures du 9 octobre sont réutilisés pour d'autres antennes et scénarios ; cette superposition est un repère, pas une validation expérimentale de ces antennes ;
- les trous Vivaldi sont décrits comme traversant la masse, alors que, dans la géométrie actuelle à masse limitée, leurs positions sont dans du FR4 sans cuivre ; leur absence du modèle reste une différence à qualifier ;
- le README des antennes n'inclut pas la Vivaldi dans son tableau récapitulatif des antennes présentes ;
- le backlog conserve des dimensions de Vivaldi dépassées ; plusieurs explications catégoriques sur la dispersion, le masque ou les trous demandent une qualification ;
- le PDF de faisabilité est un compte rendu de discussion, pas un cahier de validation numérique. Sa source LaTeX et ses formules textuelles ne constituent pas des tests exécutables ; le PDF présente notamment des caractères mathématiques mal rendus.

## 11 Reproductibilité et contenu conservé

Les deux environnements utiles existent sur cette machine :

| Environnement | Versions constatées |
|---|---|
| `ph` | Python 3.12.13 ; NumPy 2.4.4 ; SciPy 1.15.3 ; Matplotlib 3.10.1 ; gerbonara 1.6.3 |
| `openems` | Python 3.13.16 ; openEMS 0.37.0 ; CSXCAD 0.7.0 ; NumPy 2.5.3 ; Matplotlib 3.11.2 ; h5py 3.16.0 |

Les DLL openEMS sont présentes dans `outils/openEMS`. Le Python appelé par défaut dépend du shell et de l'activation conda ; les commandes de reprise doivent donc identifier l'interpréteur utilisé. Il n'y a pas de fichier de dépendances verrouillé ou d'export d'environnement dans le périmètre pour reconstruire exactement l'ensemble ailleurs.

Les résultats locaux apportent une réelle valeur : courbes S11, sondes temporelles, réglages de Vivaldi, résultats et journal du dipôle. Mais `.gitignore` écarte `**/resultats/`, `**/mesures/` et `outils/`. Un clone Git seul ne reconstitue donc pas cet état, ni même tous les manifestes de campagne. Ce risque est déjà noté dans le backlog et reste à traiter.

Pour chaque résultat retenu, il manque une traçabilité complète et immuable associant configuration, géométrie ou empreinte des sources, version des bibliothèques, grille finale, excitation, durée réelle, motif d'arrêt et fichiers produits. Les noms des essais encodent une partie des paramètres, mais les valeurs implicites changent avec les constantes du code. Les résidus temporels conservés permettent de refaire l'extraction des S11, pas de prouver après coup toute la scène simulée.

Le périmètre ne contient pas de projet CAO PCB natif `.kicad_pcb` : Python est la source de conception et les Gerbers constituent les fichiers de production. C'est une organisation viable à condition que la régénération et sa vérification soient fiables. Elle doit être claire pour la personne qui reprendra mécaniquement ou électroniquement les cartes.

## 12 Ordre de reprise proposé

Ces étapes n'ont pas été exécutées dans le cadre de cet audit.

1. **Préserver un état complet reproductible.** Archiver les sources, les résultats locaux utiles et les versions ; relier chaque simulation à sa configuration. Écarter explicitement les DXF Vivaldi dépassés de tout flux de commande.
2. **Réparer la chaîne publique.** Utiliser une série avec domaine, grille et durée comparables ; prendre en compte toutes les positions de plaque ; ajouter les contrôles d'entrée fréquentiels, le cas sans bande adaptée et un format de noms réimportable.
3. **Établir la convergence numérique.** Faire varier effectivement les pas dans le substrat, la transition, les marges et la durée. Contrôler S11 complexe, phase et résidu fond/cible. Requalifier le petit losange avec ses interruptions visibles.
4. **Qualifier le dossier de fabrication.** Brancher les comparaisons attendues, produire de vrais rendus indépendants, vérifier perçages et contours, définir les SMA, faire accepter le panneau et le cuivre au bord, fixer stratifié, masque et finition.
5. **Recaler l'UWB Surveyor sur l'exemplaire réel.** Récupérer les fichiers complexes et la description du banc, comparer l'antenne seule puis le fond et les positions de plaque. Conserver séparément les hypothèses de retard de ligne, de rayonnement et d'environnement.
6. **Valider les cartes reçues.** Mesurer leur S11 avec un plan de référence documenté, puis leur réponse utile en transmission ou réflexion. Un bon S11 seul ne valide pas le modèle direct nécessaire à la tomographie.

## 13 Éléments disponibles pour reprendre la main

**Oui pour la maintenance et le développement.** Le code, les conventions, les géométries, les résultats intermédiaires et les fichiers de production permettent de comprendre le projet, de reproduire une partie importante des analyses et d'organiser les corrections. Aucun manque de contexte ne m'empêche de commencer cette reprise technique.

**Non pour affirmer que tous les objectifs physiques sont déjà démontrés.** Pour conclure sur l'origine du décalage réel et qualifier la fabrication, il faut encore :

- les acquisitions complexes originales de chaque campagne : fond, plaques et SHORT indépendant, plus les métadonnées SOL et l'état exact de calibration des exports ;
- l'identification certaine de l'antenne et des adaptateurs de chaque campagne, les plans de référence et les distances mesurées ;
- les dimensions réelles de plaque, l'orientation, les supports et les informations utiles sur l'environnement ;
- une géométrie UWB Surveyor mieux établie, avec sa face arrière et sa transition d'alimentation, ou des mesures suffisantes pour tester les hypothèses ;
- la référence des connecteurs SMA retenus et les confirmations de fabrication mentionnées plus haut ;
- une étude de convergence et, pour une validation de tomographie, la qualification du champ rayonné ou du modèle direct utile.

**Décision finale : reprise du projet possible avec les éléments présents ; validation quantitative du banc et feu vert définitif aux commandes PCBWay encore conditionnels.** Le projet constitue une base de travail sérieusement récupérable, mais plusieurs formulations de validation dans les README dépassent actuellement ce que les contrôles démontrent.

## 14 Preuves techniques jointes

Les pièces suivantes ont été créées uniquement dans `chatGPT_critical_review` :

- `inventaire_avant_audit_2026-10-18.json` : liste, taille, date de modification et SHA-256 des 266 fichiers d'origine ;
- `preuves_verifications_2026-10-18.json` et `verifications_audit.py` : syntaxe, statistiques S11, CRC, correspondance des membres ZIP, SVG et intégrité des fichiers d'origine ;
- `preuves_traitement.txt` : contrôles exécutés et sondes de défauts du traitement et des imports ;
- `verification_fdtd_sans_calcul.py` et `verification_fdtd_resultats.json` : inspection des grilles avec les véritables objets openEMS, relecture des sondes et effets des paramètres, sans exécution FDTD ;
- `preuves_fabrication.txt` : détails de relecture, géométrie, perçage et écarts documentaires.

Pour rejouer les contrôles de lecture depuis la racine du projet, sans lancer le solveur ni les exportateurs :

```powershell
& 'C:\Users\jfeld\anaconda3\envs\ph\python.exe' -B `
  'simulation\chatGPT_critical_review\verifications_audit.py'
& 'C:\Users\jfeld\anaconda3\envs\openems\python.exe' -B `
  'simulation\chatGPT_critical_review\verification_fdtd_sans_calcul.py'
```

Le premier script réécrit uniquement son fichier de preuves dans le dossier d'audit ; le second imprime ses résultats. Les chemins d'interpréteur sont ceux constatés sur cette machine. Les sources officielles sont liées près des constats qu'elles étayent ; les observations propres au projet sont rattachées aux fichiers et aux preuves locales.
