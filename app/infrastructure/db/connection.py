from contextlib import contextmanager
from typing import Generator

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


@contextmanager
def get_db() -> Generator:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
