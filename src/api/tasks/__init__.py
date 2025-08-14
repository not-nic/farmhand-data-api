"""
Python module containing scheduler jobs definitions.
"""

from apscheduler.triggers.cron import CronTrigger

from src.api.tasks.map_tasks import get_new_maps
from src.api.tasks.scheduler import JobModel, Scheduler

base_scheduler = Scheduler()

base_scheduler.add_job(JobModel(
    func=get_new_maps,
    trigger=CronTrigger(hour=0, minute=0),
    id="get_new_maps",
    name="Check and download new Farming Simulator Maps"
))
