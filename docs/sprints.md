# Suivi des sprints — PFA As Plastique

> Ce fichier est mis à jour à la fin de chaque sprint (cocher les tâches, ajouter les résultats/notes). Il sert de tableau de bord de coordination entre les deux membres du binôme.

**Projet :** Automatisation de la structuration et de l'analyse des données commerciales d'As Plastique — ETL, suivi des impayés et prévision des ventes
**Durée :** 6 sprints d'1 semaine
**Stack :** Python (ETL, ML/DL) · FastAPI (backend) · React (frontend) · SQLite · LangGraph (agent) · Power BI (reporting bonus)

---

## Règle de fin de sprint (à répéter à chaque sprint)

Avant de clore un sprint, dans l'ordre :

1. **Tester** — vérifier que tout ce qui a été développé fonctionne (scripts d'extraction sur un échantillon, endpoints API répondent, pages React s'affichent sans erreur)
2. **Committer** avec un message clair : `git add . && git commit -m "Sprint X : <résumé>"`
3. **Pusher** sur le repo GitHub : `git push`
4. **Mettre à jour ce fichier** (cocher les tâches, ajouter les chiffres/résultats obtenus, noter les blocages restants)

---

## Sprint 1 — Cadrage & environnement ✅ TERMINÉ

**Objectif :** poser l'environnement technique et comprendre les données réelles avant de coder l'extraction.

- [x] Structure de dossiers du projet créée (`data/`, `backend/`, `frontend/`, `notebooks/`, `tests/`)
- [x] `.gitignore` en place (exclut `data/raw`, `venv`, `node_modules`, `.env`)
- [x] Environnement virtuel Python + FastAPI fonctionnel (`/api/ping` opérationnel)
- [x] Frontend React (Vite) fonctionnel
- [x] Connexion React ↔ FastAPI validée (jalon clé du sprint)
- [x] Script d'exploration des formats Excel (`explore_formats.py`) développé et corrigé (gestion des accents, titres en lettres espacées, références croisées entre documents)
- [x] Typologie des 14 fichiers réels validée : **1783 onglets analysés, 0 non classé**
- [x] Tests unitaires du script d'exploration (13 tests, couvrant les 3 pièges corrigés)

**Résultats de la typologie (data/raw) :**

| Type de document             | Nombre d'onglets |
|------------------------------|---|
| Bons de livraison            | 929 |
| Factures                     | 791 |
| Relevés de factures impayées | 58 |
| Bons de commande             | 4 |
| Règlements (fichier unique, format à part) | 1 |
| **Total** | **1783** |

**Notes / points d'attention pour la suite :**
- Le fichier de règlements (`REGLEMENT FACTURE 2018 AS PLASTIQUE.xls`) a un format radicalement différent (grille référence/montant/mode de paiement, sans titre) → nécessitera un parseur dédié, à part du parseur générique.
- Les documents se référencent mutuellement (une facture mentionne son bon de livraison d'origine et vice-versa) → la détection du type doit se baser sur la **première ligne titre rencontrée**, pas sur la simple présence d'un mot-clé dans tout le document.
- npm/Vite a posé des soucis d'installation sous Windows (bug natif rolldown) → résolu en passant sur **pnpm** + Node 24 LTS. À appliquer sur le poste de la deuxième personne du binôme si pas encore fait.

**Outils livrés :** `backend/app/extraction/explore_formats.py`

---


## Sprint 2 — Pipeline d'extraction (ETL) v1 ✅ TERMINÉ

**Objectif :** extraire automatiquement les champs utiles des types de documents les plus fréquents.

- [x] Parseur générique pour **bons de livraison** et **factures** (`parsers.py`) : détection de l'en-tête du tableau produits par mots-clés (indépendant de l'ordre des colonnes), extraction ligne par ligne (désignation, unité, quantité, PU, montant), extraction des totaux (Total H.T., TVA, Net à payer)
- [x] Extraction des métadonnées : numéro de document, date (texte, texte en lettres, et vraies cellules Excel de type date)
- [x] Journal des erreurs / statuts d'extraction (`ok`, `extraction_incomplete`, `type_non_gere_ce_sprint`, `erreur_extraction`)
- [x] Test sur échantillon réel (5 onglets/fichier, 66 onglets au total) avant d'envisager l'extraction complète
- [x] 18 tests unitaires sur le parseur (31 au total avec le Sprint 1)
- [x] Endpoints FastAPI (`/api/kpis`, `/api/documents`, `/api/documents/{fichier}/{onglet}/items`) branchés sur les CSV d'extraction
- [x] Page React connectée affichant les KPIs et le tableau des documents extraits (preuve du flux complet extraction → API → interface)

**Résultats sur l'échantillon (66 onglets, 5 par fichier) :**

| Statut | Nombre | % |
|---|---|---|
| `ok` (extraction complète) | 49 | 74.2% |
| `type_non_gere_ce_sprint` (relevés/règlements/bons commande) | 12 | 18.2% |
| `extraction_incomplete` (onglets quasi-vides "MACHINE") | 5 | 7.6% |

**KPIs obtenus sur l'échantillon :** 754 327,89 DH extraits, 24 bons de livraison, 25 factures, 169 lignes produits.

