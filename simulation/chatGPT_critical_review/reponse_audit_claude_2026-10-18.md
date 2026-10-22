---
title: "Réponse à l'audit critique du simulateur"
subtitle: "Contre-vérification indépendante de l'audit ChatGPT du 18 octobre 2026"
author: "Claude Opus 5"
date: "18 octobre 2026 — projet MicroWaveTomography, répertoire `simulation`"
lang: fr
---

# Verdict en un paragraphe

**L'audit est juste. Sur les 40 affirmations chiffrées ou vérifiables que j'ai
pu rejouer indépendamment, les 40 observations sont correctes, et 32 d'entre
elles tombent au chiffre près.** C'est un taux inhabituel : cet audit n'extrapole
pas, il a réellement ouvert les fichiers. Je corrige trois points
d'interprétation, j'ajoute quatre défauts qu'il a manqués — dont un que je place
en P1 parce qu'il attaque directement la question centrale du projet — et je
conteste une priorité. Surtout, je **mesure** la grandeur que l'audit laisse
explicitement ouverte : la contamination de la différence fond/cible par le
critère d'arrêt. Réponse : elle est réelle, elle se situe entre 3 et 20 dB sous
l'écho de plaque attendu, et elle **ne peut pas expliquer les 20 cm**. Le défaut
P1 de l'audit est un défaut d'hygiène numérique à corriger, pas la solution de
l'énigme du banc.

# 1. Méthode de cette contre-vérification

J'ai relu les mêmes sources que l'audit : les 20 fichiers Python de
`simulation`, les README et fiches d'antennes, le backlog, les trois `antenne_seule.s1p`
conservés, les sondes temporelles brutes de port, les deux ZIP PCBWay, les
Gerbers, les Excellon, les DXF, les deux rendus SVG, la sortie de vérification
du dipôle, et les pièces jointes de l'audit lui-même.

Ce que j'ai fait en plus de la lecture :

- rejoué numériquement les statistiques S11, les segmentations de bande, les
  sondes de défaut du traitement, les retards d'antenne et l'arithmétique de
  maillage, avec NumPy, dans l'environnement `ph` ;
- relu les deux ZIP avec `gerbonara` 1.6.3, recalculé les encombrements, les
  perçages, l'état de métallisation, et reproduit le défaut de rendu SVG ;
- calculé les distances cuivre / contour et cuivre / pontets directement sur les
  contours Python, par échantillonnage à 0,05 mm des polylignes ;
- **reconstruit le S11 à partir des sondes temporelles brutes conservées, puis
  raccourci la fenêtre temporelle pour mesurer la sensibilité du S11 à la
  troncature.** C'est une étude de convergence faite sur des calculs déjà payés.

Ce que je n'ai pas fait : aucune campagne FDTD, aucune vérification des pages
PCBWay, MathWorks ou openEMS citées par l'audit (pas de contrôle réseau),
aucun recalcul de son inventaire SHA-256 des 266 fichiers, aucune lecture des
figures de `report_john.pdf`. Sur ces points je prends l'audit au mot et je le
signale.

Aucun fichier du projet n'a été modifié. Mes scripts de contrôle ont tourné
depuis un répertoire de travail extérieur, avec `python -B`, et n'écrivent que
dans ce répertoire. Les seuls fichiers créés dans `MicroWaveTomography` sont
le présent document, son script de construction et le PDF produit.

# 2. Ce que je confirme, chiffre par chiffre

« exact » signifie que je retrouve la valeur de l'audit à l'arrondi
d'affichage ; « confirmé » qu'il s'agit d'un fait de code que j'ai vérifié sans
qu'un chiffre soit en jeu.

