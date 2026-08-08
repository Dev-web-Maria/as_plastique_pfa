"""
Script d'enrichissement — Sprint 3 (post-extraction)
Complète certaines valeurs manquantes UNIQUEMENT quand elles sont déductibles
de données déjà présentes (calcul ou croisement entre tables) — jamais
inventées. Chaque valeur ajoutée est tracée via une colonne *_calculee /
*_recuperee, pour ne jamais confondre une donnée extraite d'une donnée déduite.

Opérations réalisées :
1. TVA / Net à payer déduits du Total H.T. (taux 20%, standard marocain,
   observé sur 100% des documents où les 3 valeurs sont présentes)
2. Montant / PU déduits l'un de l'autre quand la quantité est connue
3. Date de facture manquante (relevés) récupérée par croisement avec le
   numéro de document dans fait_documents_vente
4. Total à payer d'un relevé recalculé comme somme des factures listées,
   quand la valeur n'a pas pu être extraite du document

Lancer depuis backend/ (venv activé), après load_to_db.py :
    python app/database/enrichissement.py
"""

import re
import sqlite3
from pathlib import Path

DB_PATH = Path("../data/processed/as_plastique.db")
TAUX_TVA = 0.20  # 20%, observé sur 100% des documents avec TVA renseignée


def normalize_ref(text: str) -> str | None:
    """Normalise une référence pour comparaison malgré les variations de
    format ('003' vs '0003' vs '3', espaces, tirets...)."""
    if not text:
        return None
    cleaned = re.sub(r"[^A-Z0-9]", "", str(text).upper())
    return cleaned.lstrip("0") or "0"


# ---------------------------------------------------------------------------
# 1. TVA / Net à payer déduits du Total H.T.
# ---------------------------------------------------------------------------

def enrichir_tva_net_a_payer(conn) -> dict:
    rows = conn.execute(
        """SELECT doc_id, total_ht, tva, net_a_payer FROM fait_documents_vente
           WHERE total_ht IS NOT NULL AND (tva IS NULL OR net_a_payer IS NULL)"""
    ).fetchall()

    n_tva, n_net = 0, 0
    for doc_id, total_ht, tva, net_a_payer in rows:
        new_tva = tva
        new_net = net_a_payer
        if tva is None:
            new_tva = round(total_ht * TAUX_TVA, 2)
            n_tva += 1
        if net_a_payer is None:
            new_net = round(total_ht + new_tva, 2)
            n_net += 1
        conn.execute(
            """UPDATE fait_documents_vente
               SET tva = ?, net_a_payer = ?,
                   tva_calculee = CASE WHEN ? THEN 1 ELSE tva_calculee END,
                   net_a_payer_calcule = CASE WHEN ? THEN 1 ELSE net_a_payer_calcule END
               WHERE doc_id = ?""",
            (new_tva, new_net, tva is None, net_a_payer is None, doc_id),
        )

    return {"tva_calculees": n_tva, "net_a_payer_calcules": n_net}


# ---------------------------------------------------------------------------
# 2. Montant / PU déduits l'un de l'autre
# ---------------------------------------------------------------------------

def enrichir_montant_pu(conn) -> dict:
    rows = conn.execute(
        """SELECT ligne_id, quantite, pu, montant FROM fait_lignes_vente
           WHERE quantite IS NOT NULL AND quantite > 0
             AND (pu IS NULL OR montant IS NULL)
             AND NOT (pu IS NULL AND montant IS NULL)"""  # au moins un des deux doit être connu
    ).fetchall()

    n_pu, n_montant = 0, 0
    for ligne_id, quantite, pu, montant in rows:
        if pu is None and montant is not None:
            new_pu = round(montant / quantite, 2)
            conn.execute(
                "UPDATE fait_lignes_vente SET pu = ?, pu_calcule = 1 WHERE ligne_id = ?",
                (new_pu, ligne_id),
            )
            n_pu += 1
        elif montant is None and pu is not None:
            new_montant = round(quantite * pu, 2)
            conn.execute(
                "UPDATE fait_lignes_vente SET montant = ?, montant_calcule = 1 WHERE ligne_id = ?",
                (new_montant, ligne_id),
            )
            n_montant += 1

    return {"pu_calcules": n_pu, "montants_calcules": n_montant}


