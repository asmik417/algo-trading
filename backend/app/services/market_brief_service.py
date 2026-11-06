"""The market brief (docs/API_CONTRACT.md -> Market brief): market context for a day from the source tables, the
deterministic regime, facts and sector leaders/laggards, and a model paragraph + stance written from the facts only.
"""
import json
import math
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now_iso
from app.core.logging import get_logger
from app.engine import config as engine_config
from app.engine.agents import base_agent
from app.engine.agents.number_audit import unsupported_numbers
from app.engine.data import index_history
from app.engine.scoring import market_regime
from app.models import MarketBriefRow, MarketContextRow
from app.services import market_data
from app.services.errors import NotFound

log = get_logger(__name__)

# Sector indices that compete for leader / laggard (NSE names). NSE's end-of-day snapshot covers all of them; on a
# day without it, the ones Yahoo carries (index_history.TICKERS) are used.
SECTOR_INDICES = (
    "NIFTY AUTO", "NIFTY BANK", "NIFTY FINANCIAL SERVICES", "NIFTY FMCG", "NIFTY IT", "NIFTY MEDIA", "NIFTY METAL",
    "NIFTY PHARMA", "NIFTY PSU BANK", "NIFTY PRIVATE BANK", "NIFTY REALTY", "NIFTY HEALTHCARE INDEX",
    "NIFTY CONSUMER DURABLES", "NIFTY OIL & GAS", "NIFTY CHEMICALS", "NIFTY CEMENT", "NIFTY ENERGY",
    "NIFTY INFRASTRUCTURE", "NIFTY PSE", "NIFTY INDIA CONSUMPTION",
)
SIZE_INDICES = ("NIFTY MIDCAP 150", "NIFTY SMALLCAP 250", "NIFTY MIDCAP 50")
MOVERS = 3
NIFTY = "NIFTY 50"

CONTEXT_FIELDS = ("nifty_close", "nifty_vs_ema50_pct", "nifty_1w_pct", "vix", "advance_decline", "fii_net_cr",
                  "dii_net_cr", "sector_index", "sector_1w_pct", "sp500_1d_pct", "crude_1w_pct", "usdinr_1w_pct")
LABELS = {"nifty_close": "Nifty 50 close", "nifty_vs_ema50_pct": "Nifty 50 vs its 50-day EMA",
          "nifty_1w_pct": "Nifty 50 weekly change", "vix": "India VIX", "advance_decline": "advance/decline",
          "fii_net_cr": "FII flows", "dii_net_cr": "DII flows", "sp500_1d_pct": "S&P 500",
          "crude_1w_pct": "Brent crude", "usdinr_1w_pct": "USD/INR", "fii_net_3_sessions": "three sessions of FII flows",
          "sectors": "sector index moves"}
REASONS = {"nifty_below_ema50": "Nifty 50 is below its 50-day EMA", "vix_over_20": "India VIX is above 20",
           "fii_heavy_selling": "FIIs net sold more than ₹2,000 cr in each of the last 3 sessions",
           "nifty_above_ema50": "Nifty 50 is above its 50-day EMA", "vix_under_15": "India VIX is below 15",
           "breadth_positive": "more stocks rose than fell",
           "nifty_not_above_ema50": "Nifty 50 is not above its 50-day EMA",
           "vix_not_under_15": "India VIX is not below 15", "breadth_not_positive": "fewer stocks rose than fell"}
FALLBACK_STANCE = {"risk_on": "Risk-on: new buys are fine at the plan's entries, always with stops.",
                   "neutral": "Neutral: be selective, take only the strongest setups and keep stops.",
                   "risk_off": "Risk-off: do not add new positions; hold winners with stops."}


# --- formatting (every figure in a fact is written exactly once, so the audit can match it) --------------------------

def _clean(x) -> float | None:
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else x


def _g(x: float, digits: int = 2) -> str:
    """24868.2 -> '24,868.2'; 1.0 -> '1'."""
    text = f"{abs(x):,.{digits}f}".rstrip("0").rstrip(".")
    return text or "0"


