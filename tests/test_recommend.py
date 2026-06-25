from pathlib import Path

from trading_lab.html_report import parse_html_report
from trading_lab.metrics import Metrics, compute_metrics
from trading_lab.recommend import NEEDS_REVIEW, PASS_TO_DEMO, REJECT, Thresholds, evaluate

FIXTURES = Path(__file__).parent / "fixtures"


def _blank_metrics(**overrides) -> Metrics:
    base = dict(
        symbol=None,
        period=None,
        initial_deposit=None,
        total_net_profit=None,
        gross_profit=None,
        gross_loss=None,
        profit_factor=None,
        expected_payoff=None,
        recovery_factor=None,
        sharpe_ratio=None,
        balance_drawdown_relative_pct=None,
        equity_drawdown_relative_pct=None,
        total_trades=None,
        profit_trades_pct=None,
        loss_trades_pct=None,
        short_trades_won_pct=None,
        long_trades_won_pct=None,
        largest_profit_trade=None,
        largest_loss_trade=None,
        average_profit_trade=None,
        average_loss_trade=None,
        max_consecutive_wins=None,
        max_consecutive_losses=None,
        win_loss_ratio=None,
    )
    base.update(overrides)
    return Metrics(**base)


def test_solid_strategy_passes_to_demo():
    metrics = _blank_metrics(
        total_net_profit=1234.56,
        profit_factor=1.85,
        total_trades=100,
        balance_drawdown_relative_pct=5.71,
        recovery_factor=2.47,
    )
    result = evaluate(metrics)
    assert result.verdict == PASS_TO_DEMO


def test_losing_strategy_is_rejected():
    metrics = _blank_metrics(
        total_net_profit=-820.00,
        profit_factor=0.52,
        total_trades=8,
        balance_drawdown_relative_pct=52.00,
        recovery_factor=-0.16,
    )
    result = evaluate(metrics)
    assert result.verdict == REJECT
    assert any("net loss" in reason.lower() for reason in result.reasons)


def test_borderline_profit_factor_needs_review():
    metrics = _blank_metrics(
        total_net_profit=500.00,
        profit_factor=1.2,
        total_trades=100,
        balance_drawdown_relative_pct=10.0,
        recovery_factor=3.0,
    )
    result = evaluate(metrics)
    assert result.verdict == NEEDS_REVIEW


def test_small_sample_needs_review_even_if_profitable():
    metrics = _blank_metrics(
        total_net_profit=500.00,
        profit_factor=3.0,
        total_trades=5,
        balance_drawdown_relative_pct=5.0,
        recovery_factor=5.0,
    )
    result = evaluate(metrics)
    assert result.verdict == NEEDS_REVIEW


def test_missing_core_metrics_needs_review():
    metrics = _blank_metrics()
    result = evaluate(metrics)
    assert result.verdict == NEEDS_REVIEW


def test_excessive_drawdown_is_rejected_even_when_profitable():
    metrics = _blank_metrics(
        total_net_profit=1000.00,
        profit_factor=2.0,
        total_trades=100,
        balance_drawdown_relative_pct=45.0,
        recovery_factor=3.0,
    )
    result = evaluate(metrics)
    assert result.verdict == REJECT


def test_custom_thresholds_are_respected():
    metrics = _blank_metrics(
        total_net_profit=500.00,
        profit_factor=1.2,
        total_trades=15,
        balance_drawdown_relative_pct=10.0,
        recovery_factor=1.5,
    )
    lenient = Thresholds(min_trades=10, min_profit_factor=1.0, min_recovery_factor=1.0)
    result = evaluate(metrics, lenient)
    assert result.verdict == PASS_TO_DEMO


def test_end_to_end_sample_report_passes_to_demo():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    metrics = compute_metrics(report)
    result = evaluate(metrics)
    assert result.verdict == PASS_TO_DEMO


def test_end_to_end_losing_report_is_rejected():
    report = parse_html_report(FIXTURES / "losing_strategy_report.htm")
    metrics = compute_metrics(report)
    result = evaluate(metrics)
    assert result.verdict == REJECT
