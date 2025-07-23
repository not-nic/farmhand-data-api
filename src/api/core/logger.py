"""
Logging Module for the farmhand-data-api
"""

import logging

from src.api.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

log_handler = logging.StreamHandler()
log_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S %Z"))
logger.addHandler(log_handler)
