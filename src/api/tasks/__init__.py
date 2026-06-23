"""
Python module containing scheduler jobs definitions.
"""
from datetime import datetime, timezone, timedelta

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.api.tasks.map_tasks import get_new_maps
from src.api.tasks.scheduler import JobModel, Scheduler

from src.api.tasks.map_tasks import (
    download_pending_maps,
    get_new_maps,
)

base_scheduler = Scheduler()

# Schedule job to poll the ModHub once a day for new mods.
base_scheduler.add_job(
    JobModel(
        func=get_new_maps,
        trigger=CronTrigger(hour=14, minute=0),
        id="get_new_maps",
        name="Check and download new Farming Simulator Maps",
    )
)

# Schedule job to download mods from S3.
base_scheduler.add_job(
    JobModel(
        func=download_pending_maps,
        trigger=IntervalTrigger(
            minutes=10,
            start_date=datetime.now(timezone.utc) + timedelta(minutes=5)
        ),
        id="download_pending_maps",
        name="Download PENDING maps to S3",
    )
)