# ---------------------------------------------------------------------------
# 3. Date de facture manquante récupérée par croisement
# ---------------------------------------------------------------------------

def enrichir_date_facture_impayee(conn) -> dict:
    # Index numero normalisé -> date_id, construit depuis fait_documents_vente
    docs = conn.execute(
        "SELECT doc_number, date_id FROM fait_documents_vente WHERE doc_number IS NOT NULL AND date_id IS NOT NULL"
    ).fetchall()
    index_par_numero = {}
    for doc_number, date_id in docs:
        norm = normalize_ref(doc_number)
        if norm and norm not in index_par_numero:  # garde la 1ère correspondance en cas de doublon
            index_par_numero[norm] = date_id

    a_completer = conn.execute(
        """SELECT ligne_id, numero_facture FROM fait_factures_impayees
           WHERE date_facture_id IS NULL AND numero_facture IS NOT NULL"""
    ).fetchall()

    n = 0
    for ligne_id, numero_facture in a_completer:
        norm = normalize_ref(numero_facture)
        date_id = index_par_numero.get(norm)
        if date_id:
            conn.execute(
                """UPDATE fait_factures_impayees
                   SET date_facture_id = ?, date_facture_recuperee = 1
                   WHERE ligne_id = ?""",
                (date_id, ligne_id),
            )
            n += 1

    return {"dates_recuperees": n}


# ---------------------------------------------------------------------------
# 4. Total à payer d'un relevé recalculé si absent
# ---------------------------------------------------------------------------

def enrichir_total_a_payer_releve(conn) -> dict:
    a_completer = conn.execute(
        "SELECT releve_id FROM fait_releves WHERE total_a_payer IS NULL"
    ).fetchall()

    n = 0
    for (releve_id,) in a_completer:
        total = conn.execute(
            "SELECT SUM(montant) FROM fait_factures_impayees WHERE releve_id = ? AND montant IS NOT NULL",
            (releve_id,),
        ).fetchone()[0]
        if total is not None:
            conn.execute(
                """UPDATE fait_releves SET total_a_payer = ?, total_a_payer_calcule = 1
                   WHERE releve_id = ?""",
                (round(total, 2), releve_id),
            )
            n += 1

    return {"totaux_a_payer_calcules": n}


# ---------------------------------------------------------------------------
# Rapport de qualité des données
# ---------------------------------------------------------------------------

COLONNES_SUIVIES = {
    "fait_documents_vente": ["date_id", "tva", "net_a_payer"],
    "fait_lignes_vente": ["pu", "montant"],
    "fait_factures_impayees": ["date_facture_id", "montant", "reference_paiement"],
    "fait_releves": ["client_id", "date_releve_id", "total_a_payer"],
}


def taux_nulls(conn) -> dict:
    resultat = {}
    for table, colonnes in COLONNES_SUIVIES.items():
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        resultat[table] = {}
        for col in colonnes:
            n_null = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[0]
            pct = round(n_null / total * 100, 1) if total else 0
            resultat[table][col] = (n_null, total, pct)
    return resultat


def afficher_rapport(titre: str, rapport: dict):
    print(f"\n--- {titre} ---")
    for table, colonnes in rapport.items():
        print(f"  {table}")
        for col, (n_null, total, pct) in colonnes.items():
            print(f"    {col:22} {n_null}/{total} NULL ({pct}%)")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def enrichir_tout():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        avant = taux_nulls(conn)

        stats = {}
        stats.update(enrichir_tva_net_a_payer(conn))
        stats.update(enrichir_montant_pu(conn))
        stats.update(enrichir_date_facture_impayee(conn))
        stats.update(enrichir_total_a_payer_releve(conn))
        conn.commit()

        apres = taux_nulls(conn)

        print("=" * 60)
        print("RÉSUMÉ DE L'ENRICHISSEMENT")
        print("=" * 60)
        for cle, val in stats.items():
            print(f"  {cle:28} {val}")

        afficher_rapport("AVANT enrichissement", avant)
        afficher_rapport("APRÈS enrichissement", apres)
        print("=" * 60)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    enrichir_tout()