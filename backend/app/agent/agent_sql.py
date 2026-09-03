"""
Agent conversationnel Text-to-SQL — Sprint 5
Utilise Gemini (gratuit) pour traduire une question en langage naturel en
requête SQL sur as_plastique.db, exécute la requête (lecture seule, SELECT
uniquement), puis reformule le résultat en français.

Garde-fous :
1. Le SQL généré doit être un SELECT unique, sans mot-clé destructeur
2. La connexion SQLite est ouverte en LECTURE SEULE (mode=ro) — même si un
   SQL destructeur passait le filtre, la base refuserait physiquement l'écriture
3. LIMIT forcé si absent, pour ne jamais renvoyer un résultat démesuré

Lancer depuis backend/ (venv activé), après avoir mis GOOGLE_API_KEY dans .env :
    python app/agent/agent_sql.py
"""

import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

SEUIL_LIGNES_POUR_FORMATAGE_DIRECT = 8

load_dotenv()

DB_PATH = Path("../data/processed/as_plastique.db")

SCHEMA_DESCRIPTION = """
Tu interroges une base de données SQLite d'une entreprise marocaine (As Plastique)
qui fabrique des sacs/sachets plastique. Voici les tables disponibles :

dim_client(client_id, nom) -- les clients de l'entreprise
dim_date(date_id, date [texte format JJ/MM/AAAA], jour, mois, annee, trimestre)
dim_produit(produit_id, designation, unite)
dim_source(source_id, fichier, onglet, type_document)

fait_documents_vente(doc_id, source_id, type_document ['bon_livraison' ou 'facture'],
    doc_number, date_id, total_ht, tva, net_a_payer, statut_extraction)
    -- une ligne par bon de livraison ou facture

fait_lignes_vente(ligne_id, doc_id, produit_id, quantite, pu, montant)
    -- lignes produits de chaque document de vente

fait_releves(releve_id, source_id, client_id, date_releve_id, total_a_payer, statut_extraction)
    -- un relevé de factures impayées envoyé à un client à une date donnée

fait_factures_impayees(ligne_id, releve_id, date_facture_id, numero_facture,
    montant, reference_paiement, statut_reel, solde_reel, montant_regle_associe)
    -- chaque facture listée comme impayée dans un relevé.
    -- statut_reel/solde_reel/montant_regle_associe viennent du rapprochement
    -- avec le grand livre client (peuvent être NULL si non rapproché) et sont
    -- PLUS FIABLES que 'montant' (qui n'est qu'un instantané à la date du relevé).

fait_reglements(reglement_id, source_id, reference_facture, montant, mode_paiement, texte_brut)
    -- règlements extraits d'un fichier de suivi (couverture limitée, 1 seul fichier source)

fait_grand_livre(ligne_id, client_id, numero_facture, date_facture_id, montant_facture,
    statut ['Payée'/'Partielle'/'Impayée'], date_reglement_id, montant_regle, solde,
    mode_paiement, reference_reglement, doc_id_rapproche)
    -- LA source la plus fiable sur l'état réel de paiement des factures

Règles impératives :
- Réponds UNIQUEMENT avec la requête SQL, sans explication, sans balises markdown.
- Utilise UNIQUEMENT des requêtes SELECT (jamais INSERT/UPDATE/DELETE/DROP/ALTER/CREATE).
- Une seule instruction SQL, jamais plusieurs séparées par des points-virgules.
- Utilise des JOIN explicites avec les tables de dimension pour des résultats lisibles
  (ex: joindre dim_client pour avoir le nom, pas juste client_id).
- Ajoute toujours une clause LIMIT (30 par défaut) sauf si la question demande
  un total agrégé (SUM/COUNT/AVG sans détail ligne par ligne).
- Pour toute question sur le statut réel de paiement d'une facture, privilégie
  fait_grand_livre ou les colonnes *_reel de fait_factures_impayees plutôt que
  fait_reglements (couverture trop limitée).
- Si la question ne peut pas être traduite en SQL avec ce schéma, réponds
  exactement : AUCUNE_REQUETE_POSSIBLE
"""

SQL_INTERDITS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


def get_llm():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY manquante — vérifie ton fichier backend/.env")
    return ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        google_api_key=api_key,
        reasoning_effort="low",                             
    )

def valider_sql(sql: str) -> bool:
    """Garde-fou n°1 : uniquement SELECT autorisé, aucun mot-clé destructeur,
    aucune requête empilée."""
    sql_nettoye = sql.strip().rstrip(";")
    if not sql_nettoye.upper().startswith("SELECT"):
        return False
    if SQL_INTERDITS.search(sql_nettoye):
        return False
    if ";" in sql_nettoye:
        return False
    return True


