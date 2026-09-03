"""
Fusion des doublons de produits (bruit de continuation de ligne) — post-Sprint 3
Bug découvert : la logique de "ligne de continuation" du parseur recolle parfois
des informations propres à UNE livraison (nombre de colis, de rouleaux, une date)
dans le nom du produit lui-même — créant des doublons du même vrai produit.

Nettoyage appliqué (validé sur des dizaines de vrais cas, aucune vraie dimension
mélangée) :
- Suppression de 'N colis' / 'N RX' en fin de désignation
- Suppression d'une date collée par erreur (ex: '2019-03-16 00:00:00')
- Unification des 2 caractères 'mu' visuellement identiques (μ grec / µ signe micro)
- Unification de 'Nu'/'NU' (micron écrit en lettre) vers 'Nμ'
- Suppression des virgules (jamais porteuses de sens ici)
- Normalisation des espaces multiples et des espaces autour du '/'

Limitation assumée : les variations de séparateur entre dimensions (x/X/+/rien,
ex: '60 X 17' vs '60x17' vs '61+23') ne sont PAS fusionnées automatiquement —
risque trop élevé de mélanger par erreur deux dimensions réellement différentes.

Lancer depuis backend/ (venv activé) :
    python app/database/fusionner_produits_doublons.py
"""

import re
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH = Path("../data/processed/as_plastique.db")

MU = "\u03bc"
MOTIF_COLIS = re.compile(r"\s*,?\s*\d+\s*(colis|rx)\.?\s*$", re.IGNORECASE)
MOTIF_DATE = re.compile(r"\s*,?\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s*$")
MOTIF_USAGE = re.compile(r"\s*,?\s*pour\s+usage\s*\s*industriel\.?\s*,?\s*$", re.IGNORECASE)
MOTIF_U_MICRON = re.compile(r"(\d)\s*[uU]\b")
ESPACES_MULTIPLES = re.compile(r"\s+")
ESPACES_AUTOUR_SLASH = re.compile(r"\s*/\s*")
PONCTUATION_FINALE = re.compile(r"[,.\s]+$")


def _nettoyer_une_passe(designation):
    designation = designation.replace("\u00b5", MU)
    sans_date = MOTIF_DATE.sub("", designation)
    sans_colis = MOTIF_COLIS.sub("", sans_date).strip()
    sans_usage = MOTIF_USAGE.sub("", sans_colis).strip()
    sans_u_micron = MOTIF_U_MICRON.sub(lambda m: m.group(1) + MU, sans_usage)
    sans_virgules = sans_u_micron.replace(",", " ")
    sans_espaces_multiples = ESPACES_MULTIPLES.sub(" ", sans_virgules)
    sans_slash = ESPACES_AUTOUR_SLASH.sub("/", sans_espaces_multiples)
    return PONCTUATION_FINALE.sub("", sans_slash).strip()


def nettoyer(designation):
    """Applique le nettoyage en boucle jusqu'à ce que le résultat ne change
    plus (point fixe). Nécessaire car certaines désignations ont plusieurs
    couches de bruit empilées (ex: 'colis' ET 'Pour Usage Industriel' collés
    successivement) — une seule passe laisserait une couche résiduelle,
    cassant l'idempotence et provoquant des conflits de regroupement."""
    precedent = None
    actuel = designation
    limite_securite = 10  # évite une boucle infinie en cas de cas pathologique imprévu
    while actuel != precedent and limite_securite > 0:
        precedent = actuel
        actuel = _nettoyer_une_passe(precedent)
        limite_securite -= 1
    return actuel


def fusionner():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")

    produits = conn.execute("SELECT produit_id, designation, unite FROM dim_produit").fetchall()

    groupes = defaultdict(list)
    for produit_id, designation, unite in produits:
        nettoye = nettoyer(designation)
        # Clé de regroupement = désignation nettoyée SEULE (majuscules pour la
        # comparaison), sans l'unité. La contrainte UNIQUE en base porte sur
        # designation seul — inclure l'unité dans la clé créait deux groupes
        # "différents" pouvant produire le même texte nettoyé (ex: KG vs Kg),
        # provoquant un conflit UNIQUE entre deux groupes traités l'un après
        # l'autre.
        cle = nettoye.upper()
        groupes[cle].append((produit_id, designation, nettoye))

    print("=" * 70)
    print("NETTOYAGE ET FUSION DES DÉSIGNATIONS DE PRODUITS")
    print("=" * 70)
    print(f"Produits totaux avant : {len(produits)}")
    print(f"Groupes distincts après nettoyage : {len(groupes)}")

    n_fusionnes = 0
    n_nettoyes_seuls = 0

    for variantes in groupes.values():
        variantes_triees = sorted(variantes, key=lambda v: v[0])
        id_garder, designation_brute, nettoye = variantes_triees[0]

        # 1) D'ABORD supprimer les doublons (libère leur texte de désignation,
        #    évite le conflit UNIQUE si le nom nettoyé du survivant correspond
        #    exactement au texte brut d'un doublon pas encore supprimé)
        for id_doublon, _, _ in variantes_triees[1:]:
            conn.execute(
                "UPDATE fait_lignes_vente SET produit_id = ? WHERE produit_id = ?",
                (id_garder, id_doublon),
            )
            conn.execute("DELETE FROM dim_produit WHERE produit_id = ?", (id_doublon,))
            n_fusionnes += 1

        # 2) ENSUITE renommer le survivant avec le texte nettoyé
        if designation_brute != nettoye:
            conn.execute(
                "UPDATE dim_produit SET designation = ? WHERE produit_id = ?",
                (nettoye, id_garder),
            )
            if len(variantes_triees) == 1:
                n_nettoyes_seuls += 1

    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")

    n_final = conn.execute("SELECT COUNT(*) FROM dim_produit").fetchone()[0]
    conn.close()

    print(f"Lignes fusionnées (doublons) : {n_fusionnes}")
    print(f"Désignations nettoyées sans doublon associé : {n_nettoyes_seuls}")
    print(f"Produits restants : {n_final}")
    print("=" * 70)


if __name__ == "__main__":
    fusionner()