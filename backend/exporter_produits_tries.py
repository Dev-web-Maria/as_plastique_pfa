import sqlite3

conn = sqlite3.connect("../data/processed/as_plastique.db")
produits = conn.execute(
    "SELECT produit_id, designation, unite FROM dim_produit ORDER BY designation"
).fetchall()
conn.close()

NOM_FICHIER = "produits_tries_export.txt"

with open(NOM_FICHIER, "w", encoding="utf-8") as f:
    for produit_id, designation, unite in produits:
        f.write(f"{produit_id}\t{unite}\t{designation}\n")

print(f"{len(produits)} produits exportés dans {NOM_FICHIER}")