"""
Endpoints FastAPI — Sprint 4 + 5
Lit la vraie base SQLite (as_plastique.db) et les résultats de modélisation
(prévision, scoring impayés), la réconciliation avec le grand livre client,
l'agent conversationnel, et les endpoints de la page Ventes.
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


def _construire_filtre_date(annee, mois, date_debut, date_fin, alias="dd"):
    conditions = []
    params = []

    if date_debut and date_fin:
        conditions.append(
            f"printf('%04d-%02d-%02d', {alias}.annee, {alias}.mois, {alias}.jour) BETWEEN ? AND ?"
        )
        params.extend([date_debut, date_fin])
    else:
        if annee is not None:
            conditions.append(f"{alias}.annee = ?")
            params.append(annee)
        if mois is not None:
            conditions.append(f"{alias}.mois = ?")
            params.append(mois)

    if not conditions:
        return "", []
    return " AND " + " AND ".join(conditions), params


# ---------------------------------------------------------------------------
# Vue globale
# ---------------------------------------------------------------------------

@router.get("/kpis")
def get_kpis(
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
):
    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin)

    total_ventes = conn.execute(
        f"""SELECT SUM(lv.montant)
            FROM fait_lignes_vente lv
            JOIN fait_documents_vente dv ON lv.doc_id = dv.doc_id
            LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
            WHERE 1=1 {filtre_sql}""",
        params,
    ).fetchone()[0] or 0

    n_documents = conn.execute(
        f"""SELECT COUNT(*)
            FROM fait_documents_vente dv
            LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
            WHERE dv.statut_extraction = 'ok' {filtre_sql}""",
        params,
    ).fetchone()[0]

    total_impaye = conn.execute(
        f"""SELECT SUM(fi.montant)
            FROM fait_factures_impayees fi
            JOIN fait_releves fr ON fi.releve_id = fr.releve_id
            LEFT JOIN dim_date dd ON fr.date_releve_id = dd.date_id
            WHERE 1=1 {filtre_sql}""",
        params,
    ).fetchone()[0] or 0

    n_releves = conn.execute(
        f"""SELECT COUNT(*)
            FROM fait_releves fr
            LEFT JOIN dim_date dd ON fr.date_releve_id = dd.date_id
            WHERE 1=1 {filtre_sql}""",
        params,
    ).fetchone()[0]

    n_clients = conn.execute("SELECT COUNT(*) FROM dim_client").fetchone()[0]
    n_produits = conn.execute("SELECT COUNT(*) FROM dim_produit").fetchone()[0]

    conn.close()

    return {
        "total_ventes_dh": round(total_ventes, 2),
        "nb_documents": n_documents,
        "nb_clients": n_clients,
        "total_impaye_dh": round(total_impaye, 2),
        "nb_releves": n_releves,
        "nb_produits": n_produits,
        "filtre_applique": {"annee": annee, "mois": mois, "date_debut": date_debut, "date_fin": date_fin},
    }


@router.get("/ventes-mensuelles")
def get_ventes_mensuelles(
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
):
    if not SERIE_CSV.exists():
        raise HTTPException(status_code=404, detail="Série mensuelle non générée — lance build_serie_mensuelle.py")

    df = pd.read_csv(SERIE_CSV, parse_dates=["date_mois"])

    if date_debut and date_fin:
        df = df[(df["date_mois"] >= date_debut) & (df["date_mois"] <= date_fin)]
    else:
        if annee is not None:
            df = df[df["annee"] == annee]
        if mois is not None:
            df = df[df["mois"] == mois]

    df["date_mois"] = df["date_mois"].dt.strftime("%Y-%m-%d")
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
    requete += " ORDER BY printf('%04d-%02d-%02d', dd.annee, dd.mois, dd.jour) DESC LIMIT ?"
    params.append(limit)

    df = pd.read_sql(requete, conn, params=params)
    conn.close()
    return _df_vers_json(df)


# ---------------------------------------------------------------------------
# Page Ventes
# ---------------------------------------------------------------------------

@router.get("/kpis-ventes")
def get_kpis_ventes(
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
):
    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin)

    row = conn.execute(
        f"""SELECT SUM(lv.montant), SUM(lv.quantite),
                   COUNT(DISTINCT dv.doc_id), COUNT(DISTINCT lv.produit_id),
                   COUNT(DISTINCT dv.client_id)
            FROM fait_lignes_vente lv
            JOIN fait_documents_vente dv ON lv.doc_id = dv.doc_id
            LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
            WHERE 1=1 {filtre_sql}""",
        params,
    ).fetchone()
    conn.close()

    ca_total, volume_total, n_docs, n_produits, n_clients_actifs = row
    ca_total = ca_total or 0
    volume_total = volume_total or 0
    panier_moyen = (ca_total / n_docs) if n_docs else 0

    return {
        "ca_total_dh": round(ca_total, 2),
        "volume_total": round(volume_total, 2),
        "panier_moyen_dh": round(panier_moyen, 2),
        "produits_distincts": n_produits or 0,
        "clients_actifs": n_clients_actifs or 0,
    }


@router.get("/top-produits")
def get_top_produits(
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
    limit: int = 5,
):
    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin)

    df = pd.read_sql(
        f"""SELECT dp.designation, dp.unite,
                   SUM(lv.quantite) AS quantite_totale, SUM(lv.montant) AS montant_total
            FROM fait_lignes_vente lv
            JOIN fait_documents_vente dv ON lv.doc_id = dv.doc_id
            JOIN dim_produit dp ON lv.produit_id = dp.produit_id
            LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
            WHERE lv.quantite IS NOT NULL {filtre_sql}
            GROUP BY dp.produit_id
            ORDER BY montant_total DESC
            LIMIT ?""",
        conn,
        params=params + [limit],
    )
    conn.close()
    return _df_vers_json(df)


@router.get("/dernieres-ventes")
def get_dernieres_ventes(
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
    limit: int = 20,
):
    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin)

    df = pd.read_sql(
        f"""SELECT dc.nom AS client, ds.fichier, ds.onglet, dv.type_document, dv.doc_number, dd.date,
                   dv.net_a_payer, dv.total_ht, dv.statut_extraction
            FROM fait_documents_vente dv
            JOIN dim_source ds ON dv.source_id = ds.source_id
            LEFT JOIN dim_client dc ON dv.client_id = dc.client_id
            LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
            WHERE 1=1 {filtre_sql}
            ORDER BY printf('%04d-%02d-%02d', dd.annee, dd.mois, dd.jour) DESC
            LIMIT ?""",
        conn,
        params=params + [limit],
    )
    conn.close()
    return _df_vers_json(df)


# ---------------------------------------------------------------------------
# Réconciliation avec le grand livre client
# ---------------------------------------------------------------------------

@router.get("/reconciliation-impayes")
def get_reconciliation_impayes(
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
):
    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin)

    base_from = """
        FROM fait_factures_impayees fi
        JOIN fait_releves fr ON fi.releve_id = fr.releve_id
        LEFT JOIN dim_date dd ON fr.date_releve_id = dd.date_id
        WHERE 1=1
    """

    total_snapshot = conn.execute(
        f"SELECT SUM(fi.montant) {base_from} {filtre_sql}", params
    ).fetchone()[0] or 0
    total_snapshot_rapproche = conn.execute(
        f"SELECT SUM(fi.montant) {base_from} {filtre_sql} AND fi.solde_reel IS NOT NULL", params
    ).fetchone()[0] or 0
    total_solde_reel = conn.execute(
        f"SELECT SUM(fi.solde_reel) {base_from} {filtre_sql} AND fi.solde_reel IS NOT NULL", params
    ).fetchone()[0] or 0
    n_total = conn.execute(
        f"SELECT COUNT(*) {base_from} {filtre_sql}", params
    ).fetchone()[0]
    n_rapproche = conn.execute(
        f"SELECT COUNT(*) {base_from} {filtre_sql} AND fi.solde_reel IS NOT NULL", params
    ).fetchone()[0]

    par_statut = pd.read_sql(
        f"""SELECT fi.statut_reel, COUNT(*) AS nombre, SUM(fi.montant) AS montant_snapshot,
                   SUM(fi.solde_reel) AS montant_solde_reel
            {base_from} {filtre_sql} AND fi.statut_reel IS NOT NULL
            GROUP BY fi.statut_reel""",
        conn,
        params=params,
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
def get_grand_livre(
    statut: str | None = None,
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
    limit: int = 300,
):
    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin, alias="ddf")

    requete = f"""
        SELECT dc.nom AS client, gl.numero_facture, ddf.date AS date_facture,
               gl.montant_facture, gl.statut, ddr.date AS date_reglement,
               gl.montant_regle, gl.solde, gl.mode_paiement, gl.reference_reglement
        FROM fait_grand_livre gl
        LEFT JOIN dim_client dc ON gl.client_id = dc.client_id
        LEFT JOIN dim_date ddf ON gl.date_facture_id = ddf.date_id
        LEFT JOIN dim_date ddr ON gl.date_reglement_id = ddr.date_id
        WHERE 1=1 {filtre_sql}
    """
    if statut:
        requete += " AND gl.statut = ?"
        params = params + [statut]
    requete += " ORDER BY printf('%04d-%02d-%02d', ddf.annee, ddf.mois, ddf.jour) DESC LIMIT ?"
    params = params + [limit]

    df = pd.read_sql(requete, conn, params=params)
    conn.close()
    return _df_vers_json(df)


# ---------------------------------------------------------------------------
# Page Clients
# ---------------------------------------------------------------------------

@router.get("/clients")
def get_clients(
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
):
    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin)

    # MAX(dd.date) sur le texte 'JJ/MM/AAAA' donnerait un tri lexical faux
    # (ex: '31/12/2020' > '05/01/2021' en comparaison de texte) — on
    # reconstruit une forme ISO comparable pour un MAX correct.
    df = pd.read_sql(
        f"""SELECT dc.client_id, dc.nom AS client,
                   SUM(lv.montant) AS ca_total,
                   COUNT(DISTINCT dv.doc_id) AS nb_commandes,
                   MAX(printf('%04d-%02d-%02d', dd.annee, dd.mois, dd.jour)) AS derniere_commande
            FROM dim_client dc
            JOIN fait_documents_vente dv ON dv.client_id = dc.client_id
            JOIN fait_lignes_vente lv ON lv.doc_id = dv.doc_id
            LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
            WHERE 1=1 {filtre_sql}
            GROUP BY dc.client_id
            ORDER BY ca_total DESC""",
        conn,
        params=params,
    )
    conn.close()
    return _df_vers_json(df)


@router.get("/clients/{client_id}")
def get_client_detail(client_id: int):
    conn = _connexion()

    client = conn.execute("SELECT nom FROM dim_client WHERE client_id = ?", (client_id,)).fetchone()
    if not client:
        conn.close()
        raise HTTPException(status_code=404, detail="Client introuvable")

    row = conn.execute(
        """SELECT SUM(lv.montant), COUNT(DISTINCT dv.doc_id)
           FROM fait_documents_vente dv
           JOIN fait_lignes_vente lv ON lv.doc_id = dv.doc_id
           WHERE dv.client_id = ?""",
        (client_id,),
    ).fetchone()
    ca_total, nb_commandes = row

    documents = pd.read_sql(
        """SELECT dv.type_document, dv.doc_number, dd.date, dv.net_a_payer, dv.total_ht, dv.statut_extraction
           FROM fait_documents_vente dv
           LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
           WHERE dv.client_id = ?
           ORDER BY printf('%04d-%02d-%02d', dd.annee, dd.mois, dd.jour) DESC
           LIMIT 25""",
        conn,
        params=(client_id,),
    )

    grand_livre = pd.read_sql(
        """SELECT gl.numero_facture, ddf.date AS date_facture, gl.montant_facture, gl.statut,
                  gl.solde, gl.mode_paiement
           FROM fait_grand_livre gl
           LEFT JOIN dim_date ddf ON gl.date_facture_id = ddf.date_id
           WHERE gl.client_id = ?
           ORDER BY printf('%04d-%02d-%02d', ddf.annee, ddf.mois, ddf.jour) DESC""",
        conn,
        params=(client_id,),
    )

    conn.close()

    return {
        "client_id": client_id,
        "nom": client[0],
        "ca_total": round(ca_total or 0, 2),
        "nb_commandes": nb_commandes or 0,
        "documents": _df_vers_json(documents),
        "grand_livre": _df_vers_json(grand_livre),
    }

@router.get("/documents-detail")
def get_documents_detail(
    type_document: str,
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
    statut: str | None = None,
    limit: int = 100,
):
    if type_document not in ("bon_livraison", "facture"):
        raise HTTPException(status_code=400, detail="type_document doit être 'bon_livraison' ou 'facture'")

    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin)

    requete = f"""
        SELECT dv.doc_id, dc.nom AS client, dv.doc_number, dd.date,
               dv.total_ht, dv.tva, dv.net_a_payer, dv.statut_extraction,
               ds.fichier, ds.onglet
        FROM fait_documents_vente dv
        LEFT JOIN dim_client dc ON dv.client_id = dc.client_id
        LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
        JOIN dim_source ds ON dv.source_id = ds.source_id
        WHERE dv.type_document = ? {filtre_sql}
    """
    params_complets = [type_document] + params
    if statut:
        requete += " AND dv.statut_extraction = ?"
        params_complets.append(statut)
    requete += " ORDER BY printf('%04d-%02d-%02d', dd.annee, dd.mois, dd.jour) DESC LIMIT ?"
    params_complets.append(limit)

    df = pd.read_sql(requete, conn, params=params_complets)
    conn.close()
    return _df_vers_json(df)


@router.get("/kpis-documents")
def get_kpis_documents(
    type_document: str,
    annee: int | None = None,
    mois: int | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
):
    if type_document not in ("bon_livraison", "facture"):
        raise HTTPException(status_code=400, detail="type_document doit être 'bon_livraison' ou 'facture'")

    conn = _connexion()
    filtre_sql, params = _construire_filtre_date(annee, mois, date_debut, date_fin)

    row = conn.execute(
        f"""SELECT COUNT(*), SUM(dv.net_a_payer),
                   SUM(CASE WHEN dv.statut_extraction = 'ok' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN dv.statut_extraction != 'ok' THEN 1 ELSE 0 END)
            FROM fait_documents_vente dv
            LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
            WHERE dv.type_document = ? {filtre_sql}""",
        [type_document] + params,
    ).fetchone()
    conn.close()

    n_total, montant_total, n_ok, n_incomplet = row
    return {
        "n_total": n_total or 0,
        "montant_total_dh": round(montant_total or 0, 2),
        "n_ok": n_ok or 0,
        "n_incomplet": n_incomplet or 0,
        "taux_extraction_pct": round((n_ok or 0) / n_total * 100, 1) if n_total else 0,
    }


# ---------------------------------------------------------------------------
# Agent conversationnel
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
        raise HTTPException(status_code=500, detail=str(e))

    return resultat