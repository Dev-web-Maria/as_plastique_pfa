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

## Sprint 2 — Pipeline d'extraction (ETL) v1

**Objectif :** extraire automatiquement les champs utiles des types de documents les plus fréquents.

- [ ] Parseur pour les **bons de livraison** (929 onglets) : date, n° document, fournisseur/client, tableau produits (désignation, quantité, PU, montant)
- [ ] Parseur pour les **factures** (791 onglets) : mêmes champs + n° facture, TVA, total
- [ ] Journal des erreurs d'extraction (onglets non extraits automatiquement, avec raison)
- [ ] Test sur un échantillon (~50 onglets par type) avant extraction complète
- [ ] Premiers endpoints FastAPI de base (`/api/kpis`, `/api/stock`) avec données extraites partielles
- [ ] Pages React connectées à ces endpoints (preuve du flux extraction → API → interface)

**Résultats :** *(à compléter en fin de sprint)*

**Blocages / notes :** *(à compléter en fin de sprint)*

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