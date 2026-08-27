"""
Scoring de risque impayés — Sprint 4/5
Score pondéré et explicable par client. Utilise le SOLDE RÉEL (grand livre
client, Sprint 5) en priorité pour le montant dû — plus fiable que le simple
snapshot des relevés extraits, qui ne reflète pas les règlements effectués
depuis. Quand une facture n'a pas pu être rapprochée du grand livre, on
retombe sur le montant du snapshot (meilleure information disponible).

Les signaux comportementaux (nombre de relevés, ancienneté) restent basés sur
l'historique complet, y compris les factures depuis réglées : le fait qu'un
client soit réapparu plusieurs fois en retard reste un vrai signal de risque,
même s'il a fini par payer.

Lancer depuis backend/ (venv activé) :
    python app/models/scoring_impayes.py
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

DB_PATH = Path("../data/processed/as_plastique.db")
OUTPUT_CSV = Path("../data/processed/scoring_impayes_clients.csv")

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
               fr.releve_id, fi.ligne_id, fi.numero_facture, fi.montant, fi.reference_paiement,
               fi.solde_reel, fi.statut_reel,
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
    df.loc[df["anciennete_jours"] < 0, "anciennete_jours"] = np.nan

    df["montant_effectif"] = df["solde_reel"].where(df["solde_reel"].notna(), df["montant"])

    agg = df.groupby(["client_id", "client"]).agg(
        nombre_releves=("releve_id", "nunique"),
        nombre_factures_impayees=("ligne_id", "count"),
        montant_total_impaye=("montant_effectif", "sum"),
        montant_moyen_facture=("montant_effectif", "mean"),
        anciennete_moyenne_jours=("anciennete_jours", "mean"),
        nb_lignes_rapprochees=("solde_reel", lambda s: s.notna().sum()),
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

    n_total_lignes = len(df_brut)
    n_rapprochees = df_brut["solde_reel"].notna().sum()

    print("=" * 70)
    print("SCORING DE RISQUE IMPAYÉS PAR CLIENT")
    print("=" * 70)
    print(f"Clients scorés : {len(resultat)}")
    print(f"Lignes impayées utilisées : {n_total_lignes} "
          f"(dont {n_rapprochees} avec solde réel du grand livre, "
          f"{n_total_lignes - n_rapprochees} sur snapshot brut)")
    print("\nRépartition par niveau de risque :")
    print(resultat["niveau_risque"].value_counts().to_string())

    print("\nTop 10 clients à risque le plus élevé :")
    cols_affichage = ["client", "score_risque", "niveau_risque", "montant_total_impaye",
                       "nombre_releves", "nombre_factures_impayees", "anciennete_moyenne_jours",
                       "nb_lignes_rapprochees"]
    print(resultat[cols_affichage].head(10).to_string(index=False))

    print(f"\n📄 Résultat complet : {OUTPUT_CSV.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    executer()