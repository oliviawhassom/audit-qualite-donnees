"""
Audit de qualite de la donnee produit
=====================================

Objectif : mesurer la qualite d'un catalogue produit sur quatre dimensions
(completude, validite, unicite, coherence), produire des indicateurs de suivi
et exporter la liste des anomalies a corriger.

Source : Open Food Facts, base collaborative de produits alimentaires.
Elle est ouverte, reelle, et volontairement imparfaite : c'est exactement
le type de catalogue qu'une equipe data doit fiabiliser.

Usage :
    pip install pandas matplotlib requests
    python audit_qualite_donnees.py
"""

import json
import os
import sqlite3
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests

# --------------------------------------------------------------------------
# Parametres
# --------------------------------------------------------------------------

CATEGORIE = "snacks"
PAYS = "france"
NB_PAGES = 15     # 15 pages x 100 produits = environ 1500 produits
TAILLE_PAGE = 100
DOSSIER_SORTIE = "resultats"

CHAMPS = [
    "code", "product_name", "brands", "categories", "quantity",
    "labels", "ingredients_text", "nutriscore_grade",
    "energy-kcal_100g", "fat_100g", "sugars_100g", "salt_100g",
]

# Champs consideres comme obligatoires dans un referentiel produit.
# C'est une regle de gestion : elle se discute avec le metier, pas seule.
CHAMPS_OBLIGATOIRES = [
    "code", "product_name", "brands", "quantity",
    "categories", "ingredients_text",
]

# Bornes de validite. Valeurs pour 100 g de produit.
BORNES = {
    "energy-kcal_100g": (0, 900),    # au dela de 900 kcal/100 g : impossible
    "fat_100g": (0, 100),
    "sugars_100g": (0, 100),
    "salt_100g": (0, 100),
}

NUTRISCORE_VALIDES = {"a", "b", "c", "d", "e"}


# --------------------------------------------------------------------------
# 1. Extraction
# --------------------------------------------------------------------------

def telecharger_produits():
    """Recupere les produits via l'API Open Food Facts, page par page.

    L'API publique renvoie parfois une erreur 503 quand elle est surchargee.
    On reessaie avec une attente croissante plutot que d'abandonner, et on
    conserve ce qui a deja ete telecharge si une page finit par echouer.
    """
    produits = []
    url = "https://world.openfoodfacts.org/api/v2/search"
    entetes = {"User-Agent": "AuditQualiteDonnees/1.0 (projet etudiant)"}

    for page in range(1, NB_PAGES + 1):
        params = {
            "categories_tags_en": CATEGORIE,
            "countries_tags_en": PAYS,
            "page": page,
            "page_size": TAILLE_PAGE,
            "fields": ",".join(CHAMPS),
        }

        lot = None
        for tentative in range(1, 5):
            try:
                reponse = requests.get(url, params=params, timeout=60, headers=entetes)
                reponse.raise_for_status()
                lot = reponse.json().get("products", [])
                break
            except requests.exceptions.RequestException as erreur:
                attente = 5 * tentative
                print(f"  page {page} : echec ({erreur.__class__.__name__}), "
                      f"nouvelle tentative dans {attente} s")
                time.sleep(attente)

        if lot is None:
            print(f"  page {page} abandonnee apres 4 tentatives")
            break
        if not lot:
            break

        produits.extend(lot)
        print(f"  page {page} : {len(lot)} produits")
        time.sleep(2)

    return produits


def charger_donnees():
    """Telecharge si besoin, puis renvoie un DataFrame."""
    cache = "produits_bruts.json"
    if os.path.exists(cache):
        print("Lecture du cache local...")
        with open(cache, encoding="utf-8") as f:
            produits = json.load(f)
    else:
        print("Telechargement depuis Open Food Facts...")
        produits = telecharger_produits()
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(produits, f, ensure_ascii=False)
    df = pd.DataFrame(produits)
    for champ in CHAMPS:
        if champ not in df.columns:
            df[champ] = None
    print(f"{len(df)} produits charges\n")
    return df[CHAMPS]


# --------------------------------------------------------------------------
# 2. Regles de qualite
# --------------------------------------------------------------------------

def est_vide(serie):
    """Un champ est vide s'il est nul ou ne contient que des espaces."""
    return serie.isna() | (serie.astype(str).str.strip() == "") | \
           (serie.astype(str).str.lower() == "none")


def mesurer_completude(df):
    """Taux de remplissage de chaque champ, en pourcentage."""
    lignes = []
    for champ in CHAMPS:
        vides = est_vide(df[champ]).sum()
        lignes.append({
            "champ": champ,
            "obligatoire": champ in CHAMPS_OBLIGATOIRES,
            "renseignes": len(df) - vides,
            "manquants": vides,
            "taux_completude": round(100 * (len(df) - vides) / len(df), 1),
        })
    return pd.DataFrame(lignes).sort_values("taux_completude")


