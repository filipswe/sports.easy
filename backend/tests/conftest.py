import os

os.environ["APP_DATA_MODE"] = "demo"
os.environ["DATABASE_URL"] = "sqlite://"
import pytest
from app.config import settings
from app.db import Base, get_db
from app.ingestion import ingest
from app.main import app, requests_by_ip
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)()
    settings.app_data_mode = "demo"
    ingest(session)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db):
    def override():
        yield db

    app.dependency_overrides[get_db] = override
    requests_by_ip.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def mutate(client, path, body=None, method="POST"):
    csrf = client.get("/api/auth/csrf").json()["csrf"]
    return client.request(
        method, path, json=body, headers={"origin": settings.public_origin, "x-csrf-token": csrf}
    )


def account(client, email="research@example.com"):
    body = {"email": email, "password": "a-unique-test-password-123"}
    response = mutate(client, "/api/auth/register", body)
    assert response.status_code == 202, response.text
    token = response.json()["demo_link"].split("verify=")[1]
    assert mutate(client, "/api/auth/verify", {"token": token}).status_code == 200
    response = mutate(client, "/api/auth/login", body)
    assert response.status_code == 200, response.text
    return response.json()
