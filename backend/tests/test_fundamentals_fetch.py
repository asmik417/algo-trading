"""Fundamentals fetching under Yahoo rate limits: retries with backoff, rate-limit detection, no trust in the empty
tables yfinance returns when limited, never caching a bundle without info, the backtest's no-fundamentals count,
and the repair script. A fake yf.Ticker; no network, no real sleeping.
"""
import os
import pickle

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from app.engine import config as engine_config
from app.engine.data import fetcher
from app.engine.data.fetcher import fetch_fundamental_bundle as real_fetch  # captured before conftest stubs it
from app.services import suggestion_service

INFO = {"trailingPE": 20.0, "marketCap": 1e11, "sector": "Tech"}


class FakeTicker:
    """Plays a script of info results per call: dict -> returned, Exception -> raised."""
    script: list = []
    calls: list = []

    def __init__(self, sym):
        self.sym = sym

    @property
    def info(self):
        FakeTicker.calls.append("info")
        step = FakeTicker.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    @property
    def quarterly_financials(self):
        FakeTicker.calls.append("quarterly")
        return pd.DataFrame({pd.Timestamp("2026-06-30"): {"Total Revenue": 100.0, "Net Income": 10.0, "Diluted EPS": 1.0}})

    @property
    def cashflow(self):
        FakeTicker.calls.append("cashflow")
        return pd.DataFrame()


