"""Local preview with isolated data; never connects to the configured database or Docker."""

import argparse
import os
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

from dotenv import dotenv_values


def live_refresh_due(database, at=None, interval=86400):
    at = at or datetime.now(UTC)
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute(
            "SELECT created_at FROM ingestion_runs WHERE provider='live' AND status='complete' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return True
    fetched = datetime.fromisoformat(row[0])
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=UTC)
    return not 0 <= (at - fetched).total_seconds() < interval


def prepare_database(root, env, database, live):
    env["DATABASE_URL"] = "sqlite:///" + str(database)
    subprocess.run(
        [str(root / ".venv/bin/alembic"), "upgrade", "head"],
        cwd=root / "backend",
        env=env,
        check=True,
    )
    database.chmod(0o600)
    if live and not live_refresh_due(database):
        print("Using isolated live cache; fixture refresh is not due yet.", flush=True)
        return
    result = subprocess.run(
        [str(root / ".venv/bin/python"), "-m", "app.cli", "ingest" if live else "seed"],
        cwd=root / "backend",
        env=env,
    )
    if result.returncode:
        if not live or result.returncode != 2:
            raise SystemExit("Preview initialization failed. Inspect the output above.")
        print(
            "Live refresh unavailable. Starting with stored data; matches without usable "
            "prices remain hidden. Check provider quota before retrying.",
            flush=True,
        )


def stop(children):
    for child in children:
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for child in children:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def serve(root, env):
    children = []
    web_env = {
        **os.environ,
        "PATH": env["PATH"],
        "API_INTERNAL_URL": env["API_INTERNAL_URL"],
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    for key in list(web_env):
        if any(word in key for word in ("KEY", "SECRET", "PASSWORD")) or key == "DATABASE_URL":
            del web_env[key]
    try:
        children.append(
            subprocess.Popen(
                [
                    str(root / ".venv/bin/python"),
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8101",
                    "--no-access-log",
                ],
                cwd=root / "backend",
                env=env,
                start_new_session=True,
            )
        )
        children.append(
            subprocess.Popen(
                ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3101"],
                cwd=root / "web",
                env=web_env,
                start_new_session=True,
            )
        )
        for _ in range(90):
            if any(child.poll() is not None for child in children):
                raise SystemExit("A preview service stopped. Inspect the output above.")
            try:
                with urlopen("http://127.0.0.1:3101/api/ready", timeout=1) as response:
                    if response.status == 200:
                        print("Preview ready: http://127.0.0.1:3101 — Ctrl+C stops it.", flush=True)
                        break
            except OSError:
                time.sleep(1)
        else:
            raise SystemExit("Preview startup timed out.")
        while all(child.poll() is None for child in children):
            time.sleep(1)
    finally:
        stop(children)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use isolated, cached real data")
    parser.add_argument("--ai", action="store_true", help="Enable the ignored Groq key")
    args = parser.parse_args()
    for port in (3101, 8101):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(
                    f"Preview port {port} is in use. If the preview is already running, open http://127.0.0.1:3101; otherwise stop the process using that port."
                ) from None
    env = {**os.environ, **{k: v for k, v in dotenv_values(root / ".env").items() if v is not None}}
    env.update(
        APP_ENV="development",
        APP_DATA_MODE="live" if args.live else "demo",
        PUBLIC_ORIGIN="http://127.0.0.1:3101",
        COOKIE_SECURE="false",
        API_INTERNAL_URL="http://127.0.0.1:8101",
        NEXT_TELEMETRY_DISABLED="1",
        SMTP_HOST="",
        GROQ_API_KEY=env.get("GROQ_API_KEY", "") if args.ai else "",
        ODDS_DAILY_BUDGET="20",
        ODDS_POLL_SECONDS="259200",
        POLL_SECONDS="86400",
        PATH="/usr/local/bin:" + os.environ.get("PATH", ""),
    )
    try:
        if args.live:
            if env.get("LIVE_RETENTION_APPROVED", "").lower() != "true":
                raise SystemExit(
                    "Live preview requires LIVE_RETENTION_APPROVED=true in ignored .env."
                )
            provider = env.get("FOOTBALL_PROVIDER", "football-data")
            if provider not in {"football-data", "api-football"}:
                raise SystemExit("Choose FOOTBALL_PROVIDER=football-data or api-football.")
            cache = root / ".preview"
            cache.mkdir(mode=0o700, exist_ok=True)
            database = cache / f"live-{provider}.db"
            prepare_database(root, env, database, live=True)
            serve(root, env)
        else:
            with tempfile.TemporaryDirectory(prefix="sports-easy-preview-") as temporary:
                prepare_database(root, env, Path(temporary) / "preview.db", live=False)
                serve(root, env)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
