from decimal import Decimal

from app.core.paper_trading import PaperBroker, PaperOrder, PaperPortfolio, RiskConfig, build_run_hash, to_money


def test_build_run_hash_is_stable_and_sensitive_to_inputs():
    cfg = {"max_open_positions": 10, "max_daily_loss_pct": 0.05}
    first = build_run_hash("v1", "snapshot-a", cfg, "abc123", "seed-7")
    second = build_run_hash("v1", "snapshot-a", cfg, "abc123", "seed-7")
    third = build_run_hash("v1", "snapshot-b", cfg, "abc123", "seed-7")

    assert first == second
    assert first != third


def test_paper_broker_executes_valid_buy_order_and_tracks_cash():
    portfolio = PaperPortfolio(cash=to_money("100000"))
    broker = PaperBroker(
        portfolio=portfolio,
        risk_config=RiskConfig(starting_capital=to_money("100000"), max_open_positions=10),
        market_prices={"INFY": to_money("1500")},
    )

    order = PaperOrder(
        order_id="o-1",
        symbol="INFY",
        side="buy",
        quantity=10,
        limit_price=to_money("1500"),
        metadata={"manual_approval": True},
    )

    executed = broker.submit_order(order)

    assert executed.status == "filled"
    assert portfolio.position_qty("INFY") == 10
    assert portfolio.cash < Decimal("100000")
    assert len(portfolio.ledger) >= 1


def test_paper_broker_rejects_duplicate_order_id_and_overdrawn_buy():
    portfolio = PaperPortfolio(cash=to_money("100000"))
    broker = PaperBroker(
        portfolio=portfolio,
        risk_config=RiskConfig(starting_capital=to_money("100000"), max_open_positions=10),
        market_prices={"TCS": to_money("2000")},
    )

    first = PaperOrder(order_id="dup", symbol="TCS", side="buy", quantity=1, metadata={"manual_approval": True})
    second = PaperOrder(order_id="dup", symbol="TCS", side="buy", quantity=1, metadata={"manual_approval": True})

    first_result = broker.submit_order(first)
    retry_result = broker.submit_order(second)
    assert first_result.status == "filled"
    assert retry_result is first_result
    assert retry_result.rejection_reason is None
    assert portfolio.position_qty("TCS") == 1

    too_big = PaperOrder(order_id="too-big", symbol="TCS", side="buy", quantity=50, metadata={"manual_approval": True})
    assert broker.submit_order(too_big).status == "rejected"
    assert broker.submit_order(too_big).rejection_reason == "insufficient_cash"


def test_paper_broker_rejects_sell_that_would_create_short_position():
    portfolio = PaperPortfolio(cash=to_money("100000"), positions={"INFY": 3})
    broker = PaperBroker(
        portfolio=portfolio,
        risk_config=RiskConfig(starting_capital=to_money("100000"), max_open_positions=10),
        market_prices={"INFY": to_money("1500")},
        execution_mode="paper-auto",
    )
    initial_cash = portfolio.cash
    initial_ledger_size = len(portfolio.ledger)

    rejected = broker.submit_order(
        PaperOrder(order_id="sell-too-many", symbol="INFY", side="sell", quantity=4)
    )

    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "insufficient_position"
    assert portfolio.position_qty("INFY") == 3
    assert portfolio.cash == initial_cash
    assert len(portfolio.ledger) == initial_ledger_size