def _move(pct: float) -> str:
    return f"up {_g(pct)}%" if pct > 0 else f"down {_g(pct)}%" if pct < 0 else "flat"


def _signed(pct: float) -> str:
    return f"+{_g(pct)}%" if pct > 0 else f"-{_g(pct)}%" if pct < 0 else "0%"


def _title(index: str) -> str:
    return " ".join(w if w in ("IT", "FMCG", "PSU", "PSE", "VIX", "USD/INR", "&") else w.title() for w in index.split())


# --- market context -----------------------------------------------------------------------------------------------------

def _stored(db: Session, day: str) -> dict[str, MarketContextRow]:
    return {r.metric: r for r in db.scalars(select(MarketContextRow).where(MarketContextRow.day == day))}


def index_moves(db: Session, day: str, stored: dict | None = None) -> dict[str, dict]:
    """{NSE index name: {close, pct_1d, pct_1w, pct_1m}} for `day`: NSE's end-of-day snapshot when it was pulled,
    else Yahoo's history for the indices it carries (only when Yahoo has a bar dated `day`)."""
    stored = _stored(db, day) if stored is None else stored
    out: dict[str, dict] = {}
    for metric, row in stored.items():
        if metric.startswith("index:") and metric.count(":") == 2:
            _, name, field = metric.split(":")
            out.setdefault(name, {})[field] = _clean(row.value)
    index_history.prefetch([n for n in index_history.TICKERS if n not in out])
    for name in index_history.TICKERS:
        if name in out:
            continue
        series = index_history.upto(index_history.closes(name), day)
        if series is None or series.index[-1].date().isoformat() != day:
            continue
        out[name] = {"close": round(float(series.iloc[-1]), 2), "pct_1d": index_history.change_pct(series, day, 1),
                     "pct_1w": index_history.change_pct(series, day, 5),
                     "pct_1m": index_history.change_pct(series, day, 21)}
    return out


def _global(stored: dict, name: str, field: str) -> float | None:
    row = stored.get(f"global:{name}")
    if row is None:
        return None
    return _clean(json.loads(row.data_json or "{}").get(field))


def context(db: Session, day: str) -> tuple[dict, dict]:
    """(MarketContext without the sector fields, extras the facts need). Every missing figure stays None."""
    stored = _stored(db, day)
    moves = index_moves(db, day, stored)
    nifty = moves.get(NIFTY, {})
    vix_row = stored.get("vix")
    vix = _clean(vix_row.value) if vix_row is not None else moves.get("INDIA VIX", {}).get("close")
    adv_dec = market_data.breadth(day)
    ratio = round(adv_dec[0] / adv_dec[1], 2) if adv_dec and adv_dec[1] else None
    value = lambda m: _clean(stored[m].value) if m in stored else None  # noqa: E731
    # Only when Nifty has a bar dated `day`: the EMA helper would otherwise answer for an earlier session.
    ema_gap = _round(market_data.nifty_vs_ema50_pct(day)) if nifty.get("close") is not None else None
    ctx = {
        "day": day, "nifty_close": nifty.get("close"), "nifty_vs_ema50_pct": ema_gap,
        "nifty_1w_pct": nifty.get("pct_1w"), "vix": vix, "advance_decline": ratio,
        "fii_net_cr": value("fii_net_cr"), "dii_net_cr": value("dii_net_cr"), "sector_index": None,
        "sector_1w_pct": None, "sp500_1d_pct": _global(stored, "sp500", "change_1d_pct"),
        "crude_1w_pct": _global(stored, "crude_brent", "change_1w_pct"),
        "usdinr_1w_pct": _global(stored, "usdinr", "change_1w_pct"),
    }
    extras = {"moves": moves, "breadth": adv_dec, "nifty_1d_pct": nifty.get("pct_1d"),
              "crude": _global(stored, "crude_brent", "value"), "usdinr": _global(stored, "usdinr", "value"),
              "us10y": _global(stored, "us10y", "value")}
    return ctx, extras


def _round(x: float | None, digits: int = 2) -> float | None:
    return round(x, digits) if x is not None else None


