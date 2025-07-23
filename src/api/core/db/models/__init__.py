"""
__init__.py module containing the imports for all database models, so that
they can be imported by:
    from src.api.core.db.models import Map, etc.
"""

from src.api.core.db.models.maps import Map

__all__ = ["Map"]
