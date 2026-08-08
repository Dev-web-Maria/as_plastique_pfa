"""
Schéma de base de données (étoile) — Sprint 3
Crée la base SQLite et ses tables. Utilise sqlite3 (stdlib) plutôt qu'un ORM :
suffisant pour un prototype, zéro dépendance supplémentaire.

Lancer depuis backend/ (venv activé) :
    python app/database/schema.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("../data/processed/as_plastique.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- Supprime les tables existantes avant recréation : indispensable tant que
-- le schéma évolue (CREATE TABLE IF NOT EXISTS ne modifierait jamais une
-- table déjà existante avec une ancienne structure — les nouvelles colonnes
-- resteraient absentes silencieusement). Sans risque ici : toutes les
-- données sont ré-extraites depuis data/raw à chaque fois, rien n'est perdu.
-- Ordre : tables enfants avant tables parentes (contraintes de clé étrangère).
DROP TABLE IF EXISTS fait_lignes_vente;
DROP TABLE IF EXISTS fait_documents_vente;
DROP TABLE IF EXISTS fait_factures_impayees;
DROP TABLE IF EXISTS fait_releves;
DROP TABLE IF EXISTS fait_reglements;
DROP TABLE IF EXISTS dim_produit;
DROP TABLE IF EXISTS dim_client;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_source;

-- ============================================================
-- DIMENSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_date (
    date_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,   -- format JJ/MM/AAAA, tel qu'extrait
    jour        INTEGER,
    mois        INTEGER,
    annee       INTEGER,
    trimestre   INTEGER
);

CREATE TABLE IF NOT EXISTS dim_produit (
    produit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    designation TEXT NOT NULL UNIQUE,
    unite       TEXT
);

CREATE TABLE IF NOT EXISTS dim_client (
    client_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_source (
    source_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    fichier       TEXT NOT NULL,
    onglet        TEXT NOT NULL,
    type_document TEXT NOT NULL,
    UNIQUE (fichier, onglet)
);

-- ============================================================
-- FAITS — bons de livraison / factures
-- ============================================================

CREATE TABLE IF NOT EXISTS fait_documents_vente (
    doc_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id        INTEGER NOT NULL REFERENCES dim_source(source_id),
    type_document    TEXT NOT NULL CHECK (type_document IN ('bon_livraison', 'facture')),
    doc_number       TEXT,
    date_id          INTEGER REFERENCES dim_date(date_id),
    total_ht         REAL,
    tva              REAL,
    net_a_payer      REAL,
    tva_calculee     INTEGER NOT NULL DEFAULT 0,  -- 1 si déduite (total_ht * 20%), pas extraite
    net_a_payer_calcule INTEGER NOT NULL DEFAULT 0,
    statut_extraction TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fait_lignes_vente (
    ligne_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      INTEGER NOT NULL REFERENCES fait_documents_vente(doc_id),
    produit_id  INTEGER REFERENCES dim_produit(produit_id),
    quantite    REAL,
    pu          REAL,
    montant     REAL,
    pu_calcule      INTEGER NOT NULL DEFAULT 0,  -- 1 si déduit (montant / quantité)
    montant_calcule INTEGER NOT NULL DEFAULT 0   -- 1 si déduit (quantité * pu)
);

-- ============================================================
-- FAITS — relevés de factures impayées
-- ============================================================

CREATE TABLE IF NOT EXISTS fait_releves (
    releve_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id         INTEGER NOT NULL REFERENCES dim_source(source_id),
    client_id         INTEGER REFERENCES dim_client(client_id),
    date_releve_id    INTEGER REFERENCES dim_date(date_id),
    total_a_payer     REAL,
    total_a_payer_calcule INTEGER NOT NULL DEFAULT 0,  -- 1 si déduit (somme des factures listées)
    statut_extraction TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fait_factures_impayees (
    ligne_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    releve_id           INTEGER NOT NULL REFERENCES fait_releves(releve_id),
    date_facture_id     INTEGER REFERENCES dim_date(date_id),
    numero_facture      TEXT,
    montant             REAL,
    reference_paiement  TEXT,
    date_facture_recuperee INTEGER NOT NULL DEFAULT 0  -- 1 si retrouvée via fait_documents_vente
);

-- ============================================================
-- FAITS — règlements (grille plate, pas de header/lignes)
-- ============================================================

CREATE TABLE IF NOT EXISTS fait_reglements (
    reglement_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id         INTEGER NOT NULL REFERENCES dim_source(source_id),
    reference_facture TEXT,
    montant           REAL,
    mode_paiement     TEXT,
    texte_brut        TEXT
);

-- ============================================================
-- INDEX utiles pour les requêtes analytiques
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_lignes_vente_doc ON fait_lignes_vente(doc_id);
CREATE INDEX IF NOT EXISTS idx_lignes_vente_produit ON fait_lignes_vente(produit_id);
CREATE INDEX IF NOT EXISTS idx_documents_vente_date ON fait_documents_vente(date_id);
CREATE INDEX IF NOT EXISTS idx_documents_vente_type ON fait_documents_vente(type_document);
CREATE INDEX IF NOT EXISTS idx_factures_impayees_releve ON fait_factures_impayees(releve_id);
CREATE INDEX IF NOT EXISTS idx_releves_client ON fait_releves(client_id);
"""


def create_schema(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        print(f"✅ Schéma créé avec succès dans {db_path.resolve()}")

        # Vérification : liste les tables créées
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nTables créées ({len(tables)}) :")
        for t in tables:
            print(f"  - {t}")
    finally:
        conn.close()


if __name__ == "__main__":
    create_schema()