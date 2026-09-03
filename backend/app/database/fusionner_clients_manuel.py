"""
Fusion manuelle de doublons clients — cas non détectables automatiquement
Ces doublons ne suivent pas le motif "préfixe exact" (déjà traité par
fusionner_clients_doublons.py) : fautes de frappe, singulier/pluriel,
abréviations, tiret ajouté... Un algorithme généraliste serait risqué ici
(faux positifs possibles sur de vraies entreprises différentes) — liste
vérifiée manuellement à la place, cas par cas.

⚠️ Vérifie la colonne GARDER ci-dessous avant de lancer : si un des deux noms
te semble plus correct que celui que j'ai choisi, inverse simplement l'ordre
dans la paire correspondante.

Lancer depuis backend/ (venv activé), APRÈS fusionner_clients_doublons.py :
    python app/database/fusionner_clients_manuel.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("../data/processed/as_plastique.db")

TABLES_AVEC_CLIENT_ID = [
    "fait_documents_vente",
    "fait_releves",
    "fait_grand_livre",
]

# (nom à GARDER, nom à FUSIONNER dedans) — vérifiés manuellement
PAIRES_A_FUSIONNER = [
    ("BENDADDA ABDERRAHMANE", "BENDADDA ABDERRAMAN , Casablanca"),
    ("COSTA CONSERVE", "COSTA - CONSERVE Kénitra"),
    ("GLACE SABRINE", "GLACES SABRINE"),
    ("ISO PLAST", "IS PLAST"),
    ("MICROTECHNIQUE INTERNATIONAL", "MICROTECHNIC INTERNATIONAL Casablanca"),
    ("MK BAGUETTERIE SARL", "MK BAGUETTE SARL"),
    ("PROMAHA", "PROHAMA Lot 515 Parc Industriel Sapino Nouaceur Casablanca"),
    ("Ste VIS AMTOUDI sarl", "Ste VIS AMTOUDI Hay lamiaa bloc 15 n 1 AIN SEBAA Casablanca"),
    ("ZIMA PLAST", "ZIMAPLAST SARL rue 7 n°5 étage 2 app 4 Sidi Bernoussi Casablanca"),
]


def fusionner():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")

    print("=" * 70)
    print("FUSION MANUELLE DE DOUBLONS CLIENTS")
    print("=" * 70)

    n_fusionnes = 0
    n_introuvables = 0

    for nom_garder, nom_fusionner in PAIRES_A_FUSIONNER:
        row_garder = conn.execute("SELECT client_id FROM dim_client WHERE nom = ?", (nom_garder,)).fetchone()
        row_fusionner = conn.execute("SELECT client_id FROM dim_client WHERE nom = ?", (nom_fusionner,)).fetchone()

        if not row_garder or not row_fusionner:
            print(f"⚠ Introuvable — garder={nom_garder!r} (trouvé={bool(row_garder)}), "
                  f"fusionner={nom_fusionner!r} (trouvé={bool(row_fusionner)})")
            n_introuvables += 1
            continue

        id_garder, id_fusionner = row_garder[0], row_fusionner[0]
        print(f"'{nom_fusionner}' -> '{nom_garder}'")

        for table in TABLES_AVEC_CLIENT_ID:
            conn.execute(
                f"UPDATE {table} SET client_id = ? WHERE client_id = ?",
                (id_garder, id_fusionner),
            )
        conn.execute("DELETE FROM dim_client WHERE client_id = ?", (id_fusionner,))
        n_fusionnes += 1

    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()

    print("\n" + "=" * 70)
    print(f"Fusionnés : {n_fusionnes}")
    print(f"Introuvables (à vérifier manuellement) : {n_introuvables}")
    print("=" * 70)


if __name__ == "__main__":
    fusionner()