| Affirmation de l'audit | Sa valeur | La mienne | Verdict |
|:-----------------------|:----------|:----------|:--------|
| Vivaldi, points sous $-10$ dB (1,4–6 GHz) | 71,4 % | 71,351 % | exact |
| Vivaldi, points sous $-6$ dB | 94,1 % | 94,054 % | exact |
| Vivaldi, puissance réfléchie moyenne | $-10{,}6$ dB | $-10{,}5929$ dB | exact |
| Vivaldi, pire S11 | $-2{,}9$ dB | $-2{,}8982$ dB | exact |
| Vivaldi, zones au-dessus de $-6$ dB | 5,45–5,65 et 5,825–5,85 | identiques | exact |
| Petit losange, segments sous $-10$ dB | 2,30–5,80 ; 6,60–9,50 ; 10,55–13,60 | identiques | exact |
| Petit losange, couverture d'enveloppe | 84,58 % | 84,5815 % | exact |
| Grand losange, segments | 1,275–1,600 ; 2,225–6,000 | identiques | exact |
| Grand losange, couverture | 87,37 % | 87,3684 % | exact |
| Grille `geomspace` : écho de 50 cm lu à | 40,46 cm | 40,457 cm | exact |
| Lobe secondaire promu « pic lointain » | 70,00 et 77,08 cm | 69,999 et 77,082 cm | exact |
| Écart entre les deux | 31,5 dB | 31,48 dB | exact |
| `derive_ns = -0,25` : décalage du pic | 20,00 $\rightarrow$ 14,75 cm | 19,999 $\rightarrow$ 14,753 cm | exact |
| $\tan\delta$ effectif Vivaldi, 1 / 6 GHz | 0,070 / 0,0117 | 0,0700 / 0,01167 | exact |
| $\tan\delta$ effectif petit losange, 1 / 14 GHz | 0,195 / 0,0139 | 0,1950 / 0,01393 | exact |
| Faces de plaque hors grille, 50 / 60 cm | 0,346 / 0,415 mm | 0,3459 / 0,4151 mm | exact |
| Cellules par $\lambda$ dans le substrat, x / z | 5,05 / 4,77 | 5,047 / 4,764 | exact |
| Rapports de cellules voisines, Vivaldi z / grand losange x | 6,27 / 7,20 | 6,2707 / 7,2000 | exact |
| Coût annoncé pour la Vivaldi seule | 57 603 cellules | 57 603 | exact |
| `banc.Antenne` : retard et décalage | 0,23 ns / 6,9 cm | 0,2311 ns / 6,929 cm | exact |
| Géométrie UWB réellement chargée | ligne 69,2 mm, 0,421 ns, 12,62 cm | 69,20 mm, 0,42090 ns, 12,618 cm | exact |
| Vivaldi : trajet interne, puis biais si émission à la bouche | 46,1 cm, 18,0 cm | 46,108 cm, 18,047 cm | exact |
| DXF Vivaldi contre contours actuels | 279,1375 contre 280,603102 mm | identiques | exact |
| Cuivre dessous Vivaldi, README contre Gerber | 143,07 contre 91,534368 mm | identiques | exact |
| Marge du cuivre à la ligne de rupture | $\approx$ 1,5 mm | 1,500 mm | exact |
| Marge du cuivre au bord d'un trou de 0,6 mm | 1,2 mm | 1,200 mm | exact |
| Dipôle : étendue, pente, écart moyen | 0,87 cm / 0,9877 / $\approx$ 4 cm | 0,87 / 0,9877 / $+4{,}00$ cm | exact |
| Deux ZIP : 7 membres, 5 Gerbers, CRC bons | — | identique, 16 trous de 0,6 et 2 de 3,0 mm | exact |
| Rendus SVG de 244 et 247 octets, sans dessin | — | 243 / 246 octets générés, 0 élément `<path>` | confirmé |
| `run.py --mode fdtd` n'appelle jamais `serie()` | — | `lance()` appelé sans `x_domaine` ni `n_pas` | confirmé |
| `mailles_par_lambda` et `maille_min` ne pilotent rien | — | aucune occurrence hors de leur déclaration | confirmé |
| `--sans-symetrie` ne désactive aucune symétrie | — | `symetrie` n'apparaît que dans `estime_cout` | confirmé |
| `verifie_maillage` ignore sa taille cible | — | `maille_cible` jamais lu dans le corps | confirmé |
| `compare()` jamais appelée | — | confirmé, et `ATTENDU` est aussi du code mort | confirmé |
| `bool(o.plated)` transforme l'inconnu en « non métallisé » | — | état brut `None` sur tous les trous | confirmé |
| Antenne non adaptée $\rightarrow$ échec du résumé | — | `ValueError: zero-size array to reduction…` | confirmé |
| 20 contrôles passent, le README en annonce 16 | — | 20 appels à `verifie()`, README ligne 51 | exact |
| Trous Vivaldi décrits comme traversant la masse | — | trous à $x = \pm 65{,}53$ mm, masse à $\pm 20$ mm | confirmé |
| `antennes/README.md` omet la Vivaldi de son tableau | — | quatre entrées, pas de Vivaldi | confirmé |
| Les sorties FDTD ne se relisent pas par `--mode mesures` | — | `plaque_50cm` ne correspond à aucun motif | confirmé |

