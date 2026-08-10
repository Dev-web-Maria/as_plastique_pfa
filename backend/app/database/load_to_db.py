"""
Script de chargement — Sprint 3
Lit les CSV produits par run_extraction.py et peuple la base SQLite (schéma
en constellation défini dans schema.py). Gère les doublons de dimensions
(un même produit/client/date ne doit être inséré qu'une fois).

Charge TOUTES les lignes, y compris celles en statut extraction_incomplete
ou erreur_extraction — la colonne statut_extraction permet de les filtrer
plus tard sans perdre la traçabilité (cohérent avec l'approche du projet :
ne jamais faire disparaître silencieusement une donnée).

Lancer depuis backend/ (venv activé), après schema.py :
    python app/database/load_to_db.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("../data/processed/as_plastique.db")

DOCS_CSV = Path("../data/processed/extraction_full_documents.csv")
ITEMS_CSV = Path("../data/processed/extraction_full_items.csv")
RELEVES_DOCS_CSV = Path("../data/processed/extraction_full_releves_documents.csv")
RELEVES_ITEMS_CSV = Path("../data/processed/extraction_full_releves_items.csv")
REGLEMENTS_CSV = Path("../data/processed/extraction_full_reglements.csv")


# ---------------------------------------------------------------------------
# Caches en mémoire (évite une requête SQL par ligne pour les dimensions)
# ---------------------------------------------------------------------------

class Caches:
    def __init__(self):
        self.source = {}   # (fichier, onglet) -> source_id
        self.date = {}     # date_str -> date_id
        self.produit = {}  # (designation, unite) -> produit_id
        self.client = {}   # nom -> client_id


def get_or_create_source(conn, caches, fichier, onglet, type_document):
    key = (fichier, onglet)
    if key in caches.source:
        return caches.source[key]
    conn.execute(
        "INSERT OR IGNORE INTO dim_source (fichier, onglet, type_document) VALUES (?, ?, ?)",
        (fichier, onglet, type_document),
    )
    source_id = conn.execute(
        "SELECT source_id FROM dim_source WHERE fichier = ? AND onglet = ?", (fichier, onglet)
    ).fetchone()[0]
    caches.source[key] = source_id
    return source_id


def get_or_create_date(conn, caches, date_str):
    if not date_str or pd.isna(date_str):
        return None
    if date_str in caches.date:
        return caches.date[date_str]
    try:
        jour, mois, annee = (int(x) for x in date_str.split("/"))
    except (ValueError, AttributeError):
        return None  # date malformée — on n'invente pas de valeur

    if annee < 100:
        # Année écrite sur 2 chiffres (ex: '07/01/19') — toutes les dates de
        # ce corpus sont dans les années 2000-2020, donc extension sûre.
        annee += 2000

    # Rejette les dates clairement invalides (ex: jour=0, mois=13...) plutôt
    # que de les enregistrer et fausser silencieusement les agrégations.
    if not (1 <= jour <= 31 and 1 <= mois <= 12 and 2000 <= annee <= 2030):
        return None

    trimestre = (mois - 1) // 3 + 1

    conn.execute(
        "INSERT OR IGNORE INTO dim_date (date, jour, mois, annee, trimestre) VALUES (?, ?, ?, ?, ?)",
        (date_str, jour, mois, annee, trimestre),
    )
    date_id = conn.execute("SELECT date_id FROM dim_date WHERE date = ?", (date_str,)).fetchone()[0]
    caches.date[date_str] = date_id
    return date_id


def get_or_create_produit(conn, caches, designation, unite):
    if not designation or pd.isna(designation) or str(designation).strip() == "":
        return None
    designation = str(designation).strip()
    unite = str(unite).strip() if pd.notna(unite) else None
    key = (designation, unite)
    if key in caches.produit:
        return caches.produit[key]
    conn.execute(
        "INSERT OR IGNORE INTO dim_produit (designation, unite) VALUES (?, ?)", (designation, unite)
    )
    produit_id = conn.execute(
        "SELECT produit_id FROM dim_produit WHERE designation = ?", (designation,)
    ).fetchone()[0]
    caches.produit[key] = produit_id
    return produit_id


def get_or_create_client(conn, caches, nom):
    if not nom or pd.isna(nom) or str(nom).strip() == "":
        return None
    nom = str(nom).strip()
    if nom in caches.client:
        return caches.client[nom]
    conn.execute("INSERT OR IGNORE INTO dim_client (nom) VALUES (?)", (nom,))
    client_id = conn.execute("SELECT client_id FROM dim_client WHERE nom = ?", (nom,)).fetchone()[0]
    caches.client[nom] = client_id
    return client_id


def none_if_nan(value):
    return None if pd.isna(value) else value


def reset_tables(conn):
    """Vide toutes les tables avant rechargement — rend le script idempotent
    même si l'ancien fichier .db n'a pas pu être supprimé (ex: verrouillé par
    DB Browser encore ouvert). Ordre important : tables enfants avant tables
    parentes, à cause des clés étrangères."""
    tables_dans_l_ordre = [
        "fait_lignes_vente", "fait_documents_vente",
        "fait_factures_impayees", "fait_releves",
        "fait_reglements",
        "dim_produit", "dim_client", "dim_date", "dim_source",
    ]
    for table in tables_dans_l_ordre:
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sqlite_sequence")  # remet les compteurs AUTOINCREMENT à zéro
    conn.commit()
    print("🔄 Tables vidées avant rechargement (script idempotent)\n")


# ---------------------------------------------------------------------------
# Chargement : bons de livraison / factures
# ---------------------------------------------------------------------------

def load_documents_vente(conn, caches):
    if not DOCS_CSV.exists():
        print("⚠ extraction_sample_documents.csv introuvable, étape ignorée")
        return

    docs = pd.read_csv(DOCS_CSV, dtype={"doc_number": str})
    items = pd.read_csv(ITEMS_CSV, dtype={"doc_number": str}) if ITEMS_CSV.exists() else pd.DataFrame()

    doc_id_par_source = {}  # (fichier, onglet) -> doc_id

    for _, row in docs.iterrows():
        source_id = get_or_create_source(conn, caches, row["fichier"], row["onglet"], row["type_detecte"])
        date_id = get_or_create_date(conn, caches, none_if_nan(row.get("date")))

        cursor = conn.execute(
            """INSERT INTO fait_documents_vente
               (source_id, type_document, doc_number, date_id, total_ht, tva, net_a_payer, statut_extraction)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source_id, row["type_detecte"], none_if_nan(row.get("doc_number")), date_id,
                none_if_nan(row.get("total_ht")), none_if_nan(row.get("tva")),
                none_if_nan(row.get("net_a_payer")), row["statut"],
            ),
        )
        doc_id_par_source[(row["fichier"], row["onglet"])] = cursor.lastrowid

    n_lignes = 0
    for _, row in items.iterrows():
        doc_id = doc_id_par_source.get((row["fichier"], row["onglet"]))
        if doc_id is None:
            continue  # ne devrait pas arriver, sécurité
        produit_id = get_or_create_produit(conn, caches, row.get("designation"), row.get("unite"))
        conn.execute(
            "INSERT INTO fait_lignes_vente (doc_id, produit_id, quantite, pu, montant) VALUES (?, ?, ?, ?, ?)",
            (doc_id, produit_id, none_if_nan(row.get("quantite")), none_if_nan(row.get("pu")), none_if_nan(row.get("montant"))),
        )
        n_lignes += 1

    print(f"✅ {len(docs)} documents (bon_livraison/facture), {n_lignes} lignes produits chargés")


