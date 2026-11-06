"""Whole-market condition: Nifty 50 vs its 50-day EMA on a day (a hard filter; only bars up to the day, so no
look-ahead), and the market brief's regime rules (risk_on / neutral / risk_off). Pure.
"""
import pandas as pd
import ta

EMA_WINDOW = 50


def nifty_vs_ema50_pct(closes: pd.Series | None, day) -> float | None:
    """(close / EMA50 - 1) x 100 on the last Nifty session on or before `day`; None with fewer than 50 sessions."""
    if closes is None or closes.empty:
        return None
    upto = closes.loc[closes.index <= pd.Timestamp(day)].astype(float)
    if len(upto) < EMA_WINDOW:
        return None
    ema = float(ta.trend.EMAIndicator(upto, window=EMA_WINDOW).ema_indicator().iloc[-1])
    if not ema or ema != ema:
        return None
    return round((float(upto.iloc[-1]) / ema - 1) * 100, 4)


# --- the market brief's regime (docs/API_CONTRACT.md -> Market brief) -----------------------------------------------

VIX_CALM = 15.0
VIX_STRESS = 20.0
FII_HEAVY_SELL_CR = 2000.0
FII_SELL_SESSIONS = 3


def regime(nifty_vs_ema50_pct: float | None, vix: float | None, advance_decline: float | None,
           fii_net_last_sessions: list[float] | None) -> tuple[str, list[str], list[str]]:
    """(regime, reasons, unknown inputs); for neutral the reasons are the risk-on conditions that failed. risk_off if Nifty is below its 50-day EMA, or VIX is over 20, or FIIs net
    sold over ₹2,000 cr in each of the last 3 sessions; risk_on if Nifty is above its EMA50, VIX is under 15 and
    advance/decline is over 1; else neutral. An input that is unavailable never triggers a rule: it cannot make the
    market risk_off, and risk_on needs all three of its inputs. `fii_net_last_sessions` must hold exactly the last
    3 sessions (newest first) or be None when any of them is missing."""
    unknown = [name for name, v in (("nifty_vs_ema50_pct", nifty_vs_ema50_pct), ("vix", vix),
                                    ("advance_decline", advance_decline)) if v is None]
    fii_known = fii_net_last_sessions is not None and len(fii_net_last_sessions) == FII_SELL_SESSIONS
    if not fii_known:
        unknown.append("fii_net_3_sessions")
    off = []
    if nifty_vs_ema50_pct is not None and nifty_vs_ema50_pct < 0:
        off.append("nifty_below_ema50")
    if vix is not None and vix > VIX_STRESS:
        off.append("vix_over_20")
    if fii_known and all(v < -FII_HEAVY_SELL_CR for v in fii_net_last_sessions):
        off.append("fii_heavy_selling")
    if off:
        return "risk_off", off, unknown
    missed = []
    if nifty_vs_ema50_pct is not None and not nifty_vs_ema50_pct > 0:
        missed.append("nifty_not_above_ema50")
    if vix is not None and not vix < VIX_CALM:
        missed.append("vix_not_under_15")
    if advance_decline is not None and not advance_decline > 1:
        missed.append("breadth_not_positive")
    if not missed and not {"nifty_vs_ema50_pct", "vix", "advance_decline"} & set(unknown):
        return "risk_on", ["nifty_above_ema50", "vix_under_15", "breadth_positive"], unknown
    return "neutral", missed, unknown
