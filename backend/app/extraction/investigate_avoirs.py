"""
Investigation — combien d'onglets classés "facture" sont en réalité des
AVOIRS (notes de crédit) ? Ne modifie rien, sert juste à mesurer l'ampleur
du problème avant de décider s'il faut créer une vraie catégorie "avoir".

Lancer depuis backend/ (venv activé) :
    python app/extraction/investigate_avoirs.py
"""

import pandas as pd
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

from explore_formats import row_text_nospace, TYPE_ANCHORS

DATA_RAW_DIR = Path("../data/raw")

# Même logique que detect_type_by_first_row, mais avec "AVOIR" ajouté en
# priorité AVANT "facture" — pour voir combien d'onglets basculeraient de
# type si on distinguait vraiment les avoirs des factures.
ALT_TYPE_ANCHORS = [
    ("reglement_facture", ["REGLEMENT"]),
    ("releve_factures_impayees", ["RELEVE DE FACTURES", "FACTURES NON PAYEES", "RELEVE DE FACTURE"]),
    ("avoir", ["AVOIR"]),  # <- nouveau, testé en priorité avant facture
    ("facture", ["FACTURE"]),
    ("bon_livraison", ["BON DE LIVRAISON"]),
    ("bon_commande", ["BON DE COMMANDE"]),
]


def detect_type_alt(df: pd.DataFrame):
    for row_idx, row in enumerate(df.values):
        line_nospace = row_text_nospace(row)
        if not line_nospace:
            continue
        for doc_type, keywords in ALT_TYPE_ANCHORS:
            for kw in keywords:
                if kw.replace(" ", "") in line_nospace:
                    return doc_type, row_idx
    return "type_inconnu", None


def investigate():
    excel_files = sorted(DATA_RAW_DIR.glob("*.xls")) + sorted(DATA_RAW_DIR.glob("*.xlsx"))
    if not excel_files:
        print(f"⚠ Aucun fichier trouvé dans {DATA_RAW_DIR.resolve()}")
        return

    total_onglets = 0
    total_facture_actuel = 0
    total_avoir_detecte = 0
    exemples_avoir = []

    for file_path in excel_files:
        try:
            xls = pd.ExcelFile(file_path)
        except Exception:
            continue

        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            except Exception:
                continue

            total_onglets += 1
            alt_type, row_idx = detect_type_alt(df)

            if alt_type == "avoir":
                total_avoir_detecte += 1
                if len(exemples_avoir) < 15:
                    exemples_avoir.append((file_path.name, sheet_name))
            elif alt_type == "facture":
                total_facture_actuel += 1

    print("=" * 60)
    print("INVESTIGATION AVOIRS")
    print("=" * 60)
    print(f"Onglets analysés               : {total_onglets}")
    print(f"Onglets 'avoir' (nouvelle regle): {total_avoir_detecte}")
    print(f"Onglets 'facture' (avec avoir exclu) : {total_facture_actuel}")
    print(f"\nExemples d'onglets AVOIR trouvés (max 15) :")
    for fichier, onglet in exemples_avoir:
        print(f"  - {fichier} [{onglet}]")
    print("=" * 60)


if __name__ == "__main__":
    investigate()