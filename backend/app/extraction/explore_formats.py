"""
Script d'exploration des fichiers Excel — Sprint 1 (v2)
Scanne tous les fichiers de data/raw, et détecte le TYPE de chaque document
en repérant le mot-clé titre qui apparaît en PREMIER en parcourant les lignes
de haut en bas (le vrai titre du document est toujours au-dessus des champs
de référence croisée comme "BON DE COMMANDE N°" mentionné dans une facture
ou un bon de livraison).

Lancer depuis le dossier backend/ (venv activé) :
    python app/extraction/explore_formats.py
"""

import pandas as pd
from pathlib import Path
import warnings
import unicodedata

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_RAW_DIR = Path("../data/raw")
OUTPUT_REPORT = Path("../data/processed/exploration_report.csv")
ERROR_LOG = Path("../data/logs/exploration_errors.log")

# Mots-clés "titre" — indiquent le VRAI type du document quand ils apparaissent
# en premier dans la feuille (ordre = priorité en cas d'égalité sur la même ligne)
TYPE_ANCHORS = [
    ("reglement_facture", ["REGLEMENT"]),
    ("releve_factures_impayees", ["RELEVE DE FACTURES", "FACTURES NON PAYEES", "RELEVE DE FACTURE"]),
    ("facture", ["FACTURE"]),
    ("bon_livraison", ["BON DE LIVRAISON"]),
    ("bon_commande", ["BON DE COMMANDE"]),
]

# Mots-clés "champs" — utiles pour localiser le tableau de données plus tard,
# mais ne servent PAS à deviner le type du document
FIELD_ANCHORS = {
    "tableau_produits": ["DESIGNATION", "QUANTITE", "P.U", "PU", "MONTANT"],
    "total": ["TOTAL H.T", "TOTAL TTC", "NET A PAYER", "TOTAL TAXABLE"],
    "tva": ["T.V.A", "TVA"],
}


def strip_accents(text: str) -> str:
    """Enlève les accents (é, è, à...) pour fiabiliser la comparaison de mots-clés."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def row_text_nospace(row) -> str:
    """Concatène une ligne du DataFrame en texte majuscule, sans accents ni espaces."""
    text = " ".join(str(cell).upper() for cell in row if pd.notna(cell))
    return strip_accents(text).replace(" ", "")


# Filet de secours : utilisé UNIQUEMENT quand aucun titre n'est trouvé dans le
# contenu (ex : tableaux bruts de règlements, sans en-tête de document classique)
FILENAME_FALLBACK_PATTERNS = [
    ("REGLEMENT", "reglement_facture"),
    ("RELEVE", "releve_factures_impayees"),
    ("FACTURE", "facture"),
    ("LIVRAISON", "bon_livraison"),
    ("COMMANDE", "bon_commande"),
]


def guess_type_from_filename(file_stem: str):
    upper_stem = strip_accents(file_stem.upper())
    for pattern, doc_type in FILENAME_FALLBACK_PATTERNS:
        if pattern in upper_stem:
            return doc_type
    return None


def detect_type_by_first_row(df: pd.DataFrame):
    """Parcourt les lignes de haut en bas et retourne le type du PREMIER
    mot-clé titre rencontré, avec le numéro de ligne et le mot-clé trouvé."""
    for row_idx, row in enumerate(df.values):
        line_nospace = row_text_nospace(row)
        if not line_nospace:
            continue  # ligne vide, on continue
        for doc_type, keywords in TYPE_ANCHORS:
            for kw in keywords:
                if kw.replace(" ", "") in line_nospace:
                    return doc_type, row_idx, kw
    return "type_inconnu", None, None


def scan_field_anchors(df: pd.DataFrame) -> dict:
    """Détecte les mots-clés de champs (tableau, total, tva) dans toute la feuille."""
    all_text_nospace = strip_accents(" ".join(
        str(cell).upper() for row in df.values for cell in row if pd.notna(cell)
    )).replace(" ", "")

    found = []
    for category, keywords in FIELD_ANCHORS.items():
        for kw in keywords:
            if kw.replace(" ", "") in all_text_nospace:
                found.append(category)
                break
    return {"champs_detectes": ", ".join(found) or "aucun"}


def explore_all_files():
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)

    excel_files = sorted(DATA_RAW_DIR.glob("*.xls")) + sorted(DATA_RAW_DIR.glob("*.xlsx"))

    if not excel_files:
        print(f"⚠ Aucun fichier .xls/.xlsx trouvé dans {DATA_RAW_DIR.resolve()}")
        return

    print(f"📂 {len(excel_files)} fichier(s) trouvé(s) dans {DATA_RAW_DIR}\n")

    results = []
    errors = []

    for file_path in excel_files:
        print(f"→ {file_path.name}")
        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            msg = f"{file_path.name} — échec d'ouverture du fichier : {e}"
            print(f"   ✗ {msg}")
            errors.append(msg)
            continue

        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                doc_type, row_idx, keyword = detect_type_by_first_row(df)
                type_source = "contenu"

                if doc_type == "type_inconnu":
                    fallback_type = guess_type_from_filename(file_path.stem)
                    if fallback_type:
                        doc_type = fallback_type
                        type_source = "nom_fichier_fallback"

                field_stats = scan_field_anchors(df)
                results.append({
                    "fichier": file_path.name,
                    "onglet": sheet_name,
                    "type_detecte": doc_type,
                    "type_source": type_source,
                    "ligne_titre": row_idx if row_idx is not None else "",
                    "mot_cle_titre": keyword or "aucun",
                    **field_stats,
                    "n_lignes": df.shape[0],
                    "n_colonnes": df.shape[1],
                })
            except Exception as e:
                msg = f"{file_path.name} [{sheet_name}] — échec de lecture de l'onglet : {e}"
                print(f"   ✗ {msg}")
                errors.append(msg)

    # --- Rapport principal ---
    report_df = pd.DataFrame(results)
    report_df.to_csv(OUTPUT_REPORT, index=False, encoding="utf-8-sig")

    # --- Journal des erreurs ---
    if errors:
        ERROR_LOG.write_text("\n".join(errors), encoding="utf-8")

    # --- Résumé affiché dans le terminal ---
    print("\n" + "=" * 60)
    print("RÉSUMÉ DE L'EXPLORATION")
    print("=" * 60)
    print(f"Fichiers scannés     : {len(excel_files)}")
    print(f"Onglets analysés     : {len(report_df)}")
    print(f"Onglets en erreur    : {len(errors)}")
    print("\nRépartition par type de document (détection par 1ère ligne titre) :")
    if not report_df.empty:
        print(report_df["type_detecte"].value_counts().to_string())
    print(f"\n📄 Rapport détaillé  : {OUTPUT_REPORT.resolve()}")
    if errors:
        print(f"📄 Journal d'erreurs : {ERROR_LOG.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    explore_all_files()