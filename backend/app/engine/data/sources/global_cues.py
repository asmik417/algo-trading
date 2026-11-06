"""Global cues for a day from yfinance: S&P 500, Brent crude, USD/INR and the US 10-year yield, each as the close
on or before `day` with its 1-day and 1-week change.
"""
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from app.engine.data.sources.common import SourceUnavailable, cached, safe

SOURCE = "global_cues"
TICKERS = {"sp500": "^GSPC", "crude_brent": "BZ=F", "usdinr": "INR=X", "us10y": "^TNX"}


def _history(ticker: str, day: date) -> pd.Series:
    hist = yf.Ticker(ticker).history(start=(day - timedelta(days=21)).isoformat(),
                                     end=(day + timedelta(days=1)).isoformat(), interval="1d", auto_adjust=False)
    closes = hist["Close"].dropna() if not hist.empty else pd.Series(dtype=float)
    closes.index = pd.to_datetime(closes.index).tz_localize(None).normalize()
    return closes.loc[closes.index <= pd.Timestamp(day)]


def cue(name: str, closes: pd.Series, day: date) -> dict | None:
    if closes.empty:
        return None
    last, at = float(closes.iloc[-1]), closes.index[-1]
    prev = float(closes.iloc[-2]) if len(closes) > 1 else None
    week = closes.loc[closes.index <= at - pd.Timedelta(days=7)]
    week_ago = float(week.iloc[-1]) if not week.empty else None
    pct = lambda a: round((last / a - 1) * 100, 2) if a else None  # noqa: E731
    return {"key": f"global:{name}", "date": day.isoformat(), "quote_date": at.date().isoformat(), "value": round(last, 4),
            "change_1d_pct": pct(prev), "change_1w_pct": pct(week_ago)}


def _fetch(day: date, history=_history) -> list[dict]:
    out, problems = [], []
    for name, ticker in TICKERS.items():
        try:
            row = cue(name, history(ticker, day), day)
            if row is None:
                problems.append(f"{name}: no data")
            else:
                out.append(row)
        except Exception as e:
            problems.append(f"{name}: {type(e).__name__}")
    if not out:
        raise SourceUnavailable("; ".join(problems) or "no global cues")
    return out + [{"key": "_warning", "date": day.isoformat(), "note": p} for p in problems]


def fetch(day: date, use_cache: bool = True) -> list[dict]:
    return cached(SOURCE, day, _fetch, use_cache)


def pull(day: date) -> list[dict]:
    return safe(fetch, SOURCE, day)
