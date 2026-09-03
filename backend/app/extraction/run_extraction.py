"""
Script d'extraction — extraction COMPLÈTE, tous les onglets
Combine la détection de type (explore_formats.py) et les parseurs de champs
(parsers.py, parser_releve.py, parser_reglement.py) pour extraire l'intégralité
des onglets de data/raw.

bon_commande reste hors périmètre (volume trop faible, 4 onglets — ce sont en
réalité des bons de livraison avec référence commande).

Lancer depuis backend/ (venv activé) :
    python app/extraction/run_extraction.py

⚠️ Avant de relancer load_to_db.py après cette extraction, supprime ou
recrée la base (schema.py) pour éviter les doublons.
"""

import pandas as pd
from pathlib import Path
import warnings
import time

warnings.filterwarnings("ignore")

from explore_formats import detect_type_by_first_row, guess_type_from_filename
from parsers import parse_document
from parser_releve import parse_releve
from parser_reglement import parse_reglements

# ---------------------------------------------------------------------------
# Onglets exclus explicitement — structure incompatible avec le schéma
# générique (une seule colonne montant par ligne). Documenté au lieu d'être
# deviné : chaque entrée doit avoir une raison claire.
# ---------------------------------------------------------------------------

ONGLETS_EXCLUS = {
    ("RELEVES 21.xls", "ANCIEN"): (
        "Structure a 2 colonnes MONTANT FACTURE sommees dans TOTAL MONTANT "
        "(ex: 36245 + 21420 = 57665) - incompatible avec le parseur generique a "
        "1 colonne montant. Volume modeste (12 lignes, 211 486 DH) : non "
        "rentable d'adapter le parseur pour ce cas unique."
    ),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_RAW_DIR = Path("../data/raw")
OUTPUT_DOCS = Path("../data/processed/extraction_full_documents.csv")
OUTPUT_ITEMS = Path("../data/processed/extraction_full_items.csv")
OUTPUT_RELEVES_DOCS = Path("../data/processed/extraction_full_releves_documents.csv")
OUTPUT_RELEVES_ITEMS = Path("../data/processed/extraction_full_releves_items.csv")
OUTPUT_REGLEMENTS = Path("../data/processed/extraction_full_reglements.csv")
ERROR_LOG = Path("../data/logs/extraction_full_errors.log")

TYPES_FACTURE_LIVRAISON = {"bon_livraison", "facture"}
TYPES_RELEVE = {"releve_factures_impayees"}
TYPES_REGLEMENT = {"reglement_facture"}


def process_all():
    for path in [OUTPUT_DOCS, OUTPUT_RELEVES_DOCS, OUTPUT_REGLEMENTS]:
        path.parent.mkdir(parents=True, exist_ok=True)
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)

    excel_files = sorted(DATA_RAW_DIR.glob("*.xls")) + sorted(DATA_RAW_DIR.glob("*.xlsx"))
    if not excel_files:
        print(f"Aucun fichier trouve dans {DATA_RAW_DIR.resolve()}")
        return

    doc_rows, item_rows = [], []
    releve_doc_rows, releve_item_rows = [], []
    reglement_rows = []
    errors = []
    statut_counts = {}

    debut = time.time()

    for file_path in excel_files:
        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            errors.append(f"{file_path.name} — échec d'ouverture : {e}")
            continue

        sheets_to_process = xls.sheet_names
        print(f"→ {file_path.name} ({len(sheets_to_process)} onglet(s))")

        for sheet_name in sheets_to_process:
            if (file_path.name, sheet_name) in ONGLETS_EXCLUS:
                raison = ONGLETS_EXCLUS[(file_path.name, sheet_name)]
                errors.append(f"{file_path.name} [{sheet_name}] — EXCLU : {raison}")
                statut_counts["exclu_manuellement"] = statut_counts.get("exclu_manuellement", 0) + 1
                continue

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
                    title_row_idx = 0
                    keyword = "aucun (type via nom de fichier)"

            if doc_type in TYPES_FACTURE_LIVRAISON:
                try:
                    result = parse_document(df, title_row_idx, keyword)
                except Exception as e:
                    errors.append(f"{file_path.name} [{sheet_name}] — erreur parse_document : {e}")
                    statut = "erreur_extraction"
                    doc_rows.append({
                        "fichier": file_path.name, "onglet": sheet_name,
                        "type_detecte": doc_type, "statut": statut,
                        "doc_number": None, "date": None, "n_items": 0,
                        "total_ht": None, "tva": None, "net_a_payer": None,
                    })
                    statut_counts[statut] = statut_counts.get(statut, 0) + 1
                    continue

                statut = "ok" if result["header_row_found"] and result["n_items"] > 0 else "extraction_incomplete"
                if statut == "extraction_incomplete":
                    errors.append(f"{file_path.name} [{sheet_name}] — type={doc_type}, incomplet")

                doc_rows.append({
                    "fichier": file_path.name, "onglet": sheet_name,
                    "type_detecte": doc_type, "statut": statut,
                    "doc_number": result["doc_number"], "date": result["date"],
                    "client_nom": result["client_nom"],
                    "n_items": result["n_items"],
                    "total_ht": result["totals"]["total_ht"],
                    "tva": result["totals"]["tva"],
                    "net_a_payer": result["totals"]["net_a_payer"],
                })
                for item in result["items"]:
                    item_rows.append({
                        "fichier": file_path.name, "onglet": sheet_name,
                        "doc_number": result["doc_number"], **item,
                    })
                statut_counts[statut] = statut_counts.get(statut, 0) + 1

            elif doc_type in TYPES_RELEVE:
                try:
                    result = parse_releve(df, title_row_idx)
                except Exception as e:
                    errors.append(f"{file_path.name} [{sheet_name}] — erreur parse_releve : {e}")
                    statut = "erreur_extraction"
                    releve_doc_rows.append({
                        "fichier": file_path.name, "onglet": sheet_name, "statut": statut,
                        "date_releve": None, "client": None, "n_factures": 0, "total_a_payer": None,
                    })
                    statut_counts[statut] = statut_counts.get(statut, 0) + 1
                    continue

                statut = "ok" if result["header_row_found"] and result["n_factures"] > 0 else "extraction_incomplete"
                if statut == "extraction_incomplete":
                    errors.append(f"{file_path.name} [{sheet_name}] — releve incomplet")

                releve_doc_rows.append({
                    "fichier": file_path.name, "onglet": sheet_name, "statut": statut,
                    "date_releve": result["date_releve"], "client": result["client"],
                    "n_factures": result["n_factures"], "total_a_payer": result["total_a_payer"],
                })
                for facture in result["factures"]:
                    releve_item_rows.append({
                        "fichier": file_path.name, "onglet": sheet_name,
                        "client": result["client"], **facture,
                    })
                statut_counts[statut] = statut_counts.get(statut, 0) + 1

            elif doc_type in TYPES_REGLEMENT:
                try:
                    result = parse_reglements(df)
                except Exception as e:
                    errors.append(f"{file_path.name} [{sheet_name}] — erreur parse_reglements : {e}")
                    statut = "erreur_extraction"
                    statut_counts[statut] = statut_counts.get(statut, 0) + 1
                    continue

                statut = "ok" if result["n_reglements"] > 0 else "extraction_incomplete"
                if statut == "extraction_incomplete":
                    errors.append(f"{file_path.name} [{sheet_name}] — reglement incomplet")

                for reglement in result["reglements"]:
                    reglement_rows.append({
                        "fichier": file_path.name, "onglet": sheet_name, **reglement,
                    })
                statut_counts[statut] = statut_counts.get(statut, 0) + 1

            else:
                statut_counts["type_non_gere_ce_sprint"] = statut_counts.get("type_non_gere_ce_sprint", 0) + 1

    pd.DataFrame(doc_rows).to_csv(OUTPUT_DOCS, index=False, encoding="utf-8-sig")
    pd.DataFrame(item_rows).to_csv(OUTPUT_ITEMS, index=False, encoding="utf-8-sig")
    pd.DataFrame(releve_doc_rows).to_csv(OUTPUT_RELEVES_DOCS, index=False, encoding="utf-8-sig")
    pd.DataFrame(releve_item_rows).to_csv(OUTPUT_RELEVES_ITEMS, index=False, encoding="utf-8-sig")
    pd.DataFrame(reglement_rows).to_csv(OUTPUT_REGLEMENTS, index=False, encoding="utf-8-sig")
    if errors:
        ERROR_LOG.write_text("\n".join(errors), encoding="utf-8")

    duree = time.time() - debut
    total_onglets = sum(statut_counts.values())
    print("\n" + "=" * 60)
    print("RÉSUMÉ DE L'EXTRACTION COMPLÈTE")
    print("=" * 60)
    print(f"Durée : {duree:.1f}s")
    print(f"Onglets traités (total) : {total_onglets}")
    print(f"  dont bon_livraison/facture   : {len(doc_rows)} (lignes produits : {len(item_rows)})")
    print(f"  dont relevés impayés         : {len(releve_doc_rows)} (lignes factures : {len(releve_item_rows)})")
    print(f"  dont lignes de règlements     : {len(reglement_rows)}")
    print("\nRépartition par statut (tous types confondus) :")
    for statut, n in sorted(statut_counts.items(), key=lambda x: -x[1]):
        pct = round(n / total_onglets * 100, 1) if total_onglets else 0
        print(f"  {statut:28} {n} ({pct}%)")
    print(f"\nDocuments facture/livraison : {OUTPUT_DOCS.resolve()}")
    print(f"Lignes produits              : {OUTPUT_ITEMS.resolve()}")
    print(f"Documents relevés             : {OUTPUT_RELEVES_DOCS.resolve()}")
    print(f"Lignes factures (relevés)     : {OUTPUT_RELEVES_ITEMS.resolve()}")
    print(f"Lignes règlements             : {OUTPUT_REGLEMENTS.resolve()}")
    if errors:
        print(f"Erreurs/incomplets            : {ERROR_LOG.resolve()} ({len(errors)} entrée(s))")
    print("=" * 60)


if __name__ == "__main__":
    process_all()