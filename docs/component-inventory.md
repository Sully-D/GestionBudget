# Inventaire frontend — GestionDuBudget

> React 19 + TypeScript + Vite + Tailwind CSS 4 + react-router 7. `frontend/src/` : `api/` (wrappers fetch typés), `components/` (UI partagée ou feature-spécifique), `pages/` (une par route), `hooks/`, `lib/` (formatters/utilitaires).

## Routing (`App.tsx`)

| Route | Page | Notes |
|---|---|---|
| `/` | `Dashboard` | Accueil — KPIs du compte sélectionné |
| `/comptes` | `Comptes` | Configuration des comptes + revenus |
| `/transactions` | `Transactions` | Liste + navigation par période |
| `/transactions/import` | `Import` | Import OFX / CSV |
| `/transactions/nouvelle` | `NouvelleTransaction` | Création (réutilise `TransactionForm`) |
| `/transactions/:id/modifier` | `ModifierTransaction` | Édition (réutilise `TransactionForm`) |
| `/budget` | `Budget` | Tags / Règles / Cibles (3 onglets) |
| `/recurrentes` | `Recurrentes` | Candidats, rapprochements, récurrentes confirmées |
| `/projection` | `Projection` | Dépenses planifiées + horizon de projection |
| `/comparaison` | `Comparaison` | Comparaison de deux périodes |
| `/export` | `Export` | Export JSON/CSV, complet ou filtré |

`main.tsx` monte `BrowserRouter` + `StrictMode`.

---

## Pages (`src/pages/`)

| Page | Rôle | API appelées |
|---|---|---|
| `Dashboard.tsx` | KPIs de la période active — hero "Disponible" + suivi cibles pour comptes personnels, répartition par tag pour le Compte Commun, projection, liste transactions | `accounts`, `budget` (disponible, tag-spending, tag-tracking), `projections` (projection), `transactions` |
| `Comptes.tsx` | Configuration compte (jour de départ, solde/date de référence) + gestion des revenus (salaire, corrections, rentrées ponctuelles) | `accounts`, `budget` (revenues) |
| `Transactions.tsx` | Liste avec navigation de période, suppression avec confirmation | `accounts`, `transactions` |
| `Import.tsx` | Import OFX (direct) ou CSV (aperçu → mappage colonnes → import) | `accounts`, `import` |
| `NouvelleTransaction.tsx` | Exporte `TransactionForm` (composant réutilisé création/édition) + page de création. Suggestion de tag débattue à 300ms via le moteur de règles | `accounts`, `rules` (evaluate), `tags`, `transactions` |
| `ModifierTransaction.tsx` | Résout `:id` puis délègue à `TransactionForm` | — |
| `Budget.tsx` | 3 onglets : arbre de tags, règles (drag-and-drop + réordonnancement clavier), cibles budgétaires (avertissement si somme des enfants > 100%) | `accounts`, `budget`, `rules`, `tags`, `transactions` (usage count) |
| `Recurrentes.tsx` | Candidats détectés (confirmer/rejeter + tag), rapprochements en attente, récurrentes confirmées (édition inline, suppression) | `projections`, `tags` |
| `Projection.tsx` | Dépenses planifiées simples ou ventilées (2-60 périodes), liste de projection (horizon 1/3/6 mois) | `projections`, `tags` |
| `Comparaison.tsx` | Deux colonnes de période navigables indépendamment, tableau de comparaison des dépenses par tag avec écarts | `accounts`, `budget`, `transactions` |
| `Export.tsx` | Export complet ou filtré (compte + période), JSON/CSV | `accounts`, `export` |

---

## Composants (`src/components/`)

