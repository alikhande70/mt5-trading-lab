from pathlib import Path

import pytest

from trading_lab.html_report import parse_html_report
from trading_lab.metrics import compute_metrics

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
