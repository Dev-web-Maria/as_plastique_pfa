"""
Prévision des prochains mois — Sprint 4
Entraîne le modèle retenu (XGBoost, sans lag_12, transformation log — le
meilleur en validation croisée) sur TOUTE la série disponible, puis prédit
les mois futurs de façon itérative (chaque prédiction sert de "lag" pour
la suivante, puisqu'on n'a pas encore la vraie valeur).

Lancer depuis backend/ (venv activé), après build_serie_mensuelle.py :
    python app/models/predire_futur.py
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

SERIE_CSV = Path("../data/processed/serie_mensuelle_ventes.csv")
OUTPUT_CSV = Path("../data/processed/prevision_ventes_futures.csv")
N_MOIS_FUTURS = 6


def construire_features(df):
    df = df.copy()
    df["mois_num"] = df["date_mois"].dt.month
    df["trimestre"] = df["date_mois"].dt.quarter
    df["lag_1"] = df["montant_total"].shift(1)
    df["lag_2"] = df["montant_total"].shift(2)
    df["lag_3"] = df["montant_total"].shift(3)
    df["moyenne_mobile_3"] = df["montant_total"].shift(1).rolling(3).mean()
    return df


def entrainer_modele_final(df):
    df_features = construire_features(df)
    colonnes = ["mois_num", "trimestre", "lag_1", "lag_2", "lag_3", "moyenne_mobile_3"]
    df_valide = df_features.dropna(subset=colonnes + ["montant_total"])

    X = df_valide[colonnes]
    y = np.log(df_valide["montant_total"])

    modele = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
    modele.fit(X, y)
    return modele, colonnes


def predire_iterativement(df, modele, colonnes, n_mois):
    historique = df[["date_mois", "montant_total"]].copy()
    previsions = []

    for _ in range(n_mois):
        derniere_date = historique["date_mois"].max()
        prochaine_date = derniere_date + pd.DateOffset(months=1)

        serie = historique["montant_total"].values
        features = {
            "mois_num": prochaine_date.month,
            "trimestre": (prochaine_date.month - 1) // 3 + 1,
            "lag_1": serie[-1],
            "lag_2": serie[-2],
            "lag_3": serie[-3],
            "moyenne_mobile_3": np.mean(serie[-3:]),
        }
        X_pred = pd.DataFrame([features])[colonnes]
        prediction_log = modele.predict(X_pred)[0]
        prediction = float(np.exp(prediction_log))

        previsions.append({"date_mois": prochaine_date, "montant_prevu": round(prediction, 2)})
        historique = pd.concat([
            historique,
            pd.DataFrame([{"date_mois": prochaine_date, "montant_total": prediction}])
        ], ignore_index=True)

    return pd.DataFrame(previsions)


def generer_prevision():
    df = pd.read_csv(SERIE_CSV, parse_dates=["date_mois"]).sort_values("date_mois").reset_index(drop=True)

    modele, colonnes = entrainer_modele_final(df)
    previsions = predire_iterativement(df, modele, colonnes, N_MOIS_FUTURS)
    previsions["date_mois"] = previsions["date_mois"].dt.strftime("%Y-%m-%d")
    previsions.to_csv(OUTPUT_CSV, index=False)

    print("=" * 60)
    print("PRÉVISION DES PROCHAINS MOIS")
    print("(XGBoost, sans lag_12, log — retenu en validation croisée, MAPE moyen 19.9%)")
    print("=" * 60)
    print(previsions.to_string(index=False))
    print(f"\n📄 Sauvegardé : {OUTPUT_CSV.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    generer_prevision()