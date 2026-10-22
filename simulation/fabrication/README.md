# Les deux articles PCBWay

Révision physique du 18 octobre 2026 : **deux articles distincts**, à déposer séparément. Le premier contient les deux losanges sur un panneau client ; le second contient la Vivaldi seule. La quantité proposée est de **5 panneaux**, donnant 5 petits et 5 grands losanges après séparation, et de **5 Vivaldi**.

| Article | ZIP à déposer | Dimensions nominales de découpe | Contenu d'une pièce commandée |
|---|---|---|---|
| 1 | [panneau_losanges_pcbway.zip](panneau_losanges/panneau_losanges_pcbway.zip) | 92,600 × 72,000 mm | Un panneau avec deux conceptions différentes |
| 2 | [vivaldi_tomographie_pcbway.zip](vivaldi_tomographie/vivaldi_tomographie_pcbway.zip) | 143,668736 × 280,903102 mm | Une Vivaldi |

Les cotes correspondent à la **ligne médiane du GKO**. La largeur du trait de dessin, 0,100 mm, ne s'ajoute pas aux dimensions de la carte. Pour un formulaire limité au dixième, saisir 92,6 × 72,0 et 143,7 × 280,9 mm ; le contour Gerber porte la découpe nominale précise.

Les coordonnées source de la Vivaldi donnent 143,668735 × 280,9031025 mm ; leur arrondi au format Gerber donne les dimensions de la table. Cet écart inférieur à 0,000002 mm est sans portée pour les tolérances de fabrication. Les valeurs source et relues sont conservées dans l'[inventaire de la livraison courante](inventaire_livraison_courante.json).

Ces jeux décrivent la géométrie actuelle et son contrat de fabrication. Les courbes historiques, obtenues avant le changement de matériau, l'ajout de l'empreinte SMA et les autres corrections, ne qualifient pas ces fichiers.

## Statut de qualification au 22 octobre 2026

Deux contrôles différents, deux verdicts différents, et **aucun ne remplace l'autre**. Les deux fichiers sont conservés côte à côte dans `resultats/pcbway_maille_controlee_v2/`.

| Question posée | Fichier | Verdict |
|---|---|---|
| `S11` est-il prédit **point par point** ? | `qualification_globale.json` | **Non.** Le contrôle spatial échoue pour les trois antennes ; le contrôle temporel et la passivité passent. |
| Les niveaux de maillage s'accordent-ils sur **ce que l'antenne fait** ? | `qualification_grandeurs_decision.json` | **Oui**, pour les trois antennes. |

**Ce qui est établi**, sur 1,4–6,0 GHz, et qui ne dépend pas du maillage :

| Antenne | Puissance réfléchie moyenne | Part de bande sous −6 dB | Étendue entre niveaux |
|---|---:|---:|---|
| Grand losange | **−11,96 dB** | **100 %** | 0,13 dB · 0,00 pt |
| Vivaldi | **−12,76 dB** | **100 %** | 0,08 dB · 0,00 pt |
| Petit losange | −7,17 dB | 78,9 % | 0,13 dB · 0,54 pt |

**Ce qui n'est pas établi** : que `S11` soit prédit à mieux que l'écart ponctuel conservé dans `qualification_globale.json`. Le [diagnostic du 22 octobre](../chatGPT_critical_review/convergence_grandeurs_decision_2026-10-22/note.md) montre qu'un maillage plus fin ne le rendra pas vrai : la suite des écarts remonte sur ses deux derniers paliers et atteint son plus mauvais écart au maillage le plus fin, parce que les grilles ne sont pas emboîtées et qu'une cellule proche du port y grossit d'un facteur 1,69. La courbe mesurée pourra s'écarter d'autant — avant même de compter le connecteur réel, la tolérance du FR4 sur sa permittivité et la finition du cuivre, tous hors modèle.

**À ne pas confondre** : le petit losange **n'est pas une antenne de travail dans cette bande**. C'est la conception publiée pour 2,5–13,5 GHz, livrée comme étalon du modèle électromagnétique. La commande porte donc sur deux antennes utilisables et un témoin de validation.

```powershell
python -B -Xutf8 qualifie_grandeurs_decision.py --campagne resultats/pcbway_maille_controlee_v2
python -B -Xutf8 verifie_coherence_livraison.py --campagne resultats/pcbway_maille_controlee_v2
python -B -Xutf8 -m pytest -q -p no:cacheprovider test_qualifie_grandeurs_decision.py test_verifie_coherence_livraison.py
```

