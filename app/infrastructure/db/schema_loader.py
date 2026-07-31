from pathlib import Path

from app.core.logging import logger
from app.core.settings import get_settings
from app.infrastructure.db.connection import get_db


def apply_postgres_schema() -> None:
    settings = get_settings()
    path = Path(settings.schema_sql_path)
    if not path.is_file():
        path = Path(__file__).resolve().parents[3] / "schema.sql"
    sql = path.read_text(encoding="utf-8")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    logger.info("Applied Postgres schema from %s", path)
