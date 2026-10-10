# Audit de qualité de la donnée produit

Mesure de la qualité d'un catalogue produit réel, détection des anomalies et construction d'indicateurs de pilotage suivables dans le temps.

## Le problème

Un catalogue produit ne devient pas inexploitable d'un coup. Les champs se vident lentement, des valeurs impossibles s'installent, des doublons apparaissent, et personne ne s'en aperçoit avant qu'une décision ait été prise sur une donnée fausse.

Ce projet part d'une question simple : peut-on mesurer, chiffrer et prioriser ce délabrement plutôt que de le subir ?

## Les données

Open Food Facts, base collaborative de produits alimentaires. Publique, réelle, et alimentée par des contributeurs, donc volontairement imparfaite.

Périmètre analysé : **700 produits** de la catégorie snacks vendus en France, récupérés via l'API v2.

## La méthode

Quatre dimensions de qualité, chacune traduite en règles vérifiables.

| Dimension | Question posée | Règle appliquée |
|---|---|---|
| Complétude | Le champ est-il renseigné ? | Champ nul, vide ou ne contenant que des espaces |
| Validité | La valeur est-elle possible ? | Bornes physiques, nomenclatures fermées |
| Cohérence | Les champs s'accordent-ils entre eux ? | Somme des nutriments inférieure à 100 g |
| Unicité | L'identifiant est-il unique ? | Code-barres présent une seule fois |

Le choix des champs obligatoires est une règle de gestion, pas une vérité technique. En entreprise, elle se décide avec le métier. Ici, j'ai retenu les champs sans lesquels un produit ne peut ni être vendu ni être recherché.

## Les résultats

| Indicateur | Valeur |
|---|---|
| Complétude des champs obligatoires | 99,8 % |
| Produits pleinement exploitables | 98,9 % |
| Produits portant au moins une anomalie | 2,0 % |

14 anomalies détectées : 11 valeurs hors nomenclature et 3 valeurs hors bornes.

Champs les moins renseignés : les labels à 98,0 %, puis les valeurs nutritionnelles entre 98,3 et 98,4 %. Quatre champs sont renseignés à 100 % : le code-barres, les catégories, la liste d'ingrédients et le Nutri-Score.

## Le constat le plus intéressant n'est pas dans ces chiffres

Un catalogue collaboratif à 99,8 % de complétude, c'est invraisemblable. Et c'est bien le cas : **ces chiffres ne décrivent pas le catalogue, ils décrivent la façon dont je suis allée le chercher.**

L'API de recherche ne renvoie pas un échantillon représentatif de la base. Elle renvoie les produits qui remontent dans une recherche, c'est-à-dire les mieux renseignés. Les fiches à moitié vides n'en sortent pas. Le signe qui ne trompe pas : la liste d'ingrédients et le Nutri-Score sont à 100 %, alors que ce sont précisément les champs les plus souvent absents de la base réelle.

Autrement dit, mon audit ne trouvait presque rien, et le problème n'était pas le catalogue mais mon mode de collecte. Un jeu de données obtenu par une API de recherche se présente comme un extrait du catalogue, et en constitue en réalité la partie la plus propre. N'importe quel audit construit dessus conclura que tout va bien.

C'est le même écart que celui que je cherchais à mesurer, un cran plus haut : entre ce qu'une source déclare être et ce qu'elle est.

## Reprise sur erreur

L'API publique renvoie régulièrement des erreurs 503 quand elle est sollicitée. La première version du script abandonnait tout à la première erreur.

La version actuelle réessaie quatre fois par page, avec une attente croissante de 5, 10, 15 puis 20 secondes, et conserve ce qui a déjà été téléchargé si une page finit par échouer.

Sur la dernière exécution, la page 5 a été rattrapée dès la première reprise, et la page 8 a été abandonnée après quatre tentatives. Le script a terminé avec 700 produits au lieu de s'arrêter net.

## Ce que j'en retiens

Trier les anomalies compte autant que les détecter. Une liste brute décourage, alors que les quelques produits cumulant plusieurs anomalies se corrigent dans l'après-midi.

Et un audit de qualité ne vaut que ce que vaut son échantillon. J'ai passé plus de temps à comprendre pourquoi mes résultats étaient trop beaux qu'à écrire les règles de contrôle elles-mêmes.

## Les sorties

Dans `resultats/` :

- `completude.csv` et `completude.png` : taux de remplissage par champ
- `anomalies.csv` et `anomalies.png` : liste détaillée et répartition par type
- `indicateurs.json` : les trois indicateurs de pilotage
- `catalogue.db` : base SQLite pour interroger les résultats en SQL

## Pour reproduire

```bash
pip install pandas matplotlib requests
python audit_qualite_donnees.py
sqlite3 resultats/catalogue.db < requetes.sql
```

## Limites connues et pistes de suite

- L'échantillonnage par API de recherche biaise les résultats vers les produits bien renseignés. Travailler sur l'export complet de la base donnerait une mesure honnête.
- La chaîne n'est ni planifiée ni supervisée : elle se lance à la main et n'envoie pas d'alerte.
- Historiser les indicateurs pour suivre l'évolution de la qualité dans le temps.
- Détecter les libellés dupliqués par similarité textuelle plutôt que par égalité stricte.

---

Olivia Whassom, élève ingénieure Big Data et Intelligence Artificielle, EFREI Paris.