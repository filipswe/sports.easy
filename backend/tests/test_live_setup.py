import pytest
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient


def configure_live(monkeypatch):
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings, "session_secret", "a-private-generated-test-secret-longer-than-32-chars"
    )
    monkeypatch.setattr(settings, "cookie_secure", False)
    monkeypatch.setattr(settings, "public_origin", "http://localhost:3000")


def test_live_data_can_start_on_local_development_http(monkeypatch):
    configure_live(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize(
    "origin", ["http://example.com", "http://localhost.example.com", "https://example.com"]
)
def test_public_live_deployment_still_requires_secure_cookie(monkeypatch, origin):
    configure_live(monkeypatch)
    monkeypatch.setattr(settings, "public_origin", origin)
    with pytest.raises(RuntimeError, match="Public live deployments require"):
        with TestClient(app):
            pass


def test_production_cannot_use_local_http_exception(monkeypatch):
    configure_live(monkeypatch)
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(RuntimeError, match="require"):
        with TestClient(app):
            pass


def test_live_mode_cannot_start_with_placeholder_secret(monkeypatch):
    configure_live(monkeypatch)
    monkeypatch.setattr(settings, "session_secret", "local-only-change-before-deployment-32chars")
    with pytest.raises(RuntimeError, match="private SESSION_SECRET"):
        with TestClient(app):
            pass


def test_secure_cookie_does_not_allow_public_http(monkeypatch):
    configure_live(monkeypatch)
    monkeypatch.setattr(settings, "public_origin", "http://example.com")
    monkeypatch.setattr(settings, "cookie_secure", True)
    with pytest.raises(RuntimeError, match="Public live deployments require"):
        with TestClient(app):
            pass
