# Stage 1 — build du frontend
FROM node:24-slim AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2 — backend + frontend buildé
FROM python:3.13.14-slim

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-builder /frontend/dist ./dist

RUN chmod +x entrypoint.sh

EXPOSE 8082

ENTRYPOINT ["./entrypoint.sh"]