| Composant | Type | Props clés | Utilisé par |
|---|---|---|---|
| `AccountCard` | Réutilisable | `account, selected, onSelect` | `Dashboard`, `Comptes`, `Comparaison` |
| `CibleRow` | Feature (cibles) | `tag, percentage, amount, widthPct, depth, onEdit, onDeleteConfirm` | `Budget` |
| `CsvColumnMapping` | Feature (import CSV) | `fileName, columns, previewRows, mapping, onChange, onSubmit, submitting` | `Import` |
| `RuleRow` | Feature (règles) | drag-and-drop + réordonnancement clavier (`onDragStart/Enter/End`, `onKeyboardMove/Commit/Cancel`), `onEdit, onDeleteConfirm` | `Budget` |
| `TagSuggestionChip` | Feature (suggestion tag) | `selectedTagId, isSuggestion, matchedRule, allTags, onChange` | `NouvelleTransaction` (création) |
| `TagTreeRow` | Feature (arbre tags) | `node: TagNode, depth, onRenameRequest, onAddChild, onDeleteConfirm` — récursif, profondeur max 2 | `Budget` |
| `TransactionTagEditor` | Feature (tags transaction) | `transactionId, tags, allTags, onTagsChange` | `NouvelleTransaction` (édition) |

Aucune librairie de composants externe — tout est fait main avec Tailwind.

---

## Hooks (`src/hooks/`)

- **`useSelectableAccounts()`** — fetch les comptes, filtre les comptes personnels (`is_common=false`), sélectionne le premier par défaut. Factorisé depuis `Recurrentes.tsx`/`Projection.tsx` (seules pages qui n'ont besoin que des comptes personnels).

---

## Lib (`src/lib/format.ts`)

| Fonction | Rôle |
|---|---|
| `formatMontant(value)` | Format monétaire fr-FR/EUR (`Intl.NumberFormat`) |
| `formatPourcentage(value)` | Formate une valeur 0-100 avec 1 décimale + `%` |
| `formatDate(value)` | `YYYY-MM-DD` → `DD/MM/YYYY` (split string, évite les soucis de fuseau horaire) |
| `shiftDate(value, days)` | Décale une date ISO de N jours (composants `Date` locaux, pas `toISOString()`) |
| `breadcrumbPath(node, byId)` | Construit un fil d'ariane générique depuis une chaîne de `parent_id` (safe contre les cycles) |
| `tagBreadcrumb(tag, byId)` | Spécialisation de `breadcrumbPath` pour `Tag` |
| `existingTagId(tagId, byId)` | Retourne l'ID seulement s'il existe encore dans la map (détecte un tag supprimé référencé) |
| `buildSpendingRows(tagSpending)` | Enrichit `TagSpending[]` avec le libellé fil d'ariane |
| `conditionLabels` | Libellés FR des types de condition de règle |

---

## Couche API (`src/api/*.ts`)

Tous les wrappers passent par `unwrap<T>()` (`http.ts`) qui déballe `{data}` et transforme `{detail}` en `Error`. Détail complet des fonctions et de leur typage : voir [api-contracts.md](./api-contracts.md) (correspondance 1:1 avec les routes backend).

| Fichier | Domaine |
|---|---|
| `accounts.ts` | Comptes, solde à date |
| `budget.ts` | Revenus, cibles, disponible, tag-tracking, tag-spending |
| `export.ts` | Téléchargement export (gère le Blob + `content-disposition`, pas de JSON) |
| `import.ts` | Import OFX/CSV, aperçu CSV |
| `projections.ts` | Récurrentes, dépenses planifiées, rapprochement, projection |
| `rules.ts` | Règles d'auto-tagging |
| `tags.ts` | Tags |
| `transactions.ts` | Transactions, tags de transaction |
| `http.ts` | `unwrap<T>()` partagé |

---

## Build & tooling

- **Vite** (`vite.config.ts`) : plugins `@vitejs/plugin-react` + `@tailwindcss/vite`, `outDir: 'dist'`.
- **TypeScript** : project references (`tsconfig.json` → `tsconfig.app.json` + `tsconfig.node.json`), cible `es2023`, `moduleResolution: bundler`, strict (`noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`).
- **Lint** : oxlint (`.oxlintrc.json`), règles `react/rules-of-hooks: error`, `react/only-export-components: warn` (exception assumée pour `NouvelleTransaction.tsx` qui exporte à la fois `TransactionForm` et la page).
- **Styles** : Tailwind CSS 4 sans config JS séparée — tokens de design (couleurs `sidebar/surface/ink/accent/positive/warn/alert`, échelle typographique, rayons, espacements) définis via `@theme` dans `src/index.css`.
- **Scripts npm** : `dev` (serveur Vite), `build` (`tsc -b && vite build`), `lint` (oxlint), `preview`.
