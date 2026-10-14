"""Configuration checks only; deployment and model validation remain operator work."""

from urllib.parse import urlsplit

from .config import settings


def release_blockers(configuration=None):
    config = configuration or settings
    try:
        origin = urlsplit(config.public_origin)
    except ValueError:
        origin = urlsplit("")
    checks = {
        "live data mode": config.app_data_mode == "live",
        "PostgreSQL persistence": config.database_url.startswith(("postgresql", "postgres://")),
        "HTTPS and secure cookies": origin.scheme == "https" and config.cookie_secure,
        "private session secret": len(config.session_secret) >= 32
        and not any(s in config.session_secret for s in ("local-only", "replace-with")),
        "SMTP delivery": bool(config.smtp_host)
        and "@" in config.smtp_from
        and not config.smtp_from.endswith(".invalid"),
        "SMTP TLS": config.smtp_starttls,
        "football credential": bool(
            config.football_data_key
            if config.football_provider == "football-data"
            else config.api_football_key
        ),
        "odds credential": bool(config.odds_api_key),
        "provider display and retention approval": config.live_retention_approved,
        "operator and support contact": bool(config.operator_name.strip())
        and "@" in config.support_email
        and not config.support_email.endswith(".invalid"),
        "eight-competition odds budget": config.odds_daily_budget >= 16,
        "bounded price cache": 60 <= config.odds_poll_seconds <= 259200,
    }
    return [name for name, passed in checks.items() if not passed]
