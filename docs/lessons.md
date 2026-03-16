# Lessons Learned

## Format
When Claude Code makes a mistake that gets caught and fixed, document it here.
This prevents the same mistake from being repeated in future phases.

---

<!-- Lessons will be added here as phases are completed -->
<!-- Example format:

## Phase 1 — 2026-03-15

### Mistake: Alembic migration failed due to circular FK references
**What happened:** Created all models in one migration. ad_names references ad_approvals which references ad_copies — but they were created in wrong order.
**Fix:** Split into two migrations: 001_core_tables.py (no FKs to creative tables) and 002_creative_tables.py.
**Rule added:** Create tables with no FK dependencies first. Add FKs in subsequent migrations.

-->
