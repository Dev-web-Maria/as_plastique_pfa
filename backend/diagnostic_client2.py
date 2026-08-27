import sys
sys.path.insert(0, "app/models")
import scoring_impayes as scoring
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 100)

df = scoring.charger_donnees()
df_client = df[df["client"] == "CHINA YANG TSE PLASTIQUE"].copy()

print(f"Nombre de lignes brutes pour ce client : {len(df_client)}")
print()

df_client["montant_effectif"] = df_client["solde_reel"].where(
    df_client["solde_reel"].notna(), df_client["montant"]
)

print(df_client[["ligne_id", "releve_id", "numero_facture", "montant", "solde_reel", "montant_effectif"]].to_string(index=False))

print()
print("Somme montant_effectif (avant dédoublonnage) :", df_client["montant_effectif"].sum())

df_dedup = scoring.deduplicate_factures(df_client)
print()
print(f"Nombre de lignes APRES dedoublonnage : {len(df_dedup)}")
if "montant_effectif" in df_dedup.columns:
    print("Somme montant_effectif (apres dédoublonnage) :", df_dedup["montant_effectif"].sum())
else:
    print("colonne montant_effectif absente apres dedup - probleme dans deduplicate_factures")