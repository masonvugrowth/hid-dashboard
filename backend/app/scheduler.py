import logging

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(
    timezone="Asia/Ho_Chi_Minh",
    executors={
        "default": ThreadPoolExecutor(max_workers=8),
        "asyncio": AsyncIOExecutor(),
    },
    job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 600},
)


def start_scheduler() -> None:
    """Register jobs and start them from FastAPI's lifespan context.

    FastAPI bypasses ``@app.on_event`` startup handlers when a lifespan handler
    is configured. Keeping scheduler lifecycle explicit prevents a deployment
    from silently coming up without the reservation poller.
    """
    if scheduler.running:
        return

    from app.routers.webhooks import poll_new_reservations, poll_realtime_safety_net

    def heartbeat() -> None:
        logger.info("Scheduler heartbeat - server alive")

    def purge_webhook_events() -> None:
        from app.services import webhook_log
        webhook_log.purge_old()

    def evaluate_rate_plan_quotas() -> None:
        """Cloudbeds incremental sync + per-reservation backfill + recount.

        Also triggered by .github/workflows/cron-rate-plan-quota.yml, but that
        schedule is not dependable: GitHub only runs cron workflows on a
        best-effort basis, and the observed gaps on this repo ranged from 29
        minutes to over five hours. Every hour a tick is skipped, freshly
        booked rows sit in the DB with no room_type or rate_plan_name, which
        makes them unmatchable by any rate plan filter — the quota counter
        reads low and rate-plan pulls come back empty. This job runs inside
        the backend, which is up continuously, so the cadence is real.

        The GitHub cron stays as a redundant trigger. Double-firing is safe:
        the sync upserts by cloudbeds_reservation_id and alert emails are
        deduped by threshold bucket.
        """
        from app.database import SessionLocal
        from app.services.rate_plan_quota_engine import evaluate_quotas

        try:
            evaluate_quotas(SessionLocal, refresh=True)
        except Exception:
            logger.exception("Rate plan quota evaluation failed")

    scheduler.add_job(
        heartbeat,
        trigger=IntervalTrigger(minutes=10),
        id="scheduler_heartbeat",
        replace_existing=True,
        executor="default",
    )
    scheduler.add_job(
        poll_new_reservations,
        trigger=IntervalTrigger(minutes=10),
        id="cloudbeds_reservation_poll",
        replace_existing=True,
        executor="default",
    )
    # Branches on push webhooks are skipped by the job above and covered here
    # instead: hourly over a 90-minute window, wide enough that a push lost to a
    # redeploy costs a delay rather than the conversion. Registered
    # unconditionally so switching a branch to realtime is an env var, not a
    # deploy — with no realtime branches configured this walks an empty list.
    scheduler.add_job(
        poll_realtime_safety_net,
        trigger=IntervalTrigger(minutes=60),
        id="cloudbeds_realtime_safety_net",
        replace_existing=True,
        executor="default",
    )
    scheduler.add_job(
        purge_webhook_events,
        trigger=CronTrigger(hour=4, minute=0),
        id="webhook_events_purge",
        replace_existing=True,
        executor="default",
    )
    # max_instances=1 from job_defaults means a tick that is still running
    # never overlaps the next one; coalesce=True collapses ticks missed
    # during a redeploy into a single catch-up run.
    scheduler.add_job(
        evaluate_rate_plan_quotas,
        trigger=IntervalTrigger(minutes=30),
        id="rate_plan_quota_eval",
        replace_existing=True,
        executor="default",
    )
    scheduler.start()
    from app.config import settings

    realtime = sorted(settings.webhook_realtime_branches)
    logger.info(
        "Scheduler started - Cloudbeds poll every 10 min, rate plan quota "
        "eval every 30 min; realtime branches=%s",
        ",".join(realtime) or "none",
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
