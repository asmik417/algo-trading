"""Pillar B — Fundamental Quality (15 pts).

Business-quality checks independent of the latest quarter's growth number:
profitability, leverage, and cash generation. Rewards improving ROE/margins,
low/declining debt, and positive & improving cash flow; penalizes leverage
and deteriorating cash generation. Missing metrics are skipped, not zeroed.
"""
from app.engine.scoring.common import PillarResult, combine_components, scale

MAX_POINTS = 15


def score(info: dict | None, cashflow_trend: list[dict] | None = None) -> PillarResult:
    """info: yfinance .info snapshot.
    cashflow_trend: chronologically ascending list of {"period": str,
    "fcf": float|None, "ocf": float|None} (most recent year last)."""
    info = info or {}
    cashflow_trend = cashflow_trend or []
    positives, risks = [], []

    roe = info.get("returnOnEquity")
    op_margin = info.get("operatingMargins")
    net_margin = info.get("profitMargins")
    debt_to_equity = info.get("debtToEquity")

    comp_roe = None
    if roe is not None:
        comp_roe = scale(roe * 100, 5, 25) * 4
        if roe > 0.20:
            positives.append(f"Strong ROE of {roe*100:.1f}%.")

    comp_margin = None
    margin_signals = [m for m in (op_margin, net_margin) if m is not None]
    if margin_signals:
        avg_margin = sum(margin_signals) / len(margin_signals)
        comp_margin = scale(avg_margin * 100, 3, 25) * 4
        if avg_margin > 0.15:
            positives.append(f"Healthy margins (~{avg_margin*100:.1f}%).")

    comp_debt = None
    if debt_to_equity is not None:
        comp_debt = scale(debt_to_equity, 0, 150, reverse=True) * 3
        if debt_to_equity > 150:
            risks.append(f"Elevated debt/equity ({debt_to_equity:.0f}%).")
        elif debt_to_equity < 30:
            positives.append("Low leverage.")

    comp_cf = None
    if len(cashflow_trend) >= 1:
        latest_fcf = cashflow_trend[-1].get("fcf")
        latest_ocf = cashflow_trend[-1].get("ocf")
        prior_fcf = cashflow_trend[-2].get("fcf") if len(cashflow_trend) >= 2 else None

        if latest_ocf is not None:
            base = 1.0 if latest_ocf > 0 else 0.0
            if latest_fcf is not None and prior_fcf is not None and prior_fcf != 0:
                trend = 1.0 if latest_fcf >= prior_fcf else 0.4
            else:
                trend = 0.7 if base else 0.0
            comp_cf = (0.5 * base + 0.5 * trend) * 4
            if latest_ocf <= 0:
                risks.append("Operating cash flow is negative.")
            elif latest_fcf is not None and prior_fcf is not None and latest_fcf < prior_fcf:
                risks.append("Free cash flow declined year-over-year.")

    pillar_score, coverage = combine_components(
        [(comp_roe, 4), (comp_margin, 4), (comp_debt, 3), (comp_cf, 4)], MAX_POINTS
    )

    return PillarResult(
        score=pillar_score,
        max_points=MAX_POINTS,
        available=pillar_score is not None,
        details={
            "roe": roe,
            "operating_margin": op_margin,
            "net_margin": net_margin,
            "debt_to_equity": debt_to_equity,
            "latest_fcf": cashflow_trend[-1].get("fcf") if cashflow_trend else None,
            "latest_ocf": cashflow_trend[-1].get("ocf") if cashflow_trend else None,
            "data_coverage": coverage,
        },
        positives=positives,
        risks=risks,
    )