Deux précisions qui renforcent l'audit plutôt qu'elles ne le corrigent.

**Le cuivre affleurant est plus étendu qu'« plusieurs portions ».** En
échantillonnant les contours cuivre tous les 0,2 mm, je compte les points à
moins de 10 µm du contour de carte : **889 pour le cuivre dessus de la Vivaldi
et 1 085 pour son cuivre dessous**, soit environ **178 mm et 217 mm de frontière
confondue avec le bord de carte**. Pour les deux losanges, ces compteurs valent
19 et 161 points, soit 3,8 mm et 32,2 mm — exactement le bord d'alimentation et
l'arête inférieure du plan de masse, et rien d'autre. La distinction que fait
l'audit entre la Vivaldi et les losanges est donc non seulement correcte, elle
est de deux ordres de grandeur.

**Le README de fabrication est périmé sur les deux dimensions, pas une seule.**
L'audit relève la largeur (143,07 contre 91,534368 mm). La hauteur annoncée,
279,14 mm, est également celle des anciens DXF : les lignes 177–178 de
`fabrication/README.md` décrivent intégralement la version abandonnée.

# 3. Les trois points où je corrige l'audit

## 3.1 La cause du rendu SVG vide n'est pas celle qu'il indique

L'audit écrit : « l'appel à `to_svg()` sans couleurs explicites laisse les
couches sans couleur utilisable ». L'observation est exacte, le mécanisme non.

Le code de `gerbonara` 1.6.3 fait ceci :

```python
if colors is None:
    colors = defaultdict(lambda: 'black')
...
for (side, use), layer in reversed(self.graphic_layers.items()):
    if re.fullmatch(side_re, side) and (fg := colors.get(f'{side} {use}')):
```

`defaultdict.get()` **n'appelle pas la fabrique par défaut** : sur une clé
absente, elle rend `None`, le test échoue, et aucune couche n'est émise. Ce
n'est donc pas un défaut de configuration côté projet mais **un bug de la
bibliothèque tierce**, qui rend `to_svg()` inopérante par défaut quelle que soit
la pile de couches. Le dépôt n'a rien fait de particulier pour mériter ce
résultat, et le même appel échouera chez quiconque relira ces Gerbers.

La conséquence pratique est la même que celle décrite par l'audit — il n'existe
aucune preuve visuelle tierce des deux cartes — mais le correctif est différent
et il tient en un mot clé. Les deux formes suivantes produisent bien un dessin,
vérifié :

```python
couleurs = {f'{s} {u}': 'black' for s, u in pile.graphic_layers}
couleurs.update({'drill pth': 'black', 'drill npth': 'black',
                 'outline': 'black'})
svg = str(pile.to_svg(force_bounds=pile.board_bounds(), colors=couleurs))
# ou, recommandé par gerbonara pour une image de contrôle :
svg = str(pile.to_pretty_svg(force_bounds=pile.board_bounds()))
```

Mesures obtenues : 5 599 octets et 10 tracés pour le panneau, 43 194 octets et
5 tracés pour la Vivaldi avec `to_svg(colors=…)` ; 7 437 et 26 205 octets avec
`to_pretty_svg()`. Les Gerbers ne sont donc pas vides, et la preuve visuelle
est à dix minutes de travail, pas à une refonte du vérificateur.

## 3.2 Le $1{,}9169$ du modèle analytique correspond à un réglage non déclaré

L'audit annonce « avec les réglages par défaut à 50 cm, il produit
$\max |S11| = 1{,}9169$ ». Avec les réglages réellement par défaut, c'est-à-dire
`echos_fixes=((0.05, 95.0),)` comme dans `modele.simule` et dans
`run.py --mode analytique`, je trouve **1,9120**. La valeur 1,9169 est celle
obtenue **sans échos fixes**, `echos_fixes=()`, ce qui est le réglage des tests
et non celui de la commande. L'écart est sans portée sur la conclusion, mais il
illustre le problème que l'audit dénonce par ailleurs : dans ce projet, la
même phrase désigne plusieurs réglages.