@pytest.fixture()
def yahoo(monkeypatch):
    sleeps: list[float] = []
    FakeTicker.script, FakeTicker.calls = [], []
    monkeypatch.setattr(fetcher.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(fetcher, "_sleep", sleeps.append)
    monkeypatch.setattr(fetcher, "_cooldown_until", 0.0)
    return sleeps


def limited():
    return YFRateLimitError()


# --- 2. retries, backoff, rate-limit detection ----------------------------------------------------------

def test_rate_limit_is_retried_with_backoff_then_succeeds(yahoo):
    FakeTicker.script = [limited(), limited(), dict(INFO)]
    b = real_fetch("ABC")
    assert b["ok"] is True and b["rate_limited"] is False and b["info"] == INFO and len(b["quarterly"]) == 1
    assert FakeTicker.calls.count("info") == 3
    backoffs = [s for s in yahoo if s in (2.0, 4.0, 8.0)]
    assert backoffs == [2.0, 4.0]                                      # exponential
    assert any(s > 20 for s in yahoo)                                  # and the shared cooldown was honoured
    assert fetcher._cooldown_until > 0


def test_gives_up_after_three_retries(yahoo):
    FakeTicker.script = [limited()] * 4
    b = real_fetch("ABC")
    assert (b["ok"], b["rate_limited"], b["info"], b["quarterly"]) == (False, True, {}, [])
    assert FakeTicker.calls == ["info"] * 4                            # 1 try + 3 retries
    assert "quarterly" not in FakeTicker.calls                         # never trusts the silently empty tables


def test_genuinely_empty_symbol_is_not_retried(yahoo):
    FakeTicker.script = [{}]
    b = real_fetch("NODATA")
    assert (b["ok"], b["rate_limited"]) == (False, False) and FakeTicker.calls == ["info"] and yahoo == []


def test_other_errors_are_retried_without_cooldown(yahoo):
    FakeTicker.script = [ConnectionError("reset by peer"), dict(INFO)]
    assert real_fetch("ABC")["ok"] is True and yahoo == [2.0] and fetcher._cooldown_until == 0.0


def test_rate_limit_detection():
    assert fetcher.is_rate_limit(YFRateLimitError())
    assert fetcher.is_rate_limit(RuntimeError("Too Many Requests. Rate limited. Try after a while."))
    assert fetcher.is_rate_limit(RuntimeError("HTTP Error 429"))
    assert not fetcher.is_rate_limit(ConnectionError("reset by peer"))


def test_limiter_spaces_requests(monkeypatch):
    sleeps = []
    monkeypatch.setattr(fetcher, "_sleep", sleeps.append)
    monkeypatch.setattr(fetcher, "_cooldown_until", 0.0)
    lim = fetcher.RateLimiter(min_interval=0.5)
    for _ in range(3):
        lim.wait()
    assert len(sleeps) == 2 and all(0.4 < s <= 1.0 for s in sleeps)   # 2nd and 3rd wait their turn


# --- 1. never cache a bundle without info ------------------------------------------------------------------

def _path(day, sym):
    return os.path.join(engine_config.FUNDAMENTALS_CACHE_DIR, day, f"{sym}.pkl")


def test_empty_bundles_are_never_cached_and_poisoned_files_heal(monkeypatch):
    answers = {"EMPTY": {"info": {}, "quarterly": [], "cashflow": [], "ok": False, "rate_limited": True},
               "GOOD": {"info": INFO, "quarterly": [], "cashflow": [], "ok": True, "rate_limited": False}}
    calls = []
    monkeypatch.setattr(fetcher, "fetch_fundamental_bundle", lambda sym, **kw: calls.append(sym) or answers[sym])

    assert suggestion_service.load_fundamentals("2026-11-05", "EMPTY")["info"] == {}
    assert not os.path.exists(_path("2026-11-05", "EMPTY"))           # not cached
    suggestion_service.load_fundamentals("2026-11-05", "GOOD")
    suggestion_service.load_fundamentals("2026-11-05", "GOOD")
    assert calls.count("GOOD") == 1 and os.path.exists(_path("2026-11-05", "GOOD"))  # cached and reused

    os.makedirs(os.path.dirname(_path("2026-11-05", "POISON")), exist_ok=True)
    with open(_path("2026-11-05", "POISON"), "wb") as f:              # written by the old code
        pickle.dump({"info": {}, "quarterly": [], "cashflow": [], "ok": True}, f)
    answers["POISON"] = answers["GOOD"]
    assert suggestion_service.load_fundamentals("2026-11-05", "POISON")["info"] == INFO
    assert calls.count("POISON") == 1
    with open(_path("2026-11-05", "POISON"), "rb") as f:
        assert pickle.load(f)["info"] == INFO                          # healed in place
    with pytest.raises(ValueError):
        suggestion_service.save_fundamentals("2026-11-05", "X", {"info": {}})


# --- 4. the backtest says how many shortlisted stocks had no fundamentals -------------------------------------

def test_backtest_caveat_counts_missing_fundamentals(clean_db, monkeypatch):
    from tests.test_backtest_service import BUNDLE, END, OPEN_PARAMS, _market
    from app.db.session import SessionLocal
    from app.engine.params import ScreenParams
    from app.models import Profile
    from app.services import backtest_service, market_data

    market = _market(n=420, end=END)
    empty = {"S01", "S04", "S07"}
    monkeypatch.setattr(market_data, "histories_for_range", lambda start, end, progress=None: market)
    monkeypatch.setattr(market_data, "panel_day", lambda: END)
    monkeypatch.setattr(market_data, "latest_close", lambda sym: float(market[sym]["Close"].iloc[-1]))
    monkeypatch.setattr(suggestion_service, "load_fundamentals", lambda day, sym, force=False, limiter=None:
                        {"info": {}, "quarterly": [], "cashflow": [], "ok": False} if sym in empty else BUNDLE)
    monkeypatch.setattr(backtest_service, "_spawn", backtest_service.execute)
    with SessionLocal() as db:
        p = Profile(name="BT", owner="T", params_json=ScreenParams.from_dict(OPEN_PARAMS).to_json())
        db.add(p)
        db.commit()
        bt_id = backtest_service.create(db, p.id, "2026-03-02", END).id
    with SessionLocal() as db:  # a fresh session: the one above still holds the object as it was queued
        bt = backtest_service.to_schema(backtest_service.get(db, bt_id))
    assert bt["status"] == "done"
    assert "3 of 12 shortlisted stocks had no fundamentals (Yahoo returned nothing for them, even after retries), " \
           "so they could not be scored." in bt["caveats"]


# --- 5. the repair script ---------------------------------------------------------------------------------------

def test_refetch_empty_fundamentals_script():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "refetch", Path(__file__).resolve().parents[1] / "scripts" / "refetch_empty_fundamentals.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    day = "2026-11-05"
    folder = os.path.join(engine_config.FUNDAMENTALS_CACHE_DIR, day)
    os.makedirs(folder, exist_ok=True)
    for sym, info in (("GOOD", INFO), ("BACK", {}), ("GONE", {}), ("LIMIT", {})):
        with open(os.path.join(folder, f"{sym}.pkl"), "wb") as f:
            pickle.dump({"info": info, "quarterly": [], "cashflow": [], "ok": True}, f)
    answers = {"BACK": {"info": INFO, "quarterly": [], "cashflow": [], "ok": True, "rate_limited": False},
               "GONE": {"info": {}, "quarterly": [], "cashflow": [], "ok": False, "rate_limited": False},
               "LIMIT": {"info": {}, "quarterly": [], "cashflow": [], "ok": False, "rate_limited": True}}
    counts = mod.refetch_day(day, fetch=lambda sym, **kw: answers[sym])
    assert counts == {"cached": 4, "empty": 3, "recovered": 1, "still_empty": 2, "rate_limited": 1}
    assert sorted(os.listdir(folder)) == ["BACK.pkl", "GOOD.pkl"]       # empties never stay cached
    assert mod.refetch_day("1999-01-01")["cached"] == 0


def test_yfinance_404_stub_counts_as_empty(yahoo):
    stub = {"trailingPegRatio": None}                       # what yfinance returns for "Quote not found"
    assert not fetcher.has_real_info(stub) and not fetcher.has_real_info({}) and fetcher.has_real_info(INFO)
    assert not suggestion_service.has_info({"info": stub})
    FakeTicker.script = [stub]
    b = real_fetch("GONE")
    assert (b["ok"], b["info"], b["rate_limited"]) == (False, {}, False) and FakeTicker.calls == ["info"]  # no retry
    with pytest.raises(ValueError):
        suggestion_service.save_fundamentals("2026-11-05", "GONE", {"info": stub})  # never cached
