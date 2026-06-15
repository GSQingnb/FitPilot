"""FastAPI dependency: provides a database session.

Re-exports get_db from database.session for convenience.
"""
from database.session import get_db

__all__ = ["get_db"]
