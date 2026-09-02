# Guide d'utilisation — Radar cartilage (LiteVNA)

Radar UWB (type *ground-penetrating radar*) qui mesure l'**épaisseur d'une couche**
(gélatine, cartilage…) posée devant une antenne, en séparant l'écho de la **surface**
et l'écho du **fond**, puis en corrigeant par la permittivité du matériau.
---

## Vue d'ensemble — les programmes et leur ordre

| Programme | Ce qu'il fait | Quand |
|---|---|---|
| `calibration_sol.py` | calibration SOL du VNA (§3) | **1× par session**, et après tout changement de câble |
| `qualif_centre_phase.py` | mesure la fonction de transfert de l'antenne sur plaque métallique | 1× par antenne |
| `qualif_ringing.py` | mesure la traînée (*ringing*) de l'antenne | 1× par antenne |
| `radar_cartilage_online.py` | affichage temps réel : viser, tare, détection à deux pics | pour régler et diagnostiquer |
| `mesure_epaisseur.py` | **la mesure** : distance *et* épaisseur, les deux méthodes, graphe | pour chaque cible |

### L'ordre à respecter

```
1.  python calibration_sol.py --nom sol_courante      # étalons S / O / L
2.  python calibration_sol.py --verifier              # plancher réel
3.  python mesure_epaisseur.py --mesure --nom fond --sans-graphe
                                                     # RIEN devant l'antenne
4.  python radar_cartilage_online.py                 # plaque métal, étapes 3-4
                                                     # -> cale DISTANCE_ANTENNE_MM
5.  python mesure_epaisseur.py --mesure --nom pmma12 --fond fond         --eps 2.6 --substrat air --max-ep 20         # la mesure
```

Les étapes 1 et 3 sont les deux soustractions indispensables, et elles retirent
**des choses différentes** :

| | Ce qui est retiré | Sans elle |
|---|---|---|
| **Calibration SOL** (1) | directivité du pont, désadaptation source, réponse du câble | amplitudes fausses, plancher élevé |
| **Fond** `--fond` (3) | la réflexion **propre de l'antenne**, additive et absente du modèle | épaisseur fausse de ~0,4 mm, distance absurde, résidu > 0,4 |

> Un résidu de soustraction de 3 % ne coûte plus que **0,02 mm** — c'est pourquoi la
> stabilité mécanique du montage compte plus que la perfection de la tare.

---

## 1. Le vocabulaire (les mots qui piègent)