def fii_last_sessions(db: Session, day: str) -> list[float] | None:
    """FII net (₹ cr) for the last 3 sessions up to `day`, newest first; None unless all three were pulled."""
    nifty = index_history.upto(index_history.closes(NIFTY), day)
    if nifty is None or len(nifty) < market_regime.FII_SELL_SESSIONS:
        return None
    days = [d.date().isoformat() for d in nifty.index[-market_regime.FII_SELL_SESSIONS:]][::-1]
    if days[0] != day:
        return None
    rows = {r.day: r.value for r in db.scalars(select(MarketContextRow).where(
        MarketContextRow.metric == "fii_net_cr", MarketContextRow.day.in_(days)))}
    values = [rows.get(d) for d in days]
    return values if all(v is not None for v in values) else None


def leaders_laggards(moves: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    ranked = sorted(((n, m["pct_1w"]) for n, m in moves.items() if n in SECTOR_INDICES and m.get("pct_1w") is not None),
                    key=lambda x: (-x[1], x[0]))
    n = min(MOVERS, len(ranked) // 2) if len(ranked) < 2 * MOVERS else MOVERS
    leaders = [{"index": name, "change_1w_pct": pct} for name, pct in ranked[:n]]
    laggards = [{"index": name, "change_1w_pct": pct} for name, pct in reversed(ranked[len(ranked) - n:])] if n else []
    return leaders, laggards


def facts(ctx: dict, extras: dict, regime: str, reasons: list[str], unknown: list[str],
          leaders: list[dict], laggards: list[dict]) -> list[str]:
    """Deterministic sentences, each carrying its figures."""
    out = []
    if ctx["nifty_close"] is not None:
        parts = [f"Nifty 50 closed at {_g(ctx['nifty_close'])}"]
        if extras["nifty_1d_pct"] is not None:
            parts.append(f"{_move(extras['nifty_1d_pct'])} on the day")
        if ctx["nifty_1w_pct"] is not None:
            parts.append(f"{_move(ctx['nifty_1w_pct'])} over the week")
        out.append(", ".join(parts) + ".")
    if ctx["nifty_vs_ema50_pct"] is not None:
        side = "above" if ctx["nifty_vs_ema50_pct"] >= 0 else "below"
        out.append(f"Nifty 50 is {_g(ctx['nifty_vs_ema50_pct'])}% {side} its 50-day EMA.")
    if ctx["vix"] is not None:
        out.append(f"India VIX is at {_g(ctx['vix'])}.")
    if extras["breadth"] and ctx["advance_decline"] is not None:
        adv, dec = extras["breadth"]
        out.append(f"Breadth: {_g(adv)} stocks rose and {_g(dec)} fell (advance/decline {_g(ctx['advance_decline'])}).")
    flows = []
    for who, key in (("FIIs", "fii_net_cr"), ("DIIs", "dii_net_cr")):
        v = ctx[key]
        if v is not None:
            flows.append(f"{who} net {'bought' if v >= 0 else 'sold'} ₹{_g(v)} cr")
    if flows:
        out.append(" and ".join(flows) + " in the cash market.")
    size = [(n, extras["moves"][n]["pct_1w"]) for n in SIZE_INDICES
            if extras["moves"].get(n, {}).get("pct_1w") is not None]
    if size and ctx["nifty_1w_pct"] is not None:
        out.append("Over the week " + ", ".join(f"{_title(n)} was {_move(p)}" for n, p in size)
                   + f", against {_signed(ctx['nifty_1w_pct'])} for the Nifty 50.")
    if leaders:
        out.append("Strongest sectors this week: " + ", ".join(f"{_title(x['index'])} {_signed(x['change_1w_pct'])}"
                                                            for x in leaders) + ".")
    if laggards:
        out.append("Weakest sectors this week: " + ", ".join(f"{_title(x['index'])} {_signed(x['change_1w_pct'])}"
                                                          for x in laggards) + ".")
    world = []
    if ctx["sp500_1d_pct"] is not None:
        world.append(f"the S&P 500 was {_move(ctx['sp500_1d_pct'])} in its last session")
    if extras["crude"] is not None and ctx["crude_1w_pct"] is not None:
        world.append(f"Brent crude is at ${_g(extras['crude'])}, {_move(ctx['crude_1w_pct'])} over the week")
    if extras["usdinr"] is not None and ctx["usdinr_1w_pct"] is not None:
        world.append(f"USD/INR is at {_g(extras['usdinr'])}, {_move(ctx['usdinr_1w_pct'])} over the week")
    if extras["us10y"] is not None:
        world.append(f"the US 10-year yield is {_g(extras['us10y'])}%")
    if world:
        out.append("Globally, " + "; ".join(world) + ".")
    label = regime.replace("_", "-")
    if regime != "neutral":
        out.append(f"Regime: {label}, because " + " and ".join(REASONS[r] for r in reasons) + ".")
    elif reasons:
        out.append("Regime: neutral. No risk-off condition is met, and it is not risk-on because "
                   + " and ".join(REASONS[r] for r in reasons) + ".")
    else:
        out.append("Regime: neutral. No risk-off condition is met, and risk-on cannot be confirmed with the data "
                   "available.")
    if unknown:
        out.append("Not available for this day: " + ", ".join(LABELS.get(u, u) for u in unknown) + ".")
    return out


# --- the model's paragraph and stance ------------------------------------------------------------------------------

# No digits in the instructions: every number the model may write comes from the facts.
SYSTEM_PROMPT = """You write the evening market brief for a retail swing trader in India who holds positions for a few
weeks. You are given the day's facts, computed by code, and the regime they imply. Return two things:
"paragraph": three to five plain-English sentences on what the facts say together (trend, breadth, flows, sectors,
global cues) and what that means for swing trades; "stance": one short line of positioning that fits the regime, in
the style "Small caps weak; do not add, hold winners with stops".
Rules: use only the facts. Every number you write must be copied exactly as it appears in the facts. Do not compute
differences, sums, averages or new percentages, and do not add any fact, date, price or number of your own. If a
figure is listed as not available, do not guess it. No generic investment advice.
Respond with valid JSON only: {"paragraph": "...", "stance": "..."}"""


def _ask(fact_lines: list[str], regime: str, previous: dict | None = None, bad: list[str] | None = None) -> dict:
    user = "Facts:\n" + "\n".join(f"- {f}" for f in fact_lines) + f"\n\nRegime: {regime.replace('_', '-')}"
    if previous is not None:
        user += ("\n\nYour previous answer used numbers that are not in the facts: " + ", ".join(bad or [])
                 + f"\nPrevious answer: {json.dumps(previous, ensure_ascii=False)}\nRewrite it without those numbers.")
    return base_agent.call_llm(SYSTEM_PROMPT, user)


def _text(reply: dict) -> tuple[str, str] | None:
    p, s = reply.get("paragraph"), reply.get("stance")
    if "error" in reply or not isinstance(p, str) or not isinstance(s, str) or not p.strip() or not s.strip():
        return None
    return p.strip(), s.strip()


def write_text(fact_lines: list[str], regime: str) -> dict:
    """{paragraph, stance, audited, notes, model}. The model writes from the facts; a reply with a number not in
    the facts is re-asked once with those numbers listed; after a second failure (or no model) the text is
    deterministic: the facts themselves and a stance fixed per regime."""
    notes: list[str] = []
    reply = _ask(fact_lines, regime)
    text = _text(reply)
    if text is None:
        notes.append(f"model unavailable: {reply.get('error', 'empty reply')}")
    else:
        bad = unsupported_numbers(list(text), fact_lines)
        if bad:
            notes.append("first answer used numbers not in the facts: " + ", ".join(bad))
            reply = _ask(fact_lines, regime, {"paragraph": text[0], "stance": text[1]}, bad)
            text = _text(reply)
            bad = unsupported_numbers(list(text), fact_lines) if text else []
            if text is None:
                notes.append(f"model unavailable on retry: {reply.get('error', 'empty reply')}")
            elif bad:
                notes.append("second answer still used numbers not in the facts: " + ", ".join(bad))
                text = None
        if text is not None:
            return {"paragraph": text[0], "stance": text[1], "audited": True, "notes": notes,
                    "model": engine_config.NARRATION_MODEL}
    body = [f for f in fact_lines if not f.startswith(("Regime:", "Not available"))]
    return {"paragraph": " ".join(body[:5]) or "No market data was available for this day.",
            "stance": FALLBACK_STANCE[regime], "audited": False, "notes": notes, "model": None}


# --- build and read -------------------------------------------------------------------------------------------------

def compute(db: Session, day: str) -> dict:
    """Everything deterministic in the brief: context, regime, leaders, laggards and facts."""
    ctx, extras = context(db, day)
    regime, reasons, unknown = market_regime.regime(ctx["nifty_vs_ema50_pct"], ctx["vix"], ctx["advance_decline"],
                                                    fii_last_sessions(db, day))
    for key in ("nifty_close", "nifty_1w_pct", "fii_net_cr", "dii_net_cr", "sp500_1d_pct", "crude_1w_pct",
                "usdinr_1w_pct"):
        if ctx[key] is None:
            unknown.append(key)
    leaders, laggards = leaders_laggards(extras["moves"])
    if not leaders:
        unknown.append("sectors")
    return {"day": day, "regime": regime, "context": ctx, "leaders": leaders, "laggards": laggards,
            "facts": facts(ctx, extras, regime, reasons, unknown, leaders, laggards)}


def build(db: Session, day: str, use_llm: bool = True) -> dict:
    """Build (or keep) the brief for `day`. Idempotent: when the stored brief has the same facts, it is returned as
    is and the model is not called again."""
    core = compute(db, day)
    row = db.scalar(select(MarketBriefRow).where(MarketBriefRow.day == day))
    if row is not None:
        old = json.loads(row.brief_json)
        if old.get("facts") == core["facts"] and old.get("regime") == core["regime"] and (row.audited or not use_llm):
            return _brief_of(row)
    text = write_text(core["facts"], core["regime"]) if use_llm else {
        "paragraph": " ".join(f for f in core["facts"] if not f.startswith(("Regime:", "Not available")))[:2000],
        "stance": FALLBACK_STANCE[core["regime"]], "audited": False, "notes": ["model not used"], "model": None}
    brief = {**core, "paragraph": text["paragraph"], "stance": text["stance"], "created_at": utc_now_iso()}
    if row is None:
        row = MarketBriefRow(day=day)
        db.add(row)
    row.brief_json, row.audited, row.model = json.dumps(brief, ensure_ascii=False), text["audited"], text["model"]
    row.audit_notes_json, row.created_at = json.dumps(text["notes"]), brief["created_at"]
    db.commit()
    if text["notes"]:
        log.info("Market brief %s: %s", day, "; ".join(text["notes"]))
    return _brief_of(row)


DETERMINISTIC = "deterministic"   # MarketBrief.model when the text is the fallback, not a model's


def _brief_of(row: MarketBriefRow) -> dict:
    """The stored brief plus its audit fields (kept in their own columns, so older rows get them too)."""
    return {**json.loads(row.brief_json), "audited": bool(row.audited),
            "audit_notes": json.loads(row.audit_notes_json or "[]"), "model": row.model or DETERMINISTIC}


def get(db: Session, day: date | None = None) -> dict:
    q = select(MarketBriefRow)
    q = q.where(MarketBriefRow.day == day.isoformat()) if day else q.order_by(MarketBriefRow.day.desc())
    row = db.scalar(q.limit(1))
    if row is None:
        raise NotFound(f"No market brief for {day.isoformat()}." if day else "No market brief has been built yet.")
    return _brief_of(row)


def recent(db: Session, limit: int = 10) -> list[dict]:
    rows = db.scalars(select(MarketBriefRow).order_by(MarketBriefRow.day.desc()).limit(limit))
    return [_brief_of(r) for r in rows]


def is_audited(db: Session, day: str) -> bool:
    row = db.scalar(select(MarketBriefRow).where(MarketBriefRow.day == day))
    return bool(row and row.audited)
