"""Pillar F — Valuation (15 pts).

Not "cheap stocks win." The real question is whether the market has already
priced in the expected improvement. A high-growth company can deserve a
higher P/E — so the dominant signal here is PE relative to actual profit
growth (PEG-style), with a light absolute-PE sanity check and a check for
whether the stock has already been re-rated over the last 6 months.
"""
from app.engine.scoring.common import PillarResult, combine_components, scale

MAX_POINTS = 15


def score(info: dict | None, profit_yoy_pct: float | None, change_6m_pct: float | None) -> PillarResult:
    info = info or {}
    pe = info.get("trailingPE")
    positives, risks = [], []

    comp_peg = None
    if pe is not None and pe > 0 and profit_yoy_pct is not None and profit_yoy_pct > 0:
        peg = pe / profit_yoy_pct
        comp_peg = scale(peg, 0.3, 3.0, reverse=True) * 8
        if peg < 1.0:
            positives.append(f"P/E of {pe:.1f} looks reasonable against {profit_yoy_pct:.0f}% profit growth (PEG ~{peg:.2f}).")
        elif peg > 2.5:
            risks.append(f"P/E of {pe:.1f} is rich relative to current profit growth (PEG ~{peg:.2f}).")

    comp_abs_pe = None
    if pe is not None and pe > 0:
        comp_abs_pe = scale(pe, 10, 80, reverse=True) * 4
        if pe > 80:
            risks.append(f"Very high absolute P/E ({pe:.0f}).")

    comp_rerating = None
    if change_6m_pct is not None:
        comp_rerating = scale(max(change_6m_pct, 0), 20, 150, reverse=True) * 3
        if change_6m_pct > 100:
            risks.append(f"Stock is up {change_6m_pct:.0f}% over 6 months — likely already re-rated by the market.")

    pillar_score, coverage = combine_components(
        [(comp_peg, 8), (comp_abs_pe, 4), (comp_rerating, 3)], MAX_POINTS
    )

    return PillarResult(
        score=pillar_score,
        max_points=MAX_POINTS,
        available=pillar_score is not None,
        details={
            "trailing_pe": pe,
            "price_to_book": info.get("priceToBook"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "peg_like_ratio": (pe / profit_yoy_pct) if (pe and profit_yoy_pct and profit_yoy_pct > 0) else None,
            "data_coverage": coverage,
        },
        positives=positives,
        risks=risks,
    )
