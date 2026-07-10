# Contrats API — GestionDuBudget

> Backend FastAPI 0.138.2, monté sur un seul processus. **Toutes** les réponses succès sont enveloppées `{"data": ...}` ; les erreurs `{"detail": "message"}` (y compris les 422 de validation Pydantic, normalisées en une chaîne unique par un handler custom dans `main.py`, au lieu du format liste-d'objets par défaut de FastAPI). Aucune authentification (réseau local uniquement, NFR-7). Les montants sont des `Decimal`, sérialisés en JSON comme des nombres à 2 décimales.

Convention de nommage : les chemins suivis de `:int` dans le code (ex. `/transactions/{transaction_id:int}`) utilisent le convertisseur Starlette `:int` — nécessaire pour ne pas entrer en collision avec les routes SPA du frontend qui partagent le même préfixe (ex. `/transactions/nouvelle`).

`GET /health` → `{"data": {"status": "ok"}}` (défini directement dans `main.py`, hors modules).

---

## accounts — `/accounts`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/accounts` | Liste tous les comptes, triés par `account_id` | `[AccountRead]` |
| GET | `/accounts/{account_id}` | Détail d'un compte (404 si absent) | `AccountRead` |
| GET | `/accounts/{account_id}/balance?as_of=<date>` | Solde à une date donnée (404 compte, 422 si `as_of < reference_date`) | `AccountBalanceRead` |
| PUT | `/accounts/{account_id}` | Met à jour `start_day` / `reference_balance` / `reference_date` (404, 422 sur IntegrityError) | `AccountRead` |

**`AccountRead`** : `account_id, name, is_common, start_day, reference_balance, reference_date, balance` (calculé), `period_start, period_end` (calculés).
**`AccountUpdate`** : `start_day?` (1-28), `reference_balance?`, `reference_date?` — validateur : `reference_balance`/`reference_date` doivent être fournis ensemble (les deux ou aucun).

---

## transactions — `/transactions`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/transactions?account_id&reference_date?` | Liste de la période active du compte. Sans `account_id` : sert le SPA `index.html` si `Accept: text/html`, sinon 422 | `{period_start, period_end, transactions: [TransactionRead]}` |
| POST | `/transactions` | Crée une transaction ; déclenche ensuite `propose_if_match` (rapprochement automatique, best-effort) | `TransactionRead` |
| GET | `/transactions/tags/{tag_id:int}/count` | Nombre d'utilisations d'un tag sur des transactions | `{count: int}` |
| GET | `/transactions/{transaction_id:int}` | Détail (404) | `TransactionRead` |
| PUT | `/transactions/{transaction_id:int}` | Mise à jour (compte non modifiable) | `TransactionRead` |
| DELETE | `/transactions/{transaction_id:int}` | Supprime ; purge d'abord les `recurring_matches` liés | `null` |
| POST | `/transactions/{transaction_id:int}/tags` | Ajoute un tag (idempotent, 422 si tag absent) | `TransactionRead` |
| DELETE | `/transactions/{transaction_id:int}/tags/{tag_id:int}` | Retire un tag | `null` |

**`TransactionCreate`** : `account_id, date, amount (Decimal 12,2), label (non vide), payee?`.
**`TransactionRead`** : `transaction_id, account_id, date, amount, label, payee, tags: [{tag_id, name}]`.

---

## tags — `/tags`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/tags` | Liste triée par `tag_id` | `[TagRead]` |
| POST | `/tags` | Crée (422 si `parent_id` absent ou déjà au niveau max 3) | `TagRead` |
| PUT | `/tags/{tag_id}` | Renomme (le parent n'est jamais modifiable — pas de déplacement dans l'arbre) | `TagRead` |
| DELETE | `/tags/{tag_id}` | Supprime (404 ; 422 si enfants présents ou tag référencé ailleurs) | `null` |

**`TagRead`** : `tag_id, name, parent_id, level`.

---

## rules — `/rules` (moteur de règles d'auto-tagging)

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/rules` | Liste triée par `sort_order` | `[RuleRead]` |
| POST | `/rules/evaluate` | Évalue `{label, payee?}` contre les règles actuelles sans persister | `{tag_id, condition_type, condition_value}` (tous `null` si aucun match) |
| POST | `/rules` | Crée (`sort_order` = max+1 auto) | `RuleRead` |
| PUT | `/rules/reorder` | Réordonne — payload doit être une permutation exacte de tous les IDs existants | `[RuleRead]` |
| PUT | `/rules/{rule_id:int}` | Modifie condition/tag (pas `sort_order`) | `RuleRead` |
| DELETE | `/rules/{rule_id:int}` | Supprime | `null` |

**`RuleCreate`/`RuleUpdate`** : `condition_type: "label_contains" | "payee_exact"`, `condition_value` (non vide), `tag_id`.

---

## budget — revenus, cibles, suivi, dépenses, disponible

### `/revenues`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| PUT | `/revenues/salaire` | Upsert salaire (`period_start=null` → référence permanente ; sinon correction ponctuelle). 422 si compte commun | `RevenueRead` |
| DELETE | `/revenues/salaire?account_id&period_start` | Supprime une correction (404 si absente) | `null` |
| POST | `/revenues/one-off` | Crée une rentrée ponctuelle | `RevenueRead` |
| DELETE | `/revenues/one-off/{revenue_id:int}` | Supprime (404 si absente ou pas `kind='ponctuel'`) | `null` |
| GET | `/revenues/period?account_id&period_start` | Résumé des revenus de la période | `RevenuePeriodSummary` |

**`RevenuePeriodSummary`** : `account_id, period_start, reference_amount, effective_salary, has_correction, one_off: [RevenueRead], total`.

### `/budget-targets`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/budget-targets?account_id` | Liste des cibles | `[BudgetTargetRead]` |
| PUT | `/budget-targets` | Upsert clé `(account_id, tag_id)`, `0 < percentage <= 100` | `BudgetTargetRead` |
| DELETE | `/budget-targets/{target_id:int}` | Supprime (404) | `null` |

### `/tag-tracking`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/tag-tracking?account_id&period_start` | Dépensé vs cible par tag (comptes personnels uniquement) | `[TagTrackingRead]` |

**`TagTrackingRead`** : `tag_id, tag_name, parent_id, level, spent, target_percentage, target_amount, gap, projection`.

### `/tag-spending`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/tag-spending?account_id&period_start` | Dépensé brut par tag, sans comparaison à une cible — fonctionne pour **tous** les comptes (y compris Commun) | `[TagSpendingRead]` |

### `/disponible`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/disponible?account_id&period_start` | Calcul du Disponible de la période (comptes personnels uniquement) | `DisponibleRead` |

**`DisponibleRead`** : `account_id, period_start, period_end, revenus, charges_recurrentes, depenses_planifiees, depenses_courantes, disponible`.

> Formules détaillées : voir [architecture.md](./architecture.md) § Logique métier notable.

---

## projections — récurrentes, dépenses planifiées, rapprochement

### `/recurring`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/recurring/candidates?account_id&tolerance_percentage=10` | Candidats détectés, non encore confirmés/rejetés | `[RecurringCandidateRead]` |
| POST | `/recurring/confirm` | Confirme un candidat (`amount < 0`) | `RecurringTransactionRead` |
| POST | `/recurring/reject` | Rejette (signature exclue des futures suggestions) | `RecurringTransactionRead` |
| GET | `/recurring?account_id&status?` | Liste (filtrable par statut) | `[RecurringTransactionRead]` |
| PUT | `/recurring/{recurring_id:int}` | Modifie montant/périodicité/tag (422 si statut ≠ `confirmed`) | `RecurringTransactionRead` |
| DELETE | `/recurring/{recurring_id:int}` | Supprime (+ ses `recurring_matches`) | `null` |

**Périodicités** : `hebdomadaire | mensuelle | trimestrielle | annuelle`.

### `/planned-expenses`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| POST | `/planned-expenses` | Crée une dépense planifiée simple (`amount < 0`) | `PlannedExpenseRead` |
| POST | `/planned-expenses/split` | Crée une dépense ventilée sur 2 à 60 périodes (`series_id` UUID partagé) | `[PlannedExpenseRead]` |
| GET | `/planned-expenses?account_id` | Liste triée par date | `[PlannedExpenseRead]` |
| PUT | `/planned-expenses/{expense_id:int}` | Modifie une ligne | `PlannedExpenseRead` |
| DELETE | `/planned-expenses/{expense_id:int}` | Supprime — si la ligne appartient à une série, **toute la série** est supprimée | `null` |

### `/projection`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/projection?account_id&horizon_months={1,3,6}` | Liste fusionnée (récurrentes projetées + dépenses planifiées) triée par date. Sans `account_id` : même fallback SPA que `/transactions` | `[ProjectionItemRead]` |

**`ProjectionItemRead`** : `date, type: "recurrente"|"planifiee", label, amount, tag_id, tag_name`.

### `/rapprochement`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/rapprochement/pending?account_id` | Propositions de rapprochement en attente | `[RapprochementCandidateRead]` |
| POST | `/rapprochement/{match_id:int}/confirm` | Confirme (404, 422 si pas `pending`) | `{match_id, status}` |
| DELETE | `/rapprochement/{match_id:int}` | Rejette (soft — `status='rejected'`, pas de suppression) | `null` |

---

## import_pipeline — `/import`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| POST | `/import/ofx` | Multipart `account_id, file`. Parse OFX, dédoublonne par FITID, persiste + auto-tag + rapprochement | `{imported_count, duplicate_count}` |
| POST | `/import/csv/preview` | Multipart `file` (`.csv` requis, sinon 400). Retourne colonnes + 3 premières lignes | `{columns, preview_rows}` |
| POST | `/import/csv` | Multipart `account_id, date_column, montant_column, libelle_column, tiers_column?, file`. Parse + persiste + auto-tag + rapprochement | `{imported_count, skipped_count}` |

Import **tout-ou-rien** : une erreur lors de l'insertion annule tout le batch (rollback), voir [architecture.md](./architecture.md) AD-7.

---

## export — `/export`

| Méthode | Path | Description | Réponse |
|---|---|---|---|
| GET | `/export/full?format={json,csv}` | Export complet (tous comptes, toutes entités). CSV = multi-sections avec BOM UTF-8 | fichier téléchargeable |
| GET | `/export/filtered?account_id&format={json,csv}&period_start?&period_end?&reference_date?` | Export des transactions d'un compte/période (période par défaut = période active du compte) | fichier téléchargeable |

Nom de fichier : `gestion-budget-export-<date>.{ext}` (full) ou `gestion-budget-export-<compte>-<période>.{ext}` (filtré). Toutes les FK sont résolues en noms lisibles (aucun ID brut dans l'export). CSV protégé contre l'injection de formule Excel (préfixe `'` sur toute cellule commençant par `=+-@`).

---

## Récapitulatif frontend → backend

Le frontend (`frontend/src/api/*.ts`) appelle exactement ces routes via des wrappers `fetch` typés (un fichier par domaine : `accounts.ts`, `budget.ts`, `export.ts`, `import.ts`, `projections.ts`, `rules.ts`, `tags.ts`, `transactions.ts`), tous passant par `unwrap<T>()` (`http.ts`) qui déballe l'enveloppe `{data}` et transforme `{detail}` en `Error`. Voir [component-inventory.md](./component-inventory.md) pour le détail des fonctions TypeScript et leur typage.
