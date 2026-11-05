"""No endpoint, error message or log line may contain APP_PASSWORD, SECRET_KEY or ANTHROPIC_API_KEY.
Every GET route is called (logged in and logged out) on a populated database, plus failure paths.
"""
import logging
import re

import pytest

from app.core.config import settings
from app.core.redaction import redact
from app.engine import config as engine_config
from app.main import create_app
from app.services import suggestion_service
from tests.conftest import TEST_LOGIN
from tests.test_suggestion_runs import _profile, _run, market  # noqa: F401  (fixture)

FAKE_ANTHROPIC_KEY = "sk-ant-api03-TESTKEY-0123456789abcdef"


@pytest.fixture()
def secrets_set(monkeypatch):
    monkeypatch.setattr(engine_config, "ANTHROPIC_API_KEY", FAKE_ANTHROPIC_KEY)
    # Narration must not call the real API in tests: make the LLM path fail like a bad key would.
    from app.engine.agents import emerging_explainer
    monkeypatch.setattr(emerging_explainer, "call_llm_explain",
                        lambda c: logging.getLogger("test").error("LLM failed with key %s", FAKE_ANTHROPIC_KEY))
    values = [settings.APP_PASSWORD, settings.SECRET_KEY, FAKE_ANTHROPIC_KEY]
    assert all(len(v) >= 4 for v in values)
    return values


def _get_paths(ids: dict) -> list[str]:
    """Every GET route in the OpenAPI schema (all of /api/v1) plus the docs pages, path params filled from real rows.
    (FastAPI nests included routers, so app.routes is not a complete list; the schema is.)"""
    schema = create_app().openapi()
    paths = ["/openapi.json", "/docs", "/redoc"]
    for path, ops in schema["paths"].items():
        if "get" not in ops:
            continue
        for name in re.findall(r"\{(\w+)\}", path):
            path = path.replace("{" + name + "}", str(ids[name]))
        paths.append(path)
    assert len(paths) >= 20, paths
    return paths


def _assert_clean(text: str, secrets: list[str], where: str):
    for s in secrets:
        assert s not in text, f"secret leaked in {where}"


def test_no_secret_in_any_get_response_or_log(client, market, secrets_set, monkeypatch, caplog):  # noqa: F811
    caplog.set_level(logging.DEBUG)
    pid = _profile(client)
    run = _run(client, pid)
    sid = client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]["id"]
    client.get(f"/api/v1/suggestions/{sid}")  # triggers (failing) narration -> logs the key, which must be masked
    pos = client.post("/api/v1/positions", json={"profile_id": pid, "suggestion_id": sid}).json()["id"]

    # A run whose exception text contains every secret: the stored and served error must be masked.
    def boom(*a, **k):
        raise RuntimeError(f"boom {' '.join(secrets_set)}")
    monkeypatch.setattr(suggestion_service, "prefilter", boom)
    failed = _run(client, pid)
    assert failed["status"] == "failed" and "***" in failed["error"]

    ids = {"profile_id": pid, "run_id": failed["id"], "suggestion_id": sid, "position_id": pos, "symbol": "GOODCO"}
    paths = _get_paths(ids)
    for path in paths:
        r = client.get(path)
        assert r.status_code < 500, (path, r.status_code)
        _assert_clean(r.text + str(r.headers), secrets_set, f"GET {path}")
    client.cookies.clear()
    for path in paths:  # logged out: 401 bodies too
        _assert_clean(client.get(path).text, secrets_set, f"GET {path} (logged out)")
    for body in ({**TEST_LOGIN, "password": "wrong"}, {"username": 1}, TEST_LOGIN):
        _assert_clean(client.post("/api/v1/auth/login", json=body).text, secrets_set, "POST /auth/login")
    for _ in range(6):
        client.post("/api/v1/auth/login", json={**TEST_LOGIN, "password": "wrong"})
    _assert_clean(client.post("/api/v1/auth/login", json=TEST_LOGIN).text, secrets_set, "429 response")

    logging.getLogger("test").exception("traceback test", exc_info=RuntimeError(secrets_set[0]))
    assert "LLM failed with key ***" in caplog.text  # the masking really ran on a record carrying the key
    _assert_clean(caplog.text, secrets_set, "logs")
    _assert_clean(repr(settings), secrets_set, "repr(settings)")


def test_redact_helper(secrets_set):
    assert redact(f"a {secrets_set[2]} b") == "a *** b"
    assert redact(None) is None and redact("") == ""
    assert redact("nothing secret here") == "nothing secret here"
