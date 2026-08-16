"""
Python module containing exceptions raised by the data API.
"""


class MapProcessingError(Exception):
    """Raised when map data fails to process"""


class LayerNotReadyError(ValueError):
    """A dependency hasn't finished converting yet — skip and retry later."""


class MapBuilderError(Exception):
    """Raised when map layers have failed to be built."""
