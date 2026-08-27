"""
Rapprochement du grand livre client — Sprint 5
Charge le fichier grand livre (source externe, validée à 85,2% de
correspondance avec les données déjà extraites), l'insère dans
fait_grand_livre, et enrichit fait_factures_impayees avec l'état réel
(statut_reel, solde_reel, montant_regle_associe) quand un rapprochement
fiable est trouvé — sans jamais écraser le montant original du relevé
(traçabilité préservée).

Lancer depuis backend/ (venv activé), après load_to_db.py :
    python app/database/charger_grand_livre.py
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("../data/processed/as_plastique.db")
GRAND_LIVRE_XLSX = Path("../data/raw_externe/grand_livre_client.xlsx")
FEUILLE = "Grand_Livre_Client"
LIGNE_ENTETE = 16


def normalize_ref(text) -> str:
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(text).upper()).lstrip("0") or "0"


def normalize_nom(text) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).upper()).strip()


def get_or_create_date(conn, date_obj):
    if pd.isna(date_obj):
        return None
    date_str = date_obj.strftime("%d/%m/%Y")
    jour, mois, annee = date_obj.day, date_obj.month, date_obj.year
    trimestre = (mois - 1) // 3 + 1

    conn.execute(
        "INSERT OR IGNORE INTO dim_date (date, jour, mois, annee, trimestre) VALUES (?, ?, ?, ?, ?)",
        (date_str, jour, mois, annee, trimestre),
    )
    return conn.execute("SELECT date_id FROM dim_date WHERE date = ?", (date_str,)).fetchone()[0]


def charger_index_clients_existants(conn):
    """Charge tous les clients déjà connus, indexés par nom normalisé
    (casse + espaces), pour retrouver le bon client_id même si le nom dans
    le grand livre n'est pas écrit exactement comme dans la base existante."""
    index = {}
    for client_id, nom in conn.execute("SELECT client_id, nom FROM dim_client"):
        index[normalize_nom(nom)] = client_id
    return index


def get_or_create_client(conn, nom, index_clients_existants):
    if not nom or pd.isna(nom):
        return None
    nom_brut = str(nom).strip()
    cle = normalize_nom(nom_brut)

    if cle in index_clients_existants:
        return index_clients_existants[cle]

    # Aucun client existant ne correspond : on en crée un nouveau, avec le
    # nom tel qu'écrit dans le grand livre (cohérent avec la convention déjà
    # utilisée par l'ETL, qui garde le nom brut sans normalisation forcée)
    conn.execute("INSERT OR IGNORE INTO dim_client (nom) VALUES (?)", (nom_brut,))
    row = conn.execute("SELECT client_id FROM dim_client WHERE nom = ?", (nom_brut,)).fetchone()
    client_id = row[0] if row else None
    index_clients_existants[cle] = client_id  # cache pour les lignes suivantes
    return client_id


def construire_index_documents(conn):
    df = pd.read_sql(
        """SELECT dv.doc_id, dv.doc_number, dv.net_a_payer, dv.total_ht, dd.annee
           FROM fait_documents_vente dv
           LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
           WHERE dv.type_document = 'facture' AND dv.doc_number IS NOT NULL""",
        conn,
    )
    index = {}
    for _, row in df.iterrows():
        norm = normalize_ref(row["doc_number"])
        index.setdefault(norm, []).append({
            "doc_id": row["doc_id"],
            "montant": row["net_a_payer"] or row["total_ht"],
            "annee": row["annee"],
        })
    return index


def trouver_doc_id(index_documents, numero_facture, annee_gl, montant_gl):
    norm = normalize_ref(numero_facture)
    candidats = index_documents.get(norm)
    if not candidats:
        return None

    candidats_meme_annee = [c for c in candidats if c["annee"] == annee_gl]
    a_tester = candidats_meme_annee if candidats_meme_annee else candidats

    for c in a_tester:
        if c["montant"] is not None and abs(float(c["montant"]) - montant_gl) < 1.0:
            return c["doc_id"]
    return None


def charger_grand_livre_fichier():
    df = pd.read_excel(GRAND_LIVRE_XLSX, sheet_name=FEUILLE, header=LIGNE_ENTETE)
    return df.dropna(subset=["client"]).reset_index(drop=True)


