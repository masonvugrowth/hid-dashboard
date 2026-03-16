"""
Weekly Report router
- GET  /report/weekly       → report data (JSON)
- POST /report/send-weekly  → generate + send email to team
"""
import smtplib
import textwrap
from datetime import datetime, date, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.branch import Branch
from app.models.daily_metrics import DailyMetrics
from app.models.kpi import KPITarget
from app.models.reservation import Reservation
from app.services.kpi_engine import (
    compute_kpi_summary,
    compute_next_month_forecast,
    _EXCLUDED_STATUSES,
    _EXCLUDED_SOURCES,
)

router = APIRouter()

MONTHS_EN = ["", "January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]


def _envelope(data):
    return {"success": True, "data": data, "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat()}


def _fmt(val, currency=""):
    if val is None:
        return "—"
    sym = {"VND": "₫", "TWD": "NT$", "JPY": "¥"}.get(currency, currency + " ")
    if abs(val) >= 1_000_000_000:
        return f"{sym}{val/1_000_000_000:.1f}B"
    if abs(val) >= 1_000_000:
        return f"{sym}{val/1_000_000:.1f}M"
    return f"{sym}{round(val):,}"


def _pct(val):
    return f"{round(val)}%" if val is not None else "—"


def _top_countries(db: Session, branch_id, days: int = 90, limit: int = 5):
    cutoff = date.today() - timedelta(days=days)
    rows = (
        db.query(
            Reservation.guest_country,
            func.count(Reservation.id).label("cnt"),
        )
        .filter(
            Reservation.branch_id == branch_id,
            Reservation.check_in_date >= cutoff,
            Reservation.guest_country.isnot(None),
            ~func.lower(func.coalesce(Reservation.guest_country, "")).contains("unknown"),
            or_(
                Reservation.status == None,
                Reservation.status.notin_(list(_EXCLUDED_STATUSES)),
            ),
        )
        .group_by(Reservation.guest_country)
        .order_by(func.count(Reservation.id).desc())
        .limit(limit)
        .all()
    )
    return [{"country": r.guest_country, "bookings": r.cnt} for r in rows]


def _growth_countries(db: Session, branch_id, limit: int = 3):
    """Top countries with biggest booking growth (90d vs prior 90d)."""
    today = date.today()
    recent_start = today - timedelta(days=90)
    prev_start = today - timedelta(days=180)

    recent = {
        r.guest_country: r.cnt
        for r in db.query(
            Reservation.guest_country,
            func.count(Reservation.id).label("cnt"),
        ).filter(
            Reservation.branch_id == branch_id,
            Reservation.check_in_date >= recent_start,
            Reservation.guest_country.isnot(None),
            ~func.lower(func.coalesce(Reservation.guest_country, "")).contains("unknown"),
            or_(Reservation.status == None,
                Reservation.status.notin_(list(_EXCLUDED_STATUSES))),
        ).group_by(Reservation.guest_country).all()
    }

    prev = {
        r.guest_country: r.cnt
        for r in db.query(
            Reservation.guest_country,
            func.count(Reservation.id).label("cnt"),
        ).filter(
            Reservation.branch_id == branch_id,
            Reservation.check_in_date >= prev_start,
            Reservation.check_in_date < recent_start,
            Reservation.guest_country.isnot(None),
            ~func.lower(func.coalesce(Reservation.guest_country, "")).contains("unknown"),
            or_(Reservation.status == None,
                Reservation.status.notin_(list(_EXCLUDED_STATUSES))),
        ).group_by(Reservation.guest_country).all()
    }

    results = []
    for country, rec_cnt in recent.items():
        if rec_cnt < 2:
            continue
        prv_cnt = prev.get(country, 0)
        if prv_cnt == 0:
            continue
        growth = round((rec_cnt - prv_cnt) / prv_cnt * 100, 1)
        if growth > 0:
            results.append({"country": country, "recent": rec_cnt,
                            "prev": prv_cnt, "growth_pct": growth})

    results.sort(key=lambda x: x["growth_pct"], reverse=True)
    return results[:limit]


def _build_report(db: Session):
    today = date.today()
    branches = db.query(Branch).filter_by(is_active=True).all()
    report = []

    for b in branches:
        kpi = compute_kpi_summary(db, b.id, today.year, today.month, b.total_rooms or 0)
        nxt = compute_next_month_forecast(db, b.id, b.total_rooms or 0, today.year, today.month)
        top = _top_countries(db, b.id)
        growth = _growth_countries(db, b.id)

        report.append({
            "branch_id": str(b.id),
            "branch_name": b.name,
            "branch_city": b.city,
            "currency": b.currency,
            # This month
            "actual_revenue": kpi["actual_revenue_native"],
            "target_revenue": kpi["target_revenue_native"],
            "achievement_pct": round(kpi["achievement_pct"] * 100, 1) if kpi["achievement_pct"] else None,
            "avg_adr": kpi["avg_adr_native"],
            "avg_occ_pct": round((kpi["avg_occ_pct"] or 0) * 100, 1) if kpi["avg_occ_pct"] else None,
            "days_elapsed": kpi["days_elapsed"],
            "total_days": kpi["total_days"],
            "occ_forecast": kpi["occ_forecast_native"],
            "occ_forecast_pct": round(kpi["occ_forecast_native"] / kpi["target_revenue_native"] * 100, 1)
                if (kpi["occ_forecast_native"] and kpi["target_revenue_native"]) else None,
            # Next month
            "next_month": nxt["next_month"],
            "next_year": nxt["next_year"],
            "next_forecast": nxt["next_month_forecast_native"],
            "next_target": nxt["next_month_target_native"],
            "next_forecast_pct": round(nxt["next_month_forecast_native"] / nxt["next_month_target_native"] * 100, 1)
                if (nxt["next_month_forecast_native"] and nxt["next_month_target_native"]) else None,
            "next_adr": nxt["next_month_adr"],
            "next_booked_nights": nxt["next_month_booked_nights"],
            # Country intel
            "top_countries": top,
            "growth_countries": growth,
        })

    return report


def _build_html(report: list, today: date) -> str:
    month_name = MONTHS_EN[today.month]
    next_month_name = MONTHS_EN[today.month % 12 + 1]

    sections = []
    next_actions_all = []

    for b in report:
        cur = b["currency"]
        ach = b["achievement_pct"]
        ach_color = "#16a34a" if ach and ach >= 100 else "#ca8a04" if ach and ach >= 80 else "#dc2626"
        ach_str = f"{ach}%" if ach else "—"

        # Country intel next actions
        actions = []
        for g in b["growth_countries"][:2]:
            actions.append(f"▲ {g['country']} +{g['growth_pct']}% growth — increase ad budget targeting this market")
        for t in b["top_countries"][:2]:
            actions.append(f"🏆 {t['country']} top market — prioritize content & OTA rates for this market")
        if not b["occ_forecast"]:
            actions.append("⚠️ Predicted OCC% not set — go to KPI Dashboard to input")
        if b["achievement_pct"] and b["achievement_pct"] < 80:
            actions.append(f"🔴 KPI at {ach_str} — review pricing and promotions")

        next_actions_all.append({
            "branch": b["branch_name"],
            "city": b["branch_city"],
            "actions": actions,
        })

        top_c = " · ".join(f"{c['country']} ({c['bookings']})" for c in b["top_countries"][:3])
        growth_c = " · ".join(
            f"{g['country']} <span style='color:#16a34a'>▲{g['growth_pct']}%</span>"
            for g in b["growth_countries"][:3]
        ) or "—"

        sections.append(f"""
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
            <div>
              <h3 style="margin:0;font-size:16px;font-weight:700;color:#111827;">{b['branch_name']}</h3>
              <p style="margin:2px 0 0;font-size:12px;color:#6b7280;">{b['branch_city']} · {cur}</p>
            </div>
            <span style="background:#f3f4f6;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:700;color:{ach_color};">
              {ach_str} of target
            </span>
          </div>

          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <tr style="background:#f9fafb;">
              <th style="padding:8px 12px;text-align:left;color:#6b7280;font-weight:500;font-size:11px;text-transform:uppercase;">Metric</th>
              <th style="padding:8px 12px;text-align:right;color:#6b7280;font-weight:500;font-size:11px;text-transform:uppercase;">{month_name} (MTD {b['days_elapsed']}/{b['total_days']}d)</th>
              <th style="padding:8px 12px;text-align:right;color:#6b7280;font-weight:500;font-size:11px;text-transform:uppercase;">{next_month_name}</th>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:8px 12px;color:#374151;">Revenue</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#111827;">{_fmt(b['actual_revenue'], cur)}</td>
              <td style="padding:8px 12px;text-align:right;color:#6b7280;">booked: {_fmt(b.get('next_booked_nights'), '')} nights</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;background:#f9fafb;">
              <td style="padding:8px 12px;color:#374151;">Target</td>
              <td style="padding:8px 12px;text-align:right;color:#6b7280;">{_fmt(b['target_revenue'], cur)}</td>
              <td style="padding:8px 12px;text-align:right;color:#6b7280;">{_fmt(b['next_target'], cur)}</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:8px 12px;color:#374151;">ADR</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#111827;">{_fmt(b['avg_adr'], cur)}</td>
              <td style="padding:8px 12px;text-align:right;font-weight:600;color:#111827;">{_fmt(b['next_adr'], cur)}</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;background:#f9fafb;">
              <td style="padding:8px 12px;color:#374151;">OCC%</td>
              <td style="padding:8px 12px;text-align:right;color:#374151;">{_pct(b['avg_occ_pct'])}</td>
              <td style="padding:8px 12px;text-align:right;color:#6b7280;">—</td>
            </tr>
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:8px 12px;color:#374151;font-weight:600;">Forecast</td>
              <td style="padding:8px 12px;text-align:right;font-weight:700;color:#4f46e5;">
                {_fmt(b['occ_forecast'], cur)}
                {f"<span style='font-weight:400;color:#6b7280;'> ({b['occ_forecast_pct']}%)</span>" if b['occ_forecast_pct'] else ""}
              </td>
              <td style="padding:8px 12px;text-align:right;font-weight:700;color:#059669;">
                {_fmt(b['next_forecast'], cur)}
                {f"<span style='font-weight:400;color:#6b7280;'> ({b['next_forecast_pct']}%)</span>" if b['next_forecast_pct'] else ""}
              </td>
            </tr>
          </table>

          <div style="margin-top:14px;padding-top:12px;border-top:1px solid #f3f4f6;font-size:12px;color:#6b7280;">
            <strong style="color:#374151;">Top markets (90d):</strong> {top_c or '—'}<br/>
            <strong style="color:#374151;">Growing markets:</strong> {growth_c}
          </div>
        </div>""")

    # Next actions section
    action_html = ""
    for na in next_actions_all:
        if not na["actions"]:
            continue
        items = "".join(f"<li style='margin:4px 0;'>{a}</li>" for a in na["actions"])
        action_html += f"""
        <div style="margin-bottom:12px;">
          <strong style="font-size:13px;color:#374151;">{na['branch']} — {na['city']}</strong>
          <ul style="margin:6px 0 0;padding-left:20px;color:#374151;font-size:13px;">{items}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f3f4f6;margin:0;padding:24px;">
  <div style="max-width:680px;margin:0 auto;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:12px;padding:24px;margin-bottom:20px;color:#fff;">
      <h1 style="margin:0;font-size:22px;font-weight:700;">HiD Weekly Report</h1>
      <p style="margin:6px 0 0;opacity:0.85;font-size:14px;">
        {today.strftime('%A, %d %B %Y')} · {month_name} {today.year}
      </p>
    </div>

    <!-- Branch sections -->
    {''.join(sections)}

    <!-- Next Actions -->
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:16px;">
      <h3 style="margin:0 0 14px;font-size:15px;font-weight:700;color:#111827;">🎯 Next Actions</h3>
      {action_html or '<p style="color:#6b7280;font-size:13px;">No actions required this week.</p>'}
    </div>

    <!-- Footer -->
    <p style="text-align:center;font-size:11px;color:#9ca3af;margin-top:16px;">
      Generated by HiD Dashboard · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
    </p>
  </div>
</body>
</html>"""


@router.get("/weekly")
def weekly_report(db: Session = Depends(get_db)):
    """Return weekly report data as JSON."""
    today = date.today()
    report = _build_report(db)
    return _envelope({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "month": today.month,
        "year": today.year,
        "branches": report,
    })


@router.post("/send-weekly")
def send_weekly_email(to: Optional[str] = None, db: Session = Depends(get_db)):
    """Generate and send weekly HTML email via Gmail SMTP.
    Pass ?to=email@example.com to override recipients (useful for testing)."""
    gmail_user = getattr(settings, "GMAIL_USER", "") or ""
    gmail_pass = getattr(settings, "GMAIL_APP_PASSWORD", "") or ""
    recipients_raw = getattr(settings, "EMAIL_RECIPIENTS", "") or ""

    if not gmail_user or not gmail_pass:
        raise HTTPException(
            status_code=500,
            detail="GMAIL_USER and GMAIL_APP_PASSWORD not configured in .env"
        )

    if to:
        recipients = [t.strip() for t in to.split(",") if t.strip()]
    else:
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not recipients:
        raise HTTPException(status_code=500, detail="EMAIL_RECIPIENTS not configured in .env")

    today = date.today()
    report = _build_report(db)
    html = _build_html(report, today)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"HiD Weekly Report — {today.strftime('%d %b %Y')}"
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, recipients, msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Email send failed: {e}")

    return _envelope({
        "sent_to": recipients,
        "subject": msg["Subject"],
        "branches_included": len(report),
    })
