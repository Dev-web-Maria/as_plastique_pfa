"""
Fusion manuelle de doublons clients (round 2) — via identifiants numériques
La comparaison de noms exacts a échoué à cause d'espaces multiples invisibles
dans les vraies données (ex: 'COSTA - CONSERVE                    Kénitra').
On utilise directement les client_id, identifiés via diagnostic_5_echecs.py
— aucune ambiguïté possible.

Lancer depuis backend/ (venv activé) :
    python app/database/fusionner_clients_manuel_v2.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("../data/processed/as_plastique.db")

TABLES_AVEC_CLIENT_ID = [
    "fait_documents_vente",
    "fait_releves",
    "fait_grand_livre",
]

# (id à GARDER, [ids à FUSIONNER dedans]) — identifiés via diagnostic_5_echecs.py
GROUPES_A_FUSIONNER = [
    (38, [76]),        # BENDADDA ABDERRAHMANE <- BENDADDA ABDERRAMAN , Casablanca
    (104, [88]),       # COSTA  CONSERVE <- COSTA - CONSERVE ... Kénitra
    (23, [106]),       # GLACE SABRINE <- GLACES  SABRINE
    (103, [86]),       # MICROTECHNIQUE INTERNATIONAL <- MICROTECHNIC INTERNATIONAL ... Casablanca
    (34, [84, 107]),   # Ste VIS AMTOUDI sarl <- Ste VIS AMTOUDI Hay lamiaa... ET <- amtoudi (3e variante trouvée)
]


def fusionner():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")

    print("=" * 70)
    print("FUSION MANUELLE DE DOUBLONS CLIENTS (via identifiants)")
    print("=" * 70)

    n_fusionnes = 0
    n_introuvables = 0

    for id_garder, ids_fusionner in GROUPES_A_FUSIONNER:
        nom_garder_row = conn.execute("SELECT nom FROM dim_client WHERE client_id = ?", (id_garder,)).fetchone()
        if not nom_garder_row:
            print(f"⚠ id_garder={id_garder} introuvable — vérifie que le script précédent n'a pas déjà changé les id")
            n_introuvables += 1
            continue

        print(f"\nRéférence conservée : id={id_garder} | {nom_garder_row[0]!r}")

        for id_fusionner in ids_fusionner:
            nom_fusionner_row = conn.execute("SELECT nom FROM dim_client WHERE client_id = ?", (id_fusionner,)).fetchone()
            if not nom_fusionner_row:
                print(f"  ⚠ id={id_fusionner} introuvable — déjà fusionné ou id incorrect")
                n_introuvables += 1
                continue

            print(f"  -> fusionné : id={id_fusionner} | {nom_fusionner_row[0]!r}")
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
    print(f"Introuvables : {n_introuvables}")
    print("=" * 70)


if __name__ == "__main__":
    fusionner()