"""
Python module containing scheduler jobs definitions.
"""
from datetime import UTC, datetime, timedelta

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.api.tasks.map_tasks import (
    download_pending_maps,
    extract_files_from_maps,
    generate_map_assets,
    get_new_maps,
    parse_map_xml,
    process_info_layers,
    process_map_layers,
    retry_stalled_downloads,
)
from src.api.tasks.scheduler import JobModel, Scheduler

base_scheduler = Scheduler()


# Get New Maps
base_scheduler.add_job(JobModel(
    func=get_new_maps,
    trigger=CronTrigger(hour=14, minute=30),
    id="get_new_maps",
    name="Scrape ModHub for new Farming Simulator maps",
    group="discovery",
))


# Download Maps
base_scheduler.add_job(JobModel(
    func=download_pending_maps,
    trigger=IntervalTrigger(
        minutes=60,
        start_date=datetime.now(UTC) + timedelta(minutes=1),
    ),
    id="download_pending_maps",
    name="Download PENDING maps to S3",
    group="pipeline",
    executor="downloads",
    enabled=False
))


# Downloaded File Extraction
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


# XML Parsers & Map Generation.
base_scheduler.add_job(JobModel(
    func=parse_map_xml,
    trigger=IntervalTrigger(seconds=30),
    id="parse_map_xml",
    name="Parse modDesc.xml for extracted maps",
    group="pipeline",
))


base_scheduler.add_job(JobModel(
    func=process_map_layers,
    trigger=IntervalTrigger(seconds=30),
    id="process_map_data",
    name="Build map information",
    group="pipeline",
))


# Image Conversion pipeline stages
base_scheduler.add_job(JobModel(
    func=generate_map_assets,
    trigger=IntervalTrigger(seconds=30),
    id="generate_map_assets",
    name="Convert and upload pending map assets",
    group="pipeline",
))


base_scheduler.add_job(JobModel(
    func=process_info_layers,
    trigger=IntervalTrigger(seconds=30),
    id="process_info_layers",
    name="Convert pending info layer GRLE files to PNG",
    group="pipeline",
))


# Recover stalled downloads.
base_scheduler.add_job(JobModel(
    func=retry_stalled_downloads,
    trigger=CronTrigger(minute=0),
    id="retry_stalled_downloads",
    name="Reset stalled DOWNLOADING maps back to PENDING",
    group="recovery",
    enabled=False
))
