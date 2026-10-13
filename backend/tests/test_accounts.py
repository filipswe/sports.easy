from app.models import User
from conftest import account, mutate
from sqlalchemy import select


def test_csrf_auth_and_admin(client):
    assert client.get("/api/admin/status").status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "a@example.com", "password": "long-test-password"}
        ).status_code
        == 403
    )
    account(client)
    assert client.get("/api/admin/status").status_code == 403
    csrf = client.get("/api/auth/csrf").json()["csrf"]
    assert (
        client.post(
            "/api/auth/logout", headers={"origin": "https://evil.invalid", "x-csrf-token": csrf}
        ).status_code
        == 403
    )


def test_save_exact_version_ownership_and_logout(client, db):
    account(client)
    selection = client.get("/api/predictions").json()["items"][0]
    response = mutate(client, "/api/saved", {"publication_id": selection["id"]})
    assert response.status_code == 201, response.text
    saved_id = response.json()["id"]
    assert (
        mutate(client, "/api/saved", {"publication_id": selection["id"]}).json()["id"] == saved_id
    )
    record = client.get("/api/saved").json()["items"][0]
    assert record["original"]["prediction_id"] == selection["prediction_id"]
    assert record["original"]["odds"] == selection["odds"]
    cookie = client.cookies.get("sports_session")
    assert mutate(client, "/api/auth/logout").status_code == 200
    assert client.get("/api/saved").status_code == 401
    client.cookies.set("sports_session", cookie)
    assert client.get("/api/saved").status_code == 401
    client.cookies.clear()
    account(client, "another@example.com")
    assert client.get("/api/saved").json()["items"] == []
    assert mutate(client, "/api/saved/" + saved_id, method="DELETE").status_code == 404


def test_verification_reset_single_use_and_account_deletion(client, db):
    credentials = {"email": "owner@example.com", "password": "unique-test-password-123"}
    registration = mutate(client, "/api/auth/register", credentials).json()
    assert mutate(client, "/api/auth/login", credentials).status_code == 401
    token = registration["demo_link"].split("verify=")[1]
    assert mutate(client, "/api/auth/verify", {"token": token}).status_code == 200
    assert mutate(client, "/api/auth/verify", {"token": token}).status_code == 400
    assert mutate(client, "/api/auth/login", credentials).status_code == 200
    reset = (
        mutate(client, "/api/auth/request-reset", {"email": credentials["email"]})
        .json()["demo_link"]
        .split("reset=")[1]
    )
    assert (
        mutate(
            client, "/api/auth/reset", {"token": reset, "password": "another-test-password-456"}
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me").status_code == 401
    assert (
        mutate(
            client, "/api/auth/reset", {"token": reset, "password": "another-test-password-456"}
        ).status_code
        == 400
    )
    credentials["password"] = "another-test-password-456"
    assert mutate(client, "/api/auth/login", credentials).status_code == 200
    assert (
        mutate(
            client, "/api/auth/account", {"password": credentials["password"]}, method="DELETE"
        ).status_code
        == 204
    )
    assert db.scalar(select(User).where(User.email == credentials["email"])) is None


def test_detail_performance_and_no_invented_context(client):
    selection = client.get("/api/predictions").json()["items"][0]
    detail = client.get("/api/fixtures/" + selection["fixture_id"]).json()
    assert detail["xg"] is None and detail["injuries"] is None
    assert detail["explanation"]["kind"] == "Deterministic statistical explanation"
    performance = client.get("/api/performance").json()
    assert performance["mode"] == "demo"
    assert performance["settled"] == 0 and performance["win_rate"] is None
    assert performance["hypothetical_return_units"] is None


def test_rate_limit_and_body_bound(client):
    for _ in range(20):
        assert mutate(client, "/api/auth/logout").status_code == 200
    assert mutate(client, "/api/auth/logout").status_code == 429
    assert client.post("/api/auth/login", content=b"x" * 33000).status_code == 413


def test_preferences_validation(client):
    account(client)
    assert (
        mutate(
            client, "/api/auth/preferences", {"timezone": "not/a/zone"}, method="PUT"
        ).status_code
        == 422
    )
    r = mutate(
        client,
        "/api/auth/preferences",
        {"timezone": "Europe/Belgrade", "odds_format": "american", "filters": "min_odds=2"},
        method="PUT",
    )
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["preferences"]["odds_format"] == "american"
