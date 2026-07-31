"""Integration smoke — skips if heavy deps / DB stack unavailable."""

from uuid import uuid4

import pytest

pytest.importorskip("langchain_huggingface")

from fastapi.testclient import TestClient

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
