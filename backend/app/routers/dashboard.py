"""
Endpoints FastAPI — Sprint 4 + 5
Lit la vraie base SQLite (as_plastique.db) et les résultats de modélisation
(prévision, scoring impayés), plus la réconciliation avec le grand livre
client (Sprint 5).
"""

import sqlite3
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.agent_sql import poser_question

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


# ---------------------------------------------------------------------------
# Sprint 5 — agent conversationnel
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str


@router.post("/chat")
def post_chat(payload: ChatRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide")

    try:
        resultat = poser_question(question)
    except RuntimeError as e:
        # Ex: clé API manquante — erreur de configuration, pas une erreur utilisateur
        raise HTTPException(status_code=500, detail=str(e))

    return resultat


# ---------------------------------------------------------------------------
# Sprint 5 — réconciliation avec le grand livre client
# ---------------------------------------------------------------------------

@router.get("/reconciliation-impayes")
def get_reconciliation_impayes():
    conn = _connexion()

    total_snapshot = conn.execute("SELECT SUM(montant) FROM fait_factures_impayees").fetchone()[0] or 0
    total_snapshot_rapproche = conn.execute(
        "SELECT SUM(montant) FROM fait_factures_impayees WHERE solde_reel IS NOT NULL"
    ).fetchone()[0] or 0
    total_solde_reel = conn.execute(
        "SELECT SUM(solde_reel) FROM fait_factures_impayees WHERE solde_reel IS NOT NULL"
    ).fetchone()[0] or 0
    n_total = conn.execute("SELECT COUNT(*) FROM fait_factures_impayees").fetchone()[0]
    n_rapproche = conn.execute(
        "SELECT COUNT(*) FROM fait_factures_impayees WHERE solde_reel IS NOT NULL"
    ).fetchone()[0]

    par_statut = pd.read_sql(
        """SELECT statut_reel, COUNT(*) AS nombre, SUM(montant) AS montant_snapshot,
                  SUM(solde_reel) AS montant_solde_reel
           FROM fait_factures_impayees
           WHERE statut_reel IS NOT NULL
           GROUP BY statut_reel""",
        conn,
    )
    conn.close()

    montant_regularise = total_snapshot_rapproche - total_solde_reel

    return {
        "total_impaye_snapshot": round(total_snapshot, 2),
        "total_rapproche_avec_grand_livre": round(total_snapshot_rapproche, 2),
        "total_solde_reel": round(total_solde_reel, 2),
        "montant_regularise": round(montant_regularise, 2),
        "nb_lignes_impayees": n_total,
        "nb_lignes_rapprochees": n_rapproche,
        "taux_rapprochement_pct": round(n_rapproche / n_total * 100, 1) if n_total else 0,
        "par_statut": _df_vers_json(par_statut),
    }


@router.get("/grand-livre")
def get_grand_livre(statut: str | None = None, limit: int = 300):
    conn = _connexion()
    requete = """
        SELECT dc.nom AS client, gl.numero_facture, ddf.date AS date_facture,
               gl.montant_facture, gl.statut, ddr.date AS date_reglement,
               gl.montant_regle, gl.solde, gl.mode_paiement, gl.reference_reglement
        FROM fait_grand_livre gl
        LEFT JOIN dim_client dc ON gl.client_id = dc.client_id
        LEFT JOIN dim_date ddf ON gl.date_facture_id = ddf.date_id
        LEFT JOIN dim_date ddr ON gl.date_reglement_id = ddr.date_id
        WHERE 1=1
    """
    params = []
    if statut:
        requete += " AND gl.statut = ?"
        params.append(statut)
    requete += " ORDER BY ddf.date DESC LIMIT ?"
    params.append(limit)

    df = pd.read_sql(requete, conn, params=params)
    conn.close()
    return _df_vers_json(df)

class ChatRequest(BaseModel):
    question: str


@router.post("/chat")
def post_chat(payload: ChatRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide")

    try:
        resultat = poser_question(question)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return resultat