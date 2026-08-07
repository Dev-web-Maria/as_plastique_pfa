"""
Script d'extraction — Sprint 2 (échantillon)
Combine la détection de type (explore_formats.py) et le parseur de champs
(parsers.py) pour extraire un échantillon réel de tes fichiers, avant de
lancer l'extraction complète en Sprint 3.

Ne traite pour l'instant que bon_livraison et facture (les 2 types couverts
par parsers.py). releve_factures_impayees, reglement_facture et bon_commande
auront leur propre parseur au Sprint 3.

Lancer depuis backend/ (venv activé) :
    python app/extraction/run_extraction.py
"""

import pandas as pd
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

from explore_formats import detect_type_by_first_row, guess_type_from_filename
from parsers import parse_document

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_RAW_DIR = Path("../data/raw")
OUTPUT_DOCS = Path("../data/processed/extraction_sample_documents.csv")
OUTPUT_ITEMS = Path("../data/processed/extraction_sample_items.csv")
ERROR_LOG = Path("../data/logs/extraction_sample_errors.log")

SAMPLE_PER_FILE = 5  # nb d'onglets max traités par fichier, pour un échantillon rapide
TYPES_GERES_CE_SPRINT = {"bon_livraison", "facture"}


def process_sample():
    OUTPUT_DOCS.parent.mkdir(parents=True, exist_ok=True)
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)

    excel_files = sorted(DATA_RAW_DIR.glob("*.xls")) + sorted(DATA_RAW_DIR.glob("*.xlsx"))
    if not excel_files:
        print(f"⚠ Aucun fichier trouvé dans {DATA_RAW_DIR.resolve()}")
        return

    doc_rows = []
    item_rows = []
    errors = []

    for file_path in excel_files:
        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            errors.append(f"{file_path.name} — échec d'ouverture : {e}")
            continue

        sheets_to_process = xls.sheet_names[:SAMPLE_PER_FILE]
        print(f"→ {file_path.name} ({len(sheets_to_process)} onglet(s) échantillonné(s))")

        for sheet_name in sheets_to_process:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            except Exception as e:
                errors.append(f"{file_path.name} [{sheet_name}] — échec de lecture : {e}")
                continue

            doc_type, title_row_idx, keyword = detect_type_by_first_row(df)
            if doc_type == "type_inconnu":
                fallback = guess_type_from_filename(file_path.stem)
                if fallback:
                    doc_type = fallback
                    # Aucun titre trouvé dans le contenu (d'où le recours au nom de
                    # fichier) : on démarre la recherche du tableau depuis le début
                    # de la feuille plutôt que de planter sur un index manquant.
                    title_row_idx = 0
                    keyword = "aucun (type via nom de fichier)"

            if doc_type not in TYPES_GERES_CE_SPRINT:
                doc_rows.append({
                    "fichier": file_path.name, "onglet": sheet_name,
                    "type_detecte": doc_type, "statut": "type_non_gere_ce_sprint",
                    "doc_number": None, "date": None, "n_items": 0,
                    "total_ht": None, "tva": None, "net_a_payer": None,
                })
                continue

            try:
                result = parse_document(df, title_row_idx, keyword)
            except Exception as e:
                errors.append(f"{file_path.name} [{sheet_name}] — erreur parse_document : {e}")
                doc_rows.append({
                    "fichier": file_path.name, "onglet": sheet_name,
                    "type_detecte": doc_type, "statut": "erreur_extraction",
                    "doc_number": None, "date": None, "n_items": 0,
                    "total_ht": None, "tva": None, "net_a_payer": None,
                })
                continue

            statut = "ok" if result["header_row_found"] and result["n_items"] > 0 else "extraction_incomplete"

            if statut == "extraction_incomplete":
                errors.append(
                    f"{file_path.name} [{sheet_name}] — type={doc_type}, "
                    f"tableau_trouve={result['header_row_found']}, n_items={result['n_items']}"
                )

            doc_rows.append({
                "fichier": file_path.name, "onglet": sheet_name,
                "type_detecte": doc_type, "statut": statut,
                "doc_number": result["doc_number"], "date": result["date"],
                "n_items": result["n_items"],
                "total_ht": result["totals"]["total_ht"],
                "tva": result["totals"]["tva"],
                "net_a_payer": result["totals"]["net_a_payer"],
            })

            for item in result["items"]:
                item_rows.append({
                    "fichier": file_path.name, "onglet": sheet_name,
                    "doc_number": result["doc_number"],
                    **item,
                })

    docs_df = pd.DataFrame(doc_rows)
    items_df = pd.DataFrame(item_rows)
    docs_df.to_csv(OUTPUT_DOCS, index=False, encoding="utf-8-sig")
    items_df.to_csv(OUTPUT_ITEMS, index=False, encoding="utf-8-sig")
    if errors:
        ERROR_LOG.write_text("\n".join(errors), encoding="utf-8")

    print("\n" + "=" * 60)
    print("RÉSUMÉ DE L'EXTRACTION (ÉCHANTILLON)")
    print("=" * 60)
    print(f"Onglets échantillonnés : {len(docs_df)}")
    print(f"Lignes produits extraites : {len(items_df)}")
    print("\nRépartition par statut :")
    print(docs_df["statut"].value_counts().to_string())
    print(f"\n📄 Documents : {OUTPUT_DOCS.resolve()}")
    print(f"📄 Lignes produits : {OUTPUT_ITEMS.resolve()}")
    if errors:
        print(f"📄 Erreurs/incomplets : {ERROR_LOG.resolve()} ({len(errors)} entrée(s))")
    print("=" * 60)


if __name__ == "__main__":
    process_sample()