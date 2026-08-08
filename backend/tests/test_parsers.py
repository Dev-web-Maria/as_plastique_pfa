"""
Tests unitaires — Sprint 2 : extraction des champs (parsers.py)

Lancer depuis backend/ (venv activé) :
    pytest tests/ -v
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extraction.parsers import (
    parse_number,
    find_header_row,
    extract_line_items,
    extract_totals,
    extract_date,
    extract_doc_number,
    parse_document,
)


# ---------------------------------------------------------------------------
# parse_number
# ---------------------------------------------------------------------------

def test_parse_number_format_francais():
    assert parse_number("1032,80") == 1032.80
    assert parse_number("17144,48") == 17144.48


def test_parse_number_avec_espaces_milliers():
    assert parse_number("1 032,80") == 1032.80


def test_parse_number_point_milliers_et_virgule_decimale():
    """Bug réel découvert sur les relevés d'impayés : '15.000,00' (point =
    séparateur de milliers, virgule = décimale) donnait auparavant None,
    car remplacer juste la virgule par un point donnait '15.000.00'
    (deux points), invalide pour float()."""
    assert parse_number("15.000,00") == 15000.00
    assert parse_number("384.625,92") == 384625.92


def test_parse_number_valeur_invalide_retourne_none():
    assert parse_number("Sachet en LDPE") is None
    assert parse_number(None) is None
    assert parse_number("") is None


# ---------------------------------------------------------------------------
# extract_doc_number
# ---------------------------------------------------------------------------

def test_doc_number_ne_capture_pas_le_n_de_bon():
    """Piège découvert en test manuel : le 'N' de 'BON' ne doit pas être
    confondu avec le 'N°' du numéro de document."""
    assert extract_doc_number("BON DE LIVRAISON N° 001666") == "001666"


def test_doc_number_facture():
    assert extract_doc_number("FACTURE N° 003") == "003"


def test_doc_number_absent():
    assert extract_doc_number("BON DE LIVRAISON SANS NUMERO") is None


# ---------------------------------------------------------------------------
# find_header_row — colonnes dans un ordre différent selon le type de document
# ---------------------------------------------------------------------------

def test_header_row_ordre_bon_livraison():
    df = pd.DataFrame([
        [None] * 7,
        ["Code", "Désignation", None, "Unité", "Quantité", "PU", "Montant"],
    ])
    row_idx, column_map = find_header_row(df)
    assert row_idx == 1
    assert column_map["designation"] == 1
    assert column_map["quantite"] == 4


def test_header_row_ordre_facture():
    """La facture a un ordre de colonnes différent (Quantité avant Désignation) —
    le parseur doit s'adapter, pas supposer une position fixe."""
    df = pd.DataFrame([
        ["Quantité", None, "DESIGNATION", None, None, "PU/H.T.", "TOTAL"],
    ])
    row_idx, column_map = find_header_row(df)
    assert row_idx == 0
    assert column_map["quantite"] == 0
    assert column_map["designation"] == 2


def test_header_row_introuvable():
    df = pd.DataFrame([["texte", "quelconque"], ["rien à voir", "ici"]])
    row_idx, column_map = find_header_row(df)
    assert row_idx is None


# ---------------------------------------------------------------------------
# extract_line_items — cas réel bon de livraison
# ---------------------------------------------------------------------------

def _df_bon_livraison():
    rows = [
        [None] * 7,
        ["BON DE LIVRAISON N° 001666"] + [None] * 6,
        [None, None, None, None, None, "SIMEC", None],
        [None] * 7,
        ["BON DE COMMANDE N° C7050032"] + [None] * 6,
        [None] * 7,
        ["Code", "Désignation", None, "Unité", "Quantité", "PU", "Montant"],
        [None] * 7,
        [None, "Sachet en PEPD 90/10 X 120, X 80μ Pour", None, "KG", "1032,80", "16,60", "17144,48"],
        [None, "Usage Industriel  52 colis", None, None, None, None, None],
        [None] * 7,
        [None, "Sachet en PEPD 60 / 80,  X 80μ Pour", None, "KG", "200,00", "16,60", "3320,00"],
        [None, "Usage Industriel  10 colis", None, None, None, None, None],
    ]
    return pd.DataFrame(rows)


