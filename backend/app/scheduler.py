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

        scheduler.start()
        logger.info(
            "Scheduler started — "
            "Cloudbeds sync at 02:00 ICT, "
            "metrics compute at 03:00 ICT"
        )

    @app.on_event("shutdown")
    async def stop_scheduler():
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
