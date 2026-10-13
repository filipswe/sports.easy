from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    app_env: Literal["development", "production"] = "development"
    app_data_mode: Literal["demo", "live"] = "demo"
    database_url: str = "sqlite:///./sports.db"
    public_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_secret: str = "local-only-change-before-deployment-32chars"
    api_football_key: str = ""
    odds_api_key: str = ""
    league_id: int = 39
    league_name: str = "Premier League"
    season: int = 2026
    odds_bookmaker_key: str = "pinnacle"
    odds_sport: str = "soccer_epl"
    odds_region: Literal["uk", "eu", "us", "au"] = "uk"
    provider_daily_budget: int = 80
    odds_daily_budget: int = 12
    live_retention_approved: bool = False
    poll_seconds: int = 14400
    quote_max_age_seconds: int = 600
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "research@example.invalid"
    smtp_starttls: bool = True
    regional_notice: str = "Adults 18+ only. Check the rules where you live."


settings = Settings()
