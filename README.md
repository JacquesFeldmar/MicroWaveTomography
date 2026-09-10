# MicroWaveTomography

Deux projets de mesure micro-onde avec le LiteVNA, développés en parallèle. Ils
partagent l'accès à l'instrument et rien d'autre.

```
MicroWaveTomography/
├── commun/        ce qui ne dépend pas du banc : instrument, calibration SOL, traitement
├── cartilage/     projet 1 : épaisseur du cartilage, sonde sur robot 6 DDL, genou ouvert
├── tomographie/   projet 2 : tomographie d'un fantôme sur plateau tournant
└── outils/        logiciels tiers (NanoVNA-Saver…), non versionnés
```

| Dossier | État |
|---|---|
| `cartilage/` | chaîne complète (calibration, mesure, qualification), validée en simulation, **jamais encore sur l'instrument réel** |
| `tomographie/` | démarrage : objectifs et questions ouvertes dans son `README.md` |
| `commun/` | extrait de `cartilage/` le 10/09/2026, sans changement de comportement |

## La règle de dépendance

```
cartilage ──► commun ◄── tomographie
```

Un projet peut importer `commun/`. **Il n'importe jamais l'autre projet.** Si la
tomographie a besoin d'un morceau du cartilage, ce morceau monte dans `commun/`,
et `commun/` ne dépend d'aucun projet.

Le critère pour décider : *ce code resterait-il juste si l'on changeait de banc ?*
Ouvrir le LiteVNA, résoudre une SOL, calculer un profil de distance : oui, il va
dans `commun/`. Le modèle d'une couche sur un substrat, les scènes du simulateur,
le plan d'antenne mesuré : non, il reste dans son projet.

## Démarrer

Aucune installation. Chaque projet rend `commun/` importable lui-même, donc les
commandes se lancent depuis le dossier du projet, comme avant :

```
cd cartilage
python radar.py --autotest
python verifier_doc.py
```

**Après toute modification de `commun/`, relancer les vérifications des deux
projets** : un changement fait pour l'un peut casser l'autre sans que rien ne le
signale.

## Données

`calibration/`, `mesures/` et `qualification/` sont créés dans le dossier de chaque
projet et ne sont pas versionnés. Chaque banc a sa propre calibration : les câbles
et les antennes du plateau tournant ne sont pas ceux de la sonde.
