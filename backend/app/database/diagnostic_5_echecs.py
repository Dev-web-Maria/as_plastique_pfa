import sqlite3

conn = sqlite3.connect("../data/processed/as_plastique.db")

mots_cles = ["BENDADDA", "COSTA", "GLACE", "MICROTECHN", "AMTOUDI"]

for mot in mots_cles:
    print(f"--- Clients contenant '{mot}' ---")
    rows = conn.execute(
        "SELECT client_id, nom, hex(nom) FROM dim_client WHERE UPPER(nom) LIKE ?",
        (f"%{mot}%",),
    ).fetchall()
    for r in rows:
        print(" ", r)
    print()

conn.close()