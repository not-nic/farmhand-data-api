"""
Python Module containing base SqlAlchemy classes and mixins.22
"""

from sqlalchemy.orm import DeclarativeBase


class BaseMixin:
    """
    Mixin class for models to inherit from to provide base methods or attributes.
    """

    pass


class SqlAlchemyBase(BaseMixin, DeclarativeBase):
    pass
