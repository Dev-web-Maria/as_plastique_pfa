"""
Prévision de la demande — Sprint 4
Compare un modèle baseline (SARIMA) et un modèle avancé (XGBoost) sur la
série mensuelle des ventes, avec un vrai jeu de test (derniers mois retenus,
jamais vus à l'entraînement).

Lancer depuis backend/ (venv activé), après build_serie_mensuelle.py :
    python app/models/train_forecast.py
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.statespace.sarimax import SARIMAX
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

SERIE_CSV = Path("../data/processed/serie_mensuelle_ventes.csv")
N_MOIS_TEST = 6  # derniers mois retenus comme jeu de test (jamais vus à l'entraînement)


def charger_serie():
    df = pd.read_csv(SERIE_CSV, parse_dates=["date_mois"])
    df = df.sort_values("date_mois").reset_index(drop=True)
    return df


def calculer_metriques(y_vrai, y_pred, nom_modele):
    mae = mean_absolute_error(y_vrai, y_pred)
    rmse = np.sqrt(mean_squared_error(y_vrai, y_pred))
    mape = np.mean(np.abs((y_vrai - y_pred) / y_vrai)) * 100
    print(f"\n--- {nom_modele} ---")
    print(f"  MAE  : {mae:,.0f} DH")
    print(f"  RMSE : {rmse:,.0f} DH")
    print(f"  MAPE : {mape:.1f}%  (équivalent 'précision' ≈ {100 - mape:.1f}%)")
    return {"modele": nom_modele, "mae": mae, "rmse": rmse, "mape": mape}


# ---------------------------------------------------------------------------
# SARIMA (baseline)
# ---------------------------------------------------------------------------

def entrainer_sarima(train, test, log_transform: bool):
    y_train = train["montant_total"].values
    y_train_utilise = np.log(y_train) if log_transform else y_train

    modele = SARIMAX(
        y_train_utilise,
        order=(1, 1, 1),
        seasonal_order=(1, 0, 0, 12),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    resultat = modele.fit(disp=False)

    prevision_brute = resultat.forecast(steps=len(test))
    prevision = np.exp(prevision_brute) if log_transform else prevision_brute

    nom = "SARIMA (log)" if log_transform else "SARIMA (échelle réelle)"
    return calculer_metriques(test["montant_total"].values, prevision, nom)


# ---------------------------------------------------------------------------
# XGBoost (features temporelles + retards)
# ---------------------------------------------------------------------------

def construire_features(df):
    df = df.copy()
    df["mois_num"] = df["date_mois"].dt.month
    df["trimestre"] = df["date_mois"].dt.quarter
    df["lag_1"] = df["montant_total"].shift(1)
    df["lag_2"] = df["montant_total"].shift(2)
    df["lag_3"] = df["montant_total"].shift(3)
    df["lag_12"] = df["montant_total"].shift(12)  # même mois, année précédente
    df["moyenne_mobile_3"] = df["montant_total"].shift(1).rolling(3).mean()
    return df


def entrainer_xgboost(df_features, n_test, utiliser_lag_12: bool, log_transform: bool):
    colonnes_features = ["mois_num", "trimestre", "lag_1", "lag_2", "lag_3", "moyenne_mobile_3"]
    if utiliser_lag_12:
        colonnes_features.append("lag_12")

    df_valide = df_features.dropna(subset=colonnes_features + ["montant_total"]).reset_index(drop=True)

    X = df_valide[colonnes_features]
    y_reelle = df_valide["montant_total"]
    y_utilisee = np.log(y_reelle) if log_transform else y_reelle

    X_train, X_test = X.iloc[:-n_test], X.iloc[-n_test:]
    y_train, y_test = y_utilisee.iloc[:-n_test], y_reelle.iloc[-n_test:]

    modele = XGBRegressor(
        n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42
    )
    modele.fit(X_train, y_train)
    prevision_brute = modele.predict(X_test)
    prevision = np.exp(prevision_brute) if log_transform else prevision_brute

    nom = f"XGBoost (lag_12={utiliser_lag_12}, log={log_transform})"
    return calculer_metriques(y_test.values, prevision, nom), modele, colonnes_features, len(X_train)


def validation_croisee_walk_forward(df, n_folds=4, horizon=3):
    """Validation croisée temporelle : chaque pli s'entraîne sur tout le passé
    disponible et teste sur les 'horizon' mois suivants, jamais l'inverse.
    La fenêtre d'entraînement s'agrandit à chaque pli (walk-forward classique)."""
    n_total = len(df)
    taille_min_train = n_total - n_folds * horizon

    if taille_min_train < 12:
        print(f"⚠ Pas assez de données pour {n_folds} plis de {horizon} mois "
              f"(il faudrait au moins {n_folds * horizon + 12} points, on en a {n_total})")
        return

    print("\n" + "=" * 60)
    print(f"VALIDATION CROISÉE WALK-FORWARD ({n_folds} plis, horizon={horizon} mois)")
    print("=" * 60)

    configs_xgb = [(False, False), (False, True), (True, False), (True, True)]
    mape_par_modele = {"SARIMA (échelle réelle)": [], "SARIMA (log)": []}
    for lag12, log in configs_xgb:
        mape_par_modele[f"XGBoost (lag_12={lag12}, log={log})"] = []

    df_features = construire_features(df)

    for fold in range(n_folds):
        fin_train = taille_min_train + fold * horizon
        train_fold = df.iloc[:fin_train]
        test_fold = df.iloc[fin_train:fin_train + horizon]

        print(f"\n--- Pli {fold + 1}/{n_folds} : entraînement sur {len(train_fold)} mois, "
              f"test sur {test_fold['date_mois'].min().strftime('%Y-%m')} → "
              f"{test_fold['date_mois'].max().strftime('%Y-%m')} ---")

        for log_transform in (False, True):
            y_train = train_fold["montant_total"].values
            y_utilise = np.log(y_train) if log_transform else y_train
            try:
                modele = SARIMAX(
                    y_utilise, order=(1, 1, 1), seasonal_order=(1, 0, 0, 12),
                    enforce_stationarity=False, enforce_invertibility=False,
                )
                resultat = modele.fit(disp=False)
                prevision_brute = resultat.forecast(steps=len(test_fold))
                prevision = np.exp(prevision_brute) if log_transform else prevision_brute
                mape = np.mean(np.abs((test_fold["montant_total"].values - prevision)
                                       / test_fold["montant_total"].values)) * 100
                nom = "SARIMA (log)" if log_transform else "SARIMA (échelle réelle)"
                mape_par_modele[nom].append(mape)
                print(f"  {nom:25} MAPE = {mape:.1f}%")
            except Exception as e:
                print(f"  SARIMA (log={log_transform}) — échec sur ce pli : {e}")

        df_features_fold = df_features.iloc[:fin_train + horizon]
        for lag12, log in configs_xgb:
            try:
                resultat_xgb, _, _, _ = entrainer_xgboost(df_features_fold, horizon, lag12, log)
                nom = f"XGBoost (lag_12={lag12}, log={log})"
                mape_par_modele[nom].append(resultat_xgb["mape"])
            except Exception as e:
                print(f"  XGBoost (lag_12={lag12}, log={log}) — échec sur ce pli : {e}")

    print("\n" + "=" * 60)
    print("MOYENNE DES MAPE SUR TOUS LES PLIS (résultat le plus fiable)")
    print("=" * 60)
    moyennes = {}
    for nom, mapes in mape_par_modele.items():
        if mapes:
            moyenne = sum(mapes) / len(mapes)
            moyennes[nom] = moyenne
            print(f"  {nom:32} MAPE moyen = {moyenne:.1f}%  (sur {len(mapes)} plis)")

    if moyennes:
        meilleur = min(moyennes, key=moyennes.get)
        print(f"\n🏆 Meilleur modèle en validation croisée : {meilleur} ({moyennes[meilleur]:.1f}%)")
    print("=" * 60)

def entrainer_et_comparer():
    df = charger_serie()
    print(f"Série chargée : {len(df)} points, {df['date_mois'].min().strftime('%Y-%m')} → "
          f"{df['date_mois'].max().strftime('%Y-%m')}")

    if len(df) < N_MOIS_TEST + 12:
        print(f"⚠ Attention : peu de données ({len(df)} points) pour un split "
              f"train/test de {N_MOIS_TEST} mois — résultats à interpréter avec prudence.")

    train, test = df.iloc[:-N_MOIS_TEST], df.iloc[-N_MOIS_TEST:]
    print(f"Entraînement : {len(train)} mois | Test : {len(test)} mois "
          f"({test['date_mois'].min().strftime('%Y-%m')} → {test['date_mois'].max().strftime('%Y-%m')})")

    print("\n" + "=" * 60)
    print("COMPARAISON DES MODÈLES DE PRÉVISION (plusieurs variantes)")
    print("=" * 60)

    resultats = []
    resultats.append(entrainer_sarima(train, test, log_transform=False))
    resultats.append(entrainer_sarima(train, test, log_transform=True))

    df_features = construire_features(df)
    for utiliser_lag_12 in (False, True):
        for log_transform in (False, True):
            resultat_xgb, _, _, n_train = entrainer_xgboost(
                df_features, N_MOIS_TEST, utiliser_lag_12, log_transform
            )
            print(f"    (entraîné sur {n_train} mois)")
            resultats.append(resultat_xgb)

    print("\n" + "=" * 60)
    print("RÉSUMÉ COMPARATIF")
    print("=" * 60)
    for r in resultats:
        print(f"  {r['modele']:22} MAE={r['mae']:>10,.0f}  RMSE={r['rmse']:>10,.0f}  MAPE={r['mape']:>5.1f}%")

    meilleur = min(resultats, key=lambda r: r["mape"])
    print(f"\n🏆 Meilleur modèle (MAPE le plus bas) : {meilleur['modele']} ({meilleur['mape']:.1f}%)")
    print("=" * 60)

    validation_croisee_walk_forward(df, n_folds=4, horizon=3)


if __name__ == "__main__":
    entrainer_et_comparer()