#!/usr/bin/env bash
# Build le frontend et synchronise le résultat dans backend/dist,
# pour servir la dernière version buildée depuis FastAPI sans passer par Docker.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/frontend"
npm run build

rm -rf "$ROOT_DIR/backend/dist"
cp -r "$ROOT_DIR/frontend/dist" "$ROOT_DIR/backend/dist"

echo "backend/dist mis à jour depuis frontend/dist."
