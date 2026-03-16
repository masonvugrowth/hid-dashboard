# ── Stage 1: Build frontend ────────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

COPY ../frontend/package*.json ./
RUN npm ci

COPY ../frontend ./
RUN npm run build

# ── Stage 2: Python backend + serve frontend static ───────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy built frontend into backend static folder
COPY --from=frontend-builder /frontend/dist /app/frontend_dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
