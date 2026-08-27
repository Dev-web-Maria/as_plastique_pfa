import sqlite3

conn = sqlite3.connect("../data/processed/as_plastique.db")
rows = conn.execute(
    "SELECT client_id, nom, length(nom), hex(nom) FROM dim_client WHERE nom LIKE '%CHINA%'"
).fetchall()
for r in rows:
    print(r)
conn.close()