def test_extraction_complete_bon_livraison():
    df = _df_bon_livraison()
    result = parse_document(df, title_row_idx=1, title_keyword="BON DE LIVRAISON")

    assert result["doc_number"] == "001666"
    assert result["n_items"] == 2

    item1 = result["items"][0]
    assert item1["quantite"] == 1032.80
    assert item1["pu"] == 16.60
    assert item1["montant"] == 17144.48
    assert "Usage Industriel" in item1["designation"]  # texte de continuation bien rattaché

    item2 = result["items"][1]
    assert item2["montant"] == 3320.00


# ---------------------------------------------------------------------------
# extract_line_items + extract_totals — cas réel facture avec TVA sur 2 lignes
# ---------------------------------------------------------------------------

def _df_facture():
    rows = [
        ["Casablanca, le", None, "07/01/2019"] + [None] * 4,
        [None] * 7,
        [None, None, "F A C T U R E      N°", None, "003", None, None],
        [None] * 7,
        ["Client", "ROCHE PLASTIC DIAMANT"] + [None] * 5,
        ["BON DE COMMANDE N° 1101934", None, None, None, "BON DE LIVRAISON N°003"] + [None] * 2,
        ["Quantité", None, "D E S I G N A T I O N", None, None, "PU/H.T.", "TOTAL"],
        [None] * 7,
        ["286,50", "Kg", "Sachet en LDPE 110/120x20cm,X 60mμ Pour", None, None, "17,75", "5085,38"],
        [None, None, "Usage Industriel", None, None, None, None],
        [None] * 7,
        [None, None, None, None, None, "TOTAL H.T.", "5085,38"],
        ["TOTAL TAXABLE", None, None, "T.V.A.  20%", None, None, "NET A PAYER"],
        ["5085,38", None, None, "1017,08", None, None, "6102,46"],
    ]
    return pd.DataFrame(rows)


def test_extraction_facture_avec_date_et_numero():
    df = _df_facture()
    result = parse_document(df, title_row_idx=2, title_keyword="FACTURE")
    assert result["doc_number"] == "003"
    assert result["date"] == "07/01/2019"
    assert result["n_items"] == 1


def test_extraction_totaux_libelle_et_valeur_sur_deux_lignes():
    """Cas réel : libellés TOTAL TAXABLE / T.V.A / NET A PAYER sur une ligne,
    valeurs alignées par colonne sur la ligne suivante."""
    df = _df_facture()
    result = parse_document(df, title_row_idx=2, title_keyword="FACTURE")
    assert result["totals"]["total_ht"] == 5085.38
    assert result["totals"]["tva"] == 1017.08
    assert result["totals"]["net_a_payer"] == 6102.46


# ---------------------------------------------------------------------------
# Cas limite : en-tête non trouvé (onglet atypique)
# ---------------------------------------------------------------------------

def test_document_sans_tableau_produits_ne_plante_pas():
    df = pd.DataFrame([
        ["BON DE LIVRAISON N° 999"] + [None] * 4,
        ["texte", "sans", "tableau", "reconnaissable"],
    ])
    result = parse_document(df, title_row_idx=0, title_keyword="BON DE LIVRAISON")
    assert result["header_row_found"] is False
    assert result["items"] == []
    assert result["n_items"] == 0


def test_onglet_vide_ne_plante_pas():
    """Cas découvert sur les vraies données (onglets 'MACHINE' quasi-vides,
    classés via le filet de secours nom de fichier) : un onglet sans aucune
    ligne ne doit pas faire planter parse_document."""
    df = pd.DataFrame()
    result = parse_document(df, title_row_idx=0, title_keyword="aucun")
    assert result["header_row_found"] is False
    assert result["n_items"] == 0


def test_title_row_idx_hors_limites_ne_plante_pas():
    """Cas où title_row_idx dépasse le nombre réel de lignes de l'onglet."""
    df = pd.DataFrame([["MACHINE 56", "arrêt", "panne"]])
    result = parse_document(df, title_row_idx=5, title_keyword="aucun")
    assert result["header_row_found"] is False
    assert result["n_items"] == 0


