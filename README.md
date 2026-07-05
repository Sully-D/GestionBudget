# GestionDuBudget

Application web self-hosted de gestion budgétaire personnelle, pour un foyer avec plusieurs comptes bancaires (comptes personnels + compte commun). Suivi des transactions, tags hiérarchiques, budget en pourcentage du salaire, projections de trésorerie, import OFX/CSV.

Conçue pour tourner en local sur un NAS ou un Raspberry Pi, sans authentification (réseau local uniquement).

## Prérequis

- **Docker** (Engine 27+)
- **Docker Compose** (plugin `docker compose`, inclus avec Docker Desktop ou installable séparément sur Linux)

Aucune autre dépendance n'est nécessaire : le backend (Python/FastAPI/SQLite) et le frontend (React) sont packagés dans une seule image Docker.

## Démarrage

```bash
git clone <url-du-repo>
cd GestionDuBudget
cp .env.example .env
docker compose up -d
```

L'application est ensuite accessible sur `http://localhost:8082` (ou l'hôte de votre NAS/Pi).

## Configuration

Variables définies dans `.env` (voir `.env.example`) :

| Variable | Défaut | Description |
|---|---|---|
| `PORT` | `8082` | Port d'écoute de l'application |
| `DATABASE_PATH` | `/data/gestion_budget.db` | Chemin du fichier SQLite dans le conteneur |

## Données

Les données (base SQLite) sont persistées dans le volume Docker nommé `gestion_budget_data`, indépendant du cycle de vie du conteneur. Un export manuel JSON/CSV est disponible depuis l'application ; il n'y a pas de sauvegarde automatique côté application — pensez à sauvegarder le volume Docker séparément.

## Arrêt

```bash
docker compose down
```

(les données restent dans le volume ; ajoutez `-v` uniquement si vous souhaitez les supprimer)

## Développeurs

### Prérequis de développement

- **Python** 3.13
- **Node.js** 24 (LTS)

### Backend

Stack : FastAPI, SQLAlchemy 2.0, Alembic, SQLite, ofxtools (import OFX).

```bash
cd backend
pip install -r requirements-dev.txt   # requirements.txt + pytest, httpx2
alembic upgrade head
uvicorn main:app --reload --port 8082
```

Dépendances principales (`requirements.txt`) :

| Paquet | Version |
|---|---|
| fastapi | 0.138.2 |
| uvicorn[standard] | 0.38.0 |
| sqlalchemy | 2.0.51 |
| alembic | 1.18.5 |
| pydantic-settings | 2.14.2 |
| ofxtools | 0.9.5 |
| python-multipart | 0.0.32 |

Dépendances de dev additionnelles (`requirements-dev.txt`) : `pytest==9.1.1`, `httpx2==2.5.0` (client de test, pas `httpx`).

Tests : `pytest` depuis `backend/`.

### Frontend

Stack : React 19, TypeScript, Vite, Tailwind CSS 4, React Router.

```bash
cd frontend
npm ci
npm run dev
```

Dépendances principales (`package.json`) :

| Paquet | Version |
|---|---|
| react / react-dom | ^19.2.7 |
| react-router | ^7.18.1 |

Dépendances de dev principales :

| Paquet | Version |
|---|---|
| typescript | ~5.9.3 |
| vite | ^8.1.1 |
| tailwindcss / @tailwindcss/vite | ^4.3.2 |
| @vitejs/plugin-react | ^6.0.3 |
| oxlint | ^1.71.0 |

Scripts : `npm run dev` (serveur de dev), `npm run build` (`tsc -b` + build Vite), `npm run lint` (oxlint), `npm run preview`.

### Build complet (image Docker)

```bash
docker compose build
```

Reproduit le build multi-stage du `Dockerfile` (frontend buildé puis servi statiquement par le backend FastAPI).