def forcer_limit(sql: str, limite: int = 30) -> str:
    """Ajoute une clause LIMIT si absente et que la requête n'est pas déjà
    un agrégat global (SUM/COUNT/AVG sans GROUP BY)."""
    sql_upper = sql.upper()
    if "LIMIT" in sql_upper:
        return sql
    if re.search(r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(", sql_upper) and "GROUP BY" not in sql_upper:
        return sql  # agrégat global sans regroupement : pas besoin de LIMIT
    return sql.rstrip().rstrip(";") + f" LIMIT {limite}"


def executer_sql_lecture_seule(sql: str):
    """Garde-fou n°2 : connexion SQLite en LECTURE SEULE — même si un SQL
    destructeur passait le filtre précédent, l'écriture serait physiquement
    refusée par SQLite lui-même."""
    uri = f"file:{DB_PATH.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.execute(sql)
        colonnes = [d[0] for d in cursor.description] if cursor.description else []
        lignes = cursor.fetchall()
        return colonnes, lignes
    finally:
        conn.close()


def extraire_texte(reponse) -> str:
    """Extrait le texte d'une réponse LangChain, quel que soit le format
    retourné. Les modèles récents (ex: gemini-3.6-flash, qui supporte le
    'thinking') renvoient parfois .content comme une LISTE de blocs
    (ex: un bloc 'thinking' + un bloc 'text') plutôt qu'une simple chaîne —
    on ne garde que le texte final, pas le raisonnement interne."""
    contenu = reponse.content
    if isinstance(contenu, str):
        return contenu.strip()
    if isinstance(contenu, list):
        morceaux = []
        for item in contenu:
            if isinstance(item, str):
                morceaux.append(item)
            elif isinstance(item, dict) and "text" in item and item.get("type", "text") == "text":
                morceaux.append(item["text"])
        return "".join(morceaux).strip()
    return str(contenu).strip()


def generer_sql(question: str, llm) -> str:
    prompt = f"{SCHEMA_DESCRIPTION}\n\nQuestion : {question}\n\nSQL :"
    reponse = llm.invoke(prompt)
    sql = extraire_texte(reponse)
    # Retire d'éventuelles balises markdown malgré la consigne
    sql = re.sub(r"^```sql\s*|```\s*$", "", sql, flags=re.MULTILINE).strip()
    return sql

def formater_directement(colonnes: list, lignes: list) -> str:
    en_tete = " | ".join(colonnes)
    separateur = "-" * len(en_tete)
    corps = "\n".join(" | ".join(str(v) for v in ligne) for ligne in lignes)
    return f"{len(lignes)} résultat(s) :\n\n{en_tete}\n{separateur}\n{corps}"

def reformuler_reponse(question: str, colonnes: list, lignes: list, llm) -> str:
    if not lignes:
        return "Je n'ai trouvé aucun résultat pour cette question dans les données."

    if len(lignes) > SEUIL_LIGNES_POUR_FORMATAGE_DIRECT:
        return formater_directement(colonnes, lignes)
    resultat_texte = f"Colonnes : {colonnes}\nLignes : {lignes[:30]}"
    prompt = (
        f"Question posée : {question}\n"
        f"Résultat de la requête SQL :\n{resultat_texte}\n\n"
        "Réponds à la question en français, de façon claire et concise (2-4 phrases), "
        "en te basant uniquement sur ces données. Formate les montants avec des "
        "espaces pour les milliers et 'DH' comme devise."
    )
    reponse = llm.invoke(prompt)
    return extraire_texte(reponse)


def poser_question(question: str) -> dict:
    llm = get_llm()
    sql = generer_sql(question, llm)

    if sql == "AUCUNE_REQUETE_POSSIBLE" or not valider_sql(sql):
        return {
            "question": question,
            "sql": sql,
            "reponse": "Je ne peux pas répondre à cette question avec les données "
                       "disponibles, ou la requête générée n'est pas autorisée.",
            "erreur": True,
        }

    sql = forcer_limit(sql)

    try:
        colonnes, lignes = executer_sql_lecture_seule(sql)
    except Exception as e:
        return {
            "question": question,
            "sql": sql,
            "reponse": f"Erreur lors de l'exécution de la requête : {e}",
            "erreur": True,
        }

    reponse_texte = reformuler_reponse(question, colonnes, lignes, llm)

    return {"question": question, "sql": sql, "reponse": reponse_texte, "erreur": False}


if __name__ == "__main__":
    print("Agent conversationnel As Plastique — tape 'exit' pour quitter\n")
    while True:
        question = input("Question > ")
        if question.lower() in ("exit", "quit"):
            break
        resultat = poser_question(question)
        print(f"\nSQL généré : {resultat['sql']}")
        print(f"Réponse : {resultat['reponse']}\n")