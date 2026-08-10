"""
Scoring de risque impayés — Sprint 4
Score pondéré et explicable par client, PAS un modèle supervisé classique :
on n'a aucune étiquette fiable "a fait défaut / n'a pas fait défaut" dans les
données (une facture listée dans un relevé d'impayés à un instant T ne dit
pas si elle a fini par être réglée avec certitude) — inventer une cible
supervisée serait plus trompeur qu'utile. Le score pondéré reste transparent
et justifiable : chaque composante et son poids sont visibles et modifiables.

Lancer depuis backend/ (venv activé) :
    python app/models/scoring_impayes.py
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

DB_PATH = Path("../data/processed/as_plastique.db")
OUTPUT_CSV = Path("../data/processed/scoring_impayes_clients.csv")

# Poids de chaque composante du score (doivent sommer à 1.0)
POIDS = {
    "montant_total_impaye": 0.35,
    "nombre_releves": 0.20,
    "nombre_factures_impayees": 0.15,
    "anciennete_moyenne_jours": 0.20,
    "taux_sans_reference": 0.10,
}


def charger_donnees():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """SELECT
               dc.client_id, dc.nom AS client,
               fr.releve_id, fi.ligne_id, fi.montant, fi.reference_paiement,
               ddr.jour AS jour_releve, ddr.mois AS mois_releve, ddr.annee AS annee_releve,
               ddf.jour AS jour_facture, ddf.mois AS mois_facture, ddf.annee AS annee_facture
           FROM dim_client dc
           JOIN fait_releves fr ON fr.client_id = dc.client_id
           JOIN fait_factures_impayees fi ON fi.releve_id = fr.releve_id
           LEFT JOIN dim_date ddr ON fr.date_releve_id = ddr.date_id
           LEFT JOIN dim_date ddf ON fi.date_facture_id = ddf.date_id""",
        conn,
    )
    conn.close()
    return df


def _construire_date(row, prefixe):
    jour, mois, annee = row[f"jour_{prefixe}"], row[f"mois_{prefixe}"], row[f"annee_{prefixe}"]
    if pd.isna(jour) or pd.isna(mois) or pd.isna(annee):
        return pd.NaT
    try:
        return pd.Timestamp(year=int(annee), month=int(mois), day=int(jour))
    except ValueError:
        return pd.NaT


def construire_features(df):
    df = df.copy()
    df["date_releve"] = df.apply(lambda r: _construire_date(r, "releve"), axis=1)
    df["date_facture"] = df.apply(lambda r: _construire_date(r, "facture"), axis=1)
    df["anciennete_jours"] = (df["date_releve"] - df["date_facture"]).dt.days
    # Ancienneté négative = incohérence de saisie (facture "après" le relevé) — écartée
    df.loc[df["anciennete_jours"] < 0, "anciennete_jours"] = np.nan

    agg = df.groupby(["client_id", "client"]).agg(
        nombre_releves=("releve_id", "nunique"),
        nombre_factures_impayees=("ligne_id", "count"),
        montant_total_impaye=("montant", "sum"),
        montant_moyen_facture=("montant", "mean"),
        anciennete_moyenne_jours=("anciennete_jours", "mean"),
    ).reset_index()

    taux_sans_ref = (
        df.groupby("client_id")["reference_paiement"]
        .apply(lambda s: s.isna().sum() / len(s))
        .reset_index(name="taux_sans_reference")
    )
    agg = agg.merge(taux_sans_ref, on="client_id")

    return agg


def _normaliser(serie):
    if serie.max() == serie.min():
        return serie * 0
    return (serie - serie.min()) / (serie.max() - serie.min())


def calculer_score(agg):
    agg = agg.copy()
    mediane_anciennete = agg["anciennete_moyenne_jours"].median()
    agg["anciennete_moyenne_jours"] = agg["anciennete_moyenne_jours"].fillna(mediane_anciennete)

    score = pd.Series(0.0, index=agg.index)
    for colonne, poids in POIDS.items():
        score += _normaliser(agg[colonne]) * poids
    agg["score_risque"] = (score * 100).round(1)

    q1, q2 = agg["score_risque"].quantile([1 / 3, 2 / 3])

    def niveau(s):
        if s <= q1:
            return "Faible"
        elif s <= q2:
            return "Moyen"
        return "Élevé"

    agg["niveau_risque"] = agg["score_risque"].apply(niveau)
    return agg.sort_values("score_risque", ascending=False).reset_index(drop=True)


def executer():
    df_brut = charger_donnees()
    if df_brut.empty:
        print("⚠ Aucune donnée d'impayés trouvée (fait_releves / fait_factures_impayees vides)")
        return

    agg = construire_features(df_brut)
    resultat = calculer_score(agg)
    resultat.to_csv(OUTPUT_CSV, index=False)

    print("=" * 70)
    print("SCORING DE RISQUE IMPAYÉS PAR CLIENT")
    print("=" * 70)
    print(f"Clients scorés : {len(resultat)}")
    print("\nRépartition par niveau de risque :")
    print(resultat["niveau_risque"].value_counts().to_string())

    print("\nTop 10 clients à risque le plus élevé :")
    cols_affichage = ["client", "score_risque", "niveau_risque", "montant_total_impaye",
                       "nombre_releves", "nombre_factures_impayees", "anciennete_moyenne_jours"]
    print(resultat[cols_affichage].head(10).to_string(index=False))

    print(f"\n📄 Résultat complet : {OUTPUT_CSV.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    executer()