import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")


def setup_scheduler(app):
    """Register scheduled jobs and attach lifecycle to FastAPI app."""

    @app.on_event("startup")
    async def start_scheduler():
        from app.services.cloudbeds import sync_all_branches
        from app.services.metrics_engine import nightly_metrics_job
        from app.services.verdict_sync import sync_combo_performance, compute_derived_verdicts
        from app.database import SessionLocal

        # Nightly Cloudbeds sync at 2:00am Vietnam time
        scheduler.add_job(
            sync_all_branches,
            trigger=CronTrigger(hour=2, minute=0),
            id="nightly_cloudbeds_sync",
            replace_existing=True,
        )

        # Nightly metrics recompute at 3:00am Vietnam time (after sync)
        scheduler.add_job(
            nightly_metrics_job,
            args=[SessionLocal],
            trigger=CronTrigger(hour=3, minute=0),
            id="nightly_metrics_compute",
            replace_existing=True,
        )

        # Nightly combo performance sync at 3:30am (after metrics)
        def _verdict_sync_job():
            db = SessionLocal()
            try:
                synced = sync_combo_performance(db)
                derived = compute_derived_verdicts(db)
                logger.info("Verdict sync complete — %d combos synced, %d components updated", synced, derived)
            except Exception:
                logger.exception("Verdict sync job failed")
            finally:
                db.close()

        scheduler.add_job(
            _verdict_sync_job,
            trigger=CronTrigger(hour=3, minute=30),
            id="nightly_verdict_sync",
            replace_existing=True,
        )

        scheduler.start()
        logger.info(
            "Scheduler started — "
            "Cloudbeds sync at 02:00 ICT, "
            "metrics compute at 03:00 ICT, "
            "verdict sync at 03:30 ICT"
        )

    @app.on_event("shutdown")
    async def stop_scheduler():
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
