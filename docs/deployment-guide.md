# Guide de déploiement — GestionDuBudget

## Cible

Self-hosted, réseau local uniquement (NAS type Synology/QNAP, Raspberry Pi). Aucune authentification (NFR-7) — l'application ne doit **jamais** être exposée directement sur Internet.

## Prérequis

- Docker (Engine 27+)
- Docker Compose (plugin `docker compose`)

## Démarrage

```bash
git clone <url-du-repo>
cd GestionDuBudget
cp .env.example .env
docker compose up -d
```

Application accessible sur `http://<hôte>:8082`.

## Configuration (`.env`)

| Variable | Défaut | Description |
|---|---|---|
| `PORT` | `8082` | Port d'écoute (exposé par docker-compose) |
| `DATABASE_PATH` | `/data/gestion_budget.db` | Chemin du fichier SQLite dans le conteneur |

Résolues par `pydantic-settings` (`app/core/config.Settings`), pas d'autre fichier de config en production.

## Build de l'image

`Dockerfile` — build multi-stage :

1. **Stage `frontend-builder`** (`node:24-slim`) : `npm ci && npm run build` → produit `frontend/dist/`.
2. **Stage final** (`python:3.13.14-slim`) : installe `backend/requirements.txt`, copie le code backend, copie le `dist/` buildé du stage précédent, expose le port `8082`.

`entrypoint.sh` (exécuté au démarrage du conteneur) :
```sh
alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8082}"
```
Les migrations Alembic sont donc appliquées automatiquement à chaque démarrage du conteneur, avant que le serveur ne commence à accepter des requêtes.

## Données et persistance

La base SQLite est persistée dans le volume Docker **nommé** `gestion_budget_data` (indépendant du cycle de vie du conteneur — `docker compose down` sans `-v` conserve les données).

Export manuel disponible depuis l'application (JSON/CSV, complet ou filtré par compte/période — voir [api-contracts.md](./api-contracts.md) § export). **Aucune sauvegarde automatique côté application** — sauvegarder le volume Docker séparément si nécessaire.

## Arrêt

```bash
docker compose down          # conserve le volume de données
docker compose down -v       # supprime aussi le volume (perte des données)
```

## Topologie

Un seul conteneur applicatif, une seule base SQLite, pas de service tiers (pas de Redis, pas de worker séparé). `docker-compose.yml` est fourni pour la facilité d'usage mais un simple `docker run` avec les mêmes variables/volume fonctionne également.
