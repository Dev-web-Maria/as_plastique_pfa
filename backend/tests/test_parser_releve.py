"""
Tests unitaires — Sprint 3 : parser_releve.py

Lancer depuis backend/ (venv activé) :
    pytest tests/ -v
"""

import sys
from pathlib import Path

import pandas as pd

# parser_releve.py utilise des imports "flat" (from parsers import ...),
# cohérents avec l'exécution réelle via run_extraction.py — donc on ajoute
# directement app/extraction/ au sys.path plutôt que d'importer via le
# chemin de package app.extraction.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "extraction"))

from parser_releve import (
    format_single_date_cell,
    extract_date_releve,
    extract_client_name,
    find_header_row_releve,
    extract_releve_items,
    extract_total_a_payer,
    parse_releve,
)


def _df_releve_ingelec():
    """Reconstruction fidèle du vrai relevé INGELEC fourni comme exemple."""
    rows = [
        ["Casablanca Le, 12/03/2021"] + [None] * 6,
        [None] * 7, [None] * 7, [None] * 7, [None] * 7, [None] * 7,
        ["INGELEC"] + [None] * 6,
        ["323, Bd Moulay Ismail 20300"] + [None] * 6,
        [None] * 7,
        ["CASABLANCA"] + [None] * 6,
        ["Objet: Relevé de Factures non payées ,"] + [None] * 6,  # title_row_idx = 10
        [None] * 7,
        ["Monsieur ,"] + [None] * 6,
        [None] * 7,
        ["Veuillez trouver ci-dessous la liste détaillée des factures échues restant  à ce jour en instance"] + [None] * 6,
        [None] * 7,
        ["de paiement :"] + [None] * 6,
        [None] * 7,
        ["DATE", None, "NUMERO FACTURE", None, "MONTANT ", None, "MONTANT CUMULE"],  # header = 18
        [None] * 7,
        ["25/01/2021", None, "0010/21", None, "43686,00", None, "réglé vir le 12/03/21"],
        ["14/06/2021", None, "096/21", None, "85852,80", None, None],
        ["25/10/2021", None, None, None, None, None, None],  # date seule, sans montant
    ] + [[None] * 7] * 10 + [
        [None, None, None, "TOTAL A PAYER", None, "0,00", None],
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# format_single_date_cell
# ---------------------------------------------------------------------------

def test_format_date_texte():
    assert format_single_date_cell("25/01/2021") == "25/01/2021"


def test_format_date_timestamp():
    assert format_single_date_cell(pd.Timestamp("2021-01-25")) == "25/01/2021"


def test_format_date_absente():
    assert format_single_date_cell(None) is None
    assert format_single_date_cell("réglé vir le 12/03/21") is None or format_single_date_cell("réglé vir le 12/03/21") == "12/03/21"
    # Note : ce texte contient une vraie date valide en fin de phrase — c'est
    # attendu que le regex la capte s'il la rencontre isolément ; le filtrage
    # de ce genre de texte en tant que "statut" se fait plus haut, au niveau
    # de la colonne montant_cumule, pas dans cette fonction générique.


# ---------------------------------------------------------------------------
# extract_date_releve / extract_client_name — cas réel INGELEC
# ---------------------------------------------------------------------------

def test_date_releve_ingelec():
    df = _df_releve_ingelec()
    assert extract_date_releve(df, title_row_idx=10) == "12/03/2021"


def test_client_name_ingelec():
    df = _df_releve_ingelec()
    assert extract_client_name(df, title_row_idx=10) == "INGELEC"


def test_client_name_bug_date_pas_en_ligne_zero():
    """Bug réel découvert : une ligne de date capturée comme nom de client
    (ex: 'Casablanca Le, 01/03/2018' dans dim_client) — arrivait quand la
    ligne de date n'est pas en position 0 du fichier."""
    df = pd.DataFrame([
        [None] * 7,
        ["Casablanca Le, 01/03/2018"] + [None] * 6,
        [None] * 7,
        ["NOM DU VRAI CLIENT"] + [None] * 6,
        ["Objet: Relevé de Factures non payées ,"] + [None] * 6,
    ])
    assert extract_client_name(df, title_row_idx=4) == "NOM DU VRAI CLIENT"


# ---------------------------------------------------------------------------
# find_header_row_releve — distinction montant / montant_cumule
# ---------------------------------------------------------------------------

def test_header_row_releve_colonnes():
    df = _df_releve_ingelec()
    header_idx, column_map = find_header_row_releve(df, search_from=10)
    assert header_idx == 18
    assert column_map["date_facture"] == 0
    assert column_map["numero_facture"] == 2
    assert column_map["montant"] == 4
    assert column_map["reference_paiement"] == 6


def test_header_row_releve_variante_effet_recu():
    """Certains fichiers utilisent 'EFFET RECU' au lieu de 'MONTANT CUMULE' —
    doit être reconnu comme la même colonne conceptuelle (reference_paiement)."""
    df = pd.DataFrame([
        ["DATE", None, "NUMERO FACTURE", None, "MONTANT ", None, "EFFET RECU"],
    ])
    header_idx, column_map = find_header_row_releve(df)
    assert header_idx == 0
    assert column_map["reference_paiement"] == 6


def test_header_row_releve_variante_cheque_recus():
    """Autre variante réelle rencontrée : 'CHEQUE RECUS'."""
    df = pd.DataFrame([
        ["DATE", None, "NUMERO FACTURE", None, "MONTANT", None, "CHEQUE RECUS"],
    ])
    header_idx, column_map = find_header_row_releve(df)
    assert column_map["reference_paiement"] == 6


# ---------------------------------------------------------------------------
# extract_releve_items — cas réel complet, avec le bug parse_number corrigé
# ---------------------------------------------------------------------------

def test_extraction_complete_releve_ingelec():
    df = _df_releve_ingelec()
    result = parse_releve(df, title_row_idx=10)

    assert result["date_releve"] == "12/03/2021"
    assert result["client"] == "INGELEC"
    assert result["n_factures"] == 3
    assert result["total_a_payer"] == 0.0

    f1 = result["factures"][0]
    assert f1["numero_facture"] == "0010/21"
    assert f1["montant"] == 43686.0
    # reference_paiement garde toujours le texte brut, jamais interprété
    # comme un montant (bug corrigé : "réglé vir le 12/03/21" donnait
    # auparavant 120321.0 en recollant les chiffres épars du texte)
    assert f1["reference_paiement"] == "réglé vir le 12/03/21"

    f2 = result["factures"][1]
    assert f2["numero_facture"] == "096/21"
    assert f2["montant"] == 85852.80

    f3 = result["factures"][2]
    assert f3["date_facture"] == "25/10/2021"
    assert f3["numero_facture"] is None
    assert f3["montant"] is None


def test_montant_avec_point_de_milliers():
    """Bug réel découvert : '15.000,00' (point = milliers, virgule = décimale)
    donnait auparavant None (float('15.000.00') invalide)."""
    df = pd.DataFrame([
        ["DATE", None, "NUMERO FACTURE", None, "MONTANT ", None, "EFFET RECU"],
        ["03/09/2020", None, "106", None, "9.995,52", None, "EFF ELC8088133"],
        [None, None, None, "TOTAL A PAYER", None, "82.924,19", None],
    ])
    result = parse_releve(df, title_row_idx=0)
    assert result["factures"][0]["montant"] == 9995.52
    assert result["total_a_payer"] == 82924.19


def test_sous_total_intermediaire_ignore():
    """Certains relevés ont une ligne 'Total MT' (sous-total) AVANT la vraie
    ligne 'TOTAL A PAYER' — elle ne doit ni arrêter l'extraction, ni être
    comptée comme une facture."""
    df = pd.DataFrame([
        ["DATE", None, "NUMERO FACTURE", None, "MONTANT ", None, "EFFET RECU"],
        ["03/09/2020", None, "106", None, "9.995,52", None, "EFF ELC8088133"],
        [None, None, None, "Total MT", None, "384.625,92", None],
        [None, None, None, "TOTAL A PAYER", None, "82.924,19", None],
    ])
    result = parse_releve(df, title_row_idx=0)
    assert result["n_factures"] == 1  # "Total MT" n'est pas compté comme une facture
    assert result["total_a_payer"] == 82924.19


def test_ligne_avec_numero_mais_sans_date():
    """Cas réel (RELEVES.xls, onglet CHINA YAN 2) : la ligne a un numéro de
    facture et un montant, mais pas de date — doit quand même être retenue
    (auparavant, l'absence de date faisait ignorer la ligne à tort)."""
    df = pd.DataFrame([
        ["DATE", None, "NUMERO FACTURE", None, "MONTANT ", None, "MONTANT CUMULE"],
        [None, None, "301", None, "71948,76", None, "71948,76"],
        [None, None, None, "TOTAL A PAYER", None, "71948,76", None],
    ])
    result = parse_releve(df, title_row_idx=0)
    assert result["n_factures"] == 1
    assert result["factures"][0]["date_facture"] is None
    assert result["factures"][0]["numero_facture"] == "301"
    assert result["factures"][0]["montant"] == 71948.76


def test_sous_total_isole_sans_date_ni_numero_ignore():
    """Cas réel : un montant isolé (sous-total parasite) juste avant TOTAL A
    PAYER, sans date NI numéro — ne doit pas être compté comme une facture."""
    df = pd.DataFrame([
        ["DATE", None, "NUMERO FACTURE", None, "MONTANT ", None, "MONTANT CUMULE"],
        [None, None, "301", None, "71948,76", None, "71948,76"],
        [None, None, None, None, "71948,76", None, None],  # montant seul, isolé
        [None, None, None, "TOTAL A PAYER", None, "71948,76", None],
    ])
    result = parse_releve(df, title_row_idx=0)
    assert result["n_factures"] == 1  # pas 2 — le sous-total isolé est exclu


# ---------------------------------------------------------------------------
# Cas limites
# ---------------------------------------------------------------------------

def test_releve_vide_ne_plante_pas():
    df = pd.DataFrame()
    result = parse_releve(df, title_row_idx=0)
    assert result["header_row_found"] is False
    assert result["n_factures"] == 0


def test_releve_sans_tableau_ne_plante_pas():
    df = pd.DataFrame([
        ["Objet: Relevé de Factures non payées"] + [None] * 4,
        ["texte", "sans", "tableau", "ici"],
    ])
    result = parse_releve(df, title_row_idx=0)
    assert result["header_row_found"] is False
    assert result["factures"] == []

def test_client_name_dates_entete_malformees():
    cas = ["Casablanca Le,/02/2021", "Casablanca Le11/06/2021", "Casablanca Le,0"]
    for ligne_entete in cas:
        df = pd.DataFrame([
            [None] * 7,
            [ligne_entete] + [None] * 6,
            [None] * 7,
            ["VRAI CLIENT"] + [None] * 6,
            ["Objet: Relevé de Factures non payées ,"] + [None] * 6,
        ])
        assert extract_client_name(df, title_row_idx=4) == "VRAI CLIENT", f"Échec pour: {ligne_entete!r}"


def test_client_name_ne_bloque_pas_un_vrai_client_contenant_le():
    df = pd.DataFrame([
        ["Casablanca Le, 12/03/2021"] + [None] * 6,
        ["INGELEC"] + [None] * 6,
        ["Objet: Relevé de Factures non payées ,"] + [None] * 6,
    ])
    assert extract_client_name(df, title_row_idx=2) == "INGELEC"