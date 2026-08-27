"""
Parseur d'extraction — bons de livraison / factures
Extrait les champs utiles (client, date, n° document, tableau produits, totaux)
des onglets déjà classés par explore_formats.py (bon_livraison / facture).

Utilisé par run_extraction.py.
"""

import re
import unicodedata
import datetime
import pandas as pd


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def normalize_cell(value) -> str:
    if pd.isna(value):
        return ""
    return strip_accents(str(value).upper()).replace(" ", "")


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
                    continue
                if any(kw.replace(" ", "") in cell_norm for kw in keywords):
                    column_map[field] = col_idx
        if "designation" in column_map and "quantite" in column_map:
            if "unite" not in column_map:
                # Cas des factures : pas de colonne "Unité" étiquetée, mais
                # l'unité est systématiquement dans la colonne juste après Quantité
                colonne_candidate = column_map["quantite"] + 1
                if colonne_candidate < len(row) and colonne_candidate not in column_map.values():
                    column_map["unite"] = colonne_candidate
            return row_idx, column_map
    return None, None


def parse_number(value) -> float | None:
    """Convertit un nombre écrit en texte en float. Gère plusieurs formats
    réels rencontrés dans les fichiers :
    - '1032,80' (virgule décimale simple)
    - '15.000,00' (point = séparateur de milliers, virgule = décimales)
    - '1032.80' (point décimal déjà standard)
    - '12750+10000' (deux montants additionnés à la main dans une cellule)
    Rejette explicitement tout texte contenant des lettres (ex : statut
    'réglé vir le 12/03/21') — sinon les chiffres épars du texte se
    recollaient en un faux nombre (12, 03, 21 -> 120321)."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    if re.search(r"[A-Za-zÀ-ÿ]", text):
        return None

    # Cas réel découvert : '12750+10000' (deux montants additionnés à la main
    # dans une même cellule) — sans ce traitement, le '+' est juste supprimé
    # par le nettoyage plus bas, collant les deux nombres (1275010000 au lieu
    # de 22750, un bug qui a fait apparaître un "impayé" de 1,275 milliard DH).
    if "+" in text:
        parties = [p.strip() for p in text.split("+")]
        valeurs = [parse_number(p) for p in parties]
        if all(v is not None for v in valeurs):
            return sum(valeurs)
        return None

    text = text.replace(" ", "").replace("\xa0", "")

    if "," in text and "." in text:
        # Les deux sont présents : le point est un séparateur de milliers,
        # la virgule est la décimale (ex: '15.000,00' -> '15000.00')
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        # Seule la virgule est présente : c'est la décimale
        text = text.replace(",", ".")
    # Si seul un point est présent, on le laisse tel quel (déjà au bon format)

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

        if quantite_num is None and column_map.get("code") is not None:
            # Cas réel découvert : sur certains bons, la quantité a été tapée
            # par erreur dans la colonne "Code" au lieu de "Quantité" (le poids
            # existe, juste mal placé) — on tente ce filet de secours avant
            # de considérer la ligne comme vide.
            code_val = row.iloc[column_map["code"]]
            quantite_num = parse_number(code_val)

        if quantite_num is not None and quantite_num > 0:
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
            suite = str(designation_val).strip()
            if suite:
                current_item["designation"] = (current_item["designation"] + " " + suite).strip()

    if current_item:
        items.append(current_item)

    return items, total_row_idx


def extract_totals(df: pd.DataFrame, total_row_idx: int | None) -> dict:
    """Extrait total_ht, tva, net_a_payer autour de la ligne de total détectée."""
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

                remaining_same_row = list(row.iloc[col_idx:])
                nums = [parse_number(v) for v in remaining_same_row]
                nums = [n for n in nums if n is not None]
                if nums:
                    totals[field] = nums[0]
                    continue

                if zone_idx + 1 < len(search_zone):
                    below_val = search_zone.iloc[zone_idx + 1, col_idx]
                    below_num = parse_number(below_val)
                    if below_num is not None:
                        totals[field] = below_num

    return totals


DATE_PATTERN = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b")

MOIS_FR = {
    "JANVIER": "01", "FEVRIER": "02", "FÉVRIER": "02", "MARS": "03", "AVRIL": "04",
    "MAI": "05", "JUIN": "06", "JUILLET": "07", "AOUT": "08", "AOÛT": "08",
    "SEPTEMBRE": "09", "OCTOBRE": "10", "NOVEMBRE": "11", "DECEMBRE": "12", "DÉCEMBRE": "12",
}
DATE_LETTRES_PATTERN = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(MOIS_FR.keys()) + r")\s+(\d{4})\b", re.IGNORECASE
)


def extract_date(df: pd.DataFrame, search_rows: int = 25) -> str | None:
    """Cherche une date dans les search_rows premières lignes de la feuille.
    Gère 3 cas : vraie cellule date Excel (Timestamp), texte au format
    numérique (07/01/2019), et texte en toutes lettres (07 Janvier 2019)."""
    for row_idx in range(min(search_rows, len(df))):
        for cell in df.iloc[row_idx]:
            if pd.isna(cell):
                continue

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
    """Extrait le numéro après 'N°' ou 'N:' dans la ligne de titre."""
    match = re.search(r"N[°:]\s*([A-Z0-9/\-]+)", title_row_text.upper())
    if match:
        return match.group(1).strip()
    return None


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

    # Protection : onglet vide, ou title_row_idx hors limites
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
        return result

    items, total_row_idx = extract_line_items(df, header_row_idx, column_map)
    totals = extract_totals(df, total_row_idx)

    result["items"] = items
    result["n_items"] = len(items)
    result["totals"] = totals
    return result