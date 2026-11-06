"""Shared pytest setup: a throwaway SQLite file, scheduler off, fixed test login credentials.
Environment is set before any app module is imported, so the real data/trade_assistant.db and .env login are never used.
"""
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="trade_assistant_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP_DIR, 'test.db')}"
os.environ["ENABLE_SCHEDULER"] = "0"
os.environ["WARM_PANEL"] = "0"
# load_dotenv never overrides variables that are already set, so these win over backend/.env.
os.environ["APP_USERNAME"] = "tester"
os.environ["APP_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TEST_LOGIN = {"username": "tester", "password": "test-password"}


@pytest.fixture(autouse=True)
def no_network_fundamentals(tmp_path, monkeypatch):
    """No test may call yfinance or read/write the real fundamentals cache. Tests that need fundamentals
    install their own fake on top of this (see tests/test_suggestion_runs.py::market)."""
    from app.engine import config as engine_config
    from app.engine.data import fetcher

    monkeypatch.setattr(engine_config, "FUNDAMENTALS_CACHE_DIR", str(tmp_path / "fundamentals"))
    monkeypatch.setattr(fetcher, "fetch_fundamental_bundle",
                        lambda symbol, **kw: {"info": {}, "quarterly": [], "cashflow": [], "ok": False})
    # NIFTY benchmark: unavailable unless a test fakes it (tests/test_tracker.py does).
    from app.services import market_data

    monkeypatch.setattr(market_data, "_nifty_closes", lambda: None)
    monkeypatch.setattr(market_data, "nifty_closes_range", lambda start, end: None)
    # Index histories (yfinance) and the LLM: unavailable unless a test fakes them.
    from app.engine.data import index_history

    def no_index_download(ticker):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(index_history, "_download", no_index_download)
    index_history._cache.clear()
    monkeypatch.setattr(engine_config, "ANTHROPIC_API_KEY", "")


@pytest.fixture()
def clean_db():
    """Empty every table (children first) so a test starts from a fresh database."""
    from app.db.base import Base
    from app.db.session import engine, init_db

    init_db()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture(scope="session")
def session_cookie() -> str:
    """Log in once through the real endpoint; every logged-in test client reuses this cookie."""
    from app.main import create_app

    with TestClient(create_app()) as c:
        r = c.post("/api/v1/auth/login", json=TEST_LOGIN)
        assert r.status_code == 200, r.text
        return r.cookies["session"]


@pytest.fixture()
def anon_client(clean_db):
    """App client with no session cookie; startup seeds the default profile like a first real launch."""
    from app.main import create_app
    from app.services import auth_service

    auth_service.reset_rate_limit()  # the failed-login counter is in memory; start each test clean
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture()
def client(anon_client, session_cookie):
    """Logged-in app client on an empty DB."""
    anon_client.cookies.set("session", session_cookie)
    yield anon_client
