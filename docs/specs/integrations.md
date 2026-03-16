# HiD Integrations Spec

## 1. Cloudbeds API

### Authentication
- API Key via header: `X-Api-Key: {CLOUDBEDS_API_KEY}`
- Base URL: `https://api.cloudbeds.com/api/v1.1`

### Key Endpoints Used

#### GET /reservations
Pull all reservations for a property.

**Params:**
```
propertyID={property_id}
pageNumber={n}
pageSize=100
checkIn[gte]={date}     # date range filter
checkIn[lte]={date}
modifiedAt[gte]={date}  # for incremental sync
```

**Response fields we use:**
```
reservationID         → cloudbeds_reservation_id
guestCountry          → guest_country (raw), guest_country_code (mapped)
roomTypeName          → room_type (raw), room_type_category (derived)
sourceID / sourceName → source (raw), source_category (derived)
startDate             → check_in_date
endDate               → check_out_date
nights                → nights
adults                → adults
total                 → grand_total_native
status                → status
dateCreated           → reservation_date
```

**Pagination:** Loop through pages until `total` is reached.

### Sync Strategy
- **Nightly full sync** (2am Vietnam): pull last 90 days of reservations by `modifiedAt`
- **On-demand sync**: POST /api/sync/cloudbeds (for manual trigger)
- **Deduplication**: upsert on `cloudbeds_reservation_id` — no duplicates

### Ingestion Mapping (services/cloudbeds.py)

```python
COUNTRY_MAP = {
    "United States of America": "USA",
    "United Kingdom": "UK",
    "Unknown": "Others",
    # all others pass through as-is
}

def map_room_type_category(room_type: str) -> str:
    if "dorm" in room_type.lower():
        return "Dorm"
    return "Room"

def map_source_category(source: str) -> str:
    direct_keywords = ["website", "booking engine", "blogger", "direct"]
    if any(kw in source.lower() for kw in direct_keywords):
        return "Direct"
    return "OTA"

OTA_CANONICAL = {
    "booking.com": "Booking.com",
    "hostelworld": "Hostelworld",
    "agoda": "Agoda",
    "ctrip": "Ctrip",
    "trip.com": "Ctrip",
    "expedia": "Expedia",
}
```

---

## 2. Exchange Rate API

### Provider
Free tier: https://www.exchangerate-api.com  
Endpoint: `GET https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{base}`

### Usage
- Fetch rates daily (cached in memory + DB)
- Base currency: always fetch from branch native currency → VND
- Currencies needed: TWD→VND, JPY→VND, USD→VND, VND→VND (1:1)

### Fallback
If API call fails → use last cached rate from DB, log warning.
Never block data ingestion due to currency API failure.

---

## 3. SendGrid (Email)

### Config
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
```

### Weekly Email Schedule
- Every Monday at 7:00am `Asia/Ho_Chi_Minh`
- Recipients: `EMAIL_RECIPIENTS` env var (comma-separated)
- From: `EMAIL_FROM` env var

### Email Content
See `services/email_service.py` for template.
Sections: KPI snapshot, Hot countries top 3, Winning ad angles, KOL opportunities, Pending approvals.

---

## 4. Future Integrations (Phase 7+)

### Meta Ads API 🔮
- Graph API v19+
- Endpoint: `/act_{account_id}/insights`
- Fields: campaign_name, adset_name, ad_name, spend, impressions, clicks, actions
- Auth: User Access Token (long-lived)

### Google Analytics 4 API 🔮
- Google Analytics Data API
- Dimensions: date, sessionSource
- Metrics: sessions, conversions, totalRevenue

### TikTok Ads API 🔮
- TikTok Marketing API
- Similar structure to Meta Ads
