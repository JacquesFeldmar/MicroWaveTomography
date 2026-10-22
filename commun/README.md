# commun — ce qui ne dépend pas du banc

Bibliothèque partagée par `cartilage/` et `tomographie/`. Elle n'importe aucun des
deux projets et n'écrit dans aucun dossier de données : les chemins sont toujours
fournis par l'appelant.

| Module | Contenu |
|---|---|
| `instrument.py` | `ouvrir_reel`, `balayage`, `acquiert` (moyennage vectoriel), `enregistre` / `relit` (balayages BRUTS), `PORT_VNA` |
| `sol.py` | modèle des étalons, `resoudre` (trois étalons → e00, e11, e10·e01), `applique` |
| `physique.py` | `c`, `eps0`, table `MILIEUX`, `milieu`, `indice`, `profil_distance`, `resolution_mm`, `cote_plaque_mm` |
| `docs/Lite_VNA.pdf` | documentation de l'instrument |

## Deux faits à ne pas oublier

- **L'état de correction USB doit être identifié.** Cette bibliothèque est
  conçue pour des acquisitions brutes suivies d'une SOL par `sol.applique`.
  Le pilote `NanoVNAv2` de scikit-rf 1.12.0 ne règle ni ne vérifie explicitement
  le registre de mode `0x26` : il ne garantit donc pas seul cet état.
  Le [manuel LiteVNA](https://nanovna.com/wp-content/uploads/2021/11/LiteVNA_User-Guide.pdf)
  décrit un mode 3 corrigé en interne, malgré une formulation contradictoire
  dans son paragraphe FIFO. Identifier firmware, mode et calibration sur le banc
  avant la mesure ; ne pas appliquer une seconde SOL à des données déjà corrigées.
  Le pilote distinct de Maurice, `from Maurice/plexiglas/progs/litevna.py`,
  sélectionne et relit le mode ; il n'est pas intégré ici ni vérifié sur matériel
  pendant cette reprise.
- **`profil_distance` utilise Δf = BW/(N−1).** Prendre 1/BW surestime toutes les
  distances de N/(N−1), soit 1 % à 101 points. La grille doit être finie,
  croissante et uniforme ; S11 doit être fini et de même taille. Le zoom doit
  être un entier positif. Les distances sont équivalentes dans l'air depuis
  le plan de référence : l'antenne n'est pas déconvoluée, et le gain de la
  fenêtre IFFT reste inclus dans l'amplitude.

## Ce qui manque pour la tomographie

`balayage` ne rend que S11. Une tomographie en transmission a besoin de S21, que
l'instrument fournit déjà (`get_s11_s21`) : il faudra l'exposer ici, sans changer
ce que voit le cartilage.
