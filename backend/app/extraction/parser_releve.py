"""
Parseur pour les relevés de factures impayées — Sprint 3
Réutilise les briques communes de parsers.py (normalize_cell, parse_number,
gestion des dates) pour rester cohérent avec le parseur bon_livraison/facture.
"""

import datetime
import pandas as pd
import re

from parsers import (
    normalize_cell,
    parse_number,
    strip_accents,
    DATE_PATTERN,
    DATE_LETTRES_PATTERN,
    MOIS_FR,
)

LIGNE_ENTETE_DATE_PATTERN = re.compile(r"^[A-Za-z\u00C0-\u00FF]+\s*LE[^0-9A-Za-z]{0,3}\d", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Date d'une cellule isolée (le relevé a des dates à plusieurs endroits :
# la date du relevé lui-même, et une date par facture listée)
# ---------------------------------------------------------------------------

def format_single_date_cell(cell) -> str | None:
    if pd.isna(cell):
        return None
    if isinstance(cell, (pd.Timestamp, datetime.datetime, datetime.date)):
        return cell.strftime("%d/%m/%Y")
    text = str(cell)
    match = DATE_PATTERN.search(text)
    if match:
        return match.group(1)
    match_lettres = DATE_LETTRES_PATTERN.search(text)
    if match_lettres:
        jour, mois_nom, annee = match_lettres.groups()
        mois_num = MOIS_FR.get(mois_nom.upper())
        if mois_num:
            return f"{jour.zfill(2)}/{mois_num}/{annee}"
    return None


# ---------------------------------------------------------------------------
# Métadonnées : date du relevé + nom du client
# ---------------------------------------------------------------------------

def extract_date_releve(df: pd.DataFrame, title_row_idx: int) -> str | None:
    """La date du relevé est cherchée AVANT la ligne de titre uniquement —
    au-delà, on tomberait sur les dates des factures listées dans le tableau."""
    for row_idx in range(min(title_row_idx, len(df))):
        for cell in df.iloc[row_idx]:
            date_str = format_single_date_cell(cell)
            if date_str:
                return date_str
    return None


def extract_client_name(df: pd.DataFrame, title_row_idx: int) -> str | None:
    for row_idx in range(min(title_row_idx, len(df))):
        row = df.iloc[row_idx]
        texts = [str(c).strip() for c in row if pd.notna(c) and str(c).strip()]
        if not texts:
            continue
        ligne_complete = " ".join(texts)
        if format_single_date_cell(ligne_complete) is not None:
            continue
        if LIGNE_ENTETE_DATE_PATTERN.search(ligne_complete):
            continue
        return ligne_complete
    return None


# ---------------------------------------------------------------------------
# En-tête du tableau de factures
# ---------------------------------------------------------------------------

def find_header_row_releve(df: pd.DataFrame, search_from: int = 0, search_limit: int = 30):
    """Cherche la ligne d'en-tête du tableau (DATE / NUMERO FACTURE / MONTANT
    / référence de règlement) et retourne (index_ligne, mapping colonne->index).

    La 4e colonne change de libellé selon les fichiers réels rencontrés :
    'MONTANT CUMULE', 'EFFET RECU', 'CHEQUE RECUS', 'EFFET / CHQ RECU'...
    Dans tous les cas, ce n'est jamais un vrai montant cumulé mais une
    référence de règlement en texte libre (n° de chèque, d'effet, statut) —
    d'où le nom générique 'reference_paiement'.
    """
    end = min(search_from + search_limit, len(df))
    for row_idx in range(search_from, end):
        row = df.iloc[row_idx]
        column_map = {}
        for col_idx, cell in enumerate(row):
            cell_norm = normalize_cell(cell)
            if not cell_norm:
                continue
            if any(kw in cell_norm for kw in ["CUMULE", "EFFET", "CHEQUE", "CHQ"]):
                column_map.setdefault("reference_paiement", col_idx)
            elif "NUMERO" in cell_norm:
                column_map.setdefault("numero_facture", col_idx)
            elif "DATE" in cell_norm:
                column_map.setdefault("date_facture", col_idx)
            elif "MONTANT" in cell_norm:
                column_map.setdefault("montant", col_idx)

        if "date_facture" in column_map and "montant" in column_map:
            return row_idx, column_map
    return None, None


# ---------------------------------------------------------------------------
# Lignes de factures impayées
# ---------------------------------------------------------------------------

def is_total_a_payer_row(row) -> bool:
    row_text = "".join(normalize_cell(c) for c in row)
    return "TOTALAPAYER" in row_text


def extract_releve_items(df: pd.DataFrame, header_row_idx: int, column_map: dict):
    """Extrait chaque ligne de facture impayée, jusqu'à la ligne TOTAL A PAYER.
    'reference_paiement' est toujours gardé en texte brut (n° de chèque,
    d'effet, statut de règlement...) — jamais interprété comme un montant.

    Une ligne est retenue si elle a une DATE ou un NUMERO DE FACTURE — les
    deux ne sont pas systématiquement remplis (ex : numéro présent sans date
    dans certains relevés). Un montant isolé, sans date NI numéro, est
    ignoré : c'est généralement un sous-total parasite qui traîne juste
    avant la ligne TOTAL A PAYER, pas une vraie facture."""
    items = []
    total_row_idx = None

    for row_idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[row_idx]

        if is_total_a_payer_row(row):
            total_row_idx = row_idx
            break

        date_val = row.iloc[column_map["date_facture"]] if "date_facture" in column_map else None
        numero_val = row.iloc[column_map["numero_facture"]] if "numero_facture" in column_map else None

        date_str = format_single_date_cell(date_val)
        numero_present = pd.notna(numero_val) and str(numero_val).strip() != ""

        if date_str is None and not numero_present:
            continue  # ni date ni numéro : probablement un sous-total isolé, pas une facture

        montant = parse_number(row.iloc[column_map["montant"]]) if "montant" in column_map else None

        reference_val = row.iloc[column_map["reference_paiement"]] if "reference_paiement" in column_map else None
        reference_paiement = str(reference_val).strip() if pd.notna(reference_val) else None

        items.append({
            "date_facture": date_str,
            "numero_facture": str(numero_val).strip() if numero_present else None,
            "montant": montant,
            "reference_paiement": reference_paiement,
        })

    return items, total_row_idx


def extract_total_a_payer(df: pd.DataFrame, total_row_idx: int | None) -> float | None:
    if total_row_idx is None:
        return None
    row = df.iloc[total_row_idx]
    for col_idx, cell in enumerate(row):
        cell_norm = normalize_cell(cell)
        if "TOTALAPAYER" in cell_norm:
            remaining = list(row.iloc[col_idx:])
            nums = [parse_number(v) for v in remaining]
            nums = [n for n in nums if n is not None]
            if nums:
                return nums[0]
    return None


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def parse_releve(df: pd.DataFrame, title_row_idx: int) -> dict:
    """Parse un onglet classé releve_factures_impayees."""
    empty_result = {
        "date_releve": None,
        "client": None,
        "header_row_found": False,
        "factures": [],
        "n_factures": 0,
        "total_a_payer": None,
    }

    if df.empty or title_row_idx is None or title_row_idx >= len(df):
        return empty_result

    date_releve = extract_date_releve(df, title_row_idx)
    client = extract_client_name(df, title_row_idx)
    header_row_idx, column_map = find_header_row_releve(df, search_from=title_row_idx)

    result = {
        "date_releve": date_releve,
        "client": client,
        "header_row_found": header_row_idx is not None,
        "factures": [],
        "n_factures": 0,
        "total_a_payer": None,
    }

    if header_row_idx is None:
        return result

    items, total_row_idx = extract_releve_items(df, header_row_idx, column_map)
    total_a_payer = extract_total_a_payer(df, total_row_idx)

    result["factures"] = items
    result["n_factures"] = len(items)
    result["total_a_payer"] = total_a_payer
    return result