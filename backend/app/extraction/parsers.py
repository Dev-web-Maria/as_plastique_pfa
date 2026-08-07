"""
Parseur d'extraction — Sprint 2
Extrait les champs utiles (client, date, n° document, tableau produits, totaux)
des onglets déjà classés par explore_formats.py (bon_livraison / facture).

Utilisé par run_extraction.py.
"""

import re
import unicodedata
import pandas as pd
import datetime

def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def normalize_cell(value) -> str:
    """Normalise une cellule en texte majuscule, sans accents ni espaces — pour comparaison."""
    if pd.isna(value):
        return ""
    return strip_accents(str(value).upper()).replace(" ", "")


# ---------------------------------------------------------------------------
# Détection de l'en-tête du tableau produits
# ---------------------------------------------------------------------------

# Variantes possibles (normalisées) pour chaque colonne du tableau produits
HEADER_KEYWORDS = {
    "code": ["CODE"],
    "designation": ["DESIGNATION"],
    "unite": ["UNITE"],
    "quantite": ["QUANTITE"],
    "pu": ["PU", "P.U", "PU/H.T", "PUHT"],
    "montant": ["MONTANT", "TOTAL"],
}


def find_header_row(df: pd.DataFrame, search_from: int = 0, search_limit: int = 30):
    """Cherche la ligne d'en-tête du tableau produits (contient au moins
    DESIGNATION + QUANTITE) et retourne (index_ligne, mapping colonne->index)."""
    end = min(search_from + search_limit, len(df))
    for row_idx in range(search_from, end):
        row = df.iloc[row_idx]
        column_map = {}
        for col_idx, cell in enumerate(row):
            cell_norm = normalize_cell(cell)
            if not cell_norm:
                continue
            for field, keywords in HEADER_KEYWORDS.items():
                if field in column_map:
                    continue  # déjà trouvé cette colonne sur cette ligne
                if any(kw.replace(" ", "") in cell_norm for kw in keywords):
                    column_map[field] = col_idx
        if "designation" in column_map and "quantite" in column_map:
            return row_idx, column_map
    return None, None


# ---------------------------------------------------------------------------
# Extraction des lignes produits
# ---------------------------------------------------------------------------

