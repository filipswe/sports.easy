"""Local live-data account verification must not expose tokens on public deployments."""

import pytest
from app.auth import issue_token
from app.config import settings
from app.db import Base
from app.models import AuthToken, User
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


@pytest.mark.parametrize(
    "origin,environment,allowed",
    [
        ("http://localhost:3000", "development", True),
        ("http://127.0.0.1:3000", "development", True),
        ("http://[::1]:3000", "development", True),
        ("https://sports.example.com", "development", False),
        ("http://localhost.example.com", "development", False),
        ("https://localhost:3000", "production", False),
    ],
)
def test_verification_links_only_appear_in_local_development(
    monkeypatch, origin, environment, allowed
):
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "app_env", environment)
    monkeypatch.setattr(settings, "public_origin", origin)
    monkeypatch.setattr(settings, "smtp_host", "")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="local-test@example.invalid", password_hash="unused")
        db.add(user)
        db.commit()
        if allowed:
            link = issue_token(db, user, "verify")
            assert link.startswith(origin + "/account?verify=")
            token = db.scalar(select(AuthToken))
            assert token.id != link.split("verify=")[1]
        else:
            with pytest.raises(HTTPException) as error:
                issue_token(db, user, "verify")
            assert error.value.status_code == 503
            assert db.scalar(select(AuthToken)) is None
    engine.dispose()
