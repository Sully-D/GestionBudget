# Arborescence source — GestionDuBudget

```text
GestionDuBudget/
├── backend/
│   ├── app/
│   │   ├── core/              # config (pydantic-settings), session DB (+ PRAGMA foreign_keys),
│   │   │                      # core.period (calcul dynamique des périodes budgétaires)
│   │   ├── accounts/          # model, schema, router, service — Compte, solde, période
│   │   ├── transactions/      # model, schema, router, service — Transaction + tags associés
│   │   ├── tags/
│   │   │   └── rule_engine/   # dispatcher (Strategy) + évaluateurs (label_contains, payee_exact)
│   │   ├── budget/            # model (Revenue, BudgetTarget) — 4 routers : revenus, cibles,
│   │   │                      # suivi (tracking), dépenses par tag (spending), disponible
│   │   ├── projections/       # model (RecurringTransaction, PlannedExpense, RecurringMatch)
│   │   │                      # 5 routers : récurrentes, dépenses planifiées, projection, rapprochement
│   │   ├── import_pipeline/   # ofx_parser, csv_parser, dedup, pipeline (import atomique)
│   │   └── export/            # router, csv_exporter, serializers JSON + CSV multi-sections
│   ├── main.py                 # montage FastAPI, handler 422 custom, app.frontend() (SPA fallback)
│   ├── entrypoint.sh            # alembic upgrade head && uvicorn
│   ├── alembic/versions/        # 12 migrations linéaires
│   └── tests/                   # ~421 tests pytest (test_<module>_api/service/migration.py)
├── frontend/
│   └── src/
│       ├── api/                 # wrappers fetch typés, un fichier par domaine backend
│       ├── components/          # AccountCard (réutilisable) + 6 composants feature-spécifiques
│       ├── pages/                # 11 pages, une par route (voir App.tsx)
│       ├── hooks/                # useSelectableAccounts
│       ├── lib/format.ts         # formatMontant, formatDate, shiftDate, breadcrumb, etc.
│       ├── App.tsx               # définition des routes react-router
│       └── main.tsx              # bootstrap React + BrowserRouter
├── docs/                        # cette documentation (générée depuis le code, tenue à jour manuellement)
├── _bmad-output/                # artefacts de planification BMad (PRD, architecture-spine, stories)
├── Dockerfile                    # build multi-stage : frontend (Node 24) puis backend (Python 3.13)
├── docker-compose.yml             # service unique, volume nommé gestion_budget_data
└── .env.example                   # PORT, DATABASE_PATH
```

## Points d'entrée

- **Backend** : `backend/main.py` — assemble l'app FastAPI, monte 15 routers + `/health`, sert le SPA en fallback.
- **Frontend (dev)** : `frontend/src/main.tsx` → `App.tsx`.
- **Frontend (prod)** : `frontend/dist/index.html`, buildé par Vite et copié dans l'image Docker, servi par `app.frontend()`.
- **Conteneur** : `backend/entrypoint.sh` — migre puis lance `uvicorn`.

## Points d'intégration

Le frontend ne communique avec le backend que via l'API REST (`fetch`, enveloppe `{data}`/`{detail}`) — aucun état partagé en dehors des requêtes HTTP. Le build frontend est un artefact statique intégré à l'image backend au build time (pas de service séparé en production). Détail : [architecture.md](./architecture.md) § Frontend ↔ Backend.

## Dossiers hors périmètre applicatif

`backend/.venv/`, `backend/dist_verify/`, `frontend/node_modules/`, `frontend/dist/` (généré), `.claude/`, `.agents/` — environnements/outils, non documentés ici.
