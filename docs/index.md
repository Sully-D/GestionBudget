---
generated: 2026-07-10
mode: initial_scan
scan_level: deep
repository_type: monolith (multi-part: backend + frontend)
---

# Documentation projet — GestionDuBudget

Point d'entrée principal pour le contexte IA et l'onboarding développeur. Application self-hosted de gestion budgétaire personnelle (foyer multi-comptes) — backend FastAPI + frontend React, un seul déployable Docker.

## Vue d'ensemble

- **Type :** monolithe, 2 parties (`backend/` API + `frontend/` SPA), un seul conteneur Docker.
- **Langage principal :** Python 3.13 (backend) / TypeScript (frontend).
- **Architecture :** monolithe en couches (Domain + API + SPA), 8 modules backend en frontières explicites. Voir [architecture.md](./architecture.md).

## Référence rapide

| | Backend | Frontend |
|---|---|---|
| Stack | FastAPI 0.138.2, SQLAlchemy 2.0.51, Alembic, SQLite | React 19.2.7, TypeScript, Vite, Tailwind CSS 4 |
| Racine | `backend/app/` | `frontend/src/` |
| Point d'entrée | `main.py` | `main.tsx` → `App.tsx` |
| Tests | pytest (~421 tests) | aucun test automatisé |

## Documentation générée

- [Vue d'ensemble du projet](./project-overview.md) — statut, epics livrés, repères de navigation
- [Architecture](./architecture.md) — paradigme, frontières de modules, logique métier notable, intégration frontend/backend
- [Arborescence source annotée](./source-tree-analysis.md)
- [Modèles de données](./data-models.md) — schéma SQLite complet, ERD, historique des migrations
- [Contrats API](./api-contracts.md) — tous les endpoints REST, requêtes/réponses
- [Inventaire frontend](./component-inventory.md) — routes, pages, composants, hooks, couche API TypeScript
- [Guide de développement](./development-guide.md) — setup, tests, conventions
- [Guide de déploiement](./deployment-guide.md) — Docker, configuration, persistance

## Documentation existante (hors `docs/`)

- [README.md](../README.md) — quickstart utilisateur/développeur
- [_bmad-output/planning-artifacts/architecture/.../ARCHITECTURE-SPINE.md](../_bmad-output/planning-artifacts/architecture/architecture-GestionDuBudget-2026-06-30/ARCHITECTURE-SPINE.md) — contrat d'architecture normatif (invariants, source de vérité historique)
- [_bmad-output/planning-artifacts/prds/](../_bmad-output/planning-artifacts/prds/) — PRD
- [_bmad-output/implementation-artifacts/](../_bmad-output/implementation-artifacts/) — stories, rétrospectives d'epic, specs correctives

## Pour démarrer

- **Lancer l'application (Docker)** : voir [deployment-guide.md](./deployment-guide.md#démarrage) ou le [README](../README.md#démarrage).
- **Développer** : voir [development-guide.md](./development-guide.md).
- **Ajouter une fonctionnalité full-stack** : lire [architecture.md](./architecture.md) (frontières de modules + logique métier) puis [api-contracts.md](./api-contracts.md) et [component-inventory.md](./component-inventory.md) pour les points d'intégration existants les plus proches.
- **Modifier le schéma** : [data-models.md](./data-models.md), puis créer une migration Alembic (voir [development-guide.md](./development-guide.md#tests)).
