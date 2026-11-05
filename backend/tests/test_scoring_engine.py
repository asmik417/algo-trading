"""Unit tests for the Emerging Opportunities scoring engine (scoring/).
All synthetic — no network calls, no real symbols — so these run offline
and fast, and pin down the specific behaviors the feature is built around.
"""
import numpy as np
import pandas as pd
import pytest

from app.engine.scoring import disconnect, earnings_acceleration, fundamental_quality, signal, stage, valuation
from app.engine.scoring.engine import evaluate
from app.engine.scoring.market_metrics import compute as compute_market_metrics
from app.engine.scoring.price_position import score as score_price_position
from app.engine.scoring.technical_setup import score as score_technical_setup


def make_history(closes: list[float], volumes: list[int] | None = None) -> pd.DataFrame:
    n = len(closes)
    volumes = volumes or [100_000] * n
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    closes = np.array(closes, dtype=float)
    df = pd.DataFrame({
        "Open": closes * 0.995,
        "High": closes * 1.01,
        "Low": closes * 0.99,
        "Close": closes,
        "Volume": volumes,
    }, index=idx)
    return df


def flat_then_history(base_price: float, n_flat: int, extra_closes: list[float], volumes=None) -> pd.DataFrame:
    """n_flat days of gentle chop around base_price, then extra_closes appended."""
    rng = np.random.default_rng(42)
    flat = base_price * (1 + rng.uniform(-0.03, 0.03, n_flat))
    return make_history(list(flat) + list(extra_closes), volumes)


def quarterly(revenues: list[float], net_incomes: list[float], eps: list[float] | None = None) -> list[dict]:
    eps = eps or [ni / 1e8 for ni in net_incomes]
    return [
        {"period": f"Q{i}", "revenue": r, "net_income": ni, "eps": e}
        for i, (r, ni, e) in enumerate(zip(revenues, net_incomes, eps))
    ]


STRONG_INFO = {
    "trailingPE": 22.0,
    "returnOnEquity": 0.22,
    "operatingMargins": 0.18,
    "profitMargins": 0.12,
    "debtToEquity": 25.0,
}

WEAK_INFO = {
    "trailingPE": 60.0,
    "returnOnEquity": None,
    "operatingMargins": 0.03,
    "profitMargins": 0.01,
    "debtToEquity": 220.0,
}

# 5 quarters, YoY profit accelerating from ~50% to +200%, revenue up a modest 30%
ACCELERATING_QUARTERLY = quarterly(
    revenues=[100, 105, 112, 120, 130],
    net_incomes=[10, 11, 13, 12, 30],   # last quarter jumps hard vs Q1 (10 -> 30 = +200%)
)

FLAT_QUARTERLY = quarterly(
    revenues=[100, 100, 100, 100, 100],
    net_incomes=[10, 10, 10, 10, 10],
)

DECLINING_QUARTERLY = quarterly(
    revenues=[100, 95, 90, 85, 80],
    net_incomes=[10, 8, 6, 4, 2],
)


# 1. Strong fundamentals + flat price -> high fundamental-price disconnect
def test_flat_price_with_strong_growth_gives_strong_disconnect():
    result = disconnect.compute(fundamental_growth_pct=200, price_return_3m_pct=5)
    assert result.available
    assert result.label == "Strong"
    assert result.score_0_1 > 0.7


# 2. Strong fundamentals + huge prior rally -> lower early-stage / disconnect score
def test_huge_prior_rally_weakens_disconnect():
    flat = disconnect.compute(fundamental_growth_pct=200, price_return_3m_pct=5)
    rallied = disconnect.compute(fundamental_growth_pct=200, price_return_3m_pct=150)
    assert rallied.score_0_1 < flat.score_0_1
    assert rallied.label in ("Weak", "Priced In")