**Le dernier contrôle à passer avant de déposer** est `verifie_coherence_livraison.py`. Ni le vérificateur de Gerbers ni la qualification ne répondent à la question « ce que je dépose est-il ce qui a été simulé ? » : le premier compare le ZIP à la géométrie *courante*, la seconde qualifie des profils calculés à une date donnée. Il suffirait d'avoir retouché un `geometrie.py` entre les deux pour que les deux contrôles passent séparément en décrivant deux cartes différentes. L'outil ferme la chaîne en neuf maillons et constate aujourd'hui que **les 18 sources gelées avec la campagne sont identiques à l'arbre de travail**.

## Options de commande

| Champ du formulaire | Article 1 : panneau | Article 2 : Vivaldi |
|---|---|---|
| Board type | **Panel by Customer** | **Single pieces** |
| Different design in panel | **2** | 1 |
| Quantity | **5 panneaux complets** | 5 cartes |
| Break-away rail / ajout de rails | No : découpe fournie | No |
| X-out allowance | Not Accept : demander les panneaux complets sans antenne rebutée | Sans objet |
| Layers | 2 | 2 |
| Material / FR4-TG | **Shengyi S1000H, TG150**, sans substitution silencieuse | Idem |
| Thickness | **1,6 mm nominal** ; faire préciser diélectrique et épaisseur finie séparément | Idem |
| Finished copper | **1 oz**, 35 µm nominal par face | Idem |
| Surface finish | **Immersion gold (ENIG)** | Idem |
| Solder mask | **None**, aucune résine sur les deux faces ni dans les fentes | Idem |
| Silkscreen / UV printing | **None** | Idem |
| Min track/spacing | 6/6 mil | 6/6 mil |
| Min hole size | Option **0,3 mm ↑** : plus petit trou réel 0,457 mm | Idem |
| Via process | Vias not covered ; pas de remplissage | Idem |
| Gold fingers, edge plating, castellated holes, bevelling | No | No |
| Remove product No. / marquages ajoutés | Yes ; aucun marquage sur cuivre ou FR4 de l'antenne | Idem |
| Assembly / pochoir | Non demandé : PCB nus | Idem |

