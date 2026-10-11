# Version 2 : du script d'audit à la chaîne de traitement

## Ce que fait la version 1
Un script unique télécharge, mesure et restitue. Les règles sont
écrites dans le code. Chaque exécution écrase la précédente.

## Ce que doit faire la version 2

### 1. Séparer les couches
- `brut` : les données telles que reçues, conservées, jamais modifiées
- `nettoye` : typage, normalisation, dédoublonnage
- `exploitable` : les indicateurs de qualité

### 2. Externaliser les règles
Les règles de qualité sont décrites dans un fichier et chargées en
base. Le moteur de contrôle lit cette table. Modifier un seuil ne
demande aucune modification de code.

### 3. Historiser
Chaque exécution ajoute ses résultats sans écraser les précédents :
une ligne par règle et par exécution, avec la date, le nombre de
lignes contrôlées et le nombre en échec.

### 4. Restituer l'évolution
Un graphique montre la trajectoire des indicateurs dans le temps,
et non leur valeur à un instant donné.

### 5. Tester le moteur
Des jeux de données réduits, contenant des anomalies connues,
vérifient que chaque règle détecte exactement ce qu'elle doit
détecter.

## Hors périmètre
Pas de passage au cloud, pas d'orchestration planifiée. Ces sujets
sont traités dans un projet distinct.