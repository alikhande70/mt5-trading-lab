from pathlib import Path

import pytest

from trading_lab.csv_deals import parse_deals_csv
from trading_lab.html_report import parse_html_report
from trading_lab.metrics import compute_deals_metrics, compute_metrics

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
