"""
Python module containing scheduler jobs definitions.
"""
from datetime import UTC, datetime, timedelta

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.api.tasks.map_tasks import (
    download_pending_maps,
    extract_files_from_maps,
    get_new_maps,
    retry_stalled_downloads,
)
from src.api.tasks.scheduler import JobModel, Scheduler

base_scheduler = Scheduler()

base_scheduler.add_job(JobModel(
    func=get_new_maps,
    trigger=CronTrigger(day_of_week="mon-fri", hour=14, minute=0),
    id="get_new_maps",
    name="Scrape ModHub for new Farming Simulator maps",
    group="discovery",
))

base_scheduler.add_job(JobModel(
    func=download_pending_maps,
    trigger=IntervalTrigger(
        minutes=10,
        start_date=datetime.now(UTC) + timedelta(minutes=5),
    ),
    id="download_pending_maps",
    name="Download PENDING maps to S3",
    group="pipeline",
))

base_scheduler.add_job(JobModel(
    func=extract_files_from_maps,
    trigger=IntervalTrigger(
        minutes=1,
        start_date=datetime.now(UTC) + timedelta(minutes=1),
    ),
    id="extract_files_from_maps",
    name="Extract files from DOWNLOADED maps",
    group="pipeline",
))

base_scheduler.add_job(JobModel(
    func=retry_stalled_downloads,
    trigger=CronTrigger(minute=0),
    id="retry_stalled_downloads",
    name="Reset stalled DOWNLOADING maps back to PENDING",
    group="recovery",
))

