"""
Fusion des doublons de clients "nom + adresse collée" — post-Sprint 5
Bug découvert : selon la mise en page du document source, le nom du client
est parfois extrait avec son adresse à la suite (ex: 'SIMEC 265 Bd Moulay
Ismail Casablanca' au lieu de 'SIMEC'). Contrairement aux doublons de
casse/espaces déjà corrigés dans get_or_create_client, ce cas produit deux
CHAÎNES DE TEXTE différentes pour le même vrai client.

Détection : si le nom d'un client A est un préfixe exact du nom d'un client
B (après normalisation), on considère qu'il s'agit du même client — on garde
le plus court (nom pur) comme référence, on fusionne l'autre dedans.
Signal fiable et prudent : vérifié sur 11 cas réels, aucun faux positif
identifié (deux entreprises distinctes n'ont normalement aucune raison de
partager un nom strictement préfixe l'une de l'autre).

Lancer depuis backend/ (venv activé), APRÈS charger_grand_livre.py :
    python app/database/fusionner_clients_doublons.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("../data/processed/as_plastique.db")

TABLES_AVEC_CLIENT_ID = [
    "fait_documents_vente",
    "fait_releves",
    "fait_grand_livre",
]


def normaliser(nom: str) -> str:
    return " ".join(nom.upper().split())


def detecter_groupes_doublons(clients):
    """clients : liste de (client_id, nom). Retourne des groupes où chaque
    nom est un préfixe exact d'un autre nom du même groupe."""
    clients_tries = sorted(clients, key=lambda c: len(c[1]))
    utilises = set()
    groupes = []

    for i, (id_court, nom_court) in enumerate(clients_tries):
        if id_court in utilises:
            continue
        norm_court = normaliser(nom_court)
        groupe = [(id_court, nom_court)]

        for id_long, nom_long in clients_tries[i + 1:]:
            if id_long in utilises:
                continue
            norm_long = normaliser(nom_long)
            if norm_long != norm_court and norm_long.startswith(norm_court):
                groupe.append((id_long, nom_long))
                utilises.add(id_long)

        if len(groupe) > 1:
            utilises.add(id_court)
            groupes.append(groupe)

    return groupes


def fusionner():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")  # le temps de rediriger les references

    clients = conn.execute("SELECT client_id, nom FROM dim_client").fetchall()
    groupes = detecter_groupes_doublons(clients)

    if not groupes:
        print("Aucun doublon nom+adresse détecté.")
        conn.close()
        return

    print("=" * 70)
    print("FUSION DES DOUBLONS NOM + ADRESSE (détection par préfixe)")
    print("=" * 70)

    n_clients_fusionnes = 0
    for groupe in groupes:
        id_canonique, nom_canonique = groupe[0]  # le plus court = la référence
        print(f"\nRéférence conservée : id={id_canonique} | {nom_canonique!r}")

        for id_doublon, nom_doublon in groupe[1:]:
            print(f"  -> fusionné : id={id_doublon} | {nom_doublon!r}")
            for table in TABLES_AVEC_CLIENT_ID:
                conn.execute(
                    f"UPDATE {table} SET client_id = ? WHERE client_id = ?",
                    (id_canonique, id_doublon),
                )
            conn.execute("DELETE FROM dim_client WHERE client_id = ?", (id_doublon,))
            n_clients_fusionnes += 1

    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()

    print("\n" + "=" * 70)
    print(f"Groupes fusionnés : {len(groupes)}")
    print(f"Entrées client supprimées (doublons) : {n_clients_fusionnes}")
    print("=" * 70)


if __name__ == "__main__":
    fusionner()