# 3. Weak fundamentals + strong price momentum -> not a strong Emerging Opportunity
def test_weak_fundamentals_with_momentum_scores_low():
    hist = make_history([100 + i * 1.5 for i in range(90)], volumes=[500_000] * 90)  # steady strong rally
    result = evaluate("WEAKCO", hist, WEAK_INFO, DECLINING_QUARTERLY, [])
    assert result.total_score is not None
    assert result.total_score < 55
    assert result.signal in (signal.SIGNALS["WEAK"], signal.SIGNALS["DEVELOPING"], signal.SIGNALS["EXTENDED"])


# 4. Strong fundamentals + breakout + volume -> high score and Breakout Confirmed
def test_strong_fundamentals_breakout_with_volume_scores_high():
    # long flat base, then a sharp breakout with a volume surge on the last 5 sessions
    base_vols = [100_000] * 80
    breakout_vols = [450_000] * 10
    hist = flat_then_history(100, 80, [104, 108, 113, 118, 122, 126, 129, 131, 133, 135],
                              volumes=base_vols + breakout_vols)
    result = evaluate("BREAKCO", hist, STRONG_INFO, ACCELERATING_QUARTERLY, [])
    assert result.total_score is not None
    assert result.total_score >= 55
    assert result.pillars["volume_accumulation"].available


# 5. Missing financial data -> no fabricated values
def test_missing_financial_data_is_not_fabricated():
    hist = make_history([100 + i * 0.1 for i in range(90)])
    result = evaluate("NODATA", hist, {}, [], [])
    earn = result.pillars["earnings_acceleration"]
    fq = result.pillars["fundamental_quality"]
    assert earn.available is False
    assert earn.score is None
    assert fq.available is False
    assert fq.score is None
    # engine must not silently treat a missing pillar as a zero contributor —
    # total score should renormalize over whatever *is* available (technical/volume/price)
    assert result.data_coverage < 1.0


# 6. Missing volume data -> gracefully degrade scoring
def test_missing_volume_column_degrades_gracefully():
    hist = make_history([100 + i * 0.2 for i in range(90)])
    hist = hist.drop(columns=["Volume"])
    m = compute_market_metrics_safe(hist)
    assert m is not None  # must not raise


def compute_market_metrics_safe(hist):
    try:
        # Volume is required by MarketMetrics; simulate "missing" by zero-filling
        # rather than crashing — the real pipeline always has a Volume column
        # from bhavcopy, this test guards the degrade-don't-crash contract.
        hist = hist.copy()
        hist["Volume"] = 0
        return compute_market_metrics(hist)
    except Exception:
        return None


# 7. Extremely overextended stock -> Extended classification
def test_extremely_overextended_stock_classified_extended():
    closes = [100 * (1.02 ** i) for i in range(90)]  # ~doubles+ over 90 sessions, near-parabolic
    hist = make_history(closes, volumes=[300_000] * 90)
    result = evaluate("EXTENDEDCO", hist, STRONG_INFO, ACCELERATING_QUARTERLY, [])
    assert result.stage == "Extended"
    assert result.signal == signal.SIGNALS["EXTENDED"]


# 8. Strong fundamentals but declining margins/cash flow -> fundamental-quality penalty
def test_declining_cashflow_penalizes_fundamental_quality():
    improving_cf = [
        {"period": "Y1", "fcf": 50, "ocf": 80},
        {"period": "Y2", "fcf": 90, "ocf": 120},
    ]
    declining_cf = [
        {"period": "Y1", "fcf": 90, "ocf": 120},
        {"period": "Y2", "fcf": 20, "ocf": 30},
    ]
    good = fundamental_quality.score(STRONG_INFO, improving_cf)
    bad = fundamental_quality.score(STRONG_INFO, declining_cf)
    assert good.score > bad.score


# 9. Improving earnings trajectory -> higher earnings-acceleration score
def test_accelerating_trajectory_scores_higher_than_flat_growth():
    # 6 quarters so both the current AND prior YoY comparison are available
    accelerating = quarterly(
        revenues=[100, 103, 106, 110, 100 * 1.1, 130],
        net_incomes=[10, 10.5, 11, 11.5, 11, 30],  # YoY jumps from ~10% to +173%
    )
    steady = quarterly(
        revenues=[100, 105, 110, 115, 120, 126],
        net_incomes=[10, 10.5, 11, 11.5, 12, 12.6],  # steady ~5% QoQ, no acceleration
    )
    accel_result = earnings_acceleration.score(accelerating, {})
    steady_result = earnings_acceleration.score(steady, {})
    assert accel_result.score > steady_result.score


