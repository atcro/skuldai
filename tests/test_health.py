from fastapi.testclient import TestClient

from skuld.api.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "skuld"
    # Health must never imply anything about simulator or provider readiness.
    assert "simulator" not in body
    assert "release" not in body
