"""
Parseur pour le fichier règlements — Sprint 3
Structure radicalement différente des autres documents : pas de titre, pas
d'en-tête de colonnes, juste une grille de paires (référence, description de
paiement) répétées plusieurs fois par ligne. On scanne donc toute la feuille
à la recherche de ces paires, plutôt que de chercher un en-tête fixe.

Ce fichier ne représente qu'1 seul onglet sur les 1783 de tout le corpus —
l'approche reste volontairement simple (scanner générique), sans investir
dans une détection de structure plus élaborée.
"""

import re
import pandas as pd

from parsers import strip_accents, parse_number

PAYMENT_MODE_KEYWORDS = {
    "EFFET": "effet",
    "EFF": "effet",
    "CHEQUE": "cheque",
    "CH": "cheque",
    "ESPECE": "especes",
    "VIR": "virement",
}

NUMBER_PATTERN = re.compile(r"\d[\d\s]*,\d{1,2}|\d+")


def looks_like_payment_desc(text) -> bool:
    """Une cellule 'description' commence typiquement par un mode de paiement
    (EFF, EFFET, CHEQUE, CH, ESPECES, VIR...)."""
    if pd.isna(text):
        return False
    norm = strip_accents(str(text).upper()).strip()
    return any(norm.startswith(kw) for kw in PAYMENT_MODE_KEYWORDS)


def extract_mode_paiement(text) -> str:
    norm = strip_accents(str(text).upper()).strip()
    for kw, mode in PAYMENT_MODE_KEYWORDS.items():
        if norm.startswith(kw):
            return mode
    return "inconnu"


def extract_montant_from_desc(text) -> float | None:
    """Cherche le premier nombre plausible dans le texte de description
    (le montant du règlement), en ignorant le reste (dates, commentaires)."""
    match = NUMBER_PATTERN.search(str(text))
    if not match:
        return None
    return parse_number(match.group(0))


def format_reference(ref_cell) -> str:
    """Formate la référence proprement : évite le '84.0' parasite quand
    Excel a stocké une référence purement numérique comme un nombre."""
    if isinstance(ref_cell, float) and ref_cell.is_integer():
        return str(int(ref_cell))
    return str(ref_cell).strip()


def parse_reglements(df: pd.DataFrame) -> dict:
    """Scanne toute la feuille à la recherche de paires (référence, description
    de paiement) adjacentes horizontalement, où que ce soit dans la grille."""
    if df.empty:
        return {"n_reglements": 0, "reglements": []}

    items = []
    n_rows, n_cols = df.shape

    for row_idx in range(n_rows):
        for col_idx in range(n_cols - 1):
            ref_cell = df.iat[row_idx, col_idx]
            desc_cell = df.iat[row_idx, col_idx + 1]

            if pd.isna(ref_cell) or not looks_like_payment_desc(desc_cell):
                continue

            reference = format_reference(ref_cell)
            if reference == "":
                continue

            items.append({
                "ligne": row_idx,
                "reference_facture": reference,
                "montant": extract_montant_from_desc(desc_cell),
                "mode_paiement": extract_mode_paiement(desc_cell),
                "texte_brut": str(desc_cell).strip(),
            })

    return {"n_reglements": len(items), "reglements": items}