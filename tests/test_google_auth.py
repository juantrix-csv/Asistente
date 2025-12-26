from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)


def test_google_auth_start_returns_url(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    response = client.get("/auth/google/start")
    assert response.status_code == 200

    data = response.json()
    assert "auth_url" in data
    assert "accounts.google.com" in data["auth_url"]