# ---------------------------------------------------------------------------
# Chargement : relevés de factures impayées
# ---------------------------------------------------------------------------

def load_releves(conn, caches):
    if not RELEVES_DOCS_CSV.exists():
        print("⚠ extraction_sample_releves_documents.csv introuvable, étape ignorée")
        return

    releves = pd.read_csv(RELEVES_DOCS_CSV)
    items = pd.read_csv(RELEVES_ITEMS_CSV, dtype={"numero_facture": str}) if RELEVES_ITEMS_CSV.exists() else pd.DataFrame()

    releve_id_par_source = {}

    for _, row in releves.iterrows():
        source_id = get_or_create_source(conn, caches, row["fichier"], row["onglet"], "releve_factures_impayees")
        client_id = get_or_create_client(conn, caches, none_if_nan(row.get("client")))
        date_releve_id = get_or_create_date(conn, caches, none_if_nan(row.get("date_releve")))

        cursor = conn.execute(
            """INSERT INTO fait_releves (source_id, client_id, date_releve_id, total_a_payer, statut_extraction)
               VALUES (?, ?, ?, ?, ?)""",
            (source_id, client_id, date_releve_id, none_if_nan(row.get("total_a_payer")), row["statut"]),
        )
        releve_id_par_source[(row["fichier"], row["onglet"])] = cursor.lastrowid

    n_lignes = 0
    for _, row in items.iterrows():
        releve_id = releve_id_par_source.get((row["fichier"], row["onglet"]))
        if releve_id is None:
            continue
        date_facture_id = get_or_create_date(conn, caches, none_if_nan(row.get("date_facture")))
        conn.execute(
            """INSERT INTO fait_factures_impayees
               (releve_id, date_facture_id, numero_facture, montant, reference_paiement)
               VALUES (?, ?, ?, ?, ?)""",
            (releve_id, date_facture_id, none_if_nan(row.get("numero_facture")),
             none_if_nan(row.get("montant")), none_if_nan(row.get("reference_paiement"))),
        )
        n_lignes += 1

    print(f"✅ {len(releves)} relevés, {n_lignes} lignes factures impayées chargés")


# ---------------------------------------------------------------------------
# Chargement : règlements
# ---------------------------------------------------------------------------

def load_reglements(conn, caches):
    if not REGLEMENTS_CSV.exists():
        print("⚠ extraction_sample_reglements.csv introuvable, étape ignorée")
        return

    reglements = pd.read_csv(REGLEMENTS_CSV, dtype={"reference_facture": str})
    if reglements.empty:
        print("ℹ️ Aucune ligne de règlement à charger")
        return

    for _, row in reglements.iterrows():
        source_id = get_or_create_source(conn, caches, row["fichier"], row["onglet"], "reglement_facture")
        conn.execute(
            """INSERT INTO fait_reglements (source_id, reference_facture, montant, mode_paiement, texte_brut)
               VALUES (?, ?, ?, ?, ?)""",
            (source_id, none_if_nan(row.get("reference_facture")), none_if_nan(row.get("montant")),
             none_if_nan(row.get("mode_paiement")), none_if_nan(row.get("texte_brut"))),
        )

    print(f"✅ {len(reglements)} lignes de règlements chargées")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def load_all():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    reset_tables(conn)
    caches = Caches()
    try:
        load_documents_vente(conn, caches)
        load_releves(conn, caches)
        load_reglements(conn, caches)
        conn.commit()

        print("\n" + "=" * 50)
        print("RÉSUMÉ DE LA BASE")
        print("=" * 50)
        for table in ["dim_source", "dim_date", "dim_produit", "dim_client",
                      "fait_documents_vente", "fait_lignes_vente",
                      "fait_releves", "fait_factures_impayees", "fait_reglements"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:28} {n}")
        print("=" * 50)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    load_all()