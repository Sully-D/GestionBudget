# Vue d'ensemble — GestionDuBudget

## But

Application web self-hosted de gestion budgétaire personnelle pour un foyer avec plusieurs comptes bancaires (comptes personnels + compte commun). Suivi des transactions, tags hiérarchiques, budget en pourcentage du salaire, projections de trésorerie, import OFX/CSV. Conçue pour tourner en local sur un NAS ou un Raspberry Pi, sans authentification (réseau local uniquement).

## Statut

Projet **feature-complete** — les 7 epics du PRD (FR-1 à FR-34, NFR-1 à NFR-8) sont livrés (voir `_bmad-output/planning-artifacts/epics.md` et `_bmad-output/implementation-artifacts/sprint-status.yaml`).

| Epic | Périmètre |
|---|---|
| 1 | Comptes, saisie et gestion manuelle des transactions |
| 2 | Hiérarchie de tags, moteur de règles d'auto-tagging |
| 3 | Import OFX (dédoublonné) et CSV (mappage visuel) |
| 4 | Revenus, cibles budgétaires, suivi réel vs cible |
| 5 | Détection des récurrentes, dépenses planifiées, rapprochement |
| 6 | Dashboard (Disponible, répartition, comparaison de périodes, projection) |
| 7 | Export complet et filtré des données |

## Type de projet et structure

**Monolithe multi-part** (un seul déployable, deux codebases séparées) :

| Part | Chemin | Type |
|---|---|---|
| Backend | `backend/` | API FastAPI + logique métier + SQLite |
| Frontend | `frontend/` | SPA React, buildée puis servie statiquement par le backend |

## Stack — résumé

Backend : Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, SQLite. Frontend : React 19, TypeScript, Vite, Tailwind CSS 4. Déploiement : image Docker unique (multi-stage), un volume nommé pour les données. Détail complet : [architecture.md](./architecture.md).

## Repères pour naviguer la documentation

- Nouveau sur le projet / contexte IA → commencer par [index.md](./index.md)
- Comprendre les règles d'architecture et la logique métier → [architecture.md](./architecture.md)
- Schéma de base de données → [data-models.md](./data-models.md)
- Contrats des endpoints REST → [api-contracts.md](./api-contracts.md)
- Pages/composants frontend et leur mapping API → [component-inventory.md](./component-inventory.md)
- Mettre en place l'environnement de dev → [development-guide.md](./development-guide.md)
- Déployer en production → [deployment-guide.md](./deployment-guide.md)
- Arborescence annotée → [source-tree-analysis.md](./source-tree-analysis.md)

## Historique et artefacts BMad

Le projet a été conduit avec la méthode BMad (spec-driven) : brief, PRD, architecture-spine, epics/stories, puis exécution story par story avec revue de code systématique. Artefacts sources dans `_bmad-output/` :
- `planning-artifacts/prds/` — PRD
- `planning-artifacts/architecture/architecture-GestionDuBudget-2026-06-30/ARCHITECTURE-SPINE.md` — contrat d'architecture normatif (source de vérité pour les invariants)
- `planning-artifacts/epics-and-stories/`, `planning-artifacts/epics.md` — découpage epics/stories
- `implementation-artifacts/` — une story par fichier, retrospectives d'epic, specs correctives ponctuelles (FK enforcement, N+1, dédup frontend)

Cette documentation (`docs/`) est dérivée du code réel, pas des artefacts de planification — en cas de divergence entre les deux, le code (et donc `docs/`) fait foi pour le comportement actuel ; `_bmad-output/` reste la trace historique des décisions.
