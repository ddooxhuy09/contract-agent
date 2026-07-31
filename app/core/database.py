"""Compatibility re-export — prefer app.infrastructure.db.connection."""
from app.infrastructure.db.connection import get_connection, get_db
from app.infrastructure.db.schema_loader import apply_postgres_schema as init_db

__all__ = ["get_connection", "get_db", "init_db"]
