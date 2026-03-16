# Current Phase: Phase 1 — Foundation & Data Pipeline

## Goal
Project skeleton running locally. Supabase DB live with all 11 tables.
Cloudbeds API pulling reservation data nightly. KPI targets can be set manually.
All derived fields (room_type_category, source_category, guest_country_code) populated on ingestion.

## Files to Create
```
(+) CLAUDE.md
(+) .env.example
(+) .claude/rules/api-conventions.md
(+) .claude/rules/database-rules.md
(+) .claude/rules/testing-rules.md
(+) .claude/rules/deployment-rules.md
(+) .claude/rules/metrics-rules.md
(+) docs/current-phase.md         ← this file
(+) docs/architecture.md
(+) docs/changelog.md
(+) docs/lessons.md
(+) docs/specs/data-model.md
(+) docs/specs/api-spec.md
(+) docs/specs/integrations.md
(+) docs/specs/frontend-spec.md
(+) backend/app/main.py
(+) backend/app/config.py
(+) backend/app/database.py
(+) backend/app/scheduler.py
(+) backend/app/models/branch.py
(+) backend/app/models/kpi.py
(+) backend/app/models/reservation.py
(+) backend/app/models/daily_metrics.py
(+) backend/app/models/event.py
(+) backend/app/models/website_metrics.py
(+) backend/app/models/ads.py
(+) backend/app/models/kol.py
(+) backend/app/models/angle.py
(+) backend/app/models/activity.py
(+) backend/app/models/creative.py    (branch_keypoints, ad_copies, ad_materials, ad_approvals, ad_names)
(+) backend/app/routers/kpi.py
(+) backend/app/routers/sync.py       (POST /api/sync/cloudbeds only)
(+) backend/app/services/cloudbeds.py
(+) backend/app/services/currency.py
(+) backend/alembic/versions/001_initial.py
(+) backend/requirements.txt
(+) backend/Dockerfile
(+) backend/tests/test_cloudbeds.py
(+) backend/tests/test_currency.py
(+) frontend/ (Vite scaffold + TailwindCSS + React Router + empty pages)
```

## Tasks
- [ ] Initialize repo + install tools (git, node, python 3.11+)
- [ ] Create full folder structure
- [ ] Install backend dependencies (see requirements.txt below)
- [ ] Create Supabase project → copy DATABASE_URL to .env
- [ ] Write all 11 SQLAlchemy models
- [ ] Write Alembic migration 001_initial.py
- [ ] Run `alembic upgrade head` — verify all tables in Supabase
- [ ] Implement Cloudbeds API client (pull reservations, map country/room_type/source)
- [ ] Implement currency conversion service (cache rate daily, convert to VND)
- [ ] Implement KPI target CRUD endpoints (POST/GET/PATCH)
- [ ] Set up APScheduler: nightly Cloudbeds pull at 2am Vietnam time
- [ ] Implement GET /health endpoint
- [ ] React scaffold: Vite + TailwindCSS + React Router + empty placeholder pages

## Backend Dependencies (requirements.txt)
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
alembic==1.13.1
psycopg2-binary==2.9.9
pydantic==2.7.1
pydantic-settings==2.2.1
httpx==0.27.0
apscheduler==3.10.4
python-dotenv==1.0.1
sendgrid==6.11.0
ruff==0.4.4
pytest==8.2.0
pytest-asyncio==0.23.6
```

## Verification Checklist
- [x] All code files written (2026-03-13)
- [ ] `alembic upgrade head` runs without errors  ← **USER: run this after setting DATABASE_URL in .env**
- [ ] All 17 tables visible in Supabase dashboard:
      branches, kpi_targets, reservations, daily_metrics, events, website_metrics,
      ads_performance, kol_records, kol_bookings, ad_angles, marketing_activities,
      users, branch_keypoints, ad_copies, ad_materials, ad_approvals, ad_names
- [ ] POST /api/sync/cloudbeds returns 200, rows appear in reservations table
- [ ] Reservations have room_type_category (Room/Dorm) and source_category (OTA/Direct) populated
- [ ] POST /api/kpi/targets returns created object with id
- [ ] GET /health returns `{ "status": "ok", "timestamp": "..." }`
- [ ] `pytest tests/ -v` — all tests pass
- [ ] `cd frontend && npm run dev` — React app loads at localhost:5173

## Notes
- Do NOT implement any dashboard UI logic in Phase 1 — React pages are empty placeholders only
- Do NOT implement metrics_engine.py in Phase 1 — that's Phase 2
- Focus: DB up, data flowing from Cloudbeds, KPI target CRUD working
