from uuid import UUID

from app.domain.entities.user import User
from app.domain.errors import ConflictError
from app.infrastructure.db.connection import get_db


class PgUserRepository:
    def create(self, email: str, password_hash: str) -> User:
        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO users (email, password_hash)
                        VALUES (%s, %s)
                        RETURNING id, email, password_hash, created_at
                        """,
                        (email.lower().strip(), password_hash),
                    )
                except Exception as e:
                    if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                        raise ConflictError("Email already registered") from e
                    raise
                row = cur.fetchone()
        return User(id=row[0], email=row[1], password_hash=row[2], created_at=row[3])

    def get_by_email(self, email: str) -> User | None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, password_hash, created_at FROM users WHERE email = %s",
                    (email.lower().strip(),),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return User(id=row[0], email=row[1], password_hash=row[2], created_at=row[3])

    def get_by_id(self, user_id: UUID) -> User | None:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, password_hash, created_at FROM users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return User(id=row[0], email=row[1], password_hash=row[2], created_at=row[3])
