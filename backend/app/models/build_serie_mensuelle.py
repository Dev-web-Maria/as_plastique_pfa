"""
Préparation de la série mensuelle pour la modélisation — Sprint 4
Agrège les ventes par mois et exclut les points non exploitables :
- l'anomalie isolée 2011-03 (incompatible avec la couverture réelle 2017-2021,
  quasi certainement une erreur de saisie dans le fichier source — 1 seul
  document concerné, décision documentée plutôt que corrigée à l'aveugle)
- le dernier mois si sa donnée semble tronquée (repli d'activité brutal et
  isolé en toute fin de série, plutôt qu'un vrai creux saisonnier)

Lancer depuis backend/ (venv activé) :
    python app/models/build_serie_mensuelle.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("../data/processed/as_plastique.db")
OUTPUT_CSV = Path("../data/processed/serie_mensuelle_ventes.csv")

ANNEE_MIN_PLAUSIBLE = 2017  # couverture réelle connue du corpus (fichiers 2017-2021)
ANNEE_MAX_PLAUSIBLE = 2021

# Démarrage effectif de la série pour la modélisation : les premiers mois de
# 2017 sont trop fragmentés (gros trous, un mois sans aucun montant connu)
# pour représenter un vrai rythme d'activité — non représentatifs, écartés
# explicitement plutôt que de laisser un modèle apprendre sur du bruit.
DATE_DEBUT_MODELISATION = "2018-01-01"


def build_serie():
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql(
        """SELECT dd.annee, dd.mois, COUNT(DISTINCT dv.doc_id) AS n_docs,
                  SUM(lv.montant) AS montant_total, SUM(lv.quantite) AS quantite_total
           FROM fait_lignes_vente lv
           JOIN fait_documents_vente dv ON lv.doc_id = dv.doc_id
           JOIN dim_date dd ON dv.date_id = dd.date_id
           GROUP BY dd.annee, dd.mois
           ORDER BY dd.annee, dd.mois""",
        conn,
    )
    conn.close()

    n_avant = len(df)

    # Exclusion des années hors plage plausible (ex: l'anomalie 2011)
    hors_plage = df[(df["annee"] < ANNEE_MIN_PLAUSIBLE) | (df["annee"] > ANNEE_MAX_PLAUSIBLE)]
    df = df[(df["annee"] >= ANNEE_MIN_PLAUSIBLE) & (df["annee"] <= ANNEE_MAX_PLAUSIBLE)].copy()

    # Construit une colonne date (1er du mois) pour trier et détecter le dernier mois
    df["date_mois"] = pd.to_datetime(dict(year=df["annee"], month=df["mois"], day=1))
    df = df.sort_values("date_mois").reset_index(drop=True)

    # Écarte le début 2017, trop fragmenté (gros trous, mois sans montant connu)
    debut_ecarte = df[df["date_mois"] < DATE_DEBUT_MODELISATION]
    df = df[df["date_mois"] >= DATE_DEBUT_MODELISATION].reset_index(drop=True)

    # Détecte si le dernier mois est probablement tronqué : nombre de documents
    # très inférieur à la médiane des 6 mois précédents
    dernier_mois_exclu = None
    if len(df) >= 7:
        mediane_recente = df["n_docs"].iloc[-7:-1].median()
        dernier = df.iloc[-1]
        if dernier["n_docs"] < mediane_recente * 0.3:  # moins de 30% de l'activité habituelle
            dernier_mois_exclu = f"{int(dernier['annee'])}-{int(dernier['mois']):02d}"
            df = df.iloc[:-1]

    df.to_csv(OUTPUT_CSV, index=False)

    print("=" * 60)
    print("PRÉPARATION DE LA SÉRIE MENSUELLE")
    print("=" * 60)
    print(f"Points mensuels avant filtrage : {n_avant}")
    if not hors_plage.empty:
        print(f"\nPoints exclus (année hors plage {ANNEE_MIN_PLAUSIBLE}-{ANNEE_MAX_PLAUSIBLE}) :")
        for _, row in hors_plage.iterrows():
            print(f"  {int(row['annee'])}-{int(row['mois']):02d} : {row['n_docs']} doc(s), "
                  f"montant={row['montant_total']}")
    if not debut_ecarte.empty:
        print(f"\nDébut 2017 écarté (trop fragmenté, {len(debut_ecarte)} points) :")
        for _, row in debut_ecarte.iterrows():
            print(f"  {int(row['annee'])}-{int(row['mois']):02d} : {row['n_docs']} doc(s)")
    if dernier_mois_exclu:
        print(f"\nDernier mois exclu (probablement tronqué) : {dernier_mois_exclu}")
    print(f"\nPoints mensuels retenus pour la modélisation : {len(df)}")
    print(f"Période : {df['date_mois'].min().strftime('%Y-%m')} → {df['date_mois'].max().strftime('%Y-%m')}")
    print(f"\n📄 Série sauvegardée : {OUTPUT_CSV.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    build_serie()