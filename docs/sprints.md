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

## Sprint 3 — Robustification ETL & base de données ✅ TERMINÉ

**Objectif :** étendre l'extraction à tous les types de documents et structurer l'ensemble des données réelles en base.

- [x] Parseur des **relevés de factures impayées** (`parser_releve.py`)
- [x] Parseur du **fichier règlements** (`parser_reglement.py`) : scan générique de paires (référence, description de paiement) sur une grille sans titre
- [x] Investigation "AVOIR" : 3 onglets sur 1783 (0,17%) — impact négligeable, non traité à part
- [x] **Extraction complète sur les 1783 onglets** (~12s d'exécution)
- [x] Schéma de base en **constellation** (`schema.py`) : 4 dimensions + 5 tables de faits à grains différents (ventes, relevés, règlements), avec versionnement (`DROP TABLE` avant recréation, pour rester synchronisé pendant que le schéma évolue)
- [x] Chargement (`load_to_db.py`) rendu **idempotent** (`reset_tables()`)
- [x] **Enrichissement post-extraction** (`enrichissement.py`) : calculs déductibles et croisements entre tables, toujours tracés (colonnes `*_calculee`/`*_recuperee`)
- [x] Vérification manuelle exhaustive des `extraction_incomplete` et des dimensions (`dim_client`, `dim_produit`)
- [x] **65 tests unitaires** au total

**Résultats finaux de l'extraction (1783 onglets) :**

| Statut | Nombre | % |
|---|---|---|
| `ok` | 1727 | 96,9% |
| `extraction_incomplete` | 52 | 2,9% |
| `type_non_gere_ce_sprint` (bon_commande) | 4 | 0,2% |

**Contenu final de la base (après enrichissement) :**

| Table | Lignes |
|---|---|
| `fait_documents_vente` | 1720 |
| `fait_lignes_vente` | 5333 |
| `fait_releves` | 58 |
| `fait_factures_impayees` | 349 |
| `fait_reglements` | 62 |
| `dim_produit` | 2653 |
| `dim_client` | 35 (nettoyé) |
| `dim_date` | 644 |

**Impact de l'enrichissement :**
- `tva` : 44,4% → 2,9% de NULL (714 valeurs déduites du Total H.T. à 20%)
- `net_a_payer` : 44,6% → 2,9% de NULL (717 valeurs déduites)
- `date_facture_id` (relevés) : 1,4% → 0,6% (croisement avec `fait_documents_vente`)
- `total_a_payer` (relevés) : 17,2% → 6,9% (recalculé depuis les factures listées)

**Bugs découverts et corrigés sur données réelles (12 au total, par ordre chronologique) :**

1. Crash sur onglets vides (`title_row_idx` hors limites)
2. Numéros de document tronqués (`001666` → `1666.0`) — `dtype=str` forcé
3. `NaN` cassant la sérialisation JSON — cast `.astype(object)`
4. Dates absentes sur 100% des factures — cellules Excel de vrai type date (`Timestamp`), pas du texte
5. `parse_number` recollait des chiffres épars d'un texte de statut (`120321.0` au lieu de `None`)
6. Format milliers avec point (`"15.000,00"`) mal géré
7. Colonne "montant cumulé" en réalité une référence de paiement en texte libre
8. Ligne avec numéro sans date exclue à tort
9. Chargement non idempotent (doublons si le `.db` verrouillé par DB Browser n'était pas supprimé)
10. Quantité tapée dans la colonne "Code" au lieu de "Quantité" sur 6 documents réels
11. **`dim_client` pollué par des lignes de date d'en-tête** — 2 sous-cas : (a) l'heuristique supposait à tort que la ligne 0 est toujours la ligne de date, (b) certaines dates d'en-tête malformées (jour manquant, séparateurs collés) échappaient à la détection de date valide → détection par la **forme** ("Ville Le" + chiffre) ajoutée en complément
12. **`dim_produit.unite` NULL en masse pour tout produit apparu uniquement dans une facture** — les factures n'ont jamais de colonne "Unité" étiquetée dans leur en-tête (contrairement aux bons de livraison) → filet de secours : l'unité est déduite de la colonne juste après "Quantité"

**Limitations assumées et documentées :**
- Documents "AVOIR" (3/1783) restent classés `facture`, montants correctement signés
- Données réellement incomplètes dans certains fichiers sources (cellules jamais remplies, `#REF!` cassé) — non récupérables
- Bons de commande autonomes (4/1783) non traités séparément

**Outils livrés :** `backend/app/extraction/parser_releve.py`, `parser_reglement.py`, `backend/app/database/schema.py`, `load_to_db.py`, `enrichissement.py`, base `data/processed/as_plastique.db`

---

---

## Sprint 4 — API finale, dashboard & modélisation ✅ TERMINÉ

**Objectif :** connecter le dashboard aux vraies données de la base, puis produire les modèles de prévision et de scoring.

- [x] Endpoints FastAPI complets branchés sur `as_plastique.db` (`dashboard.py`, remplace le routeur CSV du Sprint 2) : `/api/kpis`, `/api/ventes-mensuelles`, `/api/prevision`, `/api/clients-risque`, `/api/documents`
- [x] Page React du dashboard connectée : KPIs, graphique ventes réelles + prévision (Recharts), tableau top clients à risque
- [x] Exploration des ventes réelles avant modélisation (`explore_ventes.py`) : couverture temporelle, top produits, qualité des données
- [x] **Bug critique découvert et corrigé** : années à 2 chiffres (`07/01/19`) mal interprétées lors du chargement, fragmentant la série mensuelle en doublons (`2018-02` vs `18-02`) — extension à 4 chiffres + validation de plausibilité (jour/mois/année) ajoutées dans `load_to_db.py`
- [x] Préparation de la série mensuelle (`build_serie_mensuelle.py`) : exclusion documentée de l'anomalie isolée 2011, du début 2017 (trop fragmenté), du dernier mois tronqué
- [x] Prévision de la demande : comparaison rigoureuse de 6 configurations (SARIMA échelle réelle/log, XGBoost avec/sans `lag_12`, avec/sans transformation log)
- [x] **Validation croisée walk-forward** (4 plis, horizon 3 mois) — a inversé le classement obtenu sur un split unique, confirmant la nécessité de cette étape
- [x] Génération de la prévision finale (`predire_futur.py`) : modèle réentraîné sur toute la série, prévision itérative des 6 prochains mois
- [x] Scoring de risque impayés (`scoring_impayes.py`) : score pondéré explicable par client (montant dû, récurrence, ancienneté, taux de factures sans référence de règlement) — pas de modèle supervisé, faute d'étiquette fiable "défaut/non défaut" dans les données

**Résultat retenu pour la prévision (validation croisée, le plus fiable) :**

| Modèle | MAPE moyen (4 plis) |
|---|---|
| XGBoost (sans lag_12, log) — retenu | 19,9% |
| XGBoost (sans lag_12, sans log) | 20,6% |
| SARIMA (échelle réelle) | 28,4% |
| SARIMA (log) | 31,7% |
| XGBoost (avec lag_12, log) | 26,5% |
| XGBoost (avec lag_12, sans log) | 32,6% |

**Enseignement méthodologique clé :** sur un split unique (6 derniers mois), SARIMA semblait gagner (22,0% vs 22,3%) ; la validation croisée a révélé que ce résultat tenait à une fenêtre de test favorable par hasard — XGBoost est en réalité le modèle le plus robuste en moyenne. De même, `lag_12` et la transformation log, qui amélioraient les résultats sur données synthétiques de test, ont dégradé la performance sur les vraies données (coût en volume d'entraînement pour `lag_12` ; sous-estimation des pics erratiques pour le log) — illustration concrète de l'importance de la validation empirique plutôt que l'application de techniques par défaut.

**Résultat du scoring impayés :**

| Niveau de risque | Nombre de clients |
|---|---|
| Élevé | 11 |
| Moyen | 11 |
| Faible | 12 |

Client le plus à risque : CHINA YANG TSE PLASTIQUE (1,66 M DH dus, ancienneté moyenne 332 jours).

**KPIs globaux de la base :** 26 259 263,91 DH de ventes totales, 1673 documents extraits, 35 clients, 1 283 592 420,53 DH d'impayés totaux recensés.

**Limitations assumées et documentées :**
- Le scoring impayés est un score pondéré transparent, pas un modèle supervisé — choix méthodologique justifié par l'absence d'étiquette fiable dans les données sources
- Le MAPE de 19,9% reste élevé par rapport à l'objectif initial (équivalent 90% de "précision") — expliqué par le volume de données limité (~45 mois) et la forte volatilité intrinsèque des ventes réelles (facteur x6 entre le mois le plus faible et le plus fort)
- Matériel (CPU/GPU) sans impact sur les résultats — SARIMA et XGBoost tournent sur des volumes trop faibles pour qu'une accélération GPU ait un intérêt

**Outils livrés :** `backend/app/models/explore_ventes.py`, `build_serie_mensuelle.py`, `train_forecast.py`, `predire_futur.py`, `scoring_impayes.py`, `backend/app/routers/dashboard.py`, `frontend/src/App.jsx` (dashboard complet)

---

## Sprint 5 — Agent conversationnel, dashboard final & Power BI

### Partie 4 — Dashboard React professionnel (multi-pages) ✅ TERMINÉE

- [x] Refonte complète de l'interface : sidebar fixe avec logo, navigation par icônes (lucide-react), palette de couleurs reprenant l'identité visuelle du logo (bleu marine + rouge)
- [x] 9 pages fonctionnelles : Vue globale, Ventes, Clients (liste + fiche détaillée cliquable), Bons de livraison, Factures, Impayés, Prévisions, Assistant Data
- [x] Filtres de période réels sur chaque page pertinente (année/mois/plage de dates), branchés sur des endpoints FastAPI dédiés — fini les totaux bruts sur 4 ans, chaque vue peut être filtrée sur une période précise
- [x] Endpoints ajoutés : `/api/kpis-ventes`, `/api/top-produits`, `/api/dernieres-ventes`, `/api/clients`, `/api/clients/{id}`, `/api/documents-detail`, `/api/kpis-documents`, réconciliation et grand livre rendus filtrables
- [x] Bug de tri de dates corrigé sur tous les endpoints (`ORDER BY dd.date` triait le texte "JJ/MM/AAAA" au lieu de la vraie chronologie — `31/12/2020` apparaissait après `05/01/2021`) — corrigé partout via une reconstruction `printf('%Y-%m-%d')`

### Partie 5 — Découverte et correction de doublons massifs (clients + produits) ✅ TERMINÉE

Déclenché par une vérification manuelle des KPIs ("2653 produits, c'est exagéré") — un vrai travail d'investigation, pas juste un ticket fermé rapidement.

**Cause racine commune aux deux problèmes** : la logique de "ligne de continuation" du parseur (Sprint 2), censée recoller un texte de désignation qui déborde sur 2 lignes, recolle en réalité **n'importe quel texte parasite** trouvé juste après (adresse du client, nombre de colis/rouleaux d'une livraison précise, une date) — polluant ce qui devrait être un identifiant stable.

**Doublons clients** (122 → 61) :
- Adresse collée au nom (`"SIMEC 265 Bd Moulay Ismail Casablanca"` au lieu de `"SIMEC"`) → détection automatique par préfixe exact (36 groupes, 41 clients fusionnés) — signal fiable, vérifié sans faux positif sur 11 cas réels
- Fautes de frappe / singulier-pluriel / abréviations (`"GLACE"` vs `"GLACES"`, `"IS PLAST"` vs `"ISO PLAST"`, `"PROHAMA"` vs `"PROMAHA"`...) → fusion manuelle vérifiée cas par cas (6 groupes), volontairement non automatisée (risque de mélanger à tort deux vraies entreprises différentes)

**Doublons produits** (2653 → 1539, soit -42%) :
- `"N colis"` / `"N RX"` (quantité de livraison, pas une caractéristique produit)
- Date collée par erreur (`"...Pour Usage Industriel, 2019-03-16 00:00:00"`)
- Deux caractères "mu" visuellement identiques mais informatiquement différents (μ grec U+03BC vs µ signe micro U+00B5), et micron parfois écrit en lettre (`"70u"`)
- Espaces multiples, espaces autour du `/`, virgules parasites
- Formule `"Pour Usage Industriel"` (présente sur la quasi-totalité des désignations, aucune valeur distinctive) retirée entièrement
- **Bug de non-idempotence découvert et corrigé** : certaines désignations ont plusieurs couches de bruit empilées ; une seule passe de nettoyage en laissait une partie — corrigé par une boucle jusqu'à point fixe
- **Limitation assumée** : les variations de séparateur entre dimensions (`"60 X 17"` vs `"60x17"` vs `"61+23"`) ne sont pas fusionnées automatiquement — risque trop élevé de mélanger deux dimensions réellement différentes (ex: `80/140` vs `84/140`)

**Garde-fou appliqué à chaque étape** : le CA total (`26 259 263,91 DH`) vérifié identique avant/après chaque fusion — confirme qu'aucune vente n'est perdue, seulement regroupée sous le bon identifiant.

**Outils livrés** : `backend/app/database/fusionner_clients_doublons.py`, `fusionner_clients_manuel_v2.py`, `fusionner_produits_doublons.py`, `backend/diagnostic_5_echecs.py`, `diagnostic_produits_colis.py`

⚠️ **Ces 3 scripts de fusion doivent être relancés après tout rechargement complet du pipeline** (`schema.py` → ... → `charger_grand_livre.py`) — ce ne sont pas des étapes idempotentes intégrées à l'ETL principal, la cause racine dans `parsers.py` n'ayant pas été corrigée (choix assumé, fin de projet).

### Partie 6 — Rapport Power BI (bonus) ✅ TERMINÉ

- [x] Connexion ODBC directe à la base SQLite (pilote `sqliteodbc_w64.exe`), DSN configuré
- [x] Modèle de données : relations corrigées (suppression de fausses relations créées par coïncidence de noms de colonnes comme `ligne_id`), gestion des chemins ambigus vers `dim_date` (schéma en constellation : un seul chemin actif à la fois)
- [x] 4 pages : Couverture, Ventes, Clients, Impayés & Recouvrement
- [x] Filtres (segments) sur chaque page pertinente : année, mois, type de document, statut
- [x] Mesures DAX pour tous les KPIs (CA, volume, clients actifs, taux de rapprochement...)
- [x] Paramètre de champ pour basculer Qté/Montant sur le graphique top produits

**Bugs corrigés en cours de construction** :
- Tri de mois/années dans le désordre sur les graphiques (réglage "Trier par" du visuel, pas le type de donnée)
- Format de nombres du CSV de scoring interprété avec le mauvais séparateur décimal (import via paramètres régionaux "Anglais US" explicites)
- Agrégation "Somme" par défaut sur des colonnes déjà pré-calculées (score de risque, ancienneté) → "Ne pas résumer", fixé au niveau modèle
- Relation créée dans le mauvais sens (1-à-plusieurs inversé) causant une multiplication en cascade des valeurs

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