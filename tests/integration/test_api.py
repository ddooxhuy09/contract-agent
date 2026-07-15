from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_current_user_id

# These tests exercise validation/not-found behavior below the auth layer, so bypass real
# Supabase auth with a fixed fake user id rather than needing a live JWT.
app.dependency_overrides[get_current_user_id] = lambda: "00000000-0000-0000-0000-000000000000"

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upload_no_file():
    resp = client.post("/api/v1/upload")
    assert resp.status_code == 422


def test_analyze_invalid_id():
    resp = client.post("/api/v1/analyze", json={"contract_id": "00000000-0000-0000-0000-000000000001"})
    assert resp.status_code == 404


def test_chat_missing_fields():
    resp = client.post("/api/v1/chat", json={})
    assert resp.status_code == 422
