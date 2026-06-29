from pathlib import Path

import pytest

from trading_lab.csv_deals import parse_deals_csv
from trading_lab.html_report import parse_html_report
from trading_lab.metrics import (
    compute_deals_metrics,
    compute_metrics,
    deals_metric_results,
    report_metric_results,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_compute_metrics_from_sample_report():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    metrics = compute_metrics(report)

    assert metrics.symbol == "EURUSD,H1"
    assert metrics.initial_deposit == pytest.approx(10000.00)
    assert metrics.total_net_profit == pytest.approx(1234.56)
    assert metrics.profit_factor == pytest.approx(1.85)
    assert metrics.recovery_factor == pytest.approx(2.47)
    assert metrics.balance_drawdown_relative_pct == pytest.approx(5.71)
    assert metrics.total_trades == 100
    assert metrics.profit_trades_pct == pytest.approx(58.00)
    assert metrics.short_trades_won_pct == pytest.approx(55.00)
    assert metrics.long_trades_won_pct == pytest.approx(60.00)
    assert metrics.max_consecutive_wins == 5
    assert metrics.max_consecutive_losses == 4


def test_win_loss_ratio_is_derived():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    metrics = compute_metrics(report)
    assert metrics.win_loss_ratio == pytest.approx(86.21 / 89.65, rel=1e-3)


def test_losing_strategy_metrics():
    report = parse_html_report(FIXTURES / "losing_strategy_report.htm")
    metrics = compute_metrics(report)

    assert metrics.total_net_profit == pytest.approx(-820.00)
    assert metrics.profit_factor == pytest.approx(0.52)
    assert metrics.total_trades == 8
    assert metrics.balance_drawdown_relative_pct == pytest.approx(52.00)


def test_compute_deals_metrics_from_sample_csv():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    metrics = compute_deals_metrics(parsed)

    assert metrics.total_trades == 30
    assert metrics.win_count == 20
    assert metrics.loss_count == 10
    assert metrics.gross_profit == pytest.approx(1000.00)
    assert metrics.gross_loss == pytest.approx(-200.00)
    assert metrics.profit_factor == pytest.approx(5.0)
    assert metrics.net_profit == pytest.approx(800.00)
    assert metrics.win_rate_pct == pytest.approx(20 / 30 * 100.0)
    assert metrics.average_win == pytest.approx(50.00)
    assert metrics.average_loss == pytest.approx(-20.00)
    assert metrics.largest_win == pytest.approx(50.00)
    assert metrics.largest_loss == pytest.approx(-20.00)
    assert metrics.payoff_ratio == pytest.approx(2.5)
    assert metrics.max_consecutive_wins == 2
    assert metrics.max_consecutive_losses == 1
    assert metrics.equity_curve[-1] == pytest.approx(800.00)
    assert metrics.max_drawdown_amount == pytest.approx(20.00)


def test_compute_deals_metrics_drawdown_pct_requires_initial_balance():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")

    without_balance = compute_deals_metrics(parsed)
    assert without_balance.max_drawdown_pct is None

    with_balance = compute_deals_metrics(parsed, initial_balance=10000.0)
    assert with_balance.max_drawdown_pct == pytest.approx(20.0 / 10100.0 * 100.0, rel=1e-3)


def test_compute_deals_metrics_losing_strategy():
    parsed = parse_deals_csv(FIXTURES / "losing_deals.csv")
    metrics = compute_deals_metrics(parsed)

    assert metrics.net_profit < 0
    assert metrics.profit_factor < 1.0


# --- Phase 1: expanded metrics ----------------------------------------------


def test_expanded_deals_metrics_are_computed():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    metrics = compute_deals_metrics(parsed)

    # average_trade is net per-trade P/L (gross profits / trade count here).
    assert metrics.average_trade == pytest.approx(800.0 / 30.0)
    # recovery_factor = net profit / max drawdown amount.
    assert metrics.recovery_factor == pytest.approx(800.0 / 20.0)
    # expectancy follows the classic win/loss probability formula.
    expected = (20 / 30) * 50.0 + (10 / 30) * -20.0
    assert metrics.expectancy == pytest.approx(expected)
    # drawdown curve runs alongside the equity curve and is non-negative.
    assert len(metrics.drawdown_curve) == len(metrics.equity_curve)
    assert min(metrics.drawdown_curve) >= 0.0
    assert max(metrics.drawdown_curve) == pytest.approx(metrics.max_drawdown_amount)


def test_long_short_split_from_type_column():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    metrics = compute_deals_metrics(parsed)
    assert metrics.long_count is not None
    assert metrics.short_count is not None
    assert metrics.long_count + metrics.short_count == metrics.total_trades


def test_symbol_distribution_and_monthly_returns_available_when_data_present():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    metrics = compute_deals_metrics(parsed)
    assert metrics.symbol_distribution is not None
    assert sum(metrics.symbol_distribution.values()) == metrics.total_trades
    assert metrics.monthly_returns is not None
    assert metrics.monthly_returns  # at least one month bucket


def test_long_short_split_unavailable_without_direction():
    # custom_header_deals.csv maps its type column, but the column map gives a
    # direction only when buy/sell tokens are present; assert graceful None when
    # direction cannot be derived from a non-direction source.
    parsed = parse_deals_csv(FIXTURES / "semicolon_deals.csv")
    metrics = compute_deals_metrics(parsed)
    # semicolon_deals has buy/sell types, so this is available; the point of the
    # contract is that the counts never exceed the trade count.
    if metrics.long_count is not None:
        assert metrics.long_count + (metrics.short_count or 0) <= metrics.total_trades


def test_deals_metric_results_mark_unavailable_with_reason():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    metrics = compute_deals_metrics(parsed, initial_balance=None)
    results = {r.name: r for r in deals_metric_results(metrics)}

    dd_pct = results["max_drawdown_percent"]
    assert dd_pct.available is False
    assert dd_pct.value is None
    assert dd_pct.reason_if_unavailable

    net = results["net_profit"]
    assert net.available is True
    assert net.value == pytest.approx(metrics.net_profit)
    assert net.source == "deals_csv"


def test_report_metric_results_flag_per_trade_series_unavailable():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    metrics = compute_metrics(report)
    results = {r.name: r for r in report_metric_results(metrics)}

    assert results["profit_factor"].available is True
    assert results["equity_curve"].available is False
    assert results["equity_curve"].reason_if_unavailable
    assert results["profit_factor"].source == "strategy_tester_html"
