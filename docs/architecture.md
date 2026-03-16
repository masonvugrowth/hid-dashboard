# HiD Architecture & Design Decisions

## System Overview
```
Cloudbeds API (nightly pull)
    ↓
FastAPI Backend (Railway)
  ├── Ingestion Service → PostgreSQL (Supabase)
  ├── Nightly metrics compute → daily_metrics cache
  ├── Core REST API
  └── Email Scheduler (Monday 7am VN time)
    ↓
React Frontend (Railway)
```

## Key Design Decisions

### 1. OCC is always computed — never stored in reservations
**Decision:** OCC = rooms_sold / total_rooms. Computed nightly into daily_metrics cache.
**Why:** Avoids data integrity issues from having the same metric in two places.
**Tradeoff:** First load might be slow if cache is empty. Mitigation: backfill cache on first deploy.

### 2. daily_metrics as a computed cache layer
**Decision:** Nightly job aggregates reservations → daily_metrics. Dashboard reads from cache.
**Why:** Querying all reservations for OCC/ADR/RevPAR across 5 branches + 2 years on every page load would be slow.
**Migration:** If we need to change a formula, run `POST /api/metrics/recompute` to rebuild cache.

### 3. VND stored at write-time, not computed at read-time
**Decision:** Every monetary row stores both native and VND equivalent.
**Why:** Cross-branch comparison needs a single currency. Converting at read-time means exchange rate changes retroactively distort historical data.
**Tradeoff:** Exchange rate at time of ingestion is locked in. Use with awareness.

### 4. room_type_category and source_category derived on ingestion
**Decision:** These fields are set when the reservation is first ingested, not re-derived on query.
**Why:** Cloudbeds room type strings change format over time. Locking the category at ingestion ensures consistent reporting even if Cloudbeds changes naming.
**Migration:** If mapping logic changes, run a backfill job on historical reservations.

### 5. Manual Ad Angle and Target Audience tagging
**Decision:** Team manually tags ads with angle and audience — no auto-classification.
**Why:** Insufficient training data for ML. Manual is more accurate at this stage.
**Migration path:** Once 100+ tagged records exist, add AI suggestion endpoint (Phase 8).

### 6. Country scoring is formula-based
**Decision:** WoW booking growth (40%) + MoM growth (30%) + ADR trend (20%) + recency (10%).
**Why:** Transparent, explainable, no ML required. Team can debate and adjust weights.
**Migration:** Swap scoring function in country_scorer.py when data volume warrants ML.

### 7. Supabase Free Tier
**Decision:** Start on Supabase free tier (500MB, unlimited API).
**Why:** More than sufficient for Year 1. $0 cost to start.
**Migration:** Upgrade to Supabase Pro ($25/mo) by adding credit card. DATABASE_URL stays the same.

### 8. APScheduler inside FastAPI process
**Decision:** Scheduler runs inside the FastAPI app, not as a separate service.
**Why:** Simpler Railway setup — one service, one bill. Sufficient for 3 jobs/day.
**Migration:** Move to Railway Cron Service or Celery if scheduler reliability becomes an issue.

### 9. Website metrics: manual input MVP
**Decision:** Team manually enters weekly impressions/traffic/conversion data via dashboard form.
**Why:** GA4 API and Meta API require OAuth setup and significant auth complexity. Not worth it for 6 users at MVP.
**Migration:** Phase 8 — add GA4 API + Meta API integration. Data model already supports it (platform field).

### 10. Daily Brief replaces manual Excel workflow entirely
**Decision:** No override mechanism — HiD auto-calculates from Cloudbeds reservations.
**Why:** Manual override creates two sources of truth. Team confirmed Cloudbeds is reliable enough.
**Tradeoff:** If Cloudbeds data has errors, the dashboard reflects those errors. Mitigation: Cloudbeds data validation on ingestion (flag anomalies in logs).