La conclusion de l'audit — le modèle n'est pas une prédiction normalisée — est
juste. Je la renforce : le défaut n'est pas seulement une amplitude
« heuristique », il est **dimensionnel**. `modele.gamma_plaque` rend

$$\Gamma = -\,\frac{\text{couverture}}{2\,x}$$

avec $x$ en mètres. Cette expression a la dimension d'un inverse de longueur :
le coefficient de réflexion dépend de l'unité choisie pour $x$. Exprimer la
même distance en centimètres divise l'écho par 100. Il manque une longueur de
référence — l'ouverture équivalente de l'antenne, par exemple — et le correctif
est d'une ligne. Tant qu'elle est absente, aucune amplitude de ce module ne
peut être comparée à une mesure, et le facteur $1/(2x)$ n'est pas « heuristique »
mais faux.

## 3.3 Les cotes des deux ZIP dépendent d'une convention qu'il faut fixer

L'audit donne 92,60 × 72,00 mm pour le panneau et 143,068736 × 280,603102 mm
pour la Vivaldi. Ce sont les cotes de la **ligne médiane** du contour, celles
des sources Python. En relisant les mêmes archives, `gerbonara` rend pour
`board_bounds()` **92,700 × 72,100 mm** et **143,168736 × 280,703102 mm** : la
boîte englobante inclut la demi-largeur de l'ouverture de 0,100 mm avec laquelle
le contour est tracé de chaque côté.

Les deux valeurs sont correctes et diffèrent de 0,1 mm. Le point n'est pas
cosmétique : c'est précisément l'écart que verra le `compare()` manquant si on
le branche sur `bounding_box()` en lui donnant les cotes des sources. La
reprise doit choisir sa convention et l'écrire, sinon le contrôle qui manque
échouera dès qu'il existera, pour une raison qui n'a rien à voir avec le dessin.
C'est aussi la cote que le fabricant doit confirmer : 92,60 ou 92,70 mm de
panneau livré.

# 4. Quatre défauts que l'audit a manqués

## 4.1 P1 — les colonnes « pic proche » et « pic lointain » peuvent échanger leurs rôles

L'audit signale que « un maximum secondaire devient automatiquement un pic
lointain », et c'est vrai. Il manque la conséquence, qui est beaucoup plus
grave : `traitement.bilan` trie les deux maxima **par distance croissante**
(`traitement.py:129-131`), alors que `maxima_locaux` les a rendus **par
amplitude décroissante**. Quand le lobe secondaire tombe du côté proche, il
prend la place du pic physique dans la colonne « pic proche », et le pic
physique est reporté comme « pic lointain ».

Ce n'est pas une hypothèse. Avec un modèle à **un seul trajet interne**, donc
une vérité de terrain qui ne comporte qu'un écho, voici le tableau que le
projet imprime :

| plaque | pic proche | pic lointain | écart proche | écart lointain |
|-------:|-----------:|-------------:|-------------:|---------------:|
| 50 cm | 70,00 cm | 77,08 cm | **20,00 cm** | 27,08 cm |
| 60 cm | 80,00 cm | 87,09 cm | **20,00 cm** | 27,09 cm |
| 70 cm | 82,91 cm | 90,00 cm | **12,91 cm** | 20,00 cm |

À 70 cm, le lobe secondaire — 31,5 dB sous le principal — est passé du côté
proche. La colonne « écart proche », celle que le projet suit d'un bout à
l'autre, affiche donc une **dérive de 7,1 cm entre la première et la dernière
position, pour un modèle où le décalage est rigoureusement constant**.

Cela compte parce que c'est exactement la grandeur en jeu dans le projet. La
question ouverte du banc est « pourquoi le décalage de 20 cm et pourquoi
semble-t-il dériver avec la distance ». Un mécanisme capable de fabriquer 7 cm
de fausse dérive, sans rien signaler, dans la colonne qui porte cette question,
doit être réparé **avant** d'interpréter quoi que ce soit. Et le projet en
contient déjà un cas réel : dans `antennes/dipole_reference/sortie_verification.txt`,
un dipôle qui n'a pas de second trajet interne se voit attribuer des « pics
lointains » à 50,39, 56,89 et 68,55 cm, soit des écarts de 30,39, 26,89 et
28,55 cm — purs artefacts de fenêtrage, imprimés sans réserve à côté des
valeurs physiques.

