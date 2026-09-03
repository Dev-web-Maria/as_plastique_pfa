"""
Vérification de cohérence — grand livre client vs base extraite
Avant d'intégrer le fichier grand livre, on vérifie objectivement que ses
numéros de facture / dates / montants correspondent à ce qu'on a déjà extrait
depuis les vrais documents Excel — indépendamment de toute déclaration sur
la provenance du fichier.

Lancer depuis backend/ (venv activé) :
    python app/models/verifier_grand_livre.py
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("../data/processed/as_plastique.db")
GRAND_LIVRE_XLSX = Path("../data/raw_externe/grand_livre_client.xlsx")  # ajuste le chemin si besoin
FEUILLE = "Grand_Livre_Client"
LIGNE_ENTETE = 16  # index 0-based de la ligne d'en-tête réelle (après le papier à en-tête)


def normalize_ref(text) -> str:
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(text).upper()).lstrip("0") or "0"


def charger_grand_livre():
    df = pd.read_excel(GRAND_LIVRE_XLSX, sheet_name=FEUILLE, header=LIGNE_ENTETE)
    df = df.dropna(subset=["client"]).reset_index(drop=True)
    return df


def charger_documents_connus():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """SELECT dv.doc_number, dv.net_a_payer, dv.total_ht, dd.date, dd.annee
           FROM fait_documents_vente dv
           LEFT JOIN dim_date dd ON dv.date_id = dd.date_id
           WHERE dv.type_document = 'facture' AND dv.doc_number IS NOT NULL""",
        conn,
    )
    conn.close()
    return df


def verifier():
    grand_livre = charger_grand_livre()
    documents = charger_documents_connus()

    print(f"Grand livre : {len(grand_livre)} lignes, {grand_livre['client'].nunique()} clients")
    print(f"Documents connus (factures) : {len(documents)}")

    index_connus = {}
    for _, row in documents.iterrows():
        norm = normalize_ref(row["doc_number"])
        index_connus.setdefault(norm, []).append(
            {"montant": row["net_a_payer"] or row["total_ht"], "date": row["date"], "annee": row["annee"]}
        )

    resultats = {"numero_trouve": 0, "numero_et_montant_ok": 0, "numero_introuvable": 0}
    exemples_non_trouves = []
    exemples_montant_different = []

    for _, ligne in grand_livre.iterrows():
        norm = normalize_ref(ligne["numero_facture"])
        candidats = index_connus.get(norm)

        if not candidats:
            resultats["numero_introuvable"] += 1
            if len(exemples_non_trouves) < 10:
                exemples_non_trouves.append((ligne["client"], ligne["numero_facture"], ligne["montant_facture"]))
            continue

        resultats["numero_trouve"] += 1
        montant_gl = float(ligne["montant_facture"])
        annee_gl = pd.to_datetime(ligne["date_facture"]).year if pd.notna(ligne["date_facture"]) else None

        # Priorité aux candidats de la MÊME année (désambiguïse les numéros
        # de facture qui se répètent d'une année sur l'autre)
        candidats_meme_annee = [c for c in candidats if c["annee"] == annee_gl]
        candidats_a_tester = candidats_meme_annee if candidats_meme_annee else candidats

        match_montant = any(
            c["montant"] is not None and abs(float(c["montant"]) - montant_gl) < 1.0
            for c in candidats_a_tester
        )
        if match_montant:
            resultats["numero_et_montant_ok"] += 1
        elif len(exemples_montant_different) < 10:
            exemples_montant_different.append(
                (ligne["client"], ligne["numero_facture"], annee_gl, montant_gl,
                 [(c["montant"], c["annee"]) for c in candidats])
            )

    total = len(grand_livre)
    print("\n" + "=" * 60)
    print("RÉSULTAT DE LA VÉRIFICATION")
    print("=" * 60)
    print(f"Numéro de facture retrouvé dans la base : {resultats['numero_trouve']}/{total} "
          f"({resultats['numero_trouve']/total*100:.1f}%)")
    print(f"Numéro ET montant cohérents             : {resultats['numero_et_montant_ok']}/{total} "
          f"({resultats['numero_et_montant_ok']/total*100:.1f}%)")
    print(f"Numéro introuvable dans la base          : {resultats['numero_introuvable']}/{total} "
          f"({resultats['numero_introuvable']/total*100:.1f}%)")

    if exemples_non_trouves:
        print("\nExemples de numéros introuvables (max 10) :")
        for client, num, montant in exemples_non_trouves:
            print(f"  {client} | {num} | {montant}")

    if exemples_montant_different:
        print("\nExemples de montants différents (max 10) :")
        for client, num, annee_gl, montant_gl, montants_connus in exemples_montant_different:
            print(f"  {client} | {num} (année {annee_gl}) | grand livre={montant_gl} | base={montants_connus}")

    print("=" * 60)
    print("\nInterprétation :")
    print("- Taux élevé (>80%) sur 'numéro ET montant cohérents' -> les factures du")
    print("  grand livre sont bien ancrées dans les vraies données extraites.")
    print("- Taux faible -> à ne pas exploiter tel quel, remonter le résultat à")
    print("  l'encadrante avant toute intégration.")


if __name__ == "__main__":
    verifier()