| Mot | Ce que ça veut dire ici |
|---|---|
| **Tare** | Mémoriser le signal « à vide » (antenne seule) pour le **soustraire** ensuite. Ce n'est **pas** une calibration VNA. |
| **Calibration VNA (SOL)** | La vraie calibration avec étalons Short/Open/Load. Elle se fait avec `calibration_sol.py` (§3) — **pas** dans le menu du LiteVNA, dont l'USB renvoie toujours des données brutes. |
| **Standoff** | L'espace d'air **devant** l'antenne, où tu poses la cible. « Standoff vide » = rien devant. |
| **Fond** | Tout ce qui est fixe (réflexion de l'antenne, câble, décor). La tare le retire. |
| **TGC** (Time-Gain Compensation) | Amplification qui **monte avec la distance**, pour compenser l'atténuation des échos lointains. |
| **Zone aveugle** | Les premiers mm devant l'antenne, ignorés (le résidu de couplage y vit). Réglage `DISTANCE_MIN_MM`. |
| **Plan de l'antenne** | L'origine des distances. La calibration SOL ramène le plan au **bout du câble** ; le prolonger jusqu'au plan rayonnant se fait avec une plaque métallique, ou « à la main » avec `DISTANCE_ANTENNE_MM`. |
| **Permittivité (εr)** | Propriété du matériau qui ralentit l'onde. Sert à convertir la distance apparente en épaisseur réelle. |

---

## 2. L'interface

### Boutons (à gauche)
- **Tare (fond vide)** — mémorise le fond. À presser **rien devant l'antenne**.
- **Effacer la tare** — annule la tare (revient au signal brut).
- **Exporter CSV** — enregistre le profil affiché dans un fichier `.csv`.
- **CAPTURER** (doré) — mode procédure guidée : enregistre image + données + état, et avance d'une étape (voir §7).

### Boutons radio (petits ronds, boîte jaune) — le mode d'affichage
- **Brut** — signal cru, avec la réflexion de l'antenne. Pas de soustraction.
- **Fond retiré** — signal **moins la tare**. Amplitudes vraies. *C'est le mode le plus lisible pour régler.*
- **Fond retiré + Gain** — pareil, plus le TGC (amplifie le lointain). Mode « mesure » normal.

### Curseurs (en bas)
- **Pente Gain (TGC)** — force de l'amplification avec la distance (n'agit qu'en mode « + Gain »).
- **Permittivité Gel. (εr)** — **à régler sur ton matériau** (voir tableau §5). Par défaut 45 (gélatine).

### Le graphe
- **Axe X** = distance **depuis l'antenne** (mm), après recalage `DISTANCE_ANTENNE_MM`.
- **Courbe bleue** = profil radar (amplitude des échos vs distance).
- **Points rouges** = les deux échos suivis (surface + fond), une fois accrochés.
- **Cadre rouge** = épaisseur calculée, ou « En attente de cible ».

### La console (fenêtre texte)
- `[freq]` (1×) — le sweep réel : bande passante et mm/échantillon. Vérifie l'échelle.
- `[timing]` — vitesse : temps d'acquisition / calcul / affichage et fps.
- `[detect]` — état de détection : `cible`, `max/med` (rapport signal/bruit), `npics`, `pistes`, `pic_fort@`.

---

## 3. Calibration SOL — `calibration_sol.py`

### 3.1 Pourquoi le menu du LiteVNA ne suffit pas

Le LiteVNA possède bien un menu **CAL**, qui fait bien une calibration SOL et réclame
bien les mêmes étalons physiques. Mais **son interface USB renvoie toujours des données
brutes, par conception** : la calibration faite sur l'appareil ne corrige que son propre
écran. Tout ce que lit `get_s11_s21()` est non corrigé, quelle que soit la calibration
présente dans l'instrument.

Garde quand même la calibration embarquée : elle rend l'écran exploitable pour viser et
diagnostiquer. Mais la correction utile au logiciel se fait ici.

**Ce que la calibration retire :**

| Terme | Ce que c'est | Effet visible sans elle |
|---|---|---|
| **Directivité** `e00` | Signal qui fuit du pont vers le récepteur sans atteindre l'antenne | Faux écho à distance nulle, plancher de mesure |
| **Désadaptation source** `e11` | Allers-retours entre le VNA et une antenne mal adaptée | Échos fantômes périodiques |
| **Suivi en réflexion** `e10e01` | Réponse en amplitude et phase du câble et du pont | Amplitudes fausses, pente de phase parasite |

### 3.2 Le montage — la partie qui décide de tout

- Visse les étalons **au bout du câble**, là où ira l'antenne. Tout ce qui est en amont
  (câble, connecteurs, pont) est alors corrigé.
- **Ne déplace pas le câble** entre les trois mesures : sa flexion change sa phase et
  ruine la calibration.
- Serre les SMA **fermement mais sans forcer**, et de la même façon pour les trois.
- Ne débranche rien d'autre entre les trois mesures.

### 3.3 Les quatre modes

| Mode | Commande | Quand |
|---|---|---|
| **Acquisition** | `python calibration_sol.py --nom banc` | Au début de chaque session, ou après tout changement de câble |
| **Vérification** | `python calibration_sol.py --verifier --nom banc` | Juste après, pour connaître le plancher réel |
| **Rejeu** | `python calibration_sol.py --rejouer --nom banc --short-l0 0.1e-9` | Plus tard, pour recalculer avec de meilleurs modèles d'étalons — sans rien remesurer |
| **Application** | *automatique* | `radar_cartilage_online.py` charge `calibration/sol_courante.npz` au démarrage et l'applique à chaque balayage |

Le nom par défaut est `sol_courante`, c'est celui que le programme principal cherche.
Utilise `--nom banc` pour une calibration d'essai, `--nom sol_courante` pour celle qui
sert.

### 3.4 Déroulement d'une acquisition

Le script demande successivement le **court-circuit**, l'**ouvert** puis la **charge**.
Pour chacun :

1. Visse l'étalon, appuie sur Entrée.
2. Le script jette 2 balayages (stabilisation) puis en moyenne 16 **vectoriellement** —
   ce qui abaisse le plancher de bruit de 12 dB.
3. Il affiche le `|S11|` médian mesuré et **contrôle sa plausibilité** :
   - un court-circuit ou un ouvert doit renvoyer presque tout (~0 dB) ; sous −3 dB, le
     script signale un connecteur probablement mal vissé ;
   - une charge doit absorber ; au-dessus de −15 dB, il signale une charge suspecte.

Puis il résout le système à trois inconnues par fréquence, affiche les termes d'erreur
et sauvegarde dans `calibration/<nom>.npz`.

Options utiles : `--start` / `--stop` / `--points` (par défaut 1,4–6,3 GHz, 101 points —
**les mêmes que le programme principal**) et `--moy` (nombre de moyennes).

### 3.5 Lire le résultat

```
  TERMES D'ERREUR
  directivite                -31.4 dB  (min  -38.2 / max  -24.1)
  desadaptation source       -14.8 dB
  suivi en reflexion          -1.9 dB
  conditionnement du systeme  median 3.2, max 4.1
```

- **Directivité** : c'est le niveau du faux écho qui polluait les mesures. Il est
  maintenant soustrait.
- **Conditionnement** au-dessus de 50 → les étalons ne sont pas assez distincts à
  certaines fréquences. Vérifie les connexions et recommence.

Le mode `--verifier` demande de revisser la **charge** et mesure ce qui reste après
correction : c'est le **plancher réel** du système.

| Verdict | Signification |
|---|---|
| **BON** (< −35 dB) | Marge confortable sous l'écho de fond de couche (~−17 dB) |
| **ACCEPTABLE** (< −25 dB) | Utilisable, mais la charge du kit limite le plancher |
| **INSUFFISANT** | Reprends le serrage des connecteurs et refais la calibration |

### 3.6 Faut-il un kit d'étalons caractérisé ?

Simulation de la chaîne complète, biais résultant sur une couche de 1 à 5 mm :

| Défaut du kit ignoré | Biais | |
|---|---|---|
| Ouvert, 20 à 100 fF | 0,01 à 0,04 mm | négligeable |
| Offsets de 5 ps | 0,03 mm | négligeable |
| Court-circuit, 0,10 nH | 0,07 mm | acceptable |
| Court-circuit, 0,30 nH | 0,98 mm | **rédhibitoire** |
| Charge à −25 dB au lieu de −45 | 1,24 mm | **rédhibitoire** |

L'ordre est **charge ≫ court-circuit ≫ ouvert**, et non l'inverse comme on le suppose
souvent : tout ce qui est linéaire en fréquence (capacité de frange de l'ouvert,
offsets) est absorbé par le réglage du plan de référence ; seule la courbure subsiste.

> **La charge 50 Ω est la pièce critique du kit.** C'est elle qui fixe le plancher, et
> c'est elle qu'il faut remplacer si `--verifier` donne un mauvais résultat.

Si le fabricant publie ses coefficients, entre-les avec `--open-c0`, `--short-l0`,
`--open-offset-ps`, etc. Sinon, laisse les valeurs par défaut (étalons idéaux) : le
tableau ci-dessus montre que c'est sans conséquence, sauf sur la charge.

### 3.7 Après la calibration

Le plan de référence est au **bout du câble**, pas au plan rayonnant de l'antenne. Pour
l'y amener, mesure une **plaque métallique à distance connue** (`qualif_centre_phase.py`),
qui donne directement la fonction de transfert de l'antenne.

---

## 4. Utilisation normale (mesurer une épaisseur)

0. **Calibre** si ce n'est pas déjà fait (§3) — sinon les amplitudes et le plancher sont faux.
1. **Lance** le programme, attends « Connexion réussie ! ». La ligne `[cal]` indique si une calibration a été chargée.
2. Mets un **espace d'air** (~3-4 cm) entre l'antenne et l'endroit où ira la cible.
3. **Rien devant l'antenne** → presse **Tare (fond vide)**. Le gros pic d'antenne disparaît.
4. Choisis le mode **Fond retiré** (ou **Fond retiré + Gain** si l'écho de fond est faible).
5. Règle le curseur **Permittivité** sur ton matériau (§5).
6. **Pose la cible** dans le standoff. Les **deux points rouges** doivent accrocher les deux interfaces.
7. Lis l'**épaisseur** dans le cadre rouge. **Exporter CSV** si besoin.

> Refais la **Tare** si tu déplaces l'antenne ou les câbles (dérive).

---

## 5. Permittivités utiles (à mettre sur le curseur)

| Matériau | εr (~) |
|---|---|
| Air | 1 |
| **PMMA / plexiglas** (objet de test recommandé, §6) | **2,6** |
| Bois sec, livre / papier | 2,5 |
| Verre | ~6 |
| Gélatine | ~40-45 |
| Eau | ~78 |

Erreur classique : oublier de régler ce curseur → épaisseur fausse d'un facteur `√(εr_réel / εr_curseur)`.

---

## 6. Objets de test — vérifier que le logiciel dit vrai

Pour valider la chaîne complète, il faut une cible dont on connaît **déjà** la réponse.
L'objet recommandé est une **plaque de PMMA posée sur du polystyrène expansé**.

> **PMMA** = polyméthacrylate de méthyle, le plastique transparent rigide vendu sous les
> noms **Plexiglas**, **Altuglas**, **Perspex** ou simplement « verre acrylique ». C'est
> la matière des vitrines de magasin et des écrans de protection. On le trouve en
> plaques dans toutes les enseignes de bricolage et chez les découpeurs en ligne.

### 6.1 Pourquoi celui-là

Une plaque libre dans l'air possède deux interfaces, air→plastique puis plastique→air,
de coefficients égaux au signe près. **Ses deux échos ont donc la même amplitude** —
le cas le plus facile qui existe pour une détection de pics.

| | Écho de surface | Écho de fond | Écart |
|---|---|---|---|
| **PMMA libre dans l'air** | −12,6 dB | −13,1 dB | **0,5 dB** |
| Cartilage sur os (la vraie cible) | −2,6 dB | −16,5 dB | 13,9 dB |

L'absorption est négligeable : 0,3 dB sur 30 mm.

### 6.2 Quelle épaisseur

La résolution vaut **52 mm dans l'air** (fenêtre de Hann comprise). L'axe des distances
est en aller simple : l'écart apparent entre les deux échos vaut donc
`√εr × épaisseur`, soit **1,61 × l'épaisseur** pour le PMMA.

| Épaisseur | Écart apparent | En résolutions | Erreur des deux pics (simulée) |
|---|---|---|---|
| **80 mm** | 129 mm | **2,5 ×** | **−0,1 %** — la seule où les deux méthodes s'accordent |
| 50 mm | 81 mm | 1,55 × | −2,6 % |
| 30 mm | 48 mm | 0,93 × | −4,8 % |
| 20 mm | 32 mm | 0,62 × | la détection échoue complètement |

> **La détection à deux pics n'est fiable qu'au-delà de 2,5 résolutions**, soit
> **80 mm de PMMA**. En deçà, l'élargissement par la fenêtre biaise l'écart de plusieurs
> pour cent, et sous une résolution elle retourne une valeur fausse mais plausible —
> ce qui est plus dangereux qu'un échec franc.
>
> **L'inversion sur modèle, elle, est exacte à toute épaisseur** (vérifié à 0,000 mm
> près par `mesure_epaisseur.py --autotest`). C'est donc elle qui valide le logiciel ;
> le recoupement par les deux pics est un bonus qui exige une plaque épaisse.

### 6.3 Équivalence avec le cartilage

L'épaisseur électrique vaut `d × √εr`. Le rapport `√40 / √2,6 = 3,92` donne :

| Cartilage | PMMA équivalent |
|---|---|
| 1 mm | **3,9 mm** |
| 3 mm | **11,8 mm** |
| 5 mm | **19,6 mm** |

Une plaque de 12 mm place le logiciel exactement dans le régime d'un cartilage de 3 mm,
avec une épaisseur connue au centième de millimètre.

**À acheter : 4, 12 et 20 mm** — ce sont les trois qui comptent, et elles sont peu
chères. Ajoute un bloc de **80 mm** si tu veux pouvoir recouper les deux méthodes ;
c'est confortable mais optionnel, et nettement plus coûteux.

Un jeu **2 / 4 / 12 mm** couvre déjà l'essentiel, et de façon bien répartie :

| Plaque | Écart apparent | / résolution | ≡ cartilage de | Précision sur l'épaisseur (30 dB) |
|---|---|---|---|---|
| 2 mm | 3,2 mm | 0,06 × | 0,51 mm | ±0,218 mm — le cas extrême |
| 4 mm | 6,4 mm | 0,12 × | 1,02 mm | ±0,069 mm |
| **12 mm** | 19,3 mm | 0,37 × | **3,06 mm** | **±0,012 mm** |

Les trois sont **très en dessous de la résolution** : la détection à deux pics échoue sur
toutes. C'est voulu — c'est précisément le régime où seule l'inversion travaille, donc
celui qu'il faut tester. Trois épaisseurs dans un rapport 6:1 permettent en outre de
vérifier la **linéarité** de l'estimateur, ce qu'un point unique ne peut pas révéler.

### 6.4 Lancer les deux méthodes

Le programme temps réel `radar_cartilage_online.py` ne fait que la détection à deux
pics. Pour appliquer **les deux méthodes au même balayage**, utilise
`mesure_epaisseur.py` :

```
python mesure_epaisseur.py --autotest                       # sans instrument
python mesure_epaisseur.py --mesure --nom pmma12 \
       --eps 2.6 --substrat air --max-ep 20                 # plaque de PMMA
python mesure_epaisseur.py --mesure --eps 42.5 --substrat os # cartilage
python mesure_epaisseur.py --fichier mesures/pmma12.npz \
       --eps 2.6 --substrat air --max-ep 20                 # ré-analyse
```

Il applique la calibration SOL, soustrait le fond, exécute les deux méthodes, **donne
la distance à la première surface en plus de l'épaisseur** — les deux sortent du même
ajustement, la distance n'étant jamais fournie au programme — puis affiche les deux
résultats et leur écart — en signalant si la comparaison a un sens (écart des échos supérieur à
2,5 résolutions) ou non. Le balayage brut est conservé dans `mesures/`, ce qui permet
de le ré-analyser plus tard avec de meilleurs paramètres.

Commence par `--autotest` : il valide la chaîne de calcul sur des données synthétiques,
sans brancher quoi que ce soit.

| Option | Rôle |
|---|---|
| `--eps` | permittivité de la couche (2,6 pour le PMMA, 42,5 pour le cartilage) |
| `--substrat` | ce qu'il y a **derrière** : `air`, `os`, `os_spongieux`, `metal`, `eau` |
| `--max-ep` | épaisseur maximale explorée (mm) — mets-la un peu au-dessus de l'attendu |
| `--moy` | nombre de balayages moyennés (16 par défaut) |
| `--fond` | balayage « scène vide » à soustraire — **indispensable en mesure réelle** |
| `--epaisseur` | épaisseur connue : inverse le problème et mesure εr (§6.5) |
| `--plan-antenne` | position du pic d'antenne (702 mm) ; n'affecte pas l'épaisseur |

### 6.5 Le test qui vaut tous les autres : mesurer εr

Tu connais l'épaisseur au pied à coulisse, et εr du PMMA par la littérature (**2,6**).
On peut donc **inverser le problème** : imposer l'épaisseur et laisser le logiciel
chercher εr. Le résultat se compare alors à une valeur tabulée — vérification en boucle
fermée, sans aucune référence externe.

```
python mesure_epaisseur.py --mesure --nom pmma12 --epaisseur 12.0 --substrat air
```

Il doit rendre **εr ≈ 2,6**. Précision théorique, plaque libre dans l'air :

| Plaque | εr à 20 dB | à 30 dB | à 40 dB |
|---|---|---|---|
| 2 mm | ±0,94 | ±0,30 (11 %) | ±0,094 |
| 4 mm | ±0,16 | ±0,050 (1,9 %) | ±0,016 |
| **12 mm** | ±0,017 | **±0,0055 (0,21 %)** | ±0,0017 |

Une plaque de 12 mm détermine εr à **0,2 %** — mieux qu'aucune table publiée. C'est
exactement la procédure qu'il faudra appliquer au cartilage, où connaître εr à 4 % près
décide de toute la précision.

| Symptôme | Diagnostic |
|---|---|
| εr trouvé ≈ 2,6 | la chaîne complète est validée |
| εr trop grand d'un facteur k² | l'échelle des distances est fausse d'un facteur k |
| Résidu élevé (> 0,2) | le modèle ne décrit pas la mesure : quelque chose derrière la plaque, ou calibration absente |

### 6.6 Détails pratiques qui font rater l'essai

- **Rien derrière la plaque.** Ni table, ni serre-joint, ni mur à moins de 2 m dans
  l'axe. Pose-la sur un **bloc de polystyrène expansé** : εr ≈ 1,03, il est invisible
  aux micro-ondes.
- **Plaque d'au moins 300 × 300 mm.** À 100 mm de standoff le faisceau éclaire déjà
  200 mm ; il faut déborder, sinon les bords diffractent et créent de faux échos.
- **N'empile jamais deux plaques** pour obtenir une épaisseur : le film d'air crée deux
  interfaces parasites.
- **Demande du PMMA _coulé_ (« cast »)**, pas extrudé : l'extrudé a une tolérance
  d'épaisseur de ±5 %, ce qui ruine la comparaison. Dans tous les cas, mesure au pied à
  coulisse en cinq points et retiens la valeur réelle.

### 6.7 Progression des essais

| | Objet | Ce qu'il valide |
|---|---|---|
| 1 | Plaque métallique | Γ = −1 exactement : échelle des distances, plan de référence, phase (`qualif_centre_phase.py`) |
| 2 | PMMA 80 mm *(optionnel)* | les deux méthodes doivent concorder à 2 % |
| 3 | PMMA 20 mm | la détection de pics décroche ; le modèle doit tenir |
| 4 | PMMA 12 mm | équivalent d'un cartilage de 3 mm |
| 5 | PMMA 4 mm | équivalent d'un cartilage de 1 mm |
| 6 | Gel de gélatine sur plaque de verre | εr ≈ 40 sur ≈ 7 : la géométrie cartilage/os |

---

## 7. Procédure guidée (pour analyse à distance)

Un **bandeau jaune** en haut affiche une instruction. Tu fais l'action, tu presses **CAPTURER** :
ça enregistre une **image**, le **profil CSV** et une ligne d'**état** dans le dossier
`captures/`, puis passe à l'étape suivante. À la fin, on analyse ensemble le dossier.

La séquence est éditable dans la liste `PROTOCOLE` en haut du fichier.

### 7.1 La séquence actuelle

| | Action | Ce qu'elle produit |
|---|---|---|
| **0** | *Hors de ce programme* : `calibration_sol.py` puis `--verifier` | sans elle, tout le reste est sur données brutes |
| 1 | Mode « Fond retiré », **rien** devant l'antenne | référence : le niveau de la réflexion d'antenne |
| 2 | « Tare (fond vide) », attendre 1 s | vérifie que la scène devient vide (`max/med` doit tomber sous 4) |
| 3 | Plaque métal à **100 mm** du plan de l'antenne | première mesure du plan de référence |
| 4 | Reculer la plaque **jusqu'à 200 mm** (soit +100 mm) | seconde mesure : donne la **pente** et l'**offset** |
| 5 | PMMA sur polystyrène à 150 mm, εr = 2,6 | première épaisseur sur objet connu (§6) |

### 7.2 Comment exploiter les étapes 3 et 4

Ce sont elles qui calent `DISTANCE_ANTENNE_MM`. Relève la position du pic dans chaque
capture, puis :

- **la pente** `(pic₄ − pic₃) / 100 mm` doit valoir **1,00**. Elle vérifie l'échelle des
  distances ;
- **l'offset** `pic − distance réelle` doit être **le même** aux deux positions. Ajoute-le
  à `DISTANCE_ANTENNE_MM`.

Un offset qui change entre les deux positions signale une erreur d'échelle, pas de plan de
référence — ou, plus probablement, que les deux distances n'ont pas été celles que tu crois.

> **Attention à la formulation de l'étape 4.** L'ancienne version disait « recule la plaque
> à 100 mm », que l'on peut lire « recule-la **de** 100 mm ». Une campagne entière s'est
> ainsi retrouvée avec une pente apparente de 2,05 au lieu de 1,00. Les positions sont
> maintenant données en **absolu**, avec le déplacement rappelé entre parenthèses.

---

## 8. Réglages (constantes en haut du fichier)

| Constante | Rôle |
|---|---|
| `FREQ_START_GHZ` / `FREQ_STOP_GHZ` | Bande de balayage (fixe la résolution ≈ 30 mm). |
| `FREQ_NPOINTS` | Nombre de points. **Moins = plus rapide**, sans changer la résolution. |
| `DISTANCE_ANTENNE_MM` | Recale l'origine sur l'antenne (= position du pic fixe d'antenne). |
| `DISTANCE_MIN_MM` / `DISTANCE_MAX_MM` | Fenêtre de détection (zone aveugle → portée max). |
| `FACTEUR_BRUIT` | Sensibilité « présence de cible » (max/médiane). ↓ = plus sensible. |
| `PROMINENCE_BRUIT` | Seuil de détection d'un pic (× le bruit). ↓ = détecte des échos plus faibles. |
| `ALPHA_EMA` / `GATE_MM` / `MAX_FRAMES_PERDUES` | Lissage / rejet / mémoire du suivi des deux pics. |
| `SERIAL_BAUD` | `921600` pour tenter d'accélérer l'acquisition (série). |

---

## 9. Dépannage

| Symptôme | Cause probable → action |
|---|---|
| **Rien détecté** (`cible=non`, `max/med`≈2) | Scène vide, ou cible hors fenêtre. Regarde `pic_fort@` : si loin de la fenêtre, ajuste `DISTANCE_ANTENNE_MM` / `DISTANCE_MAX_MM`. |
| **Un seul pic** (`npics=1`) | Écho de fond trop faible → baisse `PROMINENCE_BRUIT` ; ou surface dans la zone aveugle → baisse `DISTANCE_MIN_MM`. |
| **Faux objet juste après la tare** | Résidu de couplage → augmente `DISTANCE_MIN_MM`. |
| **Distances aberrantes** | Vérifie la ligne `[freq]` (BW = 4,9 GHz ?) et recale `DISTANCE_ANTENNE_MM` avec une plaque métal à distance connue. |
| **Affichage lent** | Baisse `FREQ_NPOINTS` (101 → 51) et/ou tente `SERIAL_BAUD = 921600`. |
| **Épaisseur impossible < ~5-9 mm** | Limite physique de résolution (bande passante). Pas un bug. |
| `[cal] Aucune calibration` au démarrage | Normal si tu n'en as pas fait. Sinon, le fichier attendu est `calibration/sol_courante.npz` — vérifie le `--nom` utilisé (§3.3). |
| `[cal] le balayage ne correspond pas` | La calibration a été faite sur une autre bande ou un autre nombre de points. Les termes sont interpolés ; refais-la avec les mêmes `--start/--stop/--points` que le programme. |
| **Verdict `--verifier` INSUFFISANT** | Reprends le serrage des connecteurs (§3.2). Si ça persiste, c'est la charge 50 Ω du kit (§3.6). |
| **Conditionnement > 50** | Deux étalons trop semblables à certaines fréquences → l'un d'eux est mal vissé. |

---

## 10. Limites à connaître

- **Résolution ≈ 30 mm dans l'air** (fixée par la bande passante), soit ~4,5-9 mm réels dans un gel à εr=45. Deux interfaces plus proches fusionnent. C'est une limite mathématique, pas un problème de bruit : la séparation de deux pics ne descendra pas en dessous.
- **La calibration SOL ne place le plan de référence qu'au bout du câble.** Les distances absolues ne deviennent physiques qu'après l'avoir prolongé jusqu'au plan rayonnant — plaque métallique (`qualif_centre_phase.py`) ou recalage manuel `DISTANCE_ANTENNE_MM`. L'**épaisseur** (différence de deux échos) reste juste malgré tout.
- **Antenne + câble** : une antenne mal adaptée ou un câble long créent du clutter fixe ; la calibration retire la part stable, la tare le reste, mais ni l'une ni l'autre ne fait de miracle sur ce qui dérive.
- **La calibration ne survit pas au déplacement du câble.** Toute flexion change sa phase. Si tu bouges le montage, refais-la.
