"""
Tests unitaires — Sprint 3 : parser_reglement.py

Lancer depuis backend/ (venv activé) :
    pytest tests/ -v
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "extraction"))

from parser_reglement import (
    looks_like_payment_desc,
    extract_mode_paiement,
    extract_montant_from_desc,
    parse_reglements,
)


def test_looks_like_payment_desc_effet():
    assert looks_like_payment_desc("EFF 71 948,76") is True
    assert looks_like_payment_desc("EFFET 67277,61") is True


def test_looks_like_payment_desc_cheque():
    assert looks_like_payment_desc("CHEQUE 24433,59") is True


def test_looks_like_payment_desc_texte_normal():
    assert looks_like_payment_desc("bonjour") is False
    assert looks_like_payment_desc(None) is False


def test_extract_mode_paiement():
    assert extract_mode_paiement("EFF 71 948,76") == "effet"
    assert extract_mode_paiement("CHEQUE 24433,59") == "cheque"
    assert extract_mode_paiement("texte inconnu") == "inconnu"


def test_extract_montant_avec_espace_milliers():
    assert extract_montant_from_desc("EFF 71 948,76") == 71948.76


def test_extract_montant_colle_sans_espace():
    """Cas réel : 'EFF10290' (mode et montant collés, sans espace)."""
    assert extract_montant_from_desc("EFF10290") == 10290.0


def test_extract_montant_ignore_la_date_embarquee():
    """Cas réel : 'CHEQUE 25926,75 LE 13/6/18' — doit prendre le premier
    nombre (le montant), pas se laisser perturber par la date qui suit."""
    assert extract_montant_from_desc("CHEQUE  25926,75  LE 13/6/18") == 25926.75


def test_parse_reglements_extrait_reel():
    """Extrait fidèle du vrai fichier REGLEMENT FACTURE 2018 AS PLASTIQUE.xls."""
    df = pd.DataFrame([
        ["1", "EFF 71 948,76", None, None, "121", "EFF 52 886,59"],
        ["2/5/6/7/8/12", "EFFET 67277,61", None, None, "122", None],
        ["4", "EFF10290", "84", "EFF 40322,64", "124", None],
        ["9", "CHEQUE  25926,75  LE 13/6/18", None, None, "129", "EFF 7987,5"],
    ])
    result = parse_reglements(df)

    assert result["n_reglements"] == 7

    premier = result["reglements"][0]
    assert premier["reference_facture"] == "1"
    assert premier["montant"] == 71948.76
    assert premier["mode_paiement"] == "effet"

    # La référence groupée (plusieurs factures réglées ensemble) est
    # conservée telle quelle, pas éclatée
    refs = [r["reference_facture"] for r in result["reglements"]]
    assert "2/5/6/7/8/12" in refs


def test_parse_reglements_feuille_vide():
    df = pd.DataFrame()
    result = parse_reglements(df)
    assert result["n_reglements"] == 0
    assert result["reglements"] == []


def test_parse_reglements_aucune_paire_valide():
    df = pd.DataFrame([["texte", "quelconque"], ["sans", "paiement"]])
    result = parse_reglements(df)
    assert result["n_reglements"] == 0

def test_reference_numerique_sans_point_zero_parasite():
    df = pd.DataFrame([[84.0, "EFF 40322,64"]])
    result = parse_reglements(df)
    assert result["reglements"][0]["reference_facture"] == "84"