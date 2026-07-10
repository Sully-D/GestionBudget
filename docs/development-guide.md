# Guide de développement — GestionDuBudget

## Prérequis

- **Python** 3.13 (le conteneur de prod utilise `python:3.13.14-slim`)
- **Node.js** 24 (LTS)
- Docker + Docker Compose (optionnel en dev, requis pour reproduire le build de prod)

## Backend (`backend/`)

```bash
cd backend
pip install -r requirements-dev.txt   # requirements.txt + pytest, httpx2
alembic upgrade head
uvicorn main:app --reload --port 8082
```

Stack : FastAPI 0.138.2, SQLAlchemy 2.0.51, Alembic 1.18.5, pydantic-settings, ofxtools (import OFX). Base SQLite pointée par `DATABASE_PATH` (variable d'environnement, résolue via `app.core.config.Settings`).

### Structure des modules

8 modules sous `backend/app/` : `core`, `accounts`, `transactions`, `tags` (avec `tags/rule_engine/`), `budget`, `projections`, `import_pipeline`, `export`. Voir [architecture.md](./architecture.md) pour les frontières et dépendances entre modules, [data-models.md](./data-models.md) pour le schéma, [api-contracts.md](./api-contracts.md) pour les routes.

### Tests

```bash
cd backend
pytest
```

~421 tests dans 49 fichiers. Conventions :
- `test_<module>_api.py` — tests HTTP via `TestClient` (fixture `client(tmp_path)` locale à chaque fichier : base SQLite temporaire, seed des 3 comptes, override `get_db`).
- `test_<module>_service.py` — tests unitaires de la couche service, sans HTTP.
- `test_<module>_migration.py` — exécute `alembic upgrade head` en sous-processus contre une base temporaire et inspecte le schéma résultant (`sqlalchemy.inspect()`).
- Noms de test descriptifs : `test_<verbe>_<sujet>_<résultat_attendu>` (ex. `test_get_account_by_id_not_found_returns_404`).
- Les commentaires de test référencent souvent le critère d'acceptation ou la spec source (`# AC #6`, `# cf. Dev Notes Story 5.4`) — développement piloté par spec (BMad), voir `_bmad-output/implementation-artifacts/`.

Pour ajouter une migration :
```bash
cd backend
alembic revision -m "description"   # écrire upgrade()/downgrade() à la main ou --autogenerate
alembic upgrade head
```

### Nouvelle règle d'auto-tagging (type de condition)

Ajouter une fonction évaluateur dans `app/tags/rule_engine/evaluators.py` (signature `(rule, label, payee) -> bool`) puis l'enregistrer dans le dictionnaire `_REGISTRY` de `app/tags/rule_engine/dispatcher.py`. Aucune autre modification nécessaire (voir [architecture.md](./architecture.md) — Strategy pattern).

## Frontend (`frontend/`)

```bash
cd frontend
npm ci
npm run dev
```

Stack : React 19.2.7, TypeScript ~5.9.3, Vite ^8.1.1, Tailwind CSS ^4.3.2, react-router ^7.18.1.

Scripts :
- `npm run dev` — serveur de développement Vite
- `npm run build` — `tsc -b && vite build` (typecheck puis build de prod dans `dist/`)
- `npm run lint` — oxlint
- `npm run preview` — sert le build de prod localement

Structure : `src/api/` (wrappers fetch typés, un fichier par domaine), `src/pages/` (une par route), `src/components/` (partagés ou feature-spécifiques), `src/hooks/`, `src/lib/format.ts` (formatters). Voir [component-inventory.md](./component-inventory.md).

Pas de tests frontend automatisés à ce jour.

## Build complet (image Docker)

```bash
docker compose build
```

Reproduit le build multi-stage du `Dockerfile` (frontend buildé en stage 1, servi statiquement par FastAPI en stage 2). Voir [deployment-guide.md](./deployment-guide.md).

## Conventions de code

Voir [architecture.md](./architecture.md) § Conventions transverses — notamment : montants toujours `Decimal`/`NUMERIC(12,2)` (jamais `float`), pas de mutation d'agrégat côté frontend, enveloppe API `{data}`/`{detail}`, aucune dépendance d'authentification à ajouter.
