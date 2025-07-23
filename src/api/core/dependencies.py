"""
Module for FastAPI Dependencies that need to be called / injected before methods can be called.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from src.api.core.db.db_setup import get_db

SessionDep = Annotated[Session, Depends(get_db)]
