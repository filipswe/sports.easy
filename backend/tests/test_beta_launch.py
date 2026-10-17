import importlib.util
import os
import ssl
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from app.db import now
from app.models import UsageCounter
from app.rate_limits import reserve_request
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_beta", ROOT / "scripts/check_beta.py")
check_beta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_beta)


@pytest.fixture
def counters():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    UsageCounter.__table__.create(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


def test_request_budget_survives_new_sessions_and_keeps_only_hashed_identity(counters):
    at = now().replace(second=0, microsecond=0)
    for _ in range(3):
        with counters() as db:
            assert reserve_request(db, "203.0.113.4", "auth-mutation", at, 3)
    with counters() as db:
        assert not reserve_request(db, "203.0.113.4", "auth-mutation", at, 3)
        assert reserve_request(db, "203.0.113.4", "research", at, 3)
        assert reserve_request(db, "203.0.113.5", "auth-mutation", at, 3)
        keys = list(db.scalars(select(UsageCounter.key)))
        assert all("203.0.113" not in key for key in keys)
        assert reserve_request(db, "203.0.113.4", "auth-mutation", at + timedelta(minutes=1), 3)
        assert reserve_request(db, "203.0.113.4", "auth-mutation", at + timedelta(minutes=3), 3)
        assert db.scalar(select(func.count()).select_from(UsageCounter)) == 2
        assert not reserve_request(db, "disabled", "research", at, 0)


def beta_values():
    return {
        "APP_ENV": "production",
        "APP_DATA_MODE": "live",
        "DATABASE_URL": "postgresql://localhost/beta?sslmode=require",
        "PUBLIC_ORIGIN": "https://beta.example.org",
        "COOKIE_SECURE": "true",
        "SESSION_SECRET": "test-only-private-config-" * 2,
        "FOOTBALL_PROVIDER": "football-data",
        "FOOTBALL_DATA_KEY": "test-only",
        "ODDS_API_KEY": "test-only",
        "LIVE_RETENTION_APPROVED": "true",
        "OPERATOR_NAME": "Test operator",
        "SUPPORT_EMAIL": "support@example.org",
        "SMTP_HOST": "smtp.example.org",
        "SMTP_USER": "test-only",
        "SMTP_PASSWORD": "test-only",
        "SMTP_FROM": "support@example.org",
    }


def test_beta_configuration_checks_never_connect_and_report_only_field_names():
    values = beta_values()
    assert check_beta.blockers(values) == []
    values.update(DATABASE_URL="", PUBLIC_ORIGIN="", SMTP_PASSWORD="", ODDS_DAILY_BUDGET="bad")
    errors = check_beta.blockers(values)
    assert errors == ["invalid setting: ODDS_DAILY_BUDGET"]
    assert "test-only" not in str(errors)


def test_private_runner_excludes_owner_credentials_and_rejects_invalid_config(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import run_beta

    values = {**beta_values(), "MIGRATION_DATABASE_URL": "owner-only-do-not-propagate"}
    inherited = {"MIGRATION_DATABASE_URL": "inherited-owner", "DATABASE_URL": "wrong-database"}
    env = run_beta.environment(values, inherited)
    assert env["DATABASE_URL"] == values["DATABASE_URL"]
    assert "MIGRATION_DATABASE_URL" not in env
    assert inherited["MIGRATION_DATABASE_URL"] == "inherited-owner"
    with pytest.raises(ValueError, match="SMTP authentication"):
        run_beta.environment({**values, "SMTP_PASSWORD": ""}, inherited)


def test_private_runner_bounds_command_and_never_invokes_migrations(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import run_beta

    (tmp_path / ".env.beta").write_text("test settings provided by fixture")
    monkeypatch.setattr(run_beta, "ROOT", tmp_path)
    monkeypatch.setattr(run_beta, "dotenv_values", lambda *a, **kw: beta_values())
    monkeypatch.setattr(sys, "argv", ["run_beta.py", "refresh-prices"])
    calls = []
    monkeypatch.setattr(
        run_beta.subprocess,
        "run",
        lambda *a, **kw: calls.append((a, kw)) or SimpleNamespace(returncode=0),
    )
    with pytest.raises(SystemExit) as result:
        run_beta.main()
    assert result.value.code == 0
    assert calls[0][0][0] == [sys.executable, "-m", "app.cli", "refresh-prices"]
    assert calls[0][1]["timeout"] == 1200
    assert calls[0][1]["cwd"] == tmp_path / "backend"
    assert "MIGRATION_DATABASE_URL" not in calls[0][1]["env"]


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("PUBLIC_ORIGIN", "https://beta.example.org/", "canonical public HTTPS origin"),
        ("PUBLIC_ORIGIN", "https://localhost", "canonical public HTTPS origin"),
        ("PUBLIC_ORIGIN", "https://[bad-host]", "canonical public HTTPS origin"),
        ("DATABASE_URL", "postgresql://localhost/beta", "PostgreSQL TLS (sslmode)"),
        ("LIVE_RETENTION_APPROVED", "false", "provider display and retention approval"),
        ("SMTP_FROM", "", "verified SMTP_FROM address"),
        ("SMTP_STARTTLS", "false", "SMTP TLS"),
    ],
)
def test_beta_rejects_incomplete_launch_configuration(field, value, expected):
    values = beta_values()
    values[field] = value
    assert expected in check_beta.blockers(values)


def test_plain_hosted_postgres_uri_uses_installed_driver_and_no_idle_pool():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.db import engine; print(engine.dialect.driver, type(engine.pool).__name__)",
        ],
        cwd=ROOT / "backend",
        env={
            **os.environ,
            "VERCEL": "1",
            "DATABASE_URL": "postgresql://127.0.0.1/not-connected?sslmode=require",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "psycopg NullPool"


def test_one_shot_worker_reports_complete_then_cached_without_duplicate_job(db, monkeypatch):
    from app import worker
    from app.models import Job

    monkeypatch.setattr(worker, "engine", db.bind)
    monkeypatch.setattr(worker, "SessionLocal", sessionmaker(db.bind, expire_on_commit=False))
    assert worker.tick()["status"] == "complete"
    count = db.scalar(select(func.count()).select_from(Job))
    assert worker.tick()["status"] == "cached"
    assert db.scalar(select(func.count()).select_from(Job)) == count


def test_production_middleware_shares_request_budget_and_fails_closed(client, db, monkeypatch):
    from app import main, rate_limits
    from app.config import settings

    reserve = rate_limits.reserve_request
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(db.bind, expire_on_commit=False))
    monkeypatch.setattr(
        rate_limits,
        "reserve_request",
        lambda db, actor, category, at, limit: reserve(db, actor, category, at, 3),
    )
    for _ in range(3):
        assert client.get("/api/ready").status_code == 200
    response = client.get("/api/ready")
    assert response.status_code == 429 and response.headers["Retry-After"] == "60"

    def unavailable():
        raise RuntimeError("test-hidden-credential")

    monkeypatch.setattr(main, "SessionLocal", unavailable)
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert "test-hidden-credential" not in response.text


def test_email_validates_server_certificate_before_authentication(db, monkeypatch):
    from app.auth import issue_token
    from app.config import settings
    from app.models import User

    events = []

    class Mail:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def starttls(self, *, context):
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            events.append("verified-tls")

        def login(self, *_):
            assert events == ["verified-tls"]
            events.append("login")

        def send_message(self, _):
            assert events == ["verified-tls", "login"]
            events.append("sent-mocked-message")

    monkeypatch.setattr("app.auth.smtplib.SMTP", lambda *_args, **_kwargs: Mail())
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.org")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_user", "test-only")
    monkeypatch.setattr(settings, "public_origin", "https://beta.example.org")
    user = User(email="test@example.org", password_hash="test-only")
    db.add(user)
    db.flush()
    assert issue_token(db, user, "verify") is None
    assert events == ["verified-tls", "login", "sent-mocked-message"]
