"""
Exploration des données de vente — Sprint 4 (avant modélisation)
Objectif : comprendre la couverture temporelle, la distribution par produit
et par type de document, pour décider du bon niveau d'agrégation avant
d'entraîner un modèle de prévision.

Lancer depuis backend/ (venv activé) :
    python app/models/explore_ventes.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("../data/processed/as_plastique.db")


def explorer():
    conn = sqlite3.connect(DB_PATH)

    print("=" * 60)
    print("1. COUVERTURE TEMPORELLE")
    print("=" * 60)
    row = conn.execute(
        """SELECT MIN(dd.date), MAX(dd.date), COUNT(DISTINCT dd.annee || '-' || dd.mois)
           FROM fait_documents_vente dv
           JOIN dim_date dd ON dv.date_id = dd.date_id"""
    ).fetchone()
    print(f"Date la plus ancienne  : {row[0]}")
    print(f"Date la plus récente   : {row[1]}")
    print(f"Nombre de mois distincts couverts : {row[2]}")

    print("\nRépartition par année :")
    for annee, n in conn.execute(
        """SELECT dd.annee, COUNT(*) FROM fait_documents_vente dv
           JOIN dim_date dd ON dv.date_id = dd.date_id
           GROUP BY dd.annee ORDER BY dd.annee"""
    ):
        print(f"  {annee} : {n} documents")

    print("\n" + "=" * 60)
    print("2. VENTES MENSUELLES AGRÉGÉES (montant total des lignes produits)")
    print("=" * 60)
    rows = conn.execute(
        """SELECT dd.annee, dd.mois, COUNT(DISTINCT dv.doc_id) AS n_docs,
                  SUM(lv.montant) AS total_montant, SUM(lv.quantite) AS total_quantite
           FROM fait_lignes_vente lv
           JOIN fait_documents_vente dv ON lv.doc_id = dv.doc_id
           JOIN dim_date dd ON dv.date_id = dd.date_id
           GROUP BY dd.annee, dd.mois
           ORDER BY dd.annee, dd.mois"""
    ).fetchall()
    print(f"{'Année-Mois':12} {'Docs':>6} {'Montant total':>16} {'Quantité totale':>16}")
    for annee, mois, n_docs, montant, quantite in rows:
        montant_str = f"{montant:,.0f}" if montant else "0"
        quantite_str = f"{quantite:,.0f}" if quantite else "0"
        print(f"{annee}-{mois:02d}       {n_docs:>6} {montant_str:>16} {quantite_str:>16}")
    print(f"\nTotal : {len(rows)} points mensuels")

    print("\n" + "=" * 60)
    print("3. TOP 15 PRODUITS PAR QUANTITÉ VENDUE")
    print("=" * 60)
    for designation, unite, total_qte, n_lignes in conn.execute(
        """SELECT dp.designation, dp.unite, SUM(lv.quantite) AS total_qte, COUNT(*) AS n_lignes
           FROM fait_lignes_vente lv
           JOIN dim_produit dp ON lv.produit_id = dp.produit_id
           WHERE lv.quantite IS NOT NULL
           GROUP BY dp.produit_id
           ORDER BY total_qte DESC
           LIMIT 15"""
    ):
        designation_court = (designation[:55] + "...") if len(designation) > 55 else designation
        print(f"  {total_qte:>10,.0f} {unite or '?':4} | {n_lignes:>4} lignes | {designation_court}")

    print("\n" + "=" * 60)
    print("4. RÉPARTITION PAR TYPE DE DOCUMENT ET STATUT")
    print("=" * 60)
    for type_doc, statut, n in conn.execute(
        """SELECT type_document, statut_extraction, COUNT(*)
           FROM fait_documents_vente GROUP BY type_document, statut_extraction
           ORDER BY type_document, statut_extraction"""
    ):
        print(f"  {type_doc:15} {statut:22} {n}")

    print("\n" + "=" * 60)
    print("5. QUALITÉ DES DONNÉES POUR LA MODÉLISATION")
    print("=" * 60)
    total_lignes = conn.execute("SELECT COUNT(*) FROM fait_lignes_vente").fetchone()[0]
    lignes_utilisables = conn.execute(
        """SELECT COUNT(*) FROM fait_lignes_vente lv
           JOIN fait_documents_vente dv ON lv.doc_id = dv.doc_id
           WHERE lv.quantite IS NOT NULL AND lv.produit_id IS NOT NULL AND dv.date_id IS NOT NULL"""
    ).fetchone()[0]
    pct = round(lignes_utilisables / total_lignes * 100, 1) if total_lignes else 0
    print(f"Lignes produits totales      : {total_lignes}")
    print(f"Lignes utilisables (qté+produit+date connus) : {lignes_utilisables} ({pct}%)")

    n_produits_distincts = conn.execute(
        "SELECT COUNT(DISTINCT produit_id) FROM fait_lignes_vente WHERE produit_id IS NOT NULL"
    ).fetchone()[0]
    print(f"Produits distincts avec au moins une vente : {n_produits_distincts}")

    conn.close()
    print("=" * 60)


if __name__ == "__main__":
    explorer()