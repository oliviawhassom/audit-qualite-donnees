-- Audit de qualite de la donnee produit
-- Requetes sur la base generee par audit_qualite_donnees.py
-- Utilisation :  sqlite3 resultats/catalogue.db < requetes.sql

-- 1. Volumetrie du catalogue
SELECT COUNT(*) AS nb_produits FROM produits;

-- 2. Champs les moins bien renseignes, en priorisant les obligatoires
SELECT champ, obligatoire, taux_completude, manquants
FROM completude
ORDER BY obligatoire DESC, taux_completude ASC;

-- 3. Repartition des anomalies par type
SELECT type, COUNT(*) AS nb
FROM anomalies
GROUP BY type
ORDER BY nb DESC;

-- 4. Produits cumulant le plus d'anomalies : la liste a traiter en premier
SELECT code, produit, COUNT(*) AS nb_anomalies
FROM anomalies
GROUP BY code, produit
HAVING COUNT(*) > 1
ORDER BY nb_anomalies DESC
LIMIT 20;

-- 5. Marques dont le catalogue est le plus incomplet
-- On considere un produit incomplet si un champ obligatoire manque.
SELECT
    COALESCE(NULLIF(TRIM(brands), ''), 'marque non renseignee') AS marque,
    COUNT(*) AS nb_produits,
    SUM(CASE WHEN product_name IS NULL OR TRIM(product_name) = '' THEN 1 ELSE 0 END) AS sans_nom,
    SUM(CASE WHEN quantity     IS NULL OR TRIM(quantity)     = '' THEN 1 ELSE 0 END) AS sans_contenance,
    SUM(CASE WHEN ingredients_text IS NULL OR TRIM(ingredients_text) = '' THEN 1 ELSE 0 END) AS sans_ingredients
FROM produits
GROUP BY marque
HAVING nb_produits >= 5
ORDER BY sans_ingredients DESC
LIMIT 15;

-- 6. Taux de produits pleinement exploitables
-- Un produit est exploitable si tous ses champs obligatoires sont renseignes.
SELECT
    ROUND(100.0 * SUM(
        CASE WHEN code IS NOT NULL AND TRIM(code) <> ''
              AND product_name IS NOT NULL AND TRIM(product_name) <> ''
              AND brands IS NOT NULL AND TRIM(brands) <> ''
              AND quantity IS NOT NULL AND TRIM(quantity) <> ''
              AND categories IS NOT NULL AND TRIM(categories) <> ''
              AND ingredients_text IS NOT NULL AND TRIM(ingredients_text) <> ''
        THEN 1 ELSE 0 END) / COUNT(*), 1) AS produits_exploitables_pct
FROM produits;

-- 7. Croisement completude et anomalies : les produits a la fois incomplets
-- et porteurs d'anomalies sont ceux qui coutent le plus cher en aval.
SELECT p.code, p.product_name, p.brands, COUNT(a.code) AS nb_anomalies
FROM produits p
JOIN anomalies a ON a.code = p.code
WHERE p.ingredients_text IS NULL OR TRIM(p.ingredients_text) = ''
GROUP BY p.code, p.product_name, p.brands
ORDER BY nb_anomalies DESC
LIMIT 20;
