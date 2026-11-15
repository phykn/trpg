from fastapi.testclient import TestClient
from run_api import build_app, local_settings


def test_health_answers_without_auth():
    response = TestClient(build_app(local_settings())).get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
