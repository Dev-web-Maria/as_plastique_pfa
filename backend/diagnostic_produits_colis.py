import re
import sqlite3
from collections import defaultdict

conn = sqlite3.connect("../data/processed/as_plastique.db")
produits = conn.execute("SELECT produit_id, designation, unite FROM dim_produit").fetchall()
conn.close()

MU = "\u03bc"
MOTIF_COLIS = re.compile(r"\s*,?\s*\d+\s*(colis|rx)\.?\s*$", re.IGNORECASE)
MOTIF_DATE = re.compile(r"\s*,?\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s*$")
MOTIF_U_MICRON = re.compile(r"(\d)\s*[uU]\b")
ESPACES_MULTIPLES = re.compile(r"\s+")
ESPACES_AUTOUR_SLASH = re.compile(r"\s*/\s*")
PONCTUATION_FINALE = re.compile(r"[,.\s]+$")


def nettoyer(designation):
    designation = designation.replace("\u00b5", MU)
    sans_date = MOTIF_DATE.sub("", designation)
    sans_colis = MOTIF_COLIS.sub("", sans_date).strip()
    sans_u_micron = MOTIF_U_MICRON.sub(lambda m: m.group(1) + MU, sans_colis)
    sans_virgules = sans_u_micron.replace(",", " ")
    sans_espaces_multiples = ESPACES_MULTIPLES.sub(" ", sans_virgules)
    sans_slash = ESPACES_AUTOUR_SLASH.sub("/", sans_espaces_multiples)
    return PONCTUATION_FINALE.sub("", sans_slash).strip()


groupes = defaultdict(list)
for produit_id, designation, unite in produits:
    cle = (nettoyer(designation).upper(), (unite or "").upper())
    groupes[cle].append((produit_id, designation))

doublons = {cle: v for cle, v in groupes.items() if len(v) > 1}

print(f"Produits totaux : {len(produits)}")
print(f"Groupes fusionnables rien qu'avec le nettoyage 'N colis' : {len(doublons)}")
print(f"Lignes qui disparaîtraient (fusionnées) : {sum(len(v) - 1 for v in doublons.values())}")

print("\n--- 10 premiers exemples de groupes détectés ---")
for i, (cle, variantes) in enumerate(doublons.items()):
    if i >= 10:
        break
    print(f"\nGroupe ({len(variantes)} variantes) -> nettoyé: {cle[0][:70]}")
    for pid, desig in variantes:
        print(f"    id={pid} | {desig!r}")