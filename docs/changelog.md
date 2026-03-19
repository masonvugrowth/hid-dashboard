# Changelog

## Format
Append a new entry after each phase is completed and verified.

---

## Phase 4 — 2026-03-19 — Creative Intelligence Library (v2 — Ad Combo Layer)

### Key Design Decision
Verdict lives on ad_combos (Copy x Material pairs) — NOT on individual copies or materials.
derived_verdict on copies/materials is computed nightly from their combos.

### Added
- **Migration** `007_phase4_creative_library.py`: 4 new tables (creative_angles, creative_copies,
  creative_materials, ad_combos) with UNIQUE constraint on (copy_id, material_id)
- **Models**: `creative_angle.py`, `creative_copy.py`, `creative_material.py`, `ad_combo.py`
- **Services**: `id_generator.py` (ANG/CPY/MAT/CMB sequential codes with SELECT FOR UPDATE),
  `verdict_sync.py` (nightly sync_combo_performance + compute_derived_verdicts)
- **Routers**: `creative_angles.py`, `creative_copies.py`, `creative_materials.py`,
  `combos.py` (primary — with insights endpoint, manual sync, verdict management)
- **Frontend Pages**: `AdCombos.jsx` (primary — combo cards, filters as URL params, detail drawer
  with verdict editor + meta_ad_name input), `CreativeCopies.jsx` (copy library with derived verdict
  badges + combo list in detail drawer), `CreativeMaterials.jsx` (materials with conditional KOL fields)
- **Components**: `VerdictBadge.jsx` (winning/good/neutral/underperformer/kill + derived label),
  `ComboCard.jsx` (copy headline + material type + ROAS chip + verdict badge)
- **API Clients**: `angles.js`, `copies.js`, `materials.js`, `combos.js`
- **Rules**: `.claude/rules/creative-library-rules.md`

### Modified
- `backend/app/main.py` — Registered 4 new routers, version 4.0.0
- `backend/app/scheduler.py` — Added nightly verdict sync at 03:30 ICT
- `backend/app/models/__init__.py` — Added 4 new model imports
- `frontend/src/App.jsx` — Added 3 Phase 4 routes (/combos, /copies, /materials)
- `frontend/src/components/Sidebar.jsx` — Added Creatives section (Ad Combos primary)
- `frontend/src/context/AuthContext.jsx` — Dev mode bypass for local preview
- `CLAUDE.md` — Updated to Phase 4 Creative Library rules
- `docs/current-phase.md` — Phase 4 execution order + completion checklist

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
