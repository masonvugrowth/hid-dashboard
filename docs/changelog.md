# Changelog

## Format
Append a new entry after each phase is completed and verified.

---

## Phase 1 — 2026-03-13 — Foundation & Data Pipeline

### Added
- `backend/app/config.py` — Pydantic Settings; all secrets from env, never hardcoded
- `backend/app/database.py` — SQLAlchemy engine + `get_db()` dependency
- `backend/app/main.py` — FastAPI app, CORS, `GET /health`, router mounts, scheduler setup
- `backend/app/scheduler.py` — APScheduler nightly Cloudbeds sync at 02:00 ICT
- **Models** (17 tables): `Branch`, `KPITarget`, `Reservation`, `DailyMetrics`, `Event`,
  `WebsiteMetrics`, `AdAngle`, `AdsPerformance`, `KOLRecord`, `KOLBooking`,
  `MarketingActivity`, `User`, `BranchKeypoint`, `AdCopy`, `AdMaterial`, `AdApproval`, `AdName`
- **Alembic migrations**: `001_core_tables.py` (12 tables) + `002_creative_tables.py` (5 creative tables)
- `backend/app/services/cloudbeds.py` — Cloudbeds API client, mapping helpers, upsert ingestion
- `backend/app/services/currency.py` — Exchange rate fetch, daily in-memory cache, VND conversion
- `backend/app/routers/kpi.py` — `POST/GET/PATCH /api/kpi/targets`
- `backend/app/routers/sync.py` — `POST /api/sync/cloudbeds` (single or all branches)
- `backend/tests/test_cloudbeds.py` — Unit tests for all mapping functions
- `backend/tests/test_currency.py` — Unit tests for rate cache and conversion
- `frontend/` — Vite + React + TailwindCSS + React Router scaffold with Sidebar and 5 empty pages
- `.env.example`, `backend/requirements.txt`, `backend/Dockerfile`
