"""
Endpoints FastAPI — Sprint 4
Remplace le routeur kpis.py du Sprint 2 (qui lisait les CSV d'échantillon) :
celui-ci lit la vraie base SQLite (as_plastique.db) et les résultats de
modélisation (prévision, scoring impayés).
"""

import sqlite3
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["dashboard"])

DB_PATH = Path("../data/processed/as_plastique.db")
SERIE_CSV = Path("../data/processed/serie_mensuelle_ventes.csv")
PREVISION_CSV = Path("../data/processed/prevision_ventes_futures.csv")
SCORING_CSV = Path("../data/processed/scoring_impayes_clients.csv")


def _connexion():
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Base de données introuvable — lance load_to_db.py")
    return sqlite3.connect(DB_PATH)


def _df_vers_json(df: pd.DataFrame):
    """astype(object) avant where() : sinon un NaN dans une colonne float64
    redevient NaN au lieu de None, et casse la sérialisation JSON."""
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict(orient="records")


@router.get("/kpis")
def get_kpis():
    conn = _connexion()
    total_ventes = conn.execute("SELECT SUM(montant) FROM fait_lignes_vente").fetchone()[0] or 0
    n_documents = conn.execute(
        "SELECT COUNT(*) FROM fait_documents_vente WHERE statut_extraction = 'ok'"
    ).fetchone()[0]
    n_clients = conn.execute("SELECT COUNT(*) FROM dim_client").fetchone()[0]
    total_impaye = conn.execute("SELECT SUM(montant) FROM fait_factures_impayees").fetchone()[0] or 0
    n_releves = conn.execute("SELECT COUNT(*) FROM fait_releves").fetchone()[0]
    n_produits = conn.execute("SELECT COUNT(*) FROM dim_produit").fetchone()[0]
    conn.close()

    return {
        "total_ventes_dh": round(total_ventes, 2),
        "nb_documents": n_documents,
        "nb_clients": n_clients,
        "total_impaye_dh": round(total_impaye, 2),
        "nb_releves": n_releves,
        "nb_produits": n_produits,
    }


@router.get("/ventes-mensuelles")
def get_ventes_mensuelles():
    if not SERIE_CSV.exists():
        raise HTTPException(status_code=404, detail="Série mensuelle non générée — lance build_serie_mensuelle.py")
    df = pd.read_csv(SERIE_CSV)
    return _df_vers_json(df)


@router.get("/prevision")
def get_prevision():
    if not PREVISION_CSV.exists():
        raise HTTPException(status_code=404, detail="Prévision non générée — lance predire_futur.py")
    df = pd.read_csv(PREVISION_CSV)
    return _df_vers_json(df)


@router.get("/clients-risque")
def get_clients_risque(niveau: str | None = None):
    if not SCORING_CSV.exists():
        raise HTTPException(status_code=404, detail="Scoring non généré — lance scoring_impayes.py")
    df = pd.read_csv(SCORING_CSV)
    if niveau:
        df = df[df["niveau_risque"] == niveau]
    return _df_vers_json(df)


@router.get("/documents")
def get_documents(statut: str | None = None, type_document: str | None = None, limit: int = 200):
    conn = _connexion()
    requete = """
        SELECT ds.fichier, ds.onglet, dv.type_document, dv.doc_number, dd.date,
               dv.total_ht, dv.tva, dv.net_a_payer, dv.statut_extraction
        FROM fait_documents_vente dv
        JOIN dim_source ds ON dv.source_id = ds.source_id
        LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
        WHERE 1=1
    """
    params = []
    if statut:
        requete += " AND dv.statut_extraction = ?"
        params.append(statut)
    if type_document:
        requete += " AND dv.type_document = ?"
        params.append(type_document)
    requete += " ORDER BY dd.date DESC LIMIT ?"
    params.append(limit)

    df = pd.read_sql(requete, conn, params=params)
    conn.close()
    return _df_vers_json(df)