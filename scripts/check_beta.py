"""Report missing beta settings by name, without connecting or printing secrets."""

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from dotenv import dotenv_values
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings  # noqa: E402
from app.readiness import release_blockers  # noqa: E402


def blockers(values):
    fields = {
        name: values[name.upper()] for name in Settings.model_fields if name.upper() in values
    }
    try:
        config = Settings(_env_file=None, _env_prefix="BETA_CHECK_UNUSED_", **fields)
    except ValidationError as exc:
        return ["invalid setting: " + str(error["loc"][0]).upper() for error in exc.errors()]
    missing = release_blockers(config)
    if config.app_env != "production":
        missing.append("APP_ENV=production")
    try:
        origin = urlsplit(config.public_origin)
    except ValueError:
        origin = urlsplit("")
    if (
        not origin.hostname
        or config.public_origin != f"https://{origin.netloc}"
        or origin.username
        or origin.password
        or origin.hostname in {"localhost", "0.0.0.0", "::1"}
        or origin.hostname.startswith("127.")
        or origin.hostname.endswith((".invalid", ".local"))
    ):
        missing.append("canonical public HTTPS origin")
    try:
        database = urlsplit(config.database_url)
    except ValueError:
        database = urlsplit("")
    if parse_qs(database.query).get("sslmode", [""])[0] not in {
        "require",
        "verify-ca",
        "verify-full",
    }:
        missing.append("PostgreSQL TLS (sslmode)")
    if not config.smtp_from or "@" not in config.smtp_from:
        missing.append("verified SMTP_FROM address")
    if not config.smtp_user or not config.smtp_password:
        missing.append("SMTP authentication")
    return missing


if __name__ == "__main__":
    file = ROOT / ".env.beta"
    if not file.is_file():
        raise SystemExit("Create ignored .env.beta from .env.beta.example first.")
    missing = blockers(dotenv_values(file, interpolate=False))
    print(json.dumps({"configuration_blockers": missing, "connected_to_services": False}, indent=2))
    raise SystemExit(1 if missing else 0)
