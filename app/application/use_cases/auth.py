from uuid import UUID

from app.domain.errors import AuthError, ConflictError
from app.domain.ports.repositories import UserRepository
from app.domain.ports.services import PasswordHasher, TokenService


MIN_PASSWORD_LENGTH = 8


class RegisterUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService):
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    def execute(self, email: str, password: str) -> dict:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AuthError(f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự")
        try:
            user = self._users.create(email, self._hasher.hash(password))
        except ConflictError:
            raise
        token = self._tokens.create_access_token(user.id, user.email)
        return {"access_token": token, "token_type": "bearer", "user_id": str(user.id), "email": user.email}


class LoginUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService):
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    def execute(self, email: str, password: str) -> dict:
        user = self._users.get_by_email(email)
        if user is None or not self._hasher.verify(password, user.password_hash):
            raise AuthError("Invalid email or password")
        token = self._tokens.create_access_token(user.id, user.email)
        return {"access_token": token, "token_type": "bearer", "user_id": str(user.id), "email": user.email}


class ResolveUserId:
    def __init__(self, tokens: TokenService):
        self._tokens = tokens

    def execute(self, authorization: str | None) -> UUID:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise AuthError("Missing or invalid Authorization header")
        token = authorization.split(" ", 1)[1]
        payload = self._tokens.parse_access_token(token)
        return UUID(payload["sub"])