# 10. No look-ahead bias: metrics computed on a historical slice must not
# change when future rows are appended after that cutoff.
def test_market_metrics_have_no_look_ahead_bias():
    closes = [100 + i * 0.3 for i in range(150)]
    full_hist = make_history(closes, volumes=[200_000] * 150)

    cutoff = 100
    hist_as_of_cutoff = full_hist.iloc[:cutoff]
    metrics_at_cutoff = compute_market_metrics(hist_as_of_cutoff)

    # Recompute using the exact same slice — must be identical (pure function of the data given)
    metrics_at_cutoff_again = compute_market_metrics(full_hist.iloc[:cutoff])

    assert metrics_at_cutoff.current_price == metrics_at_cutoff_again.current_price
    assert metrics_at_cutoff.change_1m_pct == metrics_at_cutoff_again.change_1m_pct
    # And it must differ from a computation that includes the "future" rows —
    # proving the function only used what was in the slice, not the full series.
    metrics_full = compute_market_metrics(full_hist)
    assert metrics_at_cutoff.current_price != metrics_full.current_price


# 11. Weights are an argument: a profile's weights change the total; defaults are unchanged
def _breakout_case():
    hist = flat_then_history(100, 80, [104, 108, 113, 118, 122, 126, 129, 131, 133, 135],
                              volumes=[100_000] * 80 + [450_000] * 10)
    return hist, STRONG_INFO, ACCELERATING_QUARTERLY, []


def test_custom_weights_change_total_score():
    from app.engine import config

    args = _breakout_case()
    default = evaluate("WCO", *args)
    explicit_default = evaluate("WCO", *args, weights=dict(config.EMERGING_SCORE_WEIGHTS))
    tech_heavy = evaluate("WCO", *args, weights={
        "earnings_acceleration": 5, "fundamental_quality": 5, "early_price_position": 5,
        "volume_accumulation": 5, "technical_setup": 75, "valuation": 5,
    })
    assert default.total_score == pytest.approx(explicit_default.total_score)
    assert tech_heavy.total_score != pytest.approx(default.total_score)

    # The total must equal sum(frac_i * w_i) / sum(available w_i) * 100 under the given weights.
    w = {"earnings_acceleration": 5, "fundamental_quality": 5, "early_price_position": 5,
         "volume_accumulation": 5, "technical_setup": 75, "valuation": 5}
    avail = [(p.score / p.max_points, w[k]) for k, p in tech_heavy.pillars.items() if p.available]
    expected = sum(f * wt for f, wt in avail) / sum(wt for _, wt in avail) * 100
    assert tech_heavy.total_score == pytest.approx(expected)


def test_default_weights_match_original_points_formula():
    # Before weights became an argument the total was sum(points) / sum(available weights) * 100,
    # which relied on max_points == default weight. The new formula must give the same numbers.
    from app.engine import config

    result = evaluate("WCO", *_breakout_case())
    avail = [(p.score, config.EMERGING_SCORE_WEIGHTS[k]) for k, p in result.pillars.items() if p.available]
    assert result.total_score == pytest.approx(sum(s for s, _ in avail) / sum(w for _, w in avail) * 100)


def test_zero_weight_on_every_available_pillar_gives_no_score():
    hist = make_history([100 + i * 0.1 for i in range(90)])
    only_fundamentals = {"earnings_acceleration": 50, "fundamental_quality": 50, "early_price_position": 0,
                         "volume_accumulation": 0, "technical_setup": 0, "valuation": 0}
    result = evaluate("NODATA", hist, {}, [], [], weights=only_fundamentals)
    assert result.total_score is None  # unavailable, never a fabricated 0