Correctif minimal : rendre les pics avec leur rang d'amplitude et leur niveau,
exiger une proéminence minimale, et refuser de nommer « lointain » un maximum
situé en deçà du principal.

## 4.2 P2 — l'étalon dipôle manque de 20 % la seule grandeur qu'il prédit

`antennes/dipole_reference/sortie_verification.txt` contient ceci :

```
[OK  ] resonance dans la bande attendue
       minimum de |S11| a 4.00 GHz pour 5.00 attendus
```

Le contrôle est marqué réussi parce que son critère est « minimum entre 3,8 et
5,5 GHz ». Mais la prédiction analytique était 5,00 GHz et le solveur rend
4,00 GHz : **20 % d'erreur sur la fréquence de résonance d'un dipôle dans le
vide**, avec des cellules de 1 mm, soit 60 cellules par longueur d'onde. C'est
le cas le plus facile qu'un solveur FDTD puisse rencontrer : pas de substrat,
pas de ligne, pas de transition.

Un écart de quelques pour cent serait normal — un dipôle fin résonne vers
$0{,}48\,\lambda$. Vingt pour cent désigne autre chose : la modélisation du gap
d'alimentation, le rayon effectif du conducteur, ou le port localisé. Le projet
appelle cette antenne « l'étalon du traitement » et en tire que « ni le
traitement ni l'extraction du S11 n'en sont responsables » — ce qui reste vrai,
V3 le montre. Mais l'étalon ne dit rien de bon sur la **chaîne
électromagnétique**, et la fenêtre d'acceptation de 1,7 GHz de large a absorbé
l'information au lieu de la rapporter.

C'est directement lié à la question de convergence que l'audit pose au §5 : la
même machinerie de maillage, de port et de lissage sert à la Vivaldi. Avant
d'étudier la convergence de la Vivaldi, il faut expliquer le GHz manquant du
dipôle, où l'on connaît la réponse.

## 4.3 P2 — l'estimation de coût est fausse d'un facteur 19 à 106

L'audit note que l'estimation est « un plancher » dont l'optimisme est aggravé,
et compare 57 603 cellules annoncées à 996 996 construites. Le chiffre qui
compte pour planifier une campagne n'est pas le nombre de cellules mais les
minutes affichées, et le facteur y est bien plus grand parce que les deux
erreurs se multiplient : `estime_cout` sous-estime les cellules **et** le
nombre de pas, puisqu'il calcule le pas de temps sur la maille d'air de
4,997 mm alors que la grille réelle descend à 0,797 mm.

En reprenant les grilles et les pas de temps de l'audit lui-même :

| Scène                                | Annoncé  | Réel, durée 1/$\Delta f$ | Réel, durée enregistrée |
|:-------------------------------------|---------:|-------------------------:|------------------------:|
| Vivaldi seule                        | 0,14 min | 14,4 min ($\times$ 106)  | 2,6 min ($\times$ 19)   |
| Plaque à 70 cm, domaine commun       | 3,04 min | 103,8 min ($\times$ 34)  | 18,6 min ($\times$ 6)   |

L'estimation n'est donc pas optimiste, elle est hors d'usage : elle annonce
une dizaine de minutes pour une série qui en demande plusieurs heures. Comme
`run.py --cout` existe précisément pour décider d'engager un calcul, c'est une
correction à faire tôt et facile : passer à `estime_cout` le demi-encombrement
réel rendu par `pose()` et le pas de temps réel rendu par `verifie_maillage`,
au lieu de deux valeurs par défaut.

## 4.4 P3 — le projet contient déjà la réfutation de sa borne de 24 cm

`antennes/uwb_surveyor/fiche.md:43` affirme que « la géométrie seule ne peut pas
produire plus de 24 cm ». L'audit juge cette borne non établie, et il a raison,
mais l'argument décisif est déjà écrit dans le dépôt, trois dossiers plus loin.
`antennes/dipole_reference/fiche.md:41-46` explique qu'« un dipôle résonne, donc
il stocke de l'énergie, donc il retarde sa réponse de l'ordre de $Q/(\pi f)$ »,
et la simulation mesure effectivement **+4,00 cm de décalage moyen pour un
dipôle nu de quelques centimètres**, dont le retard géométrique est nul par
construction. Le même raisonnement appliqué à une carte de 120 mm portant des
structures résonantes interdit de plafonner son retard à deux traversées de
carte.