**Bugs découverts et corrigés sur données réelles (par ordre chronologique) :**

1. **Crash sur onglets vides** (`IndexError: single positional indexer is out-of-bounds`) — des onglets "MACHINE" quasi-vides, classés via le filet de secours nom de fichier, faisaient planter `parse_document` en tentant d'indexer une ligne inexistante. → Ajout d'une garde `df.empty` / `title_row_idx >= len(df)`.
2. **Numéros de document tronqués** (`001666` devenait `1666.0`) — pandas relit une colonne CSV majoritairement numérique comme un nombre, supprimant les zéros de tête. → Forçage `dtype=str` à la lecture des CSV côté API.
3. **Valeurs `NaN` cassant la sérialisation JSON** dans l'API (`ValueError: Out of range float values are not JSON compliant`) — `.where(cond, None)` sur une colonne `float64` redonne `NaN` au lieu de `None`. → Cast `.astype(object)` avant le `.where()`.
4. **Dates absentes sur 100% des factures** — cause racine : certaines colonnes date sont de vraies cellules Excel typées date, lues par pandas comme des `Timestamp` (`"2019-03-29 00:00:00"`), que le regex texte (conçu pour `JJ/MM/AAAA`) ne reconnaît pas. → Détection directe du type `Timestamp`/`datetime` avant tentative de regex.

**Points identifiés pour le Sprint 3 :**
- Un type de document supplémentaire repéré dans les données réelles : les **AVOIRS** (notes de crédit, ex. *"AVOIR SUR FACTURE N° 170 DU 29/11/2018"*) sont probablement mal classés en `facture` à cause du mot "FACTURE" présent dans leur texte de référence. À quantifier et corriger si le volume le justifie.
- Vérifier que la date extraite correspond bien à la date de CHAQUE document et non à une date d'en-tête de fichier réutilisée par erreur, une fois l'extraction complète lancée sur les 1783 onglets.

**Outils livrés :** `backend/app/extraction/parsers.py`, `backend/app/extraction/run_extraction.py`, `backend/app/routers/kpis.py`, page React de test (`App.jsx`)

---

## Sprint 3 — Robustification ETL & base de données

**Objectif :** étendre l'extraction aux cas restants et structurer les données en base.

- [ ] Parseur pour les **relevés de factures impayées** (58 onglets)
- [ ] Parseur dédié pour le **fichier règlements** (1 onglet, format grille)
- [ ] Extension du parseur aux **bons de commande** (4 onglets)
- [ ] Extraction complète lancée sur les 1783 onglets — rapport de couverture final
- [ ] Création du schéma en étoile dans SQLite (`schema.py`)
- [ ] Chargement des données extraites dans la base
- [ ] Endpoints FastAPI complets (ventes, stocks/production si disponible, impayés)
- [ ] Pages React du dashboard principal connectées aux vraies données

**Résultats :** *(à compléter en fin de sprint)*

**Blocages / notes :** *(à compléter en fin de sprint)*

---

## Sprint 4 — Modélisation : prévision & scoring impayés

**Objectif :** produire les modèles analytiques sur données réelles.

- [ ] Prévision de la demande (baseline SARIMA/Prophet vs XGBoost vs LSTM)
- [ ] Comparaison des modèles (métriques MAE / RMSE / MAPE documentées)
- [ ] Module de scoring de risque de paiement / retards clients (à partir des relevés d'impayés)
- [ ] Endpoint `/api/forecast` et `/api/risk-score`
- [ ] Page React "Prévisions" connectée

**Résultats :** *(à compléter en fin de sprint)*

**Blocages / notes :** *(à compléter en fin de sprint)*

---

## Sprint 5 — Agent conversationnel, dashboard final & Power BI

**Objectif :** finaliser l'expérience utilisateur et ajouter le reporting BI.

- [ ] Agent conversationnel (LangGraph) branché sur la base structurée
- [ ] Endpoint `/api/chat`
- [ ] Interface de chat React connectée
- [ ] Finalisation des pages React (KPI, prévisions, stocks, impayés)
- [ ] Rapport(s) Power BI connecté(s) à la base SQLite finale *(bonus)*

**Résultats :** *(à compléter en fin de sprint)*

**Blocages / notes :** *(à compléter en fin de sprint)*

---

## Sprint 6 — Tests, documentation & soutenance

**Objectif :** fiabiliser, documenter, préparer la présentation.

- [ ] Tests d'intégration bout en bout (ETL → base → API → React)
- [ ] Corrections des bugs identifiés
- [ ] Rédaction du rapport PFA
- [ ] Préparation des slides de soutenance
- [ ] Répétition de la démonstration live
- [ ] Nettoyage final du repo (README à jour, code commenté)

**Résultats :** *(à compléter en fin de sprint)*

**Blocages / notes :** *(à compléter en fin de sprint)*

---

## Répartition en binôme (rappel)

| Étudiant(e) | Axes principaux |
|---|---|
| A | ETL, base de données, modélisation ML, endpoints FastAPI |
| B | Frontend React, intégration API, Power BI |
| Commun | Sprint 1, premières intégrations (Sprint 2), Sprint 6 |

---

*Dernière mise à jour : fin Sprint 1*