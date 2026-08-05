"""
Python module containing exceptions raised by the data API.
"""


class MapProcessingError(Exception):
    """Raised when map data fails to process"""


class UnknownTaskError(Exception):
    """Raised when a job_id does not match any registered scheduler task"""


class InvalidTaskTriggerError(Exception):
    """Raised when trigger_args passed to a task update are invalid for its trigger type"""
