from datetime import datetime, timedelta, UTC
from typing import Any
from uuid import UUID

import jwt

from app.core.settings import get_settings
from app.domain.errors import AuthError


class JwtTokenService:
    def create_access_token(self, user_id: UUID, email: str) -> str:
        settings = get_settings()
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
            "iat": datetime.now(UTC),
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def parse_access_token(self, token: str) -> dict[str, Any]:
        settings = get_settings()
        try:
            return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        except jwt.PyJWTError as e:
            raise AuthError("Invalid or expired token") from e
