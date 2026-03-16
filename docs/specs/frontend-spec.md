# HiD Frontend Spec

## Stack
- React 18 + Vite
- TailwindCSS (utility classes only)
- Recharts (charts)
- React Router v6
- Axios (API calls)

## Route Map
```
/                     → Home.jsx           (KPI summary + hot countries + OCC heatmap)
/kpi                  → KPI.jsx            (KPI detail + forecast + predicted OCC input)
/performance          → Performance.jsx    (hub: pick Daily/Weekly/Monthly/OTA)
/performance/daily    → PerformanceDaily.jsx
/performance/weekly   → PerformanceWeekly.jsx
/performance/monthly  → PerformanceMonthly.jsx
/performance/ota      → PerformanceOTA.jsx
/countries            → Countries.jsx      (ranking table with Hot/Warm/Cold)
/countries/:code      → CountryDetail.jsx  (booking trend + YoY + activities)
/marketing            → Marketing.jsx      (activity log)
/ads                  → Ads.jsx            (ads performance table + ROAS chart)
/kols                 → KOLs.jsx           (KOL table + reservation linker)
/angles               → Angles.jsx         (WIN/TEST/LOSE cards)
/insights             → Insights.jsx       (KOL → Paid Ads feed)
/report               → Report.jsx         (weekly email preview + send)
/creative             → Creative.jsx       (Phase 6 hub)
```

## Color System (OCC bands — match Excel)
```js
// Used in PerformanceDaily.jsx
const OCC_COLOR = (pct) => {
  if (pct < 0.50) return 'bg-red-100 text-red-800'      // 0-50%
  if (pct < 0.70) return 'bg-yellow-100 text-yellow-800' // 50-70%
  if (pct < 0.90) return 'bg-blue-100 text-blue-800'    // 70-90%
  return 'bg-green-100 text-green-800'                   // 90-100%
}
```

## Branch Selector
- Persistent across all performance pages (stored in React Context)
- Dropdown in top navigation bar
- Default: show all branches (where applicable)

## Key Components
```
components/
  Layout.jsx          # nav sidebar + top bar
  KPICard.jsx         # branch KPI card with achievement % + bar
  BranchSelector.jsx  # global branch dropdown
  TrendChart.jsx      # Recharts LineChart wrapper (revenue/OCC over time)
  DataTable.jsx       # sortable, filterable table
  CountryBadge.jsx    # Hot/Warm/Cold colored badge
  AngleCard.jsx       # WIN/TEST/LOSE card with metrics
  OCCHeatmap.jsx      # calendar heatmap for OCC per day
  OTAMixChart.jsx     # stacked bar chart for OTA channel %
  EventPin.jsx        # event annotation on charts
  ColorBandCell.jsx   # colored cell for daily metrics table
```

## API Layer (src/api/)
```
api/
  client.js           # Axios instance with base URL + error interceptor
  kpi.js              # KPI endpoints
  metrics.js          # Daily/Weekly/Monthly/OTA endpoints
  events.js           # Event calendar endpoints
  websiteMetrics.js   # Website metrics endpoints
  countries.js        # Country ranking + detail endpoints
  ads.js
  kols.js
  angles.js
  reports.js
```

## Chart Specs

### PerformanceDaily
- Table view: rows = metrics (OCC, Revenue, ADR, RevPAR), columns = dates
- Color-band cells using OCC_COLOR()
- Event icons pinned on dates with events
- 2025 average column always visible for comparison

### PerformanceWeekly
- Line chart: Revenue trend (weekly, current year)
- Bar chart: Cancellation % per week
- Stacked bar: OTA channel mix per week
- Table: Conversion % + impressions from website_metrics

### PerformanceMonthly
- Summary cards: OCC%, Revenue, ADR, RevPAR
- Table: Country reservation breakdown, columns = months, rows = countries
- Multi-year tabs: 2024 / 2025 / 2026
- Bar chart: OTA Room Night % per OTA per month

### OTA Mix Chart
- Stacked bar chart (Recharts BarChart, stacked=true)
- X-axis: months, Y-axis: % share
- One bar segment per OTA (Agoda, Booking, Ctrip, Expedia, Hostelworld, Direct)
- Filter: branch selector

## State Management
- React Context for: selected branch, current date range
- No Redux — keep it simple
- All server state: fetch on mount, no client-side caching beyond React state

## Phase 1 Frontend Scope
Phase 1 only: scaffold + empty pages. No real API calls.
Each page renders a placeholder: `<div>Phase N — Coming Soon</div>`
Navigation must work between all routes.
