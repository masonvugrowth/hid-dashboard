# Phase 4 — Creative Intelligence Library

## Goal
A three-layer creative system: Angles -> Components (Copy + Materials) -> Combos.
Verdict lives on Combos. Team filters combos to find what worked for each audience.

## Execution Order
1. Migration 007 — 4 new tables (creative_angles, creative_copies, creative_materials, ad_combos)
2. ORM models (all 4)
3. id_generator.py service (with SELECT FOR UPDATE)
4. verdict_sync.py service (sync performance + compute derived verdicts)
5. All 4 routers + register in main.py
6. Add verdict sync to scheduler.py
7. Frontend: VerdictBadge + ComboCard components
8. Frontend: AdCombos.jsx (primary page)
9. Frontend: CreativeCopies.jsx + CreativeMaterials.jsx
10. Sidebar + App.jsx routes

## Completion Checklist
- [x] alembic upgrade head: 0 errors
- [x] 4 new tables in Supabase with correct columns
- [x] UNIQUE constraint on ad_combos(copy_id, material_id) verified
- [ ] POST /api/copies -> copy_code = CPY-001
- [ ] POST /api/materials -> material_code = MAT-001
- [ ] POST /api/combos -> combo_code = CMB-001, verdict = NULL
- [ ] POST /api/combos with duplicate (copy_id, material_id) -> HTTP 409
- [ ] PATCH /api/combos/{id} with verdict -> verdict_source = "manual" in DB
- [ ] Nightly sync: combo with meta_ad_name gets roas synced from ads_performance
- [ ] Nightly sync: manual verdict combo NOT overwritten
- [ ] derived_verdict on copy updated nightly from its combos
- [ ] GET /api/combos?target_audience=Solo&verdict=winning returns filtered results
- [ ] /combos page loads, all filters work, URL params persist
- [ ] Add Combo modal: can select copy + material, creates CMB row
- [ ] Copy detail drawer shows list of combos with their verdicts
- [ ] /copies and /materials pages functional
