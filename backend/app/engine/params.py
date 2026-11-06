"""Screening parameters a trader or CA sets in the Account page.

One ScreenParams object fully describes *how* the algo picks stocks for a
profile. PARAM_SPEC drives the settings UI, so adding a parameter means
adding it to DEFAULTS and PARAM_SPEC — the Account page, validation and
storage pick it up automatically.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

CAP_BUCKETS = ["Large Cap", "Mid Cap", "Small Cap", "Unknown"]
HORIZONS = ["Short (2-6 weeks)", "Medium (1-3 months)", "Long (3-6 months)"]

WEIGHT_KEYS = [
    "earnings_acceleration",
    "fundamental_quality",
    "early_price_position",
    "volume_accumulation",
    "technical_setup",
    "valuation",
]

DEFAULTS: dict = {
    # Universe
    "min_price": 20.0,
    "min_avg_turnover_lacs": 200.0,
    "allowed_caps": ["Large Cap", "Mid Cap", "Small Cap"],
    "shortlist_size": 250,
    # Fundamentals (0 = ignore for the "max" style limits)
    "max_pe": 50.0,
    "min_roe_pct": 15.0,
    "max_debt_to_equity": 100.0,
    "min_profit_growth_pct": 20.0,
    "require_positive_ocf": True,
    # Technicals
    "rsi_min": 45.0,
    "rsi_max": 70.0,
    "require_above_200ema": True,
    "max_3m_runup_pct": 50.0,
    "max_dist_from_52w_high_pct": 25.0,
    "min_volume_ratio": 1.2,
    "min_nifty_vs_ema50_pct": 0.0,   # market filter; 0 = off
    # Pillar weights (sum to 100)
    "w_earnings_acceleration": 25,
    "w_fundamental_quality": 20,
    "w_early_price_position": 10,
    "w_volume_accumulation": 15,
    "w_technical_setup": 20,
    "w_valuation": 10,
    # Output / plan
    "min_score": 65.0,
    "max_suggestions": 10,
    "horizon": "Medium (1-3 months)",
    "paper_capital": 10000.0,
    "target_rr": 2.0,
    "stop_atr_mult": 2.0,
}

# Sections -> fields. "type" is one of: number, int, bool, select, multiselect.
PARAM_SPEC: list[dict] = [
    {
        "section": "Universe",
        "help": "Which stocks are even considered before any scoring.",
        "fields": [
            {"key": "min_price", "label": "Minimum share price (₹)", "type": "number", "min": 1.0, "max": 5000.0, "step": 1.0,
             "help": "Excludes penny stocks."},
            {"key": "min_avg_turnover_lacs", "label": "Minimum avg daily turnover (₹ lakh)", "type": "number", "min": 0.0, "max": 100000.0, "step": 10.0,
             "help": "20-day average traded value. Keeps out illiquid names you could not exit."},
            {"key": "allowed_caps", "label": "Market cap buckets", "type": "multiselect", "options": CAP_BUCKETS,
             "help": "Large ≥ ₹20,000 Cr, Mid ≥ ₹5,000 Cr, Small below that. 'Unknown' keeps stocks whose cap could not be fetched."},
            {"key": "shortlist_size", "label": "Stocks fully scored per run", "type": "int", "min": 20, "max": 600, "step": 10,
             "help": "The whole NSE is screened cheaply first; only this many top chart setups get fundamentals pulled. Higher = slower run."},
        ],
    },
    {
        "section": "Fundamentals",
        "help": "Hard filters applied after scoring. Set a 'max' to 0 to ignore it.",
        "fields": [
            {"key": "max_pe", "label": "Maximum trailing P/E (0 = ignore)", "type": "number", "min": 0.0, "max": 500.0, "step": 5.0},
            {"key": "min_roe_pct", "label": "Minimum ROE (%)", "type": "number", "min": -50.0, "max": 100.0, "step": 1.0},
            {"key": "max_debt_to_equity", "label": "Maximum debt / equity (%) (0 = ignore)", "type": "number", "min": 0.0, "max": 1000.0, "step": 10.0},
            {"key": "min_profit_growth_pct", "label": "Minimum profit growth YoY (%)", "type": "number", "min": -100.0, "max": 500.0, "step": 5.0},
            {"key": "require_positive_ocf", "label": "Require positive operating cash flow", "type": "bool"},
        ],
    },
    {
        "section": "Technicals",
        "help": "Chart conditions a stock must satisfy on the suggestion day.",
        "fields": [
            {"key": "rsi_min", "label": "RSI minimum", "type": "number", "min": 0.0, "max": 100.0, "step": 1.0},
            {"key": "rsi_max", "label": "RSI maximum", "type": "number", "min": 0.0, "max": 100.0, "step": 1.0},
            {"key": "require_above_200ema", "label": "Price must be above 200-day EMA", "type": "bool"},
            {"key": "max_3m_runup_pct", "label": "Maximum 3-month run-up (%)", "type": "number", "min": 0.0, "max": 500.0, "step": 5.0,
             "help": "Skip stocks that already rallied more than this — the aim is to find setups early."},
            {"key": "min_nifty_vs_ema50_pct", "label": "Market filter: max Nifty 50 fall below its 50-day EMA (%)",
             "type": "number", "min": 0.0, "max": 20.0, "step": 0.5,
             "help": "No new picks on a day Nifty 50 closes more than this % below its 50-day EMA; 0 = off"},
            {"key": "max_dist_from_52w_high_pct", "label": "Maximum distance below 52-week high (%)", "type": "number",
             "min": 0.0, "max": 100.0, "step": 5.0,
             "help": "Stock must be within this % below its 52-week high; 0 = ignore"},
            {"key": "min_volume_ratio", "label": "Minimum volume vs 20-day average (x)", "type": "number", "min": 0.0, "max": 10.0, "step": 0.1},
        ],
    },
    {
        "section": "Scoring weights",
        "help": "How much each pillar counts in the 0-100 score. Must add up to 100.",
        "fields": [
            {"key": "w_earnings_acceleration", "label": "Earnings acceleration", "type": "int", "min": 0, "max": 100, "step": 5},
            {"key": "w_fundamental_quality", "label": "Fundamental quality", "type": "int", "min": 0, "max": 100, "step": 5},
            {"key": "w_early_price_position", "label": "Early price position", "type": "int", "min": 0, "max": 100, "step": 5},
            {"key": "w_volume_accumulation", "label": "Volume / accumulation", "type": "int", "min": 0, "max": 100, "step": 5},
            {"key": "w_technical_setup", "label": "Technical setup", "type": "int", "min": 0, "max": 100, "step": 5},
            {"key": "w_valuation", "label": "Valuation", "type": "int", "min": 0, "max": 100, "step": 5},
        ],
    },
    {
        "section": "Suggestions & trade plan",
        "help": "What makes the final list, and how entry, stop, target and holding time are planned.",
        "fields": [
            {"key": "min_score", "label": "Minimum score to suggest", "type": "number", "min": 0.0, "max": 100.0, "step": 5.0},
            {"key": "max_suggestions", "label": "Maximum stocks suggested", "type": "int", "min": 1, "max": 100, "step": 1},
            {"key": "horizon", "label": "Preferred holding horizon", "type": "select", "options": HORIZONS},
            {"key": "paper_capital", "label": "Paper money per tracked stock (₹)", "type": "number", "min": 1000.0, "max": 10000000.0, "step": 1000.0},
            {"key": "target_rr", "label": "Target reward : risk", "type": "number", "min": 0.5, "max": 10.0, "step": 0.5,
             "help": "Target = entry + this × (entry − stop)."},
            {"key": "stop_atr_mult", "label": "Stop-loss distance (× ATR)", "type": "number", "min": 0.5, "max": 6.0, "step": 0.5,
             "help": "ATR = average true range, a volatility measure. 2× ATR is a common swing-trade stop."},
        ],
    },
]


@dataclass
class ScreenParams:
    values: dict = field(default_factory=lambda: dict(DEFAULTS))

    # --- access -----------------------------------------------------------
    def __getattr__(self, name):
        values = self.__dict__.get("values", {})
        if name in values:
            return values[name]
        if name in DEFAULTS:
            return DEFAULTS[name]
        raise AttributeError(name)

    def get(self, key, default=None):
        return self.values.get(key, DEFAULTS.get(key, default))

    @property
    def weights(self) -> dict:
        return {k: float(self.get(f"w_{k}")) for k in WEIGHT_KEYS}

    # --- (de)serialisation ----------------------------------------------
    @classmethod
    def from_dict(cls, d: dict | None) -> "ScreenParams":
        merged = dict(DEFAULTS)
        merged.update({k: _coerce(k, v) for k, v in (d or {}).items() if k in DEFAULTS})
        return cls(values=merged)

    @classmethod
    def from_json(cls, s: str | None) -> "ScreenParams":
        try:
            return cls.from_dict(json.loads(s) if s else {})
        except (TypeError, ValueError):
            return cls.from_dict({})

    def to_dict(self) -> dict:
        return dict(self.values)

    def to_json(self) -> str:
        return json.dumps(self.values)

    # --- validation ------------------------------------------------------
    def validate(self) -> list[str]:
        """Return a list of human-readable problems; empty list means valid."""
        problems = _spec_problems(self.values)
        if problems:
            return problems  # wrong types would make the cross-field checks below meaningless
        total = sum(self.weights.values())
        if round(total) != 100:
            problems.append(f"Scoring weights add up to {total:.0f}, they must add up to 100.")
        if self.rsi_min >= self.rsi_max:
            problems.append("RSI minimum must be below RSI maximum.")
        if not self.allowed_caps:
            problems.append("Pick at least one market-cap bucket.")
        if self.horizon not in HORIZONS:
            problems.append("Unknown holding horizon.")
        if self.paper_capital <= 0:
            problems.append("Paper capital must be positive.")
        return problems

    def summary(self) -> str:
        pe = f"P/E ≤ {self.max_pe:.0f}" if self.max_pe > 0 else "any P/E"
        return (f"score ≥ {self.min_score:.0f}, top {self.max_suggestions}, {self.horizon}, "
                f"{pe}, ROE ≥ {self.min_roe_pct:.0f}%, RSI {self.rsi_min:.0f}-{self.rsi_max:.0f}")


# --- per-field type / range rules, driven by PARAM_SPEC ---------------------
FIELDS: dict[str, dict] = {f["key"]: f for s in PARAM_SPEC for f in s["fields"]}


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _coerce(key: str, value):
    """Normalise safe numeric forms (25.0 for an int field, 5 for a number field);
    anything else is kept as given so validate() can report it."""
    ftype = FIELDS.get(key, {}).get("type")
    if ftype == "number" and _is_number(value):
        return float(value)
    if ftype == "int" and _is_number(value) and float(value).is_integer():
        return int(value)
    return value


def _spec_problems(values: dict) -> list[str]:
    problems = []
    for key, spec in FIELDS.items():
        v, label, ftype = values.get(key), spec["label"], spec["type"]
        if ftype in ("number", "int"):
            if not _is_number(v) or (ftype == "int" and not float(v).is_integer()):
                problems.append(f"{label}: must be {'a whole number' if ftype == 'int' else 'a number'}.")
                continue
            if "min" in spec and v < spec["min"]:
                problems.append(f"{label}: {v:g} is below the minimum {spec['min']:g}.")
            if "max" in spec and v > spec["max"]:
                problems.append(f"{label}: {v:g} is above the maximum {spec['max']:g}.")
        elif ftype == "bool" and not isinstance(v, bool):
            problems.append(f"{label}: must be true or false.")
        elif ftype == "select" and v not in spec["options"]:
            problems.append(f"{label}: must be one of {', '.join(spec['options'])}.")
        elif ftype == "multiselect":
            if not isinstance(v, list) or any(x not in spec["options"] for x in v):
                problems.append(f"{label}: each choice must be one of {', '.join(spec['options'])}.")
    return problems
