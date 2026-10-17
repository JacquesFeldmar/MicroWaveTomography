# Backlog — options écartées, et ce qui les ferait revenir

Chaque entrée dit **pourquoi** elle n'est pas retenue aujourd'hui et **ce qui
devrait arriver** pour qu'on y revienne. Une option sans condition de retour
n'est pas un choix différé, c'est un regret.

## 1. Vivaldi à 2 GHz, carte de 80 × 200 mm

**Décidé le 17/10/2026 : on part sur 1,4 GHz**, carte de 112 × 291 mm, pour
couvrir toute la bande du LiteVNA.

| | |
|---|---|
| Ce qu'on y gagnerait | une carte deux fois plus petite, bien plus maniable sur une table XY ; une simulation de ~10 min au lieu de ~30 |
| Ce qu'on y perdrait | la bande 1,4–2 GHz, celle qui pénètre le mieux et où la méthode de Born est la plus sûre |
| **Ce qui la ferait revenir** | la carte de 291 mm s'avère ingérable sur le banc, ou le temps de simulation bloque les itérations de conception |

## 2. Substrat Rogers RO4350B

**Décidé le 17/10/2026 : FR4 1,6 mm**, comme les losanges.

| | |
|---|---|
| Caractéristiques | εr 3,66, tanδ 0,0037 contre 4,4 et 0,02 pour le FR4 |
| Ce qu'on y gagnerait | cinq fois moins de pertes diélectriques, et une permittivité bien plus stable en fréquence |
| Ce qu'on y perdrait | environ dix fois le prix du panneau |
| **Ce qui le ferait revenir** | deux cas, tous deux mesurables : les pertes du FR4 au-dessus de 4 GHz mangent le budget de liaison en transmission ; ou sa dispersion dépasse le budget de 0,65 mm sur l'axe des distances — rappel, une ligne de 50 mm sur FR4 en consomme déjà 1,4 mm |

## 3. Les quatre paramètres S

Le LiteVNA ne mesure que S11 et S21. La suppression d'artefacts d'Amineh
compare l'image reconstruite depuis S11 seul à celle depuis S22 seul.

| | |
|---|---|
| **Ce qui la ferait revenir** | la tomographie bute sur des artefacts en profondeur. Deux voies : un second balayage câbles inversés, ou un LibreVNA (~600 $, deux ports complets, 100 kHz–6 GHz) |

## 4. openEMS dans l'environnement `ph`

openEMS tourne dans un environnement `openems` dédié, en Python 3.13, parce
que les wheels Windows n'existent que pour 3.13 et 3.14.

| | |
|---|---|
| **Ce qui le ferait revenir** | une version publiée avec des wheels cp312, ou le besoin de piloter openEMS depuis les scripts de mesure, qui vivent dans `ph` |

## 5. Cornet TEM

C'est l'antenne de la littérature en tomographie — Amineh et Nikolova
l'emploient — et sa géométrie est entièrement connue.

| | |
|---|---|
| Pourquoi écarté | ce n'est pas un circuit imprimé : impossible à faire fabriquer chez PCBWay |
| **Ce qui le ferait revenir** | la Vivaldi se révèle trop dispersive pour que le champ incident soit exploitable, et on accepte un usinage mécanique |

## 6. Les 36,5 cm du 17 septembre

L'écart mesuré ce jour-là dépasse ce que la carte peut produire — au plus
24 cm, géométrie relevée sur photo à l'appui. Quelque chose d'autre était dans
le trajet, ou le traitement n'appliquait pas la calibration SOL.

| | |
|---|---|
| **Ce qui le ferait revenir** | les fichiers bruts de cette campagne. Le test est immédiat : traiter un même balayage avec et sans `sol.applique` et regarder si le pic se déplace de la longueur de câble divisée par 0,7 |

## 7. Rapatrier les fichiers de mesure

Les campagnes des 17 septembre et 9 octobre ont leurs dossiers et leurs
manifestes dans `antennes/uwb_surveyor/mesures/`, mais **pas leurs fichiers**.

| | |
|---|---|
| **Ce qui le ferait revenir** | retrouver les CSV et `.s1p` envoyés à John. `python run.py --mode mesures --donnees <dossier>` les traite alors exactement comme les simulations |

## 8. Commander les cartes sans vernis épargne

La simulation suppose du cuivre nu et du FR4 nu. Les Gerbers livrés ouvrent le
vernis sur **tout le cuivre**, mais il en reste dans les fentes.

| | |
|---|---|
| Ce qu'on y gagnerait | coller exactement à la simulation : vingt micromètres de diélectrique en moins dans les fentes rayonnantes |
| Ce qu'on y perdrait | « Solder Mask : None » n'est pas une option sûre du formulaire PCBWay — leur liste publique ne montre que des couleurs. Le risque, c'est une commande bloquée en vérification, donc une semaine. |
| Combien ça vaut | moins de 1 % sur la fréquence : 20 µm contre 1,6 mm de substrat, soit dix fois moins que la tolérance du FR4 sur sa permittivité |
| **Ce qui le ferait revenir** | une mesure qui s'écarte de la simulation de plus que la tolérance du FR4, et dont on aurait écarté toutes les autres causes. Ou simplement : PCBWay confirme l'option par courriel avant la prochaine commande. |

## 9. Vivaldi : dentelures et substrat trapézoïdal

Les deux remèdes classiques au défaut qui reste — l'ondulation du `|S11|`,
c'est-à-dire l'écho de la bouche et de la transition.

| | |
|---|---|
| Dentelures (*corrugations*) | des encoches le long des bords extérieurs des ailes, qui cassent le courant qui remonte sur la tranche. Profondeur utile ≈ λ/4 à la fréquence basse, soit 53 mm : nos ailes font 18 mm. Il faudrait donc une carte franchement plus large. |
| Substrat trapézoïdal | couper le FR4 en biais vers la bouche, pour que le diélectrique ne s'arrête pas net. Gratuit en fabrication — c'est un contour, pas une couche. |
| **Ce qui les ferait revenir** | le `\|S11\|` mesuré sur la carte fabriquée confirme la simulation, et la tomographie bute sur le budget de liaison. Le substrat trapézoïdal est le premier à essayer : il ne coûte qu'une simulation et aucune surface. |

## 10. Les manifestes de campagne, sous `.gitignore`

`**/mesures/` écarte les dossiers de campagne, donc aussi leurs
`manifeste.md` — qui sont de la documentation, pas des données, et se relisent
sans les fichiers.

| | |
|---|---|
| Pourquoi ce n'est pas corrigé | git ne redescend pas dans un répertoire ignoré : un `!**/mesures/**/manifeste.md` ne suffit pas. Il faudrait ignorer le *contenu* et non le répertoire, et ce motif-là, mal écrit, laisse passer des mégaoctets de mesures. |
| **Ce qui le ferait revenir** | le besoin de relire un manifeste depuis le dépôt seul. La réécriture tient en quatre lignes — `**/mesures/**`, puis trois négations — mais elle demande d'être vérifiée avec `git check-ignore` sur un vrai dossier de campagne. |
