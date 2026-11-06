"""The number audit for model-written text (market brief now, analyst view next): every number the model writes must
already be in the evidence it was given, within 1 % or as that figure rounded to the decimals written. Pure.
"""
import math
import re

TOLERANCE = 0.01   # ±1 % of the evidence figure

# 24,868.2 · 1,23,456 · 17.4 · 05 — a sign or ₹ before it and a % or "cr" after it do not change the number.
_NUMBER = re.compile(r"\d+(?:,\d+)*(?:\.\d+)?")


def numbers_in_text(text: str) -> list[tuple[str, float]]:
    """(as written, absolute value) for every number in the text. Dates split into parts: '2026-11-05' gives
    2026, 11 and 05, which is also how dates in the evidence are read."""
    out = []
    for raw in _NUMBER.findall(text or ""):
        try:
            out.append((raw, abs(float(raw.replace(",", "")))))
        except ValueError:
            continue
    return out


def evidence_numbers(evidence) -> list[float]:
    """Every number in the evidence (absolute values): numeric fields, and numbers written inside its strings."""
    found: list[float] = []

    def walk(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            if math.isfinite(x):
                found.append(abs(float(x)))
        elif isinstance(x, str):
            found.extend(v for _, v in numbers_in_text(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple, set)):
            for v in x:
                walk(v)

    walk(evidence)
    return found


def _decimals(raw: str) -> int:
    return len(raw.split(".", 1)[1]) if "." in raw else 0


def supported(raw: str, value: float, evidence: list[float]) -> bool:
    places = _decimals(raw)
    for e in evidence:
        if e == 0:
            if value == 0:
                return True
            continue
        if abs(value - e) <= TOLERANCE * e or round(e, places) == value:
            return True
    return False


def unsupported_numbers(texts: list[str], evidence, extra: tuple[float, ...] = ()) -> list[str]:
    """Numbers (as written, de-duplicated, in order) that appear in `texts` but not in the evidence.
    `extra` adds figures the caller fixed in the instructions (for example a 20-session horizon)."""
    pool = evidence_numbers(evidence) + [abs(float(x)) for x in extra]
    bad: list[str] = []
    for text in texts:
        for raw, value in numbers_in_text(text):
            if raw not in bad and not supported(raw, value, pool):
                bad.append(raw)
    return bad
