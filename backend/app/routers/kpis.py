"""
Endpoints FastAPI — Sprint 2
Expose les données extraites (échantillon pour l'instant) : KPIs de synthèse
et liste des documents. Sera branché sur la vraie base SQLite au Sprint 3 ;
pour l'instant, lit directement les CSV produits par run_extraction.py.
"""

from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["extraction"])

DOCS_CSV = Path("../data/processed/extraction_sample_documents.csv")
ITEMS_CSV = Path("../data/processed/extraction_sample_items.csv")


def _load_docs() -> pd.DataFrame:
    if not DOCS_CSV.exists():
        raise HTTPException(
            status_code=404,
            detail="Aucune donnée extraite trouvée — lance d'abord run_extraction.py",
        )
    # dtype=str sur doc_number : sinon pandas le lit comme un nombre et
    # supprime les zéros de tête ('001666' devient 1666.0)
    return pd.read_csv(DOCS_CSV, dtype={"doc_number": str})


def _load_items() -> pd.DataFrame:
    if not ITEMS_CSV.exists():
        return pd.DataFrame()
    return pd.read_csv(ITEMS_CSV, dtype={"doc_number": str})


@router.get("/kpis")
def get_kpis():
    """Indicateurs de synthèse calculés sur les documents extraits."""
    docs = _load_docs()
    items = _load_items()

    ok_docs = docs[docs["statut"] == "ok"]

    montant_total = float(items["montant"].sum()) if not items.empty else 0.0
    n_livraisons = int((ok_docs["type_detecte"] == "bon_livraison").sum())
    n_factures = int((ok_docs["type_detecte"] == "facture").sum())

    return {
        "documents_extraits": int(len(ok_docs)),
        "documents_echantillon": int(len(docs)),
        "taux_extraction_pct": round(len(ok_docs) / len(docs) * 100, 1) if len(docs) else 0,
        "montant_total_extrait": round(montant_total, 2),
        "nb_bons_livraison": n_livraisons,
        "nb_factures": n_factures,
        "nb_lignes_produits": int(len(items)),
    }


@router.get("/documents")
def get_documents(statut: str | None = None, type_detecte: str | None = None):
    """Liste des documents extraits, avec filtres optionnels."""
    docs = _load_docs()

    if statut:
        docs = docs[docs["statut"] == statut]
    if type_detecte:
        docs = docs[docs["type_detecte"] == type_detecte]

    # astype(object) avant where() : sur une colonne float64, assigner None
    # à la place d'un NaN redonne un NaN (pandas reconvertit) — object l'évite
    docs = docs.astype(object).where(pd.notna(docs), None)
    return docs.to_dict(orient="records")


@router.get("/documents/{fichier}/{onglet}/items")
def get_document_items(fichier: str, onglet: str):
    """Lignes produits d'un document précis."""
    items = _load_items()
    if items.empty:
        return []
    filtered = items[(items["fichier"] == fichier) & (items["onglet"] == onglet)]
    filtered = filtered.astype(object).where(pd.notna(filtered), None)
    return filtered.to_dict(orient="records")