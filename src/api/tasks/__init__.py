"""
__init__.py for the /tasks package. Importing this module registers every
job defined in job_registry.py with the base_scheduler singleton.
"""

from src.api.tasks.job_registry import base_scheduler

__all__ = ["base_scheduler"]
