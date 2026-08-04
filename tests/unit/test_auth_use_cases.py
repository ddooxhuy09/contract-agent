from datetime import datetime
from uuid import uuid4

import pytest

from app.application.use_cases.auth import LoginUser, RegisterUser, ResolveUserId
from app.domain.entities.user import User
from app.domain.errors import AuthError, ConflictError


class FakeUsers:
    def __init__(self):
        self._by_email: dict[str, User] = {}

    def create(self, email: str, password_hash: str) -> User:
        key = email.lower().strip()
        if key in self._by_email:
            raise ConflictError("Email already registered")
        user = User(id=uuid4(), email=key, password_hash=password_hash, created_at=datetime.utcnow())
        self._by_email[key] = user
        return user

    def get_by_email(self, email: str) -> User | None:
        return self._by_email.get(email.lower().strip())

    def get_by_id(self, user_id):
        for u in self._by_email.values():
            if u.id == user_id:
                return u
        return None


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeTokens:
    def create_access_token(self, user_id, email: str) -> str:
        return f"token:{user_id}:{email}"

    def parse_access_token(self, token: str) -> dict:
        if not token.startswith("token:"):
            raise AuthError("bad")
        _, uid, email = token.split(":", 2)
        from uuid import UUID

        return {"sub": uid, "email": email}


def test_register_and_login():
    users = FakeUsers()
    hasher = FakeHasher()
    tokens = FakeTokens()
    reg = RegisterUser(users, hasher, tokens).execute("a@b.com", "secret1")
    assert reg["email"] == "a@b.com"
    assert reg["access_token"].startswith("token:")

    login = LoginUser(users, hasher, tokens).execute("a@b.com", "secret1")
    assert login["user_id"] == reg["user_id"]

    with pytest.raises(AuthError):
        LoginUser(users, hasher, tokens).execute("a@b.com", "wrong")


def test_resolve_user_id():
    tokens = FakeTokens()
    uid = uuid4()
    token = tokens.create_access_token(uid, "x@y.com")
    resolved = ResolveUserId(tokens).execute(f"Bearer {token}")
    assert resolved == uid
