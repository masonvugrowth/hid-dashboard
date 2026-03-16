# HiD Data Model — Full Schema

## Tables Overview (17 total)
1. branches
2. kpi_targets
3. reservations
4. daily_metrics ← computed cache
5. events
6. website_metrics
7. ads_performance
8. kol_records
9. kol_bookings
10. ad_angles
11. marketing_activities
12. users
13. branch_keypoints
14. ad_copies
15. ad_materials
16. ad_approvals
17. ad_names

---

## 1. branches
```sql
CREATE TABLE branches (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                VARCHAR(100) NOT NULL,        -- e.g. "MEANDER Saigon"
  city                VARCHAR(100) NOT NULL,        -- Ho Chi Minh City, Taipei, Osaka...
  country             VARCHAR(100) NOT NULL,
  currency            VARCHAR(10) NOT NULL,         -- VND, TWD, JPY
  total_rooms         INTEGER NOT NULL,             -- total capacity (rooms + dorms combined)
  total_room_count    INTEGER,                      -- private rooms only (nullable, input later)
  total_dorm_count    INTEGER,                      -- dorm beds only (nullable, input later)
  timezone            VARCHAR(50) NOT NULL,         -- Asia/Ho_Chi_Minh, Asia/Taipei, Asia/Tokyo
  cloudbeds_property_id VARCHAR(100),               -- from CLOUDBEDS_PROPERTY_IDS env var
  is_active           BOOLEAN DEFAULT TRUE,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

## 2. kpi_targets
```sql
CREATE TABLE kpi_targets (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id           UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  year                INTEGER NOT NULL,
  month               INTEGER NOT NULL,             -- 1-12
  target_revenue_native DECIMAL(15,2) NOT NULL,
  target_revenue_vnd  DECIMAL(18,2) NOT NULL,       -- converted at time of entry
  predicted_occ_pct   DECIMAL(5,4),                 -- manual input 0.0–1.0 for OCC-based forecast
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(branch_id, year, month)
);
```

## 3. reservations
```sql
CREATE TABLE reservations (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id                   UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  cloudbeds_reservation_id    VARCHAR(50) UNIQUE NOT NULL,  -- deduplication key
  guest_country               VARCHAR(100),        -- raw Cloudbeds country name
  guest_country_code          VARCHAR(50),         -- standardized: "Australia", "USA", "Taiwan"...
  room_type                   VARCHAR(100),        -- full Cloudbeds room type string
  room_type_category          VARCHAR(10),         -- "Room" or "Dorm" — derived on ingestion
  source                      VARCHAR(100),        -- raw Cloudbeds source string
  source_category             VARCHAR(20),         -- "OTA" or "Direct" — derived on ingestion
  check_in_date               DATE NOT NULL,
  check_out_date              DATE NOT NULL,
  nights                      INTEGER NOT NULL,    -- check_out_date - check_in_date
  adults                      INTEGER,
  grand_total_native          DECIMAL(12,2),       -- in branch native currency
  grand_total_vnd             DECIMAL(15,2),       -- converted to VND at ingestion time
  status                      VARCHAR(50),         -- Confirmed, Checked Out, Cancelled
  cancellation_date           DATE,                -- populated when status = Cancelled
  reservation_date            DATE,                -- when booking was made
  raw_data                    JSONB,               -- full Cloudbeds response
  created_at                  TIMESTAMPTZ DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_reservations_branch_checkin ON reservations(branch_id, check_in_date);
CREATE INDEX idx_reservations_status ON reservations(status);
CREATE INDEX idx_reservations_source_category ON reservations(source_category);
CREATE INDEX idx_reservations_country_code ON reservations(guest_country_code);
```

### Country Code Mapping (cloudbeds.py)
Raw Cloudbeds values → standardized guest_country_code:
- "United States of America" → "USA"
- "United Kingdom" → "UK"
- "Unknown" → "Others"
- All others: use country name as-is

### Room Type Category Logic (cloudbeds.py)
If room_type string contains "Dorm" (case-insensitive) → "Dorm"
Else → "Room"

### Source Category Logic (cloudbeds.py)
If source contains "Website" or "Booking Engine" → "Direct"
If source contains "Blogger" → "Direct"
Else → "OTA"

## 4. daily_metrics (computed cache)
```sql
CREATE TABLE daily_metrics (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id           UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  date                DATE NOT NULL,
  rooms_sold          INTEGER DEFAULT 0,
  dorms_sold          INTEGER DEFAULT 0,
  total_sold          INTEGER DEFAULT 0,           -- rooms_sold + dorms_sold
  occ_pct             DECIMAL(5,4) DEFAULT 0,      -- total_sold / branches.total_rooms
  room_occ_pct        DECIMAL(5,4),                -- nullable if split counts not configured
  dorm_occ_pct        DECIMAL(5,4),                -- nullable if split counts not configured
  revenue_native      DECIMAL(15,2) DEFAULT 0,
  revenue_vnd         DECIMAL(18,2) DEFAULT 0,
  adr_native          DECIMAL(12,2) DEFAULT 0,     -- revenue_native / total_sold
  revpar_native       DECIMAL(12,2) DEFAULT 0,     -- adr_native * occ_pct
  new_bookings        INTEGER DEFAULT 0,           -- reservations where reservation_date = this date
  cancellations       INTEGER DEFAULT 0,
  cancellation_pct    DECIMAL(5,4) DEFAULT 0,
  computed_at         TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(branch_id, date)
);
CREATE INDEX idx_daily_metrics_branch_date ON daily_metrics(branch_id, date);
```

## 5. events
```sql
CREATE TABLE events (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id           UUID REFERENCES branches(id) ON DELETE SET NULL,  -- nullable = city-level
  city                VARCHAR(100) NOT NULL,
  event_name          VARCHAR(200) NOT NULL,
  event_date_from     DATE NOT NULL,
  event_date_to       DATE NOT NULL,
  estimated_attendance INTEGER,
  is_key_event        BOOLEAN DEFAULT FALSE,
  notes               TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

## 6. website_metrics
```sql
CREATE TABLE website_metrics (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id             UUID REFERENCES branches(id) ON DELETE SET NULL,  -- nullable = group-level
  week_start_date       DATE NOT NULL,               -- Monday of the tracked week
  platform              VARCHAR(50) NOT NULL,        -- Meta, Google, GA4, TikTok, Overall
  impressions           INTEGER,
  clicks                INTEGER,
  ctr                   DECIMAL(8,6),                -- clicks / impressions
  website_traffic       INTEGER,                     -- unique sessions
  add_to_cart           INTEGER,
  checkout_initiated    INTEGER,
  conversions           INTEGER,                     -- completed bookings tracked
  conversion_pct        DECIMAL(8,6),               -- conversions / website_traffic
  conversion_hit_pct    DECIMAL(8,6),               -- conversions / add_to_cart
  notes                 TEXT,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);
```

## 7. ads_performance
```sql
CREATE TABLE ads_performance (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id           UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  campaign_name       VARCHAR(200),
  adset_name          VARCHAR(200),
  ad_name             VARCHAR(200),
  channel             VARCHAR(50),                  -- Meta, Google, TikTok
  target_country      VARCHAR(100),
  target_audience     VARCHAR(100),                 -- Solo, Couple, Group Friend, Business — manual tag
  ad_angle_id         UUID REFERENCES ad_angles(id) ON DELETE SET NULL,
  campaign_category   VARCHAR(100),
  funnel_stage        VARCHAR(20),                  -- TOF, MOF, BOF
  date_from           DATE,
  date_to             DATE,
  cost_native         DECIMAL(12,2),
  cost_vnd            DECIMAL(15,2),
  impressions         INTEGER,
  clicks              INTEGER,
  leads               INTEGER,
  bookings            INTEGER,
  revenue_native      DECIMAL(12,2),
  revenue_vnd         DECIMAL(15,2),
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

## 8. kol_records
```sql
CREATE TABLE kol_records (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id                 UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  kol_name                  VARCHAR(100) NOT NULL,
  kol_nationality           VARCHAR(100),
  language                  VARCHAR(100),
  target_audience           VARCHAR(100),
  ad_angle_id               UUID REFERENCES ad_angles(id) ON DELETE SET NULL,
  cost_native               DECIMAL(12,2),
  cost_vnd                  DECIMAL(15,2),
  is_gifted_stay            BOOLEAN DEFAULT FALSE,
  invitation_date           DATE,
  published_date            DATE,
  link_ig                   TEXT,
  link_tiktok               TEXT,
  link_youtube              TEXT,
  -- Creative Ops extensions (Phase 6)
  deliverable_status        VARCHAR(50),            -- Not Started, In Progress, Editing, Done
  paid_ads_eligible         BOOLEAN DEFAULT FALSE,
  paid_ads_usage_fee_vnd    DECIMAL(15,2),
  paid_ads_channel          VARCHAR(100),
  usage_rights_expiry_date  DATE,                   -- alert 30 days before
  contract_status           VARCHAR(50),            -- Draft, Negotiating, Signed, Cancelled
  notes                     TEXT,
  created_at                TIMESTAMPTZ DEFAULT NOW(),
  updated_at                TIMESTAMPTZ DEFAULT NOW()
);
```

## 9. kol_bookings
```sql
CREATE TABLE kol_bookings (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kol_id                  UUID NOT NULL REFERENCES kol_records(id) ON DELETE CASCADE,
  reservation_id          UUID NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
  attributed_revenue_vnd  DECIMAL(15,2),
  created_at              TIMESTAMPTZ DEFAULT NOW()
);
```

## 10. ad_angles
```sql
CREATE TABLE ad_angles (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          VARCHAR(200) NOT NULL,
  description   TEXT,
  status        VARCHAR(20),                        -- WIN, TEST, LOSE — auto-calculated
  branch_id     UUID REFERENCES branches(id) ON DELETE SET NULL,
  created_by    VARCHAR(100),
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);
```

## 11. marketing_activities
```sql
CREATE TABLE marketing_activities (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id       UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  target_country  VARCHAR(100),
  activity_type   VARCHAR(50),                      -- PaidAds, KOL, CRM, Event, Organic
  target_audience VARCHAR(100),
  description     TEXT,
  result_notes    TEXT,
  date_from       DATE,
  date_to         DATE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

## 12. users
```sql
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email       VARCHAR(200) UNIQUE NOT NULL,
  name        VARCHAR(100),
  role        VARCHAR(20) DEFAULT 'editor',         -- admin, editor, viewer
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

## 13–17. Creative Ops Tables (Phase 6)

### 13. branch_keypoints
```sql
CREATE TABLE branch_keypoints (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  branch_id   UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  keypoint    TEXT NOT NULL,
  category    VARCHAR(100),                         -- Location, Amenity, Social, Price, Experience
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 14. ad_copies
```sql
CREATE TABLE ad_copies (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  copy_id         VARCHAR(20) UNIQUE NOT NULL,      -- CPY-001, CPY-002...
  angle_id        UUID REFERENCES ad_angles(id) ON DELETE SET NULL,
  branch_id       UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  channel         VARCHAR(50),
  ad_format       VARCHAR(50),
  target_audience VARCHAR(100),
  target_country  VARCHAR(100),
  language        VARCHAR(100),
  headline        VARCHAR(500),
  primary_text    TEXT,
  copywriter      VARCHAR(100),
  status          VARCHAR(20) DEFAULT 'Draft',      -- Draft, Review, Approved
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 15. ad_materials
```sql
CREATE TABLE ad_materials (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  material_id     VARCHAR(20) UNIQUE NOT NULL,      -- MAT-001, MAT-002...
  angle_id        UUID REFERENCES ad_angles(id) ON DELETE SET NULL,
  branch_id       UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  material_type   VARCHAR(50),
  format_ratio    VARCHAR(20),
  design_type     VARCHAR(50),
  assigned_to     VARCHAR(100),
  brief_link      TEXT,
  order_status    VARCHAR(50) DEFAULT 'Briefing',
  deadline        DATE,
  file_link       TEXT,
  channel         VARCHAR(50),
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 16. ad_approvals
```sql
CREATE TABLE ad_approvals (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  copy_id           UUID NOT NULL REFERENCES ad_copies(id) ON DELETE CASCADE,
  material_id       UUID REFERENCES ad_materials(id) ON DELETE SET NULL,
  kol_id            UUID REFERENCES kol_records(id) ON DELETE SET NULL,
  submitted_by      VARCHAR(100),
  submitted_date    TIMESTAMPTZ DEFAULT NOW(),
  landing_page_url  TEXT,
  reviewer          VARCHAR(100),
  approval_status   VARCHAR(30) DEFAULT 'Pending',  -- Pending, Approved, Rejected, Needs Revision
  approval_deadline TIMESTAMPTZ,
  feedback          TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);
```

### 17. ad_names
```sql
CREATE TABLE ad_names (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  approval_id     UUID NOT NULL REFERENCES ad_approvals(id) ON DELETE CASCADE,
  copy_id         UUID NOT NULL REFERENCES ad_copies(id),
  material_id     UUID REFERENCES ad_materials(id),
  generated_name  VARCHAR(500) NOT NULL,            -- auto-generated on approval
  channel         VARCHAR(50),
  branch_id       UUID REFERENCES branches(id),
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```
