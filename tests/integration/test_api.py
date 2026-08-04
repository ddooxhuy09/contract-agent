"""Integration smoke — skips if heavy deps / DB stack unavailable."""

import os
from uuid import uuid4

import pytest

pytest.importorskip("langchain_huggingface")

from fastapi.testclient import TestClient

# The app refuses to start with the default JWT secret (W-050). Provide a
# non-default test secret before app import so lifespan does not abort, even
# when running in an environment without a local .env file.
os.environ["JWT_SECRET"] = "integration-test-secret"
os.environ.setdefault("GEMINI_API_KEY", "integration-test-key")
from app.core.settings import get_settings

get_settings.cache_clear()

from app.api.deps import get_current_user_id
from app.main import app

TEST_USER_ID = uuid4()


async def _override_user():
    return TEST_USER_ID


app.dependency_overrides[get_current_user_id] = _override_user


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_models(client):
    res = client.get("/api/v1/models")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