def parse_number(value) -> float | None:
    """Convertit '1 032,80' ou '17144,48' en float. Retourne None si impossible."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace("\xa0", "")
    text = text.replace(",", ".")
    # Garde uniquement chiffres, point et signe moins
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in ("", "-", "."):
        return None
    try:
        return float(text)
    except ValueError:
        return None


TOTAL_ROW_KEYWORDS = ["TOTALH.T", "TOTALTTC", "NETAPAYER", "TOTALTAXABLE"]


def is_total_row(row) -> bool:
    row_text = "".join(normalize_cell(c) for c in row)
    return any(kw in row_text for kw in TOTAL_ROW_KEYWORDS)


def extract_line_items(df: pd.DataFrame, header_row_idx: int, column_map: dict):
    """Extrait les lignes produits après l'en-tête, jusqu'à la ligne de total.
    Retourne (liste_items, index_ligne_total ou None)."""
    items = []
    current_item = None
    total_row_idx = None

    for row_idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[row_idx]

        if is_total_row(row):
            total_row_idx = row_idx
            break

        quantite_val = row.iloc[column_map["quantite"]] if column_map.get("quantite") is not None else None
        designation_val = row.iloc[column_map["designation"]] if column_map.get("designation") is not None else None
        quantite_num = parse_number(quantite_val)

        if quantite_num is not None and quantite_num > 0:
            # Nouvelle ligne produit — on sauvegarde la précédente si elle existe
            if current_item:
                items.append(current_item)
            current_item = {
                "designation": str(designation_val).strip() if pd.notna(designation_val) else "",
                "unite": str(row.iloc[column_map["unite"]]).strip() if column_map.get("unite") is not None and pd.notna(row.iloc[column_map["unite"]]) else "",
                "quantite": quantite_num,
                "pu": parse_number(row.iloc[column_map["pu"]]) if column_map.get("pu") is not None else None,
                "montant": parse_number(row.iloc[column_map["montant"]]) if column_map.get("montant") is not None else None,
            }
        elif current_item is not None and pd.notna(designation_val):
            # Ligne de continuation du texte de désignation (ex : "Usage Industriel")
            suite = str(designation_val).strip()
            if suite:
                current_item["designation"] = (current_item["designation"] + " " + suite).strip()

    if current_item:
        items.append(current_item)

    return items, total_row_idx


def extract_totals(df: pd.DataFrame, total_row_idx: int | None) -> dict:
    """Extrait total_ht, tva, net_a_payer autour de la ligne de total détectée.
    Gère deux mises en page rencontrées dans les fichiers réels :
    - libellé et valeur sur la MÊME ligne (valeur à droite du libellé)
    - libellé sur une ligne, valeur juste EN DESSOUS dans la même colonne
      (ex : "TOTAL TAXABLE | T.V.A. | NET A PAYER" puis les 3 montants dessous)
    """
    totals = {"total_ht": None, "tva": None, "net_a_payer": None}
    if total_row_idx is None:
        return totals

    search_zone = df.iloc[total_row_idx: total_row_idx + 5].reset_index(drop=True)

    for zone_idx in range(len(search_zone)):
        row = search_zone.iloc[zone_idx]
        for col_idx, cell in enumerate(row):
            cell_norm = normalize_cell(cell)
            if not cell_norm:
                continue

            label_map = [
                (["TOTALH.T", "TOTALTAXABLE"], "total_ht"),
                (["TVA", "T.V.A"], "tva"),
                (["NETAPAYER"], "net_a_payer"),
            ]
            for keywords, field in label_map:
                if totals[field] is not None:
                    continue
                if not any(kw.replace(".", "") in cell_norm.replace(".", "") for kw in keywords):
                    continue

                # 1) essaie d'abord à droite sur la MÊME ligne
                remaining_same_row = list(row.iloc[col_idx:])
                nums = [parse_number(v) for v in remaining_same_row]
                nums = [n for n in nums if n is not None]
                if nums:
                    totals[field] = nums[0]
                    continue

                # 2) sinon, cherche dans la MÊME colonne, une ligne en dessous
                if zone_idx + 1 < len(search_zone):
                    below_val = search_zone.iloc[zone_idx + 1, col_idx]
                    below_num = parse_number(below_val)
                    if below_num is not None:
                        totals[field] = below_num

    return totals


# ---------------------------------------------------------------------------
# Métadonnées du document (date, n° document, tiers)
# ---------------------------------------------------------------------------

DATE_PATTERN = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b")

MOIS_FR = {
    "JANVIER": "01", "FEVRIER": "02", "FÉVRIER": "02", "MARS": "03", "AVRIL": "04",
    "MAI": "05", "JUIN": "06", "JUILLET": "07", "AOUT": "08", "AOÛT": "08",
    "SEPTEMBRE": "09", "OCTOBRE": "10", "NOVEMBRE": "11", "DECEMBRE": "12", "DÉCEMBRE": "12",
}
DATE_LETTRES_PATTERN = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(MOIS_FR.keys()) + r")\s+(\d{4})\b", re.IGNORECASE
)


import datetime


def extract_date(df: pd.DataFrame, search_rows: int = 25) -> str | None:
    """Cherche une date dans les search_rows premières lignes de la feuille.
    Gère 3 cas rencontrés dans les vrais fichiers :
    1. Vraie cellule de type date Excel (lue par pandas comme Timestamp/datetime)
    2. Date en texte au format numérique (07/01/2019, 04/11/17...)
    3. Date en texte en toutes lettres (07 Janvier 2019)
    """
    for row_idx in range(min(search_rows, len(df))):
        for cell in df.iloc[row_idx]:
            if pd.isna(cell):
                continue

            # Cas 1 : vraie cellule date (le plus fréquent dans les factures,
            # où la colonne date est formatée comme une date Excel, pas du texte)
            if isinstance(cell, (pd.Timestamp, datetime.datetime, datetime.date)):
                return cell.strftime("%d/%m/%Y")

            cell_text = str(cell)

            match = DATE_PATTERN.search(cell_text)
            if match:
                return match.group(1)

            match_lettres = DATE_LETTRES_PATTERN.search(cell_text)
            if match_lettres:
                jour, mois_nom, annee = match_lettres.groups()
                mois_num = MOIS_FR.get(mois_nom.upper())
                if mois_num:
                    return f"{jour.zfill(2)}/{mois_num}/{annee}"
    return None


def extract_doc_number(title_row_text: str) -> str | None:
    """Extrait le numéro après 'N°' ou 'N:' dans la ligne de titre.
    Le symbole ° ou : est obligatoire pour éviter de matcher un 'N' isolé
    dans un mot comme 'BON' ou 'LIVRAISON'."""
    match = re.search(r"N[°:]\s*([A-Z0-9/\-]+)", title_row_text.upper())
    if match:
        return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def parse_document(df: pd.DataFrame, title_row_idx: int, title_keyword: str) -> dict:
    """Parse un onglet déjà classé (bon_livraison ou facture) et retourne
    un dictionnaire structuré avec métadonnées + lignes produits + totaux."""

    empty_result = {
        "doc_number": None,
        "date": None,
        "header_row_found": False,
        "items": [],
        "totals": {"total_ht": None, "tva": None, "net_a_payer": None},
        "n_items": 0,
    }

    # Protection : onglet vide, ou title_row_idx hors limites (ex : onglet
    # quasi-vide passé par le filet de secours nom de fichier)
    if df.empty or title_row_idx is None or title_row_idx >= len(df):
        return empty_result

    title_row_text = " ".join(str(c) for c in df.iloc[title_row_idx] if pd.notna(c))
    doc_number = extract_doc_number(title_row_text)
    date = extract_date(df)

    header_row_idx, column_map = find_header_row(df, search_from=title_row_idx)

    result = {
        "doc_number": doc_number,
        "date": date,
        "header_row_found": header_row_idx is not None,
        "items": [],
        "totals": {"total_ht": None, "tva": None, "net_a_payer": None},
        "n_items": 0,
    }

    if header_row_idx is None:
        return result  # tableau produits non localisé — sera journalisé en erreur

    items, total_row_idx = extract_line_items(df, header_row_idx, column_map)
    totals = extract_totals(df, total_row_idx)

    result["items"] = items
    result["n_items"] = len(items)
    result["totals"] = totals
    return result