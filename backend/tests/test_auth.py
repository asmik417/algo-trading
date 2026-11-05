"""Single-user login: login sets a signed HttpOnly cookie, wrong credentials 401, every non-public route 401
without it, health stays public, logout clears it, tampered/expired cookies fail, owner defaults to the user.
"""
from app.core.config import settings
from app.services import auth_service
from tests.conftest import TEST_LOGIN

PROTECTED = [("GET", "/api/v1/profiles"), ("GET", "/api/v1/profiles/param-spec"), ("GET", "/api/v1/stocks"),
             ("GET", "/api/v1/runs/1"), ("GET", "/api/v1/suggestions/1"), ("GET", "/api/v1/positions/1"),
             ("GET", "/api/v1/reviews/tags"), ("GET", "/api/v1/jobs/status"), ("POST", "/api/v1/jobs/daily-update"),
             ("POST", "/api/v1/positions"), ("GET", "/api/v1/profiles/1/stats")]


def test_login_ok_sets_cookie(anon_client):
    r = anon_client.post("/api/v1/auth/login", json=TEST_LOGIN)
    assert r.status_code == 200 and r.json() == {"username": "tester"}
    header = r.headers["set-cookie"].lower()
    assert header.startswith("session=") and "httponly" in header and "samesite=lax" in header
    assert f"max-age={30 * 24 * 3600}" in header and "path=/" in header
    assert anon_client.get("/api/v1/auth/me").json() == {"username": "tester"}
    assert anon_client.get("/api/v1/profiles").status_code == 200


def test_login_wrong_password_401(anon_client):
    for body in ({**TEST_LOGIN, "password": "nope"}, {**TEST_LOGIN, "username": "someone"}, {"username": "", "password": ""}):
        r = anon_client.post("/api/v1/auth/login", json=body)
        assert r.status_code == 401 and "set-cookie" not in r.headers
    assert anon_client.post("/api/v1/auth/login", json={"username": "tester"}).status_code == 400  # missing field


def test_protected_routes_without_cookie_401(anon_client):
    for method, path in PROTECTED:
        r = anon_client.request(method, path, json={} if method == "POST" else None)
        assert (r.status_code, r.json()) == (401, {"detail": "Not authenticated"}), (method, path)
    assert anon_client.get("/api/v1/auth/me").status_code == 401
    assert anon_client.get("/api/v1/health").status_code == 200  # public


def test_protected_route_with_cookie_200(client):
    assert client.get("/api/v1/profiles").status_code == 200
    assert client.get("/api/v1/reviews/tags").status_code == 200
    assert client.get("/api/v1/jobs/status").status_code == 200


def test_logout_clears_cookie(anon_client):
    anon_client.post("/api/v1/auth/login", json=TEST_LOGIN)
    r = anon_client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    cleared = r.headers["set-cookie"].lower()
    assert cleared.startswith("session=") and "max-age=0" in cleared and "httponly" in cleared
    assert anon_client.get("/api/v1/profiles").status_code == 401


def test_bad_tampered_expired_or_foreign_cookies(anon_client, monkeypatch):
    good = auth_service.make_token("tester")
    for bad in ("garbage", good[:-2] + "xx", auth_service.make_token("intruder")):
        anon_client.cookies.set("session", bad)
        assert anon_client.get("/api/v1/profiles").status_code == 401
    anon_client.cookies.set("session", good)
    assert anon_client.get("/api/v1/profiles").status_code == 200
    monkeypatch.setattr(settings, "SESSION_MAX_AGE", -1)  # every token is now older than the limit
    assert anon_client.get("/api/v1/profiles").status_code == 401


def test_owner_defaults_to_logged_in_user(client):
    r = client.post("/api/v1/profiles", json={"name": "No owner given"})
    assert r.status_code == 201 and r.json()["owner"] == "tester"
    assert client.post("/api/v1/profiles", json={"name": "Blank owner", "owner": "  "}).json()["owner"] == "tester"
    assert client.post("/api/v1/profiles", json={"name": "Named", "owner": "MD"}).json()["owner"] == "MD"


def test_no_login_configured_rejects_everyone(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "APP_PASSWORD", "")
    assert anon_client.post("/api/v1/auth/login", json={"username": "tester", "password": ""}).status_code == 401


TOO_MANY = {"detail": "Too many attempts, try again later"}


def test_five_failures_block_the_ip_even_for_the_right_password(anon_client):
    wrong = {**TEST_LOGIN, "password": "nope"}
    for _ in range(5):
        assert anon_client.post("/api/v1/auth/login", json=wrong).status_code == 401
    r = anon_client.post("/api/v1/auth/login", json=TEST_LOGIN)  # correct, but blocked: no more guessing
    assert (r.status_code, r.json()) == (429, TOO_MANY) and "set-cookie" not in r.headers
    assert anon_client.post("/api/v1/auth/login", json=wrong).json() == TOO_MANY


def test_block_lifts_after_15_minutes_and_success_resets(anon_client, monkeypatch):
    from app.services import auth_service

    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(auth_service.time, "monotonic", lambda: clock["t"])
    wrong = {**TEST_LOGIN, "password": "nope"}
    for _ in range(4):
        anon_client.post("/api/v1/auth/login", json=wrong)
    assert anon_client.post("/api/v1/auth/login", json=TEST_LOGIN).status_code == 200  # 4 < 5, success resets
    for _ in range(4):
        anon_client.post("/api/v1/auth/login", json=wrong)
    assert anon_client.post("/api/v1/auth/login", json=wrong).status_code == 401      # 5th failure still answered
    assert anon_client.post("/api/v1/auth/login", json=TEST_LOGIN).status_code == 429
    clock["t"] += 15 * 60 - 1
    assert anon_client.post("/api/v1/auth/login", json=TEST_LOGIN).status_code == 429
    clock["t"] += 1  # oldest failures now 15 minutes old
    assert anon_client.post("/api/v1/auth/login", json=TEST_LOGIN).status_code == 200


def test_rate_limit_is_per_ip(anon_client):
    from app.services import auth_service

    for _ in range(5):
        auth_service.record_failure("10.0.0.9")
    assert auth_service.is_blocked("10.0.0.9")
    assert anon_client.post("/api/v1/auth/login", json=TEST_LOGIN).status_code == 200  # testclient is another IP
