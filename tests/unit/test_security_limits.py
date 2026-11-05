"""Light security limits: login throttle, password length, duplicate-email wording, upload cap."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import app.api.routes as routes
from app.api.login_throttle import LoginThrottle
from app.application.use_cases.auth import RegisterUser
from app.domain.errors import AuthError, ConflictError


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_throttle_blocks_after_max_failures_then_recovers():
    clock = Clock()
    th = LoginThrottle(max_failures=3, window_seconds=100, clock=clock)
    for _ in range(2):
        th.record_failure("k")
    assert th.retry_after("k") == 0
    th.record_failure("k")
    assert th.retry_after("k") > 0
    assert th.retry_after("other") == 0
    clock.t = 101
    assert th.retry_after("k") == 0


def test_throttle_reset_and_bounded_memory():
    th = LoginThrottle(max_failures=1, window_seconds=100, clock=Clock(), max_keys=3)
    th.record_failure("a")
    th.reset("a")
    assert th.retry_after("a") == 0
    for k in "bcdef":
        th.record_failure(k)
    assert len(th._failures) <= 3


def test_register_requires_8_characters():
    with pytest.raises(ValidationError):
        routes.RegisterRequest(email="a@b.co", password="1234567")
    routes.RegisterRequest(email="a@b.co", password="12345678")
    # Existing accounts made under the old 6-char rule must still be able to log in.
    routes.LoginRequest(email="a@b.co", password="123456")
    with pytest.raises(AuthError):
        RegisterUser(SimpleNamespace(), SimpleNamespace(), SimpleNamespace()).execute("a@b.co", "1234567")


class _Users:
    def __init__(self, exists):
        self.exists = exists

    def create(self, email, password_hash):
        if self.exists:
            raise ConflictError("Email already registered")
        return SimpleNamespace(id=uuid4(), email=email)

    def get_by_email(self, email):
        return None


def _container(exists=False):
    hasher = SimpleNamespace(hash=lambda p: "h", verify=lambda p, h: False)
    tokens = SimpleNamespace(create_access_token=lambda uid, email: "tok")
    return SimpleNamespace(users=_Users(exists), password_hasher=hasher, tokens=tokens)


def test_duplicate_email_gets_generic_message_without_confirming_existence():
    req = routes.RegisterRequest(email="a@b.co", password="12345678")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(routes.register(req, _container(exists=True)))
    assert exc.value.status_code == 400
    assert "đã tồn tại" not in exc.value.detail and "already" not in exc.value.detail.lower()


def test_login_is_throttled_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(routes, "_login_throttle", LoginThrottle(max_failures=2, window_seconds=100, clock=Clock()))
    req = routes.LoginRequest(email="a@b.co", password="wrong")
    request = SimpleNamespace(client=SimpleNamespace(host="1.2.3.4"))
    statuses = []
    for _ in range(3):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(routes.login(req, request, _container()))
        statuses.append(exc.value.status_code)
    assert statuses == [401, 401, 429]
    assert "Retry-After" in exc.value.headers


class _BigFile:
    def __init__(self, size):
        self.size, self.filename = size, "x.docx"

    async def read(self, n=-1):
        return b"x" * (self.size if n < 0 else min(self.size, n))


def test_upload_over_limit_is_rejected_before_processing(monkeypatch):
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(max_upload_mb=1))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(routes.upload(_BigFile(2 * 1024 * 1024), uuid4(), SimpleNamespace()))
    assert exc.value.status_code == 413