Le [formulaire PCBWay](https://www.pcbway.com/QuickOrderOnline.aspx), consulté le 18 octobre 2026, propose les options S1000H TG150, masque None et sérigraphie None. L'[aide sur les panneaux clients](https://www.pcbway.com/helpcenter/panel_issues/Confirm_the_panel_way_of_the_boards.html) s'applique au panneau à pontets fourni. Déclarer les **deux conceptions** même si elles partagent une seule plaque ; conserver la confirmation du prix et de la quantité de panneaux livrés.

Le champ « Edge connector » du formulaire concerne ici les doigts de contact et traitements de bord : laisser **No**. Le connecteur SMA se soude sur les surfaces planes de l'empreinte déjà dessinée. Il ne demande ni métallisation de tranche ni chanfrein.

Copier les [instructions techniques en anglais](instructions_pcbway_anglais.txt) dans la demande de fabrication ou les joindre comme consignes. Elles sont préparées pour la revue CAM ; aucun envoi ni commande n'a été effectué par ces scripts.

## Géométries et perçages

| Élément | Définition actuelle |
|---|---|
| Petit losange | Carte 32 × 40 mm, radiateur dérivé de la référence publiée ; interface SMA ajoutée |
| Grand losange | Carte 57,6 × 72 mm ; échelle 1,8 du radiateur, épaisseur 1,6 mm et ligne nominale 3,1 mm |
| Séparation du panneau | Fraisage 3,0 mm, deux pontets de 3,0 mm ; pas de rainure en V |
| NPTH panneau | 16 amorces de rupture, diamètre 0,600 mm |
| PTH panneau | 4 vias de masse, diamètre fini demandé 0,457 mm : deux par antenne |
| Vivaldi | Cuivres conservés hors implantation SMA ; substrat agrandi de 0,300 mm aux côtés et à la bouche |
| NPTH Vivaldi | 2 trous de fixation de 3,000 mm |
| PTH Vivaldi | 2 vias de masse de diamètre fini demandé 0,457 mm |

Les deux bords d'alimentation des losanges sont sur le bord extérieur inférieur du panneau. Après séparation, **araser les restes de pontets jusqu'aux contours rectangulaires nominaux**, sans entamer le cuivre, avant la comparaison aux simulations des antennes individuelles. La simulation d'une antenne séparée ne décrit pas le panneau intact.

Le cuivre arrive volontairement au bord inférieur pour le SMA. Hors de ce bord, la marge nominale est notamment de 0,400 mm pour la masse du petit losange, 0,720 mm pour celle du grand et 0,300 mm aux côtés et à la bouche de la Vivaldi. Le contrôle géométrique exige au moins 0,250 mm hors alimentation. Les [capacités PCBWay](https://www.pcbway.com/capabilities.html) et la revue CAM doivent être confrontées aux tolérances réellement acceptées ; ne pas laisser déplacer le cuivre pour résoudre une alerte automatique.

## Matériau, connecteur et comparaison future

Le matériau demandé est le **stratifié S1000H**. S1000HB désigne le préimprégné associé dans la [fiche officielle conservée](../references/S1000H_fiche_PCBWay.pdf), et ne constitue pas une autre référence de stratifié à substituer. La fiche donne à 1 GHz des valeurs typiques Dk = 4,6 et Df = 0,011, sur un échantillon de 1,6 mm de construction 8 × 7628. Le modèle Debye nominal est construit à partir de ce point ; ce n'est pas une identification large bande du lot commandé.

L'épaisseur du diélectrique est `h = 1,6 mm` dans le modèle. Faire documenter séparément **épaisseur diélectrique, cuivre et finition**, puis mesurer l'épaisseur finie à réception. La seule valeur « Thickness 1.6 » ne garantit pas que le diélectrique livré fasse exactement 1,6 mm. La comparaison expérimentale doit utiliser les dimensions et tolérances connues du lot.

Le connecteur retenu est une **SMA femelle bord de carte Cinch/Johnson 142-0701-851**, standard, non RP-SMA. Les trois antennes ont la même implantation : pad signal 2,286 × 5,080 mm, deux pattes de masse dessus reliées au plan de masse dessous par deux vias. Les connecteurs sont à commander séparément et à souder après les contrôles de réception. La [vérification détaillée de l'implantation](VERIFICATION_EMPREINTE_SMA.md) distingue les cotes du catalogue et l'adaptation de ligne du projet.

Le port de simulation est idéal et référencé au bord du PCB. Le boîtier SMA, sa broche, le PTFE et la soudure ne sont pas modélisés intégralement. Une calibration SOL au raccord coaxial du SMA et le plan de port au bord du PCB sont deux plans distincts ; conserver la calibration et documenter la transition selon le protocole de mesure du projet.

## Contenu des ZIP et preuves de transfert

Chaque ZIP courant contient **9 fichiers** : les cinq Gerbers `.GTL`, `.GBL`, `.GTS`, `.GBS`, `.GKO`, les deux Excellon `-NPTH.DRL` et `-PTH.DRL`, une notice et un manifeste JSON. Les GTS/GBS sont ouverts sur toute l'enveloppe ; ils accompagnent l'exigence de masque None. Les fichiers Excellon déclarent séparément `TYPE=NON_PLATED` et `TYPE=PLATED`. Les diamètres PTH sont les diamètres finis après métallisation.

Le manifeste contient les coordonnées exportées, leur empreinte SHA-256, les empreintes des sources, le modèle de matériau, le connecteur et les empreintes de tous les fichiers utiles. L'empreinte du ZIP lui-même est dans le fichier `.zip.sha256` voisin, afin d'éviter une auto-référence impossible.

Depuis `simulation`, dans l'environnement `ph` :

```powershell
python -B -Xutf8 export_gerber.py --tout
python -B -Xutf8 verifie_gerber.py fabrication/panneau_losanges/panneau_losanges_pcbway.zip fabrication/vivaldi_tomographie/vivaldi_tomographie_pcbway.zip
python -B -Xutf8 apercu.py --panneau losanges --antenne vivaldi_tomographie --sortie fabrication/apercus
python -B -Xutf8 -m pytest -q -p no:cacheprovider test_fabrication.py
```

Le vérificateur relit chaque fichier avec gerbonara et compare les **surfaces complètes** des cuivres, les ouvertures de masque, les lignes médianes des contours fermés et chaque position, diamètre et métallisation de perçage à la source courante. Un simple accord de dimensions extérieures ne suffit pas. Ses rapports JSON, SVG et PNG sont dans `verification/` de chaque article. L'aperçu des sources complète cette lecture indépendante avec les marges, anneaux de vias et contrôles de topologie. Il écrit aussi les résultats détaillés dans `contours.controles.txt`.

Conserver le ZIP effectivement envoyé, son SHA-256, les réponses CAM et les données du lot. Toute modification de géométrie, matériau ou connectique demande de régénérer les fichiers et de réévaluer les simulations correspondantes. Les DXF sont destinés à l'inspection ou à l'édition, et ne remplacent pas ces ZIP.

La suite pratique est dans [Contrôles à réception](CONTROLE_RECEPTION.md).