Le dépôt se contredit donc lui-même sur un point qui porte toute
l'interprétation des 20 cm. Il n'y a pas d'étude à faire pour le trancher : il
suffit de retirer la borne et de renvoyer à la fiche du dipôle.

# 5. Ce que l'audit laisse ouvert et que l'on peut mesurer

C'est le cœur de cette réponse. L'audit écrit, à propos de son défaut P1 :
« L'ampleur de cette contamination reste à mesurer ; son mécanisme et l'absence
de protection dans la commande recommandée sont établis. » Et, à propos des
durées d'enregistrement : « Ces durées ne constituent donc pas, isolément, une
preuve d'erreur. »

Les deux questions sont décidables avec les données déjà présentes, sans
relancer openEMS, parce que les sondes temporelles brutes de port sont
conservées.

## 5.1 Les enregistrements sont bel et bien éteints

J'ai relu `port_ut_1` et `port_it_1` des trois simulations d'antenne seule.

| Antenne seule       | $\lvert u\rvert$ crête | Dernier échantillon | RMS du dernier 10 % | Énergie du dernier 10 % |
|:--------------------|-----------------------:|--------------------:|--------------------:|------------------------:|
| Petit losange       | $3{,}51\times10^{-3}$  | $-59{,}3$ dB        | $-56{,}8$ dB        | 0,0007 %                |
| Grand losange       | $4{,}83\times10^{-3}$  | $-58{,}5$ dB        | $-51{,}1$ dB        | 0,0018 %                |
| Vivaldi             | $8{,}89\times10^{-3}$  | $-58{,}4$ dB        | $-57{,}4$ dB        | 0,0010 %                |

Les enregistrements couvrent 7,8 %, 6,9 % et 17,9 % de $1/\Delta f$. **Et c'est
sans conséquence** : la tension de port est retombée à 58 dB sous sa crête, et
le dernier dixième de chaque enregistrement ne porte qu'un millième de pour cent
de l'énergie. L'audit a donc raison contre le dépôt : le commentaire de
`fdtd.py:92-96`, qui présente toute troncature avant $1/\Delta f$ comme fatale,
est trop absolu, et le critère d'énergie à $-40$ dB a fait son travail. Ce point
peut être retiré de la liste des inquiétudes.

## 5.2 Mais le S11 reste sensible à la fenêtre, et voici de combien

J'ai refait le S11 depuis les sondes avec ma propre recette, puis raccourci la
fenêtre temporelle. Précaution d'honnêteté : ma reconstruction reproduit le
`.s1p` du dépôt à $1{,}6 \times 10^{-2}$ près et non à $6{,}5 \times 10^{-11}$
comme celle de l'audit, qui a employé le vrai `CalcPort` — il me manque la
correction de demi-pas entre tension et courant. Les écarts ci-dessous sont
donc des **différences à recette constante**, valides en relatif, et le plancher
absolu de ma recette est de l'ordre de $1{,}6 \times 10^{-2}$.

Vivaldi, référence = enregistrement complet de 7,16 ns :

| Fenêtre | Durée   | $\max\lvert\Delta S_{11}\rvert$ | $\max\Delta\lvert S_{11}\rvert$ | $\max\Delta$ phase |
|--------:|--------:|--------------------------------:|--------------------------------:|-------------------:|
| 95 %    | 6,80 ns | $9{,}6\times10^{-3}$            | 0,55 dB                         | 2,7°               |
| 90 %    | 6,44 ns | $1{,}4\times10^{-2}$            | 1,08 dB                         | 5,8°               |
| 80 %    | 5,72 ns | $4{,}9\times10^{-2}$            | 1,73 dB                         | 12,6°              |
| 70 %    | 5,00 ns | $1{,}0\times10^{-1}$            | 3,45 dB                         | 21,0°              |
| 50 %    | 3,57 ns | $4{,}6\times10^{-1}$            | 32,83 dB                        | 175,3°             |

Les deux losanges se comportent de la même façon, en plus raide : à 70 % de
fenêtre, le grand losange bouge déjà de $1{,}6\times 10^{-1}$ et de 151° de
phase.

