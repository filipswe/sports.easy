"""Run bounded operator commands with private beta settings; never run migrations."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from check_beta import blockers
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def environment(values, inherited):
    missing = blockers(values)
    if missing:
        raise ValueError("Incomplete beta configuration: " + ", ".join(missing))
    env = {**inherited, **{k: v for k, v in values.items() if v is not None}}
    env.pop("MIGRATION_DATABASE_URL", None)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["readiness", "refresh", "refresh-prices"])
    args = parser.parse_args()
    config = ROOT / ".env.beta"
    if not config.is_file():
        raise SystemExit("Create private .env.beta from .env.beta.example first.")
    try:
        env = environment(dotenv_values(config, interpolate=False), os.environ)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.cli", args.command],
            cwd=ROOT / "backend",
            env=env,
            timeout=1200,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit("Beta command exceeded 20 minutes; saved records are retained.") from None
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
