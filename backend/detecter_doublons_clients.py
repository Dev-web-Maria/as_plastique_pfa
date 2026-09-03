import sqlite3
import re

conn = sqlite3.connect("../data/processed/as_plastique.db")
rows = conn.execute("SELECT client_id, nom FROM dim_client").fetchall()

def normaliser(nom):
    return re.sub(r"\s+", " ", nom.strip().upper())

groupes = {}
for client_id, nom in rows:
    cle = normaliser(nom)
    groupes.setdefault(cle, []).append((client_id, nom))

doublons = {cle: v for cle, v in groupes.items() if len(v) > 1}

print(f"Total clients : {len(rows)}")
print(f"Groupes de doublons potentiels détectés : {len(doublons)}")
print()
for cle, variantes in doublons.items():
    print(f"  '{cle}' apparaît {len(variantes)} fois :")
    for client_id, nom in variantes:
        print(f"    - id={client_id} | {nom!r}")