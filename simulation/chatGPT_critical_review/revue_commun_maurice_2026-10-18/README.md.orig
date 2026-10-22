# commun — ce qui ne dépend pas du banc

Bibliothèque partagée par `cartilage/` et `tomographie/`. Elle n'importe aucun des
deux projets et n'écrit dans aucun dossier de données : les chemins sont toujours
fournis par l'appelant.

| Module | Contenu |
|---|---|
| `instrument.py` | `ouvrir_reel`, `balayage`, `acquiert` (moyennage vectoriel), `enregistre` / `relit` (balayages BRUTS), `PORT_VNA` |
| `sol.py` | modèle des étalons, `resoudre` (trois étalons → e00, e11, e10·e01), `applique` |
| `physique.py` | `c`, `eps0`, table `MILIEUX`, `milieu`, `indice`, `profil_distance`, `resolution_mm` |
| `docs/Lite_VNA.pdf` | documentation de l'instrument |

## Deux faits à ne pas oublier

- **L'USB du LiteVNA renvoie toujours des données brutes**, quelle que soit la
  calibration faite dans son menu. La correction se fait ici, par `sol.applique`.
- **`profil_distance` utilise Δf = BW/(N−1).** Prendre 1/BW surestime toutes les
  distances de N/(N−1), soit 1 % à 101 points.

## Ce qui manque pour la tomographie

`balayage` ne rend que S11. Une tomographie en transmission a besoin de S21, que
l'instrument fournit déjà (`get_s11_s21`) : il faudra l'exposer ici, sans changer
ce que voit le cartilage.
