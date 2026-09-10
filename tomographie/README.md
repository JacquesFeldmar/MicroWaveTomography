# tomographie — fantôme sur plateau tournant

Projet démarré le 10/09/2026, en parallèle du projet `cartilage/`. Rien n'est
encore décidé : ce document fixe ce qui est acquis et ce qu'il reste à trancher.

## Ce qui est acquis

- **Instrument** : le LiteVNA, piloté par `commun/instrument.py`.
- **Calibration** : une SOL propre à ce banc, au bout de ses propres câbles, par
  `commun/sol.py`. Celle du cartilage ne s'applique pas ici.
- **Mouvement** : un plateau tournant. Moteur NEMA et Arduino sont envisagés.

## Ce qui se transpose du projet cartilage

- **Arrêt / mesure / marche, jamais de rotation pendant un balayage.** Un
  déplacement `e` pendant les 0,25 s d'acquisition crée une erreur de phase
  4πe/λ, soit 15 µm de budget à 6,3 GHz. Avec un moteur pas à pas, le risque
  n'est pas la résolution du pas mais les vibrations de maintien : attendre
  l'amortissement, ou couper le courant, avant de déclencher la mesure.
- **Résolution en profondeur** c/2B : 52 mm dans l'air sur 1,4–6,3 GHz avec une
  fenêtre de Hann.
- **Résolution latérale plancher λ/4**, soit 11,9 mm à 6,3 GHz, atteinte seulement
  si l'ouverture enveloppe l'objet — ce que fait justement un plateau tournant.
  C'est l'ordre de grandeur du plus petit détail qu'un fantôme pourra révéler.

## Ce qui ne se transpose pas

- La fenêtre de distance de 100 à 150 mm : elle a été établie pour une couche
  mince sur un condyle, en réflexion.
- Le modèle stratifié et l'inversion d'épaisseur de `cartilage/noyau.py`.

## Questions à trancher

1. **Réflexion ou transmission ?** Une antenne en S11, ou deux antennes de part et
   d'autre en S21. La transmission demande d'exposer S21 dans `commun/`.
2. **Le fantôme** : matériau, dimensions, inclusions et leur contraste de
   permittivité.
3. **La reconstruction** : rétroprojection, méthode de Born, inversion itérative.
   Le choix fixe le nombre d'angles nécessaire.
4. **Le banc** : protocole PC ↔ Arduino, prise d'origine du plateau, répétabilité
   angulaire.

## Organisation prévue

Les dossiers seront créés avec leur premier fichier :

```
tomographie/
├── banc/            pilotage du plateau (PC) et micrologiciel Arduino
├── acquisition.py   rotation et balayages, enregistrement BRUT par angle
├── reconstruction/  algorithmes d'image
├── fantomes/        description des fantômes réalisés
└── docs/
```
