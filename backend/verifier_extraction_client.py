import pandas as pd

df = pd.read_csv("../data/processed/extraction_full_documents.csv")
total = len(df)
avec_client = df["client_nom"].notna().sum()

print(f"Documents totaux : {total}")
print(f"Avec client extrait : {avec_client} ({avec_client/total*100:.1f}%)")
print(f"Sans client : {total - avec_client} ({(total-avec_client)/total*100:.1f}%)")

print("\nExemples de clients extraits (10 premiers distincts) :")
for nom in df["client_nom"].dropna().unique()[:10]:
    print(" -", nom)

print("\nExemples SANS client (10 premiers, pour diagnostic) :")
sans_client = df[df["client_nom"].isna()][["fichier", "onglet", "type_detecte"]].head(10)
print(sans_client.to_string(index=False))