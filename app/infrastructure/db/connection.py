from contextlib import contextmanager
from collections.abc import Generator
from contextvars import ContextVar

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from app.core.settings import get_settings

psycopg2.extras.register_uuid()


def get_connection():
    conn = psycopg2.connect(get_settings().database_url)
    # register_vector may issue SQL; toggling autocommit must be outside a transaction.
    conn.autocommit = True
    register_vector(conn)
    conn.autocommit = False
    return conn


# Set by transaction(): every get_db() inside reuses one connection, committed once at the end.
_shared_conn: ContextVar = ContextVar("shared_conn", default=None)


@contextmanager
def get_db() -> Generator:
    shared = _shared_conn.get()
    if shared is not None:
        yield shared
        return
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaction() -> Generator:
    """All-or-nothing scope for several repository calls (e.g. one legal document ingest)."""
    with get_db() as conn:
        token = _shared_conn.set(conn)
        try:
            yield conn
        finally:
            _shared_conn.reset(token)
