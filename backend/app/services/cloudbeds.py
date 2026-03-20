import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import text as _text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.reservation import Reservation
from app.services.currency import convert_to_vnd, get_cached_rate

logger = logging.getLogger(__name__)

CLOUDBEDS_BASE_URL = "https://hotels.cloudbeds.com/api/v1.2"
PAGE_SIZE = 100
SYNC_LOOKBACK_DAYS = 90
# For initial/full sync: only fetch reservations with check-in in this window
CHECKIN_LOOKBACK_DAYS = 365   # past: 1 year of check-ins
CHECKIN_FUTURE_DAYS = 180     # future: 6 months of upcoming check-ins

# ── Mapping helpers ────────────────────────────────────────────────────────────

COUNTRY_MAP: dict[str, str] = {
    "United States of America": "USA",
    "United Kingdom": "UK",
    "Unknown": "Others",
}


def map_country_code(raw: Optional[str]) -> str:
    if not raw:
        return "Others"
    return COUNTRY_MAP.get(raw, raw)


def map_room_type_category(room_type: Optional[str]) -> str:
    if room_type and "dorm" in room_type.lower():
        return "Dorm"
    return "Room"


DIRECT_KEYWORDS = ["website", "booking engine", "blogger", "direct"]


def map_source_category(source: Optional[str]) -> str:
    if not source:
        return "OTA"
    if any(kw in source.lower() for kw in DIRECT_KEYWORDS):
        return "Direct"
    return "OTA"


OTA_CANONICAL: dict[str, str] = {
    "booking.com": "Booking.com",
    "hostelworld": "Hostelworld",
    "agoda": "Agoda",
    "ctrip": "Ctrip",
    "trip.com": "Ctrip",
    "expedia": "Expedia",
}


def normalize_source(source: Optional[str]) -> Optional[str]:
    if not source:
        return source
    lower = source.lower()
    for key, canonical in OTA_CANONICAL.items():
        if key in lower:
            return canonical
    return source


# ── API client ─────────────────────────────────────────────────────────────────

def _headers(api_key: Optional[str] = None) -> dict:
    key = api_key or settings.CLOUDBEDS_API_KEY
    return {"Authorization": f"Bearer {key}"}


