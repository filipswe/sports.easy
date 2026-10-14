import importlib.util
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "preview", Path(__file__).resolve().parents[2] / "scripts/preview.py"
)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def cache(database, fetched=None):
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE ingestion_runs (provider TEXT, status TEXT, created_at TEXT)")
        if fetched is not None:
            db.execute(
                "INSERT INTO ingestion_runs VALUES ('live', 'complete', ?)", (fetched.isoformat(),)
            )


@pytest.mark.parametrize("hours,due", [(-1, True), (0, False), (3, False), (4, True)])
def test_live_preview_respects_four_hour_cache(tmp_path, hours, due):
    database = tmp_path / "live.db"
    at = datetime(2026, 10, 14, 12, tzinfo=UTC)
    cache(database, at - timedelta(hours=hours))
    assert preview.live_refresh_due(database, at) is due


def test_recent_live_preview_skips_ingestion_and_never_uses_configured_db(tmp_path, monkeypatch):
    database = tmp_path / "live.db"
    cache(database, datetime.now(UTC))
    calls = []
    monkeypatch.setattr(
        preview.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command) or SimpleNamespace(returncode=0),
    )
    env = {"DATABASE_URL": "postgresql://do-not-connect-to-existing-data"}
    preview.prepare_database(tmp_path, env, database, live=True)
    assert len(calls) == 1 and calls[0][-2:] == ["upgrade", "head"]
    assert env["DATABASE_URL"] == "sqlite:///" + str(database)
    assert database.stat().st_mode & 0o777 == 0o600


def test_provider_outage_preserves_live_preview_cache(tmp_path, monkeypatch, capsys):
    database = tmp_path / "live.db"
    cache(database)
    monkeypatch.setattr(
        preview.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=2 if command[-1] == "ingest" else 0),
    )
    preview.prepare_database(tmp_path, {}, database, live=True)
    assert "Live refresh unavailable" in capsys.readouterr().out
    assert database.exists()


def test_initialization_bugs_are_not_mislabelled_provider_outages(tmp_path, monkeypatch):
    database = tmp_path / "live.db"
    cache(database)
    monkeypatch.setattr(
        preview.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=1 if command[-1] == "ingest" else 0),
    )
    with pytest.raises(SystemExit, match="initialization failed"):
        preview.prepare_database(tmp_path, {}, database, live=True)