Lecture : **deux simulations de la même antenne arrêtées à 10 % d'intervalle
rendent des S11 qui diffèrent jusqu'à $1{,}4 \times 10^{-2}$, soit $-37$ dB.**
Or `run.py --mode fdtd` laisse précisément les deux calculs s'arrêter
indépendamment, chacun sur son propre critère d'énergie, sur des grilles et des
domaines différents. Le terme de troncature est donc bien présent dans la
différence $R = S_{11}^{\text{plaque}} - S_{11}^{\text{fond}}$.

## 5.3 L'ordre de grandeur : réel, mais insuffisant pour expliquer les 20 cm

Reste à comparer ce $-37$ dB à l'écho que l'on cherche. Une plaque métallique
grande devant la zone de Fresnel agit en miroir : l'antenne voit son image à
$2x$. Le couplage vaut alors $|S_{11}^{\text{écho}}| \simeq G\lambda/(4\pi\,2x)$.

| Gain | 1 GHz, 50 cm | 3 GHz, 50 cm | 6 GHz, 50 cm |
|:-----|-------------:|-------------:|-------------:|
| 3 dBi | $-26$ dB | $-36$ dB | $-42$ dB |
| 7 dBi | $-18$ dB | $-28$ dB | $-34$ dB |

Conclusion, et c'est la réponse à la question que l'audit laisse ouverte :

- **le terme de troncature seul se situe entre 3 et 20 dB sous l'écho de
  plaque.** Il est donc capable de perturber l'amplitude de l'écho de quelques
  pour cent à quelques dizaines de pour cent, surtout en haut de bande, où se
  fait justement la résolution en distance ;
- **il ne peut pas produire 20 cm de décalage.** Un terme 3 à 20 dB sous le pic
  déplace le maximum d'un profil de l'ordre de quelques millimètres à un
  centimètre, pas de 20 cm. Le P1 de l'audit est un défaut d'hygiène numérique
  réel, à corriger avant toute comparaison quantitative — il n'est pas
  l'explication de l'anomalie du banc, et il ne faut pas que la reprise le
  croie ;
- **le terme que je ne peux pas borner est l'autre.** Dans la commande
  publique, le fond est calculé dans un domaine d'environ 350 mm de côté, donc
  avec la PML à 115 mm de l'antenne, soit $\lambda/2{,}6$ à 1 GHz ; les scènes
  avec plaque placent la PML à 415 mm. Ce n'est pas une nuance de maillage,
  c'est un changement de l'environnement rayonnant de l'antenne, et il porte
  sur le terme que l'on soustrait. Il demande les deux calculs pour être chiffré,
  et c'est la première chose que la reprise devrait mesurer.

# 6. Un désaccord de priorité

L'audit classe **P2** le fait que la grille commune ne place exactement que la
plaque la plus éloignée, avec 0,346 et 0,415 mm d'écart aux lignes de grille
pour les plaques à 50 et 60 cm. Le constat est exact, j'ai retrouvé les deux
chiffres. Mais la grandeur ne justifie pas ce rang :

- 0,35 mm, c'est **cinq fois moins que le pas de l'axe des distances** du
  traitement (1,864 mm) ;
- c'est **85 fois moins que la résolution physique** $c/2B$ (3,0 cm) ;
- c'est **570 fois moins que l'anomalie étudiée** (20 cm).

Un biais qui ne peut pas déplacer un pic d'un seul échantillon d'axe n'est pas
du même ordre que les autres P2 de la liste, dont certains faussent le résultat
d'un facteur. Je le classe **P3** : à documenter, pas à corriger avant de
calculer.

Symétriquement, deux points méritent de monter. Le maillage dans le substrat,
à 5 cellules par longueur d'onde, est classé P1 par l'audit et je suis d'accord ;
mais il faudrait y ajouter que le même défaut a probablement déjà laissé une
trace mesurable, le GHz manquant du dipôle (§4.2). Et l'échange des étiquettes
de pics (§4.1) est à mes yeux le P1 le plus urgent de toute la liste, parce que
tous les critères de convergence que l'audit propose — « contrôler S11 complexe,
phase et résidu fond/cible », « vérifier la continuité avec la distance » — se
lisent à travers ce tableau.

# 7. Ordre de reprise : d'accord, à deux changements près

Les six étapes proposées par l'audit sont les bonnes, et dans le bon ordre. Je
propose deux modifications.

