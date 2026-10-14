"""Configuration checks only; deployment and model validation remain operator work."""

from urllib.parse import urlsplit

from .config import settings


def release_blockers():
    origin = urlsplit(settings.public_origin)
    checks = {
        "live data mode": settings.app_data_mode == "live",
        "PostgreSQL persistence": settings.database_url.startswith("postgresql"),
        "HTTPS and secure cookies": origin.scheme == "https" and settings.cookie_secure,
        "private session secret": len(settings.session_secret) >= 32
        and not any(s in settings.session_secret for s in ("local-only", "replace-with")),
        "SMTP delivery": bool(settings.smtp_host) and not settings.smtp_from.endswith(".invalid"),
        "football credential": bool(
            settings.football_data_key
            if settings.football_provider == "football-data"
            else settings.api_football_key
        ),
        "odds credential": bool(settings.odds_api_key),
        "provider display and retention approval": settings.live_retention_approved,
        "operator and support contact": bool(settings.operator_name.strip())
        and "@" in settings.support_email
        and not settings.support_email.endswith(".invalid"),
        "eight-competition odds budget": settings.odds_daily_budget >= 16,
        "bounded price cache": 60 <= settings.odds_poll_seconds <= 259200,
    }
    return [name for name, passed in checks.items() if not passed]