def detecter_anomalies(df):
    """Repere les valeurs invalides, incoherentes ou dupliquees."""
    anomalies = []

    # Validite : valeurs numeriques hors bornes physiques
    for champ, (mini, maxi) in BORNES.items():
        valeurs = pd.to_numeric(df[champ], errors="coerce")
        hors_bornes = df[(valeurs < mini) | (valeurs > maxi)]
        for _, ligne in hors_bornes.iterrows():
            anomalies.append({
                "code": ligne["code"],
                "produit": ligne["product_name"],
                "type": "valeur hors bornes",
                "champ": champ,
                "detail": f"{ligne[champ]} hors de [{mini}, {maxi}]",
            })

    # Validite : nutriscore hors nomenclature
    ns = df["nutriscore_grade"].astype(str).str.lower()
    invalides = df[(~ns.isin(NUTRISCORE_VALIDES)) & (~est_vide(df["nutriscore_grade"]))]
    for _, ligne in invalides.iterrows():
        anomalies.append({
            "code": ligne["code"], "produit": ligne["product_name"],
            "type": "valeur hors nomenclature", "champ": "nutriscore_grade",
            "detail": str(ligne["nutriscore_grade"]),
        })

    # Coherence : la somme des nutriments ne peut pas depasser 100 g
    somme = (pd.to_numeric(df["fat_100g"], errors="coerce").fillna(0)
             + pd.to_numeric(df["sugars_100g"], errors="coerce").fillna(0)
             + pd.to_numeric(df["salt_100g"], errors="coerce").fillna(0))
    for _, ligne in df[somme > 100].iterrows():
        anomalies.append({
            "code": ligne["code"], "produit": ligne["product_name"],
            "type": "incoherence entre champs", "champ": "nutriments",
            "detail": "matieres grasses + sucres + sel superieur a 100 g",
        })

    # Unicite : un code barre doit identifier un seul produit
    doublons = df[df.duplicated("code", keep=False) & ~est_vide(df["code"])]
    for _, ligne in doublons.iterrows():
        anomalies.append({
            "code": ligne["code"], "produit": ligne["product_name"],
            "type": "doublon", "champ": "code",
            "detail": "code barre present plusieurs fois",
        })

    # Qualite editoriale : un nom de produit trop court est inexploitable
    noms_courts = df[(~est_vide(df["product_name"]))
                     & (df["product_name"].astype(str).str.len() < 3)]
    for _, ligne in noms_courts.iterrows():
        anomalies.append({
            "code": ligne["code"], "produit": ligne["product_name"],
            "type": "libelle inexploitable", "champ": "product_name",
            "detail": "moins de 3 caracteres",
        })

    return pd.DataFrame(anomalies)


def score_global(completude, df, anomalies):
    """Trois indicateurs simples, suivables dans le temps."""
    oblig = completude[completude["obligatoire"]]
    manque = df[CHAMPS_OBLIGATOIRES].apply(est_vide).any(axis=1)
    produits_complets = df[~manque]
    codes_en_anomalie = anomalies["code"].nunique() if len(anomalies) else 0
    return {
        "completude_champs_obligatoires_%": round(oblig["taux_completude"].mean(), 1),
        "produits_exploitables_%": round(100 * len(produits_complets) / len(df), 1),
        "produits_en_anomalie_%": round(100 * codes_en_anomalie / len(df), 1),
    }


# --------------------------------------------------------------------------
# 3. Restitution
# --------------------------------------------------------------------------

def graphique_completude(completude, chemin):
    donnees = completude.set_index("champ")["taux_completude"]
    couleurs = ["#c0392b" if v < 50 else "#e67e22" if v < 80 else "#27ae60"
                for v in donnees]
    plt.figure(figsize=(9, 5))
    plt.barh(donnees.index, donnees.values, color=couleurs)
    plt.xlabel("Taux de completude (%)")
    plt.title("Completude des champs du catalogue")
    plt.xlim(0, 100)
    plt.tight_layout()
    plt.savefig(chemin, dpi=130)
    plt.close()


def graphique_anomalies(anomalies, chemin):
    if anomalies.empty:
        return
    comptes = anomalies["type"].value_counts()
    plt.figure(figsize=(9, 4.5))
    plt.barh(comptes.index, comptes.values, color="#1f3864")
    plt.xlabel("Nombre d'anomalies")
    plt.title("Anomalies detectees par type")
    plt.tight_layout()
    plt.savefig(chemin, dpi=130)
    plt.close()


def exporter_sqlite(df, completude, anomalies, chemin):
    """Charge les resultats en base pour les interroger en SQL."""
    conn = sqlite3.connect(chemin)
    df.to_sql("produits", conn, if_exists="replace", index=False)
    completude.to_sql("completude", conn, if_exists="replace", index=False)
    if not anomalies.empty:
        anomalies.to_sql("anomalies", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------

def main():
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)
    df = charger_donnees()

    completude = mesurer_completude(df)
    anomalies = detecter_anomalies(df)
    indicateurs = score_global(completude, df, anomalies)

    print("=== Completude des champs ===")
    print(completude.to_string(index=False), "\n")

    print("=== Anomalies detectees ===")
    if anomalies.empty:
        print("aucune anomalie\n")
    else:
        print(anomalies["type"].value_counts().to_string(), "\n")

    print("=== Indicateurs de pilotage ===")
    for cle, valeur in indicateurs.items():
        print(f"  {cle} : {valeur}")

    completude.to_csv(f"{DOSSIER_SORTIE}/completude.csv", index=False)
    anomalies.to_csv(f"{DOSSIER_SORTIE}/anomalies.csv", index=False)
    with open(f"{DOSSIER_SORTIE}/indicateurs.json", "w", encoding="utf-8") as f:
        json.dump(indicateurs, f, indent=2, ensure_ascii=False)

    graphique_completude(completude, f"{DOSSIER_SORTIE}/completude.png")
    graphique_anomalies(anomalies, f"{DOSSIER_SORTIE}/anomalies.png")
    exporter_sqlite(df, completude, anomalies, f"{DOSSIER_SORTIE}/catalogue.db")

    print(f"\nResultats ecrits dans le dossier '{DOSSIER_SORTIE}'.")


if __name__ == "__main__":
    main()
