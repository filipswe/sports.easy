"""Disposable local preview; never connects to the configured database or Docker services."""

import argparse
import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--live", action="store_true", help="Fetch real data into a new disposable DB (uses provider quota)")
parser.add_argument("--ai", action="store_true", help="Enable the ignored Groq key for this preview")
args = parser.parse_args()
for port in (3101, 8101):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Preview port {port} is in use. Stop that preview first.") from None
env = {**os.environ, **{k: v for k, v in dotenv_values(root / ".env").items() if v is not None}}
env.update(
    APP_ENV="development", APP_DATA_MODE="live" if args.live else "demo",
    PUBLIC_ORIGIN="http://127.0.0.1:3101", COOKIE_SECURE="false",
    API_INTERNAL_URL="http://127.0.0.1:8101", NEXT_TELEMETRY_DISABLED="1",
    SMTP_HOST="", GROQ_API_KEY=env.get("GROQ_API_KEY", "") if args.ai else "",
    ODDS_DAILY_BUDGET="20", ODDS_POLL_SECONDS="259200", POLL_SECONDS="86400",
    PATH="/usr/local/bin:" + os.environ.get("PATH", ""),
)
children = []
with tempfile.TemporaryDirectory(prefix="sports-easy-preview-") as temporary:
    env["DATABASE_URL"] = "sqlite:///" + str(Path(temporary) / "preview.db")
    python = str(root / ".venv/bin/python")
    try:
        for command in ([str(root / ".venv/bin/alembic"), "upgrade", "head"], [python, "-m", "app.cli", "ingest" if args.live else "seed"]):
            subprocess.run(command, cwd=root / "backend", env=env, check=True)
        children.append(subprocess.Popen([python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8101", "--no-access-log"], cwd=root / "backend", env=env, start_new_session=True))
        children.append(subprocess.Popen(["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3101"], cwd=root / "web", env=env, start_new_session=True))
        for _ in range(90):
            if any(child.poll() is not None for child in children):
                raise SystemExit("A preview service stopped. Inspect the output above.")
            try:
                with urlopen("http://127.0.0.1:3101", timeout=1) as response:
                    if response.status == 200:
                        print("Preview ready: http://127.0.0.1:3101 — Ctrl+C stops it and removes its disposable database.", flush=True)
                        break
            except OSError:
                time.sleep(1)
        else:
            raise SystemExit("Preview startup timed out.")
        while all(child.poll() is None for child in children):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