def charger():
    if not GRAND_LIVRE_XLSX.exists():
        print(f"⚠ Fichier introuvable : {GRAND_LIVRE_XLSX.resolve()}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("DELETE FROM fait_grand_livre")
    conn.execute("UPDATE fait_factures_impayees SET statut_reel = NULL, solde_reel = NULL, montant_regle_associe = NULL")
    conn.commit()

    grand_livre = charger_grand_livre_fichier()
    index_documents = construire_index_documents(conn)
    index_clients_existants = charger_index_clients_existants(conn)

    n_rapproches_docs = 0
    n_rapproches_impayes = 0

    factures_impayees = pd.read_sql(
        """SELECT fi.ligne_id, fi.numero_facture, fr.client_id
           FROM fait_factures_impayees fi
           JOIN fait_releves fr ON fi.releve_id = fr.releve_id
           WHERE fi.numero_facture IS NOT NULL""",
        conn,
    )
    index_impayees = {}
    for _, row in factures_impayees.iterrows():
        cle = (normalize_ref(row["numero_facture"]), row["client_id"])
        index_impayees.setdefault(cle, []).append(row["ligne_id"])

    for _, ligne in grand_livre.iterrows():
        client_id = get_or_create_client(conn, ligne["client"], index_clients_existants)
        date_facture_id = get_or_create_date(conn, ligne["date_facture"])
        date_reglement_id = get_or_create_date(conn, ligne.get("date_reglement"))

        montant_facture = float(ligne["montant_facture"]) if pd.notna(ligne["montant_facture"]) else None
        annee_gl = ligne["date_facture"].year if pd.notna(ligne["date_facture"]) else None

        doc_id = trouver_doc_id(index_documents, ligne["numero_facture"], annee_gl, montant_facture) \
            if montant_facture is not None else None
        if doc_id:
            n_rapproches_docs += 1

        conn.execute(
            """INSERT INTO fait_grand_livre
               (client_id, numero_facture, date_facture_id, montant_facture, statut,
                date_reglement_id, montant_regle, solde, mode_paiement, reference_reglement, doc_id_rapproche)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id, str(ligne["numero_facture"]), date_facture_id, montant_facture,
                ligne.get("statut"),
                date_reglement_id,
                float(ligne["montant_regle"]) if pd.notna(ligne.get("montant_regle")) else None,
                float(ligne["solde"]) if pd.notna(ligne.get("solde")) else None,
                ligne.get("mode_paiement"), ligne.get("reference_reglement"), doc_id,
            ),
        )

        norm = normalize_ref(ligne["numero_facture"])
        cle = (norm, client_id)
        for ligne_id_impayee in index_impayees.get(cle, []):
            conn.execute(
                """UPDATE fait_factures_impayees
                   SET statut_reel = ?, solde_reel = ?, montant_regle_associe = ?
                   WHERE ligne_id = ?""",
                (
                    ligne.get("statut"),
                    float(ligne["solde"]) if pd.notna(ligne.get("solde")) else None,
                    float(ligne["montant_regle"]) if pd.notna(ligne.get("montant_regle")) else None,
                    ligne_id_impayee,
                ),
            )
            n_rapproches_impayes += 1

    conn.commit()

    n_grand_livre = len(grand_livre)
    print("=" * 60)
    print("RAPPROCHEMENT DU GRAND LIVRE CLIENT")
    print("=" * 60)
    print(f"Lignes du grand livre chargées         : {n_grand_livre}")
    print(f"Rapprochées avec fait_documents_vente  : {n_rapproches_docs}/{n_grand_livre} "
          f"({n_rapproches_docs/n_grand_livre*100:.1f}%)")
    print(f"Lignes fait_factures_impayees enrichies : {n_rapproches_impayes}")

    total_snapshot = conn.execute("SELECT SUM(montant) FROM fait_factures_impayees").fetchone()[0] or 0
    total_solde_reel = conn.execute(
        "SELECT SUM(solde_reel) FROM fait_factures_impayees WHERE solde_reel IS NOT NULL"
    ).fetchone()[0] or 0
    total_snapshot_rapproche = conn.execute(
        "SELECT SUM(montant) FROM fait_factures_impayees WHERE solde_reel IS NOT NULL"
    ).fetchone()[0] or 0
    montant_regularise = total_snapshot_rapproche - total_solde_reel

    print(f"\nMontant total listé impayé (snapshot relevés) : {total_snapshot:,.2f} DH")
    print(f"  dont rapproché avec le grand livre           : {total_snapshot_rapproche:,.2f} DH")
    print(f"  solde réel selon le grand livre (rapproché)  : {total_solde_reel:,.2f} DH")
    print(f"  -> montant réglé depuis / à corriger         : {montant_regularise:,.2f} DH")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    charger()