1. **Insérer la réparation de la détection de pics avant l'étape 3.** Établir la
   convergence numérique en lisant les colonnes « pic proche » et « pic
   lointain » revient à calibrer un instrument avec une aiguille qui change
   d'échelle. C'est une demi-journée de travail et cela conditionne tout le
   reste.
2. **Sortir la preuve visuelle des Gerbers de l'étape 4 et la faire maintenant.**
   L'audit la place avec la qualification du dossier de fabrication, ce qui est
   logique, mais le correctif est d'un mot clé (§3.1) et il donne immédiatement
   la seule image produite par un tiers. Il n'y a aucune raison d'attendre.

J'ajoute, dans l'étape 1 de préservation, un élément que l'audit ne mentionne pas
et que ma propre vérification rend précieux : **les sondes `port_ut_1` et
`port_it_1` sont la donnée la plus réutilisable du dépôt**. Elles permettent de
refaire le S11, de l'étudier en troncature, de changer de recette d'extraction —
tout cela sans relancer un solveur. Elles tombent sous le `**/resultats/`
de `.gitignore`. Elles devraient être archivées en premier.

# 8. Ce que je n'ai pas vérifié

Par honnêteté sur la portée de ce document :

- les quatre liens externes de l'audit — pages PCBWay, documentation openEMS,
  exemple MathWorks, DOI Singhal — n'ont fait l'objet d'aucun contrôle de ma
  part. L'option `Solder mask: None`, la règle `Panel by customer` et la bande
  publiée 2,5–13,5 GHz sont reprises de l'audit sans vérification ;
- je n'ai pas recalculé son inventaire SHA-256, ni vérifié sa déclaration
  d'intégrité des 266 fichiers ;
- je n'ai lancé **aucune** simulation FDTD. Comme l'audit, je n'établis donc
  aucune convergence électromagnétique. Mes mesures du §5 portent sur la
  sensibilité à la fenêtre temporelle de calculs déjà faits, ce qui est un
  sous-ensemble strict d'une étude de convergence ;
- je n'ai pas ouvert `report_john.pdf` ni confronté les figures aux formules ;
  je reprends de l'audit la correspondance entre `traitement.py` et les pages 2
  et 4 du rapport ;
- je n'ai pas contrôlé les règles de gravure, les distances cuivre/cuivre, ni
  rien qui relève d'un vrai DRC. Mes mesures de marges portent sur les contours
  Python, non sur les Gerbers.

# 9. Verdict

Je souscris à la décision finale de l'audit : **reprise du projet possible avec
les éléments présents, validation quantitative du banc et feu vert aux commandes
PCBWay encore conditionnels.** Avec trois amendements.

**Premier amendement.** L'audit est plus fiable que son propre ton prudent ne
le laisse croire. Quarante affirmations rejouées, quarante observations justes,
trente-deux au chiffre près : on peut travailler à partir de ce document sans
le re-vérifier. Les deux erreurs d'interprétation que je relève (§3.1 et §3.2)
ne portent sur aucune de ses conclusions.

**Deuxième amendement.** La contamination de la différence fond/cible par le
critère d'arrêt est mesurée, pas seulement établie : elle vaut $-37$ dB pour
10 % d'écart de fenêtre, soit 3 à 20 dB sous l'écho cherché. Elle justifie
pleinement le P1, et elle disqualifie l'idée qu'elle puisse expliquer les
20 cm. L'explication du décalage est encore entièrement à trouver, et la piste
la plus crédible reste celle que le dépôt documente lui-même : un retard
d'antenne qui n'est pas borné par la géométrie, et un lieu de rayonnement qui
se déplace avec la fréquence. Les 18,0 cm que l'audit calcule pour la Vivaldi
entre son trajet interne et son trajet aérien sont, à cet égard, le chiffre le
plus intéressant des quatorze pages.

**Troisième amendement.** Le défaut le plus coûteux du dépôt n'est dans aucune
des deux listes. Ce sont les colonnes « pic proche » et « pic lointain », qui
peuvent échanger leurs rôles sans rien dire et fabriquer 7 cm de dérive
artificielle dans la grandeur même que le projet cherche à expliquer. Tant
qu'elles ne sont pas réparées, chaque tableau produit par ce projet — y compris
ceux du rapport pour John, y compris celui du dipôle « validé » — doit être
relu en se demandant laquelle des deux colonnes porte le pic physique.
