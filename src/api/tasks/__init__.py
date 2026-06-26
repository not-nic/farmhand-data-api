"""
Python module containing scheduler jobs definitions.
"""
from datetime import UTC, datetime, timedelta

from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.api.tasks.map_tasks import (
    download_pending_maps,
    extract_files_from_maps,
    get_new_maps,
)
from src.api.tasks.scheduler import JobModel, Scheduler

base_scheduler = Scheduler()

# Schedule job to poll the ModHub once a day for new mods.
base_scheduler.add_job(
    JobModel(
        func=get_new_maps,
        trigger=OrTrigger([
            CronTrigger(day_of_week="mon-fri", hour=14, minute=0),
            DateTrigger(run_date=datetime.now(UTC) + timedelta(minutes=10)),
        ]),
        id="get_new_maps",
        name="Check and download new Farming Simulator Maps",
    )
)

# Schedule job to download mods from S3.
base_scheduler.add_job(
    JobModel(
        func=download_pending_maps,
        trigger=IntervalTrigger(
            minutes=15,
            start_date=datetime.now(UTC) + timedelta(minutes=20)
        ),
        id="download_pending_maps",
        name="Download PENDING maps to S3",
    )
)

# Schedule job to extract and restructure files from DOWNLOADED map archives.
base_scheduler.add_job(
    JobModel(
        func=extract_files_from_maps,
        trigger=IntervalTrigger(
            minutes=1,
            start_date=datetime.now(UTC) + timedelta(minutes=1)
        ),
        id="extract_files_from_maps",
        name="Extract files from DOWNLOADED maps",
    )
)