def _fetch_transactions_page(
    property_id: str,
    page: int,
    api_key: Optional[str] = None,
    checkin_from: Optional[date] = None,
    checkin_to: Optional[date] = None,
) -> dict:
    """Fetch transactions filtered by guest check-in date (for reservation revenue sync)."""
    params: dict = {
        "propertyID": property_id,
        "pageNumber": page,
        "pageSize": PAGE_SIZE,
    }
    if checkin_from:
        params["guestCheckIn[gte]"] = checkin_from.isoformat()
    if checkin_to:
        params["guestCheckIn[lte]"] = checkin_to.isoformat()
    with httpx.Client(timeout=60) as client:
        response = client.get(
            f"{CLOUDBEDS_BASE_URL}/getTransactions",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        return response.json()


def _fetch_transactions_by_date_page(
    property_id: str,
    page: int,
    api_key: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """Fetch transactions filtered by TRANSACTION DATE (the night the charge was posted).
    Each night of a multi-night stay has its own Room Revenue transaction on that date.
    This naturally produces per-night revenue without any proration math.
    Matches the Cloudbeds OCC report methodology exactly.
    """
    params: dict = {
        "propertyID": property_id,
        "pageNumber": page,
        "pageSize": PAGE_SIZE,
    }
    if date_from:
        params["date[gte]"] = date_from.isoformat()
    if date_to:
        params["date[lte]"] = date_to.isoformat()
    with httpx.Client(timeout=60) as client:
        response = client.get(
            f"{CLOUDBEDS_BASE_URL}/getTransactions",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        return response.json()


def sync_daily_revenue(
    branch_id: str,
    property_id: str,
    currency: str,
    api_key: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """
    Sync daily revenue directly from Cloudbeds transaction dates into daily_metrics.

    Fetches all Room Revenue debit transactions filtered by TRANSACTION DATE
    (= the actual night the room charge was posted). Groups by date and writes
    revenue_native / revenue_vnd into daily_metrics rows.

    This matches the Cloudbeds OCC report exactly — no per-night proration needed
    since each stay-night already has its own transaction. Also handles stayovers
    automatically (Feb check-in → March transactions appear in March naturally).
    No per-reservation API calls, no fallback logic needed.
    """
    today = date.today()
    if date_from is None:
        date_from = today.replace(day=1)  # start of current month
    if date_to is None:
        date_to = today

    rate = get_cached_rate(currency, "VND")
    daily_rev: dict[date, float] = {}  # date → sum of Room Revenue debits

    logger.info(
        "Daily revenue sync branch %s property %s [%s → %s]",
        branch_id, property_id, date_from, date_to,
    )

    page = 1
    while True:
        data = _fetch_transactions_by_date_page(
            property_id, page, api_key,
            date_from=date_from,
            date_to=date_to,
        )
        records = data.get("data", [])
        total_count = data.get("total", 0)

        for txn in records:
            is_room_revenue = (
                txn.get("category") == "Room Revenue"
                and txn.get("transactionType") == "debit"
                and not txn.get("isDeleted", False)
            )
            if not is_room_revenue:
                continue
            txn_date_str = txn.get("serviceDate") or txn.get("transactionDateTime") or ""
            try:
                txn_date = date.fromisoformat(txn_date_str[:10])
            except (ValueError, TypeError):
                continue
            amount = float(_safe_decimal(txn.get("amount")) or 0)
            daily_rev[txn_date] = daily_rev.get(txn_date, 0.0) + amount

        logger.info("Daily rev page %d/%d — %d txns, %d dates so far",
                    page, (total_count // PAGE_SIZE) + 1, len(records), len(daily_rev))
        if (page - 1) * PAGE_SIZE + len(records) >= total_count or not records:
            break
        page += 1

    # Write to daily_metrics — one raw SQL UPDATE per date
    updated = 0
    for d, rev in daily_rev.items():
        rev_vnd = round(rev * rate, 2) if rate is not None else None
        _s = SessionLocal()
        try:
            _s.execute(_text(
                "UPDATE daily_metrics "
                "SET revenue_native=:n, revenue_vnd=:v, computed_at=NOW() "
                "WHERE branch_id=CAST(:bid AS UUID) AND date=:d"
            ), {"n": round(rev, 2), "v": rev_vnd, "bid": branch_id, "d": d})
            _s.commit()
            updated += 1
        except Exception as e:
            _s.rollback()
            logger.warning("Daily rev write failed date %s: %s", d, e)
        finally:
            _s.close()

    logger.info("Daily revenue sync complete branch %s: %d dates updated", branch_id, updated)
    return {"branch_id": branch_id, "dates_updated": updated, "date_from": str(date_from), "date_to": str(date_to)}


def sync_branch_revenue(
    branch_id: str,
    property_id: str,
    currency: str,
    api_key: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """
    Pull Accommodation transactions from Cloudbeds and update grand_total_native
    for matching reservations. Uses getTransactions?category=Accommodation which
    returns bulk revenue data without needing per-reservation API calls.

    Groups transaction amounts by reservationID, sums them, and writes to DB.
    """
    if not api_key:
        raise ValueError(f"No API key for property {property_id}")

    today = date.today()
    if date_from is None:
        # Default: first day of current month — past months already settled, skip them
        date_from = today.replace(day=1)
    if date_to is None:
        date_to = today + timedelta(days=CHECKIN_FUTURE_DAYS)

    db = SessionLocal()
    page = 1
    revenue_map: dict[str, float] = {}   # cloudbeds_reservation_id → total accommodation revenue
    room_type_map: dict[str, str] = {}    # cloudbeds_reservation_id → roomTypeName

    logger.info(
        "Revenue sync branch %s property %s [checkIn %s → %s]",
        branch_id, property_id, date_from, date_to,
    )

    try:
        rate = get_cached_rate(currency, "VND")

        # Fetch all transaction pages
        while True:
            data = _fetch_transactions_page(
                property_id, page, api_key,
                checkin_from=date_from,
                checkin_to=date_to,
            )
            records = data.get("data", [])
            total_count = data.get("total", 0)

            for txn in records:
                res_id = str(txn.get("reservationID", ""))
                # USALI Room Revenue: only "Room Revenue" debit transactions.
                # Excludes OTA credits (Booking.com, Expedia, etc.), cash/CC payments,
                # Items & Services, cancellation fees, and taxes — per USALI standards.
                is_room_revenue = (
                    txn.get("category") == "Room Revenue"
                    and txn.get("transactionType") == "debit"
                    and not txn.get("isDeleted", False)
                )
                if is_room_revenue:
                    amount = _safe_decimal(txn.get("amount")) or 0.0
                    revenue_map[res_id] = revenue_map.get(res_id, 0.0) + amount
                rt = txn.get("roomTypeName")
                if rt and res_id not in room_type_map:
                    room_type_map[res_id] = rt

            logger.info(
                "Revenue page %d/%d — %d transactions for %d reservations",
                page, (total_count // PAGE_SIZE) + 1, len(records), len(revenue_map),
            )

            fetched_so_far = (page - 1) * PAGE_SIZE + len(records)
            if fetched_so_far >= total_count or not records:
                break
            page += 1

        # Update DB — raw SQL per row, commit every BATCH_SIZE rows to avoid
        # pgBouncer executemany failures while keeping round-trips reasonable.
        BATCH_SIZE = 20
        updated = 0
        now = datetime.now(timezone.utc)
        items = list(revenue_map.items())
        for batch_start in range(0, len(items), BATCH_SIZE):
            batch = items[batch_start: batch_start + BATCH_SIZE]
            _s = SessionLocal()
            try:
                for cloudbeds_id, total_rev in batch:
                    native = round(total_rev, 2)
                    vnd = round(total_rev * rate, 2) if rate is not None else None
                    _s.execute(_text(
                        "UPDATE reservations SET grand_total_native=:n, grand_total_vnd=:v, updated_at=:t "
                        "WHERE cloudbeds_reservation_id=:cid"
                    ), {"n": native, "v": vnd, "t": now, "cid": str(cloudbeds_id)})
                    if cloudbeds_id in room_type_map:
                        rt = room_type_map[cloudbeds_id]
                        _s.execute(_text(
                            "UPDATE reservations SET room_type=:rt, room_type_category=:rc "
                            "WHERE cloudbeds_reservation_id=:cid AND room_type IS NULL"
                        ), {"rt": rt, "rc": map_room_type_category(rt), "cid": str(cloudbeds_id)})
                    updated += 1
                _s.commit()
            except Exception as e:
                _s.rollback()
                logger.warning("Revenue batch write failed at row %d: %s", batch_start, e)
            finally:
                _s.close()

        fallback_updated = 0
        # Cloudbeds bulk getReservations returns lite payload (no accommodation total).
        # For NULL reservations, use backfill_accommodation_total() as a one-time job.

        logger.info(
            "Revenue sync complete branch %s: %d from transactions + %d from fallback",
            branch_id, updated, fallback_updated,
        )
        return {
            "branch_id": branch_id,
            "revenue_reservations_updated": updated,
            "revenue_fallback_updated": fallback_updated,
        }

    except Exception as exc:
        logger.error("Revenue sync failed for branch %s: %s", branch_id, exc)
        raise
    finally:
        db.close()


def backfill_accommodation_total(
    branch_id: str,
    property_id: str,
    currency: str,
    api_key: str,
    checkin_from: Optional[date] = None,
    checkin_to: Optional[date] = None,
    limit: Optional[int] = None,
) -> dict:
    """
    One-time backfill: for reservations with NULL grand_total_native, call
    getReservation individually and store balanceDetailed.subTotal (accommodation only).
    Slow (~1s/call) — run once, not in the daily sync loop.
    """
    today = date.today()
    df = checkin_from or today.replace(day=1)
    dt = checkin_to or (today + timedelta(days=CHECKIN_FUTURE_DAYS))

    db = SessionLocal()
    query = db.query(Reservation).filter(
        Reservation.branch_id == branch_id,
        Reservation.check_in_date >= df,
        Reservation.check_in_date <= dt,
        Reservation.grand_total_native == None,  # noqa: E711
        Reservation.status.notin_(["cancelled", "canceled", "no_show", "noshow"]),
    )
    if limit:
        query = query.limit(limit)
    null_res = query.all()
    db.close()

    rate = get_cached_rate(currency, "VND")
    total_fetched = filled = 0
    now = datetime.now(timezone.utc)
    BATCH_SIZE = 20

    logger.info("Backfill: %d NULL reservations for branch %s", len(null_res), branch_id)

    with httpx.Client(timeout=30) as client:
        batch_buf: list[tuple[str, float]] = []
        for i, r in enumerate(null_res):
            try:
                resp = client.get(
                    f"{CLOUDBEDS_BASE_URL}/getReservation",
                    headers=_headers(api_key),
                    params={"propertyID": property_id, "reservationID": r.cloudbeds_reservation_id},
                )
                resp.raise_for_status()
                bd = (resp.json().get("data") or {}).get("balanceDetailed") or {}
                sub = float(_safe_decimal(bd.get("subTotal")) or 0)
                extra = float(_safe_decimal(bd.get("additionalItems")) or 0)
                accom = sub - extra
                if accom > 0:
                    batch_buf.append((r.cloudbeds_reservation_id, accom))
                total_fetched += 1
            except Exception as e:
                logger.warning("Backfill fetch failed res %s: %s", r.cloudbeds_reservation_id, e)

            # Flush batch every BATCH_SIZE rows
            if len(batch_buf) >= BATCH_SIZE or (i == len(null_res) - 1 and batch_buf):
                _s = SessionLocal()
                try:
                    for cb_id, accom in batch_buf:
                        native = round(accom, 2)
                        vnd = round(accom * rate, 2) if rate else None
                        result = _s.execute(_text(
                            "UPDATE reservations SET grand_total_native=:n, grand_total_vnd=:v, updated_at=:t "
                            "WHERE cloudbeds_reservation_id=:cid AND grand_total_native IS NULL"
                        ), {"n": native, "v": vnd, "t": now, "cid": cb_id})
                        if result.rowcount:
                            filled += 1
                    _s.commit()
                except Exception as e:
                    _s.rollback()
                    logger.warning("Backfill batch write failed: %s", e)
                finally:
                    _s.close()
                batch_buf.clear()

            if (i + 1) % 50 == 0:
                logger.info("Backfill progress: %d/%d fetched, %d filled", i + 1, len(null_res), filled)

    logger.info("Backfill complete branch %s: %d fetched, %d filled", branch_id, total_fetched, filled)
    return {"branch_id": branch_id, "fetched": total_fetched, "filled": filled}


def _fetch_reservations_page(
    property_id: str,
    page: int,
    api_key: Optional[str] = None,
    modified_since: Optional[date] = None,
    checkin_from: Optional[date] = None,
    checkin_to: Optional[date] = None,
) -> dict:
    params: dict = {
        "propertyID": property_id,
        "pageNumber": page,
        "pageSize": PAGE_SIZE,
    }
    if modified_since:
        params["modifiedAt[gte]"] = modified_since.isoformat()
    if checkin_from:
        params["checkIn[gte]"] = checkin_from.isoformat()
    if checkin_to:
        params["checkIn[lte]"] = checkin_to.isoformat()
    with httpx.Client(timeout=60) as client:
        response = client.get(
            f"{CLOUDBEDS_BASE_URL}/getReservations",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        return response.json()


def pull_reservations(
    property_id: str, modified_since: Optional[date] = None, api_key: Optional[str] = None
) -> list[dict]:
    """Fetch all reservation pages for a property from Cloudbeds."""
    if modified_since is None:
        modified_since = date.today() - timedelta(days=SYNC_LOOKBACK_DAYS)

    all_reservations: list[dict] = []
    page = 1

    try:
        while True:
            data = _fetch_reservations_page(property_id, modified_since, page, api_key)
            records = data.get("data", [])
            all_reservations.extend(records)

            total = data.get("total", 0)
            if len(all_reservations) >= total or not records:
                break
            page += 1

        logger.info("Pulled %d reservations for property %s", len(all_reservations), property_id)
    except Exception as exc:
        logger.error("Failed to pull reservations for property %s: %s", property_id, exc)
        raise

    return all_reservations


# ── Ingestion ──────────────────────────────────────────────────────────────────

def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def ingest_reservations(
    db: Session,
    branch_id: str,
    currency: str,
    raw_records: list[dict],
) -> tuple[int, int]:
    """
    Upsert reservation rows. Returns (created_count, updated_count).
    Converts grand_total to VND using cached rate (sync context).
    """
    created = updated = 0
    rate = get_cached_rate(currency, "VND")

    for raw in raw_records:
        cloudbeds_id = str(raw.get("reservationID", ""))
        if not cloudbeds_id:
            continue

        check_in = _parse_date(raw.get("startDate"))
        check_out = _parse_date(raw.get("endDate"))
        if not check_in or not check_out:
            continue

        nights = (check_out - check_in).days
        # "total" is only present in full API responses (modifiedAt filter).
        # CheckIn-filter responses return a lite payload without "total".
        # Only update revenue fields when the API actually provides them.
        has_total = "total" in raw
        grand_total_native = _safe_decimal(raw.get("total")) if has_total else None
        grand_total_vnd = (
            round(grand_total_native * rate, 2)
            if grand_total_native is not None and rate is not None
            else None
        )

        room_type = raw.get("roomTypeName")
        source = raw.get("sourceName") or raw.get("sourceID")
        guest_country = raw.get("guestCountry")

        # Base payload — fields always present in the API response
        payload = dict(
            branch_id=branch_id,
            check_in_date=check_in,
            check_out_date=check_out,
            nights=nights,
            status=raw.get("status"),
            adults=raw.get("adults"),
            cancellation_date=_parse_date(raw.get("cancellationDate")),
            reservation_date=_parse_date(raw.get("dateCreated")),
        )

        # Only update enriched fields when the API returned them
        if room_type is not None:
            payload["room_type"] = room_type
            payload["room_type_category"] = map_room_type_category(room_type)
        if source is not None:
            payload["source"] = normalize_source(source)
            payload["source_category"] = map_source_category(source)
        if guest_country is not None:
            payload["guest_country"] = guest_country
            payload["guest_country_code"] = map_country_code(guest_country)
        if has_total:
            payload["grand_total_native"] = grand_total_native
            payload["grand_total_vnd"] = grand_total_vnd
        if raw:
            payload["raw_data"] = raw

        existing = db.query(Reservation).filter_by(cloudbeds_reservation_id=cloudbeds_id).first()
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            # New reservation — set branch_id and all available fields
            payload["branch_id"] = branch_id
            if "room_type" not in payload:
                payload["room_type"] = room_type
                payload["room_type_category"] = map_room_type_category(room_type)
            if "source" not in payload:
                payload["source"] = normalize_source(source)
                payload["source_category"] = map_source_category(source)
            if "guest_country" not in payload:
                payload["guest_country"] = guest_country
                payload["guest_country_code"] = map_country_code(guest_country)
            db.add(Reservation(cloudbeds_reservation_id=cloudbeds_id, **payload))
            created += 1

    db.commit()
    logger.info("Ingested %d created, %d updated for branch %s", created, updated, branch_id)
    return created, updated


def _safe_decimal(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# ── Room count ─────────────────────────────────────────────────────────────────

def fetch_total_rooms(property_id: str, api_key: Optional[str] = None) -> int:
    """
    Call Cloudbeds getRooms (paginated) and return the total physical room/bed count.
    API returns count=20 per page with a `total` field for the full count.
    """
    url = f"{CLOUDBEDS_BASE_URL}/getRooms"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=_headers(api_key), params={"propertyID": property_id, "pageSize": 1})
        resp.raise_for_status()
        payload = resp.json()

    if not payload.get("success"):
        raise RuntimeError(f"getRooms error for property {property_id}: {payload.get('message')}")

    # `total` is the true count of all physical units across all pages
    total = payload.get("total")
    if total is not None:
        return int(total)

    # Fallback: sum rooms from data if total not present
    data = payload.get("data") or []
    return sum(len(item.get("rooms", [])) for item in data)


# ── Orchestration ──────────────────────────────────────────────────────────────

def sync_branch(
    branch_id: str,
    property_id: str,
    currency: str,
    api_key: Optional[str] = None,
    incremental: bool = False,
    checkin_from: Optional[date] = None,
    checkin_to: Optional[date] = None,
) -> dict:
    """
    Sync a single branch — ingest page-by-page for progressive DB writes.

    incremental=True:  use modifiedAt (last 2 days) — catches cancellations/modifications.
    incremental=False: use checkIn window (past CHECKIN_LOOKBACK_DAYS → future CHECKIN_FUTURE_DAYS)
                       to populate ALL reservations in the date range regardless of when modified.
    checkin_from/to:   explicit override — used by daily sync to limit to current+next month only.
    Revenue (grand_total_native) is populated separately via sync_branch_revenue.
    """
    if not api_key:
        raise ValueError(f"No API key for property {property_id}")

    today = date.today()
    db = SessionLocal()
    total_created = total_updated = 0
    page = 1

    if checkin_from is not None or checkin_to is not None:
        # Explicit date range — used for focused/daily sync
        fetch_kwargs = {"checkin_from": checkin_from, "checkin_to": checkin_to}
        window_desc  = f"checkIn {checkin_from} → {checkin_to}"
    elif incremental:
        fetch_kwargs = {"modified_since": today - timedelta(days=2)}
        window_desc = "modifiedAt 2d"
    else:
        _from = today - timedelta(days=CHECKIN_LOOKBACK_DAYS)
        _to   = today + timedelta(days=CHECKIN_FUTURE_DAYS)
        fetch_kwargs = {"checkin_from": _from, "checkin_to": _to}
        window_desc  = f"checkIn {_from} → {_to}"

    logger.info("Syncing branch %s property %s [%s]", branch_id, property_id, window_desc)

    try:
        while True:
            data = _fetch_reservations_page(property_id, page, api_key, **fetch_kwargs)
            records = data.get("data", [])
            total_count = data.get("total", 0)
            total_pages = (total_count // PAGE_SIZE) + 1

            if records:
                created, updated = ingest_reservations(db, branch_id, currency, records)
                total_created += created
                total_updated += updated
                logger.info(
                    "Branch %s page %d/%d — +%d created, ~%d updated",
                    branch_id, page, total_pages, created, updated,
                )

            fetched_so_far = (page - 1) * PAGE_SIZE + len(records)
            if fetched_so_far >= total_count or not records:
                break
            page += 1

        logger.info(
            "Sync complete for branch %s: %d created, %d updated",
            branch_id, total_created, total_updated,
        )
        return {"branch_id": branch_id, "created": total_created, "updated": total_updated}
    except Exception as exc:
        logger.error("Sync failed for branch %s: %s", branch_id, exc)
        raise
    finally:
        db.close()


# ── Reservation Daily population (v2.0) ───────────────────────────────────────

def _fetch_nightly_rates_from_transactions(
    property_id: str,
    currency: str,
    api_key: Optional[str],
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict[str, dict[date, float]]:
    """
    Fetch Room Revenue transactions from Cloudbeds grouped by (reservationID, serviceDate).
    Returns: { cloudbeds_reservation_id: { date: nightly_rate } }

    Cloudbeds posts one Room Revenue debit transaction per night of stay on the
    serviceDate = the actual night. This gives us TRUE per-night rates without
    any proration math needed.
    """
    rev_map: dict[str, dict[date, float]] = {}  # res_id → { date → amount }

    page = 1
    while True:
        data = _fetch_transactions_by_date_page(
            property_id, page, api_key,
            date_from=date_from, date_to=date_to,
        )
        records = data.get("data", [])
        total_count = data.get("total", 0)

        for txn in records:
            is_room_revenue = (
                txn.get("category") == "Room Revenue"
                and txn.get("transactionType") == "debit"
                and not txn.get("isDeleted", False)
            )
            if not is_room_revenue:
                continue

            res_id = str(txn.get("reservationID", ""))
            if not res_id:
                continue

            txn_date_str = txn.get("serviceDate") or txn.get("transactionDateTime") or ""
            try:
                txn_date = date.fromisoformat(txn_date_str[:10])
            except (ValueError, TypeError):
                continue

            amount = float(_safe_decimal(txn.get("amount")) or 0)
            if res_id not in rev_map:
                rev_map[res_id] = {}
            rev_map[res_id][txn_date] = rev_map[res_id].get(txn_date, 0.0) + amount

        fetched_so_far = (page - 1) * PAGE_SIZE + len(records)
        if fetched_so_far >= total_count or not records:
            break
        page += 1

    logger.info(
        "Fetched nightly rates for %d reservations from Cloudbeds transactions [%s → %s]",
        len(rev_map), date_from, date_to,
    )
    return rev_map


def populate_reservation_daily(
    db: Session,
    branch_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    property_id: Optional[str] = None,
    currency: Optional[str] = None,
    api_key: Optional[str] = None,
) -> int:
    """
    v2.0: Expand reservations into per-night rows in reservation_daily.

    Strategy:
    1. PRIMARY — If Cloudbeds API credentials are provided, fetch actual per-night
       Room Revenue transactions (serviceDate-based). Each night gets its true rate.
    2. FALLBACK — If no API access or no transaction found for a night, prorate:
       nightly_rate = grand_total_native / nights.

    Upserts on (reservation_id, date). Returns count of rows written.
    """
    from app.models.reservation_daily import ReservationDaily

    # ── Fetch actual nightly rates from Cloudbeds if API available ────────
    txn_rates: dict[str, dict[date, float]] = {}
    if property_id and api_key:
        try:
            txn_rates = _fetch_nightly_rates_from_transactions(
                property_id, currency or "USD", api_key,
                date_from=date_from, date_to=date_to,
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch nightly rates from Cloudbeds for branch %s: %s. "
                "Falling back to proration.", branch_id, e,
            )

    # ── Build cloudbeds_id → txn_rates lookup ────────────────────────────
    # txn_rates keys are cloudbeds_reservation_id, need to map to DB reservation.id

    q = db.query(Reservation).filter(Reservation.branch_id == branch_id)
    if date_from:
        q = q.filter(Reservation.check_out_date > date_from)
    if date_to:
        q = q.filter(Reservation.check_in_date <= date_to)

    reservations = q.all()

    # Map cloudbeds_id → per-night rates
    cb_id_to_rates: dict[str, dict[date, float]] = {}
    for cb_id, rates in txn_rates.items():
        cb_id_to_rates[cb_id] = rates

    vnd_rate = get_cached_rate(currency or "USD", "VND") if currency else None
    count = 0

    for res in reservations:
        if not res.check_in_date or not res.check_out_date:
            continue
        nights = res.nights or (res.check_out_date - res.check_in_date).days
        if nights <= 0:
            continue

        # Try to get actual per-night rates from Cloudbeds transactions
        actual_rates = cb_id_to_rates.get(res.cloudbeds_reservation_id, {})

        # Fallback proration
        grand_total = float(res.grand_total_native or 0)
        fallback_rate = round(grand_total / nights, 2) if nights > 0 else 0.0

        # Determine room_id (first room from comma-separated list)
        room_id = None
        if res.room_number:
            for rm in str(res.room_number).split(","):
                rm = rm.strip()
                if rm:
                    room_id = rm
                    break

        current = res.check_in_date
        end = res.check_out_date
        while current < end:
            # Use actual Cloudbeds nightly rate if available, otherwise prorate
            if current in actual_rates:
                night_rate = round(actual_rates[current], 2)
            else:
                night_rate = fallback_rate

            night_rate_vnd = round(night_rate * vnd_rate, 2) if vnd_rate else None

            existing = db.query(ReservationDaily).filter_by(
                reservation_id=res.id, date=current,
            ).first()

            if existing:
                existing.nightly_rate = night_rate
                existing.nightly_rate_vnd = night_rate_vnd
                existing.status = res.status
                existing.source = res.source
                existing.source_category = res.source_category
                existing.room_type_category = res.room_type_category
                existing.room_id = room_id
            else:
                db.add(ReservationDaily(
                    reservation_id=res.id,
                    branch_id=branch_id,
                    date=current,
                    room_id=room_id,
                    nightly_rate=night_rate,
                    nightly_rate_vnd=night_rate_vnd,
                    status=res.status,
                    source=res.source,
                    source_category=res.source_category,
                    room_type_category=res.room_type_category,
                ))

            count += 1
            current += timedelta(days=1)

    db.commit()
    logger.info("Populated %d reservation_daily rows for branch %s", count, branch_id)
    return count


async def sync_all_branches() -> list[dict]:
    """Sync all active branches — uses per-property API key from config."""
    from app.models.branch import Branch

    db = SessionLocal()
    results = []
    try:
        branches = db.query(Branch).filter_by(is_active=True).all()
        for branch in branches:
            pid = branch.cloudbeds_property_id
            if not pid:
                logger.warning("No property_id for branch %s — skipping", branch.name)
                results.append({"branch_id": str(branch.id), "branch": branch.name, "error": "no property_id"})
                continue
            api_key = settings.get_api_key_for_property(str(pid))
            if not api_key:
                logger.warning("No API key for property %s (%s) — skipping", pid, branch.name)
                results.append({"branch_id": str(branch.id), "branch": branch.name, "error": "no api_key configured"})
                continue
            try:
                result = sync_branch(str(branch.id), pid, branch.currency, api_key=api_key, incremental=True)
                result["branch"] = branch.name
                results.append(result)
            except Exception as exc:
                logger.error("Branch %s sync error: %s", branch.name, exc)
                results.append({"branch_id": str(branch.id), "branch": branch.name, "error": str(exc)})
    finally:
        db.close()

    return results
