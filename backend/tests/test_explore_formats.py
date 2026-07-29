"""
Tests unitaires — Sprint 1 : détection du type de document et des mots-clés.

Lancer depuis backend/ (venv activé) :
    pytest tests/ -v
"""

import sys
from pathlib import Path

import pandas as pd

# Permet d'importer app.extraction.explore_formats depuis backend/tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extraction.explore_formats import (
    strip_accents,
    row_text_nospace,
    detect_type_by_first_row,
    guess_type_from_filename,
    scan_field_anchors,
)


# ---------------------------------------------------------------------------
# strip_accents
# ---------------------------------------------------------------------------

def test_strip_accents_basique():
    assert strip_accents("RELEVÉ") == "RELEVE"
    assert strip_accents("Désignation") == "Designation"


def test_strip_accents_texte_sans_accent_inchange():
    assert strip_accents("FACTURE") == "FACTURE"


# ---------------------------------------------------------------------------
# detect_type_by_first_row — cas réels validés sur les documents As Plastique
# ---------------------------------------------------------------------------

def test_bon_livraison_avec_reference_bon_commande():
    """Un bon de livraison qui référence un n° de bon de commande ne doit
    PAS être classé comme bon_commande (piège identifié sur les vrais fichiers)."""
    rows = [
        [None] * 7,
        ["BON DE LIVRAISON N° 001666"] + [None] * 6,
        [None, None, None, None, None, "SIMEC", None],
        [None] * 7,
        ["BON DE COMMANDE N° C7050032"] + [None] * 6,
        ["Code", "Désignation", None, None, "Unité", "Quantité", "PU"],
    ]
    df = pd.DataFrame(rows)
    doc_type, row_idx, keyword = detect_type_by_first_row(df)
    assert doc_type == "bon_livraison"
    assert row_idx == 1


def test_facture_avec_references_croisees():
    """Une facture qui référence son bon de commande ET son bon de livraison
    d'origine ne doit pas être classée comme l'un des deux (piège principal)."""
    rows = [
        ["Casablanca, le", None, "07/01/2019"] + [None] * 4,
        [None] * 7,
        [None, None, "F A C T U R E      N°", None, "003", None, None],
        [None] * 7,
        ["Client", "ROCHE PLASTIC DIAMANT"] + [None] * 5,
        ["BON DE COMMANDE N° 1101934", None, None, None, "BON DE LIVRAISON N°003"] + [None] * 2,
    ]
    df = pd.DataFrame(rows)
    doc_type, row_idx, keyword = detect_type_by_first_row(df)
    assert doc_type == "facture"
    assert row_idx == 2


def test_releve_factures_impayees_avec_accent():
    """Le titre contient un accent ('Relevé') — doit être détecté malgré tout,
    et avant que le mot-clé 'FACTURE' du tableau plus bas ne soit atteint."""
    rows = [
        ["Casablanca Le, 12/03/2021"] + [None] * 6,
        [None] * 7,
        ["INGELEC"] + [None] * 6,
        [None] * 7,
        ["Objet: Relevé de Factures non payées ,"] + [None] * 6,
        [None] * 7,
        ["DATE", None, "NUMERO FACTURE", None, "MONTANT"] + [None] * 2,
    ]
    df = pd.DataFrame(rows)
    doc_type, row_idx, keyword = detect_type_by_first_row(df)
    assert doc_type == "releve_factures_impayees"
    assert row_idx == 4


def test_document_sans_titre_reconnu():
    """Une feuille sans aucun mot-clé titre doit retourner type_inconnu,
    pas planter ni deviner au hasard."""
    rows = [
        ["Référence", "Montant"],
        ["001", "1200,50"],
        ["002", "980,00"],
    ]
    df = pd.DataFrame(rows)
    doc_type, row_idx, keyword = detect_type_by_first_row(df)
    assert doc_type == "type_inconnu"
    assert row_idx is None


def test_feuille_vide_ne_plante_pas():
    """Une feuille entièrement vide doit être gérée sans erreur."""
    df = pd.DataFrame([[None] * 5 for _ in range(10)])
    doc_type, row_idx, keyword = detect_type_by_first_row(df)
    assert doc_type == "type_inconnu"


# ---------------------------------------------------------------------------
# guess_type_from_filename — filet de secours uniquement
# ---------------------------------------------------------------------------

def test_fallback_reconnait_reglement():
    assert guess_type_from_filename("REGLEMENT FACTURE 2018 AS PLASTIQUE") == "reglement_facture"


def test_fallback_priorite_reglement_avant_facture():
    """'REGLEMENT' doit l'emporter sur 'FACTURE' quand les deux sont présents
    dans le nom (ordre de priorité du filet de secours)."""
    assert guess_type_from_filename("REGLEMENT FACTURE 2018") == "reglement_facture"


def test_fallback_aucun_motif_connu():
    assert guess_type_from_filename("XYZ_INCONNU_2022") is None


# ---------------------------------------------------------------------------
# scan_field_anchors — détection des champs utiles à l'extraction (sprint 2)
# ---------------------------------------------------------------------------

def test_detection_champs_tableau_produits():
    rows = [
        ["Code", "Désignation", "Unité", "Quantité", "PU", "Montant"],
        [None, "Sachet en LDPE", "KG", "300", "17,75", "5325"],
    ]
    df = pd.DataFrame(rows)
    result = scan_field_anchors(df)
    assert "tableau_produits" in result["champs_detectes"]


def test_detection_champs_total_et_tva():
    rows = [
        ["TOTAL H.T.", "22795,62"],
        ["T.V.A. 20%", "4559,12"],
    ]
    df = pd.DataFrame(rows)
    result = scan_field_anchors(df)
    assert "total" in result["champs_detectes"]
    assert "tva" in result["champs_detectes"]


def test_aucun_champ_detecte_retourne_aucun():
    df = pd.DataFrame([["texte", "quelconque"]])
    result = scan_field_anchors(df)
    assert result["champs_detectes"] == "aucun"