"""
Schéma de base de données (constellation) — Sprint 3+5
Crée la base SQLite et ses tables. DROP TABLE avant recréation à chaque
lancement : indispensable tant que le schéma évolue (sans ça, une table déjà
existante garderait son ancienne structure, sans les nouvelles colonnes).
Sans risque : toutes les données sont ré-extraites depuis data/raw et
data/raw_externe à chaque fois, rien n'est perdu.

Lancer depuis backend/ (venv activé) :
    python app/database/schema.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("../data/processed/as_plastique.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- Ordre important : toute table ENFANT (qui référence une autre via clé
-- étrangère) doit être supprimée AVANT la table qu'elle référence. Bug réel
-- rencontré : fait_grand_livre référence fait_documents_vente — la
-- supprimer après fait_documents_vente déclenche une erreur de contrainte
-- de clé étrangère dès qu'il y a de vraies données en base.
DROP TABLE IF EXISTS fait_lignes_vente;
DROP TABLE IF EXISTS fait_grand_livre;
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

CREATE TABLE dim_date (
    date_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,
    jour        INTEGER,
    mois        INTEGER,
    annee       INTEGER,
    trimestre   INTEGER
);

CREATE TABLE dim_produit (
    produit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    designation TEXT NOT NULL UNIQUE,
    unite       TEXT
);

CREATE TABLE dim_client (
    client_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_source (
    source_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    fichier       TEXT NOT NULL,
    onglet        TEXT NOT NULL,
    type_document TEXT NOT NULL,
    UNIQUE (fichier, onglet)
);

-- ============================================================
-- FAITS — bons de livraison / factures
-- ============================================================

CREATE TABLE fait_documents_vente (
    doc_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id        INTEGER NOT NULL REFERENCES dim_source(source_id),
    type_document    TEXT NOT NULL CHECK (type_document IN ('bon_livraison', 'facture')),
    doc_number       TEXT,
    date_id          INTEGER REFERENCES dim_date(date_id),
    client_id        INTEGER REFERENCES dim_client(client_id),
    total_ht         REAL,
    tva              REAL,
    net_a_payer      REAL,
    tva_calculee     INTEGER NOT NULL DEFAULT 0,
    net_a_payer_calcule INTEGER NOT NULL DEFAULT 0,
    statut_extraction TEXT NOT NULL
);

CREATE TABLE fait_lignes_vente (
    ligne_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      INTEGER NOT NULL REFERENCES fait_documents_vente(doc_id),
    produit_id  INTEGER REFERENCES dim_produit(produit_id),
    quantite    REAL,
    pu          REAL,
    montant     REAL,
    pu_calcule      INTEGER NOT NULL DEFAULT 0,
    montant_calcule INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- FAITS — relevés de factures impayées
-- ============================================================

CREATE TABLE fait_releves (
    releve_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id         INTEGER NOT NULL REFERENCES dim_source(source_id),
    client_id         INTEGER REFERENCES dim_client(client_id),
    date_releve_id    INTEGER REFERENCES dim_date(date_id),
    total_a_payer     REAL,
    total_a_payer_calcule INTEGER NOT NULL DEFAULT 0,
    statut_extraction TEXT NOT NULL
);

CREATE TABLE fait_factures_impayees (
    ligne_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    releve_id           INTEGER NOT NULL REFERENCES fait_releves(releve_id),
    date_facture_id     INTEGER REFERENCES dim_date(date_id),
    numero_facture      TEXT,
    montant             REAL,
    reference_paiement  TEXT,
    date_facture_recuperee INTEGER NOT NULL DEFAULT 0,
    statut_reel           TEXT,
    solde_reel             REAL,
    montant_regle_associe  REAL
);

-- ============================================================
-- FAITS — règlements (grille plate, extraits d'un fichier Excel source)
-- ============================================================

CREATE TABLE fait_reglements (
    reglement_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id         INTEGER NOT NULL REFERENCES dim_source(source_id),
    reference_facture TEXT,
    montant           REAL,
    mode_paiement     TEXT,
    texte_brut        TEXT
);

-- ============================================================
-- FAIT — grand livre client (source externe, Sprint 5)
-- ============================================================

CREATE TABLE fait_grand_livre (
    ligne_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id           INTEGER REFERENCES dim_client(client_id),
    numero_facture       TEXT,
    date_facture_id      INTEGER REFERENCES dim_date(date_id),
    montant_facture      REAL,
    statut               TEXT,
    date_reglement_id    INTEGER REFERENCES dim_date(date_id),
    montant_regle        REAL,
    solde                REAL,
    mode_paiement         TEXT,
    reference_reglement   TEXT,
    doc_id_rapproche      INTEGER REFERENCES fait_documents_vente(doc_id)
);

-- ============================================================
-- INDEX utiles pour les requêtes analytiques
-- ============================================================

CREATE INDEX idx_lignes_vente_doc ON fait_lignes_vente(doc_id);
CREATE INDEX idx_lignes_vente_produit ON fait_lignes_vente(produit_id);
CREATE INDEX idx_documents_vente_date ON fait_documents_vente(date_id);
CREATE INDEX idx_documents_vente_type ON fait_documents_vente(type_document);
CREATE INDEX idx_factures_impayees_releve ON fait_factures_impayees(releve_id);
CREATE INDEX idx_releves_client ON fait_releves(client_id);
CREATE INDEX idx_grand_livre_client ON fait_grand_livre(client_id);
CREATE INDEX idx_grand_livre_doc ON fait_grand_livre(doc_id_rapproche);
"""


def create_schema(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        print(f"✅ Schéma créé avec succès dans {db_path.resolve()}")

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nTables créées ({len(tables)}) :")
        for t in tables:
            print(f"  - {t}")
    finally:
        conn.close()


if __name__ == "__main__":
    create_schema()