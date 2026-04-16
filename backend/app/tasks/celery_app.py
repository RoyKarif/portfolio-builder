from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("portfolio_builder", broker=settings.redis_url)

celery_app.conf.beat_schedule = {
    "update-market-data-daily": {
        "task": "app.tasks.market_update.update_all_market_data",
        "schedule": crontab(hour=1, minute=0),
    },
    "update-portfolio-snapshots-daily": {
        "task": "app.tasks.snapshot_update.update_all_snapshots",
        "schedule": crontab(hour=2, minute=0),
    },
}

celery_app.conf.timezone = "UTC"
celery_app.autodiscover_tasks(["app.tasks"])