def test_date_en_toutes_lettres_francais():
    """Certains fichiers factures écrivent la date en toutes lettres."""
    df = pd.DataFrame([["Casablanca, le 07 Janvier 2019"] + [None] * 4])
    assert extract_date(df) == "07/01/2019"


def test_date_trouvee_au_dela_de_dix_lignes():
    """La date peut être plus bas que les 10 premières lignes sur certains
    gabarits (bloc client plus long) — la recherche doit couvrir plus large."""
    rows = [[None] * 5 for _ in range(15)]
    rows[14] = ["Casablanca, le", None, "07/01/2019"]
    df = pd.DataFrame(rows)
    assert extract_date(df) == "07/01/2019"


def test_date_vraie_cellule_excel_timestamp():
    """Bug réel découvert : certains fichiers (factures) stockent la date
    comme une vraie cellule Excel de type date, lue par pandas comme un
    Timestamp — pas comme du texte '29/03/2019'. str(Timestamp) donne
    '2019-03-29 00:00:00', que le regex texte ne reconnaît pas : il faut
    détecter le type Timestamp directement."""
    df = pd.DataFrame([[pd.Timestamp("2019-03-29"), None, None]])
    assert extract_date(df) == "29/03/2019"


def test_quantite_recuperee_depuis_colonne_code():
    """Cas réel découvert sur les vrais bons de livraison (2019/2020/2021) :
    la quantité a été tapée par erreur dans la colonne 'Code' au lieu de
    'Quantité'. La donnée existe, juste mal placée — on la récupère plutôt
    que de compter la ligne comme vide. PU/Montant restent None (le document
    source n'a jamais eu ces cases remplies — livraison faite, pas encore
    tarifée)."""
    df = pd.DataFrame([
        ["Code", "Désignation", None, None, "Unité", "Quantité", "PU", "Montant"],
        ["284,8", "Sachet en LDPE 84/140", None, None, "KG", None, None, None],
    ])
    result = parse_document(df, title_row_idx=0, title_keyword="BON DE LIVRAISON")
    assert result["n_items"] == 1
    assert result["items"][0]["quantite"] == 284.8
    assert result["items"][0]["pu"] is None


def test_ligne_vraiment_vide_ne_beneficie_pas_du_filet_de_secours():
    """Cas réel (onglet 105) : ni la colonne Quantité NI la colonne Code ne
    contiennent de valeur — la ligne doit rester exclue, pas de faux positif."""
    df = pd.DataFrame([
        ["Code", "Désignation", None, None, "Unité", "Quantité", "PU", "Montant"],
        [None, "Sachet en LDPE 18/40", None, None, "KG", None, None, "0,00"],
    ])
    result = parse_document(df, title_row_idx=0, title_keyword="BON DE LIVRAISON")
    assert result["n_items"] == 0

def test_unite_deduite_apres_quantite_pour_facture():
    """Bug réel découvert (dim_produit avec unité NULL en masse) : les
    factures n'ont jamais de colonne 'Unité' étiquetée dans leur en-tête
    (contrairement aux bons de livraison), mais l'unité (ex: 'Kg') est
    systématiquement présente dans la colonne juste après 'Quantité'."""
    df = pd.DataFrame([
        ["Quantité", None, "D E S I G N A T I O N", None, None, "PU/H.T.", "TOTAL"],
        ["286,50", "Kg", "Sachet en LDPE 110/120x20cm", None, None, "17,75", "5085,38"],
    ])
    row_idx, column_map = find_header_row(df)
    assert column_map["unite"] == 1  # juste après quantite (col 0)

    result = parse_document(df, title_row_idx=0, title_keyword="FACTURE")
    assert result["items"][0]["unite"] == "Kg"


def test_unite_explicite_prioritaire_sur_le_filet_de_secours():
    """Quand une colonne 'Unité' est explicitement étiquetée (bons de
    livraison), elle doit être utilisée telle quelle — le filet de secours
    ne doit jamais l'écraser."""
    df = pd.DataFrame([
        ["Code", "Désignation", None, "Unité", "Quantité", "PU", "Montant"],
    ])
    row_idx, column_map = find_header_row(df)
    assert column_map["unite"] == 3  # la vraie colonne Unité, pas quantite+1