from pathlib import Path

from trading_lab.csv_deals import parse_deals_csv
from trading_lab.diagnostics import (
    BLOCKING,
    HIGH,
    DiagnosticInput,
    input_from_deals,
    input_from_report,
    max_severity,
    run_diagnostics,
)
from trading_lab.html_report import parse_html_report
from trading_lab.metrics import compute_deals_metrics, compute_metrics
from trading_lab.recommend import Thresholds

FIXTURES = Path(__file__).parent / "fixtures"


def _codes(diags):
    return {d.code for d in diags}


def test_low_sample_size_flagged_high():
    diags = run_diagnostics(DiagnosticInput(source="deals_csv", trade_count=10))
    by_code = {d.code: d for d in diags}
    assert "LOW_SAMPLE_SIZE" in by_code
    assert by_code["LOW_SAMPLE_SIZE"].severity == HIGH


def test_high_drawdown_above_hard_limit_is_blocking():
    diags = run_diagnostics(DiagnosticInput(source="deals_csv", trade_count=50, drawdown_pct=52.0))
    by_code = {d.code: d for d in diags}
    assert by_code["HIGH_DRAWDOWN"].severity == BLOCKING


def test_unrealistic_profit_factor_flagged():
    diags = run_diagnostics(DiagnosticInput(source="deals_csv", trade_count=50, profit_factor=15.0))
    assert "UNREALISTIC_PROFIT_FACTOR" in _codes(diags)


def test_overfit_risk_is_composite():
    diags = run_diagnostics(
        DiagnosticInput(source="deals_csv", trade_count=5, profit_factor=15.0)
    )
    codes = _codes(diags)
    assert "OVERFIT_RISK" in codes  # low sample + unrealistic PF => composite flag


def test_fat_tail_loss_flagged():
    diags = run_diagnostics(
        DiagnosticInput(source="deals_csv", trade_count=50, largest_loss=-500.0, average_loss=-50.0)
    )
    assert "FAT_TAIL_LOSS" in _codes(diags)


def test_high_winrate_low_payoff_flagged():
    diags = run_diagnostics(
        DiagnosticInput(source="deals_csv", trade_count=50, win_rate_pct=85.0, payoff_ratio=0.4)
    )
    codes = _codes(diags)
    assert "HIGH_WINRATE_LOW_PAYOFF" in codes
    assert "BAD_RR_PROFILE" in codes


def test_missing_cost_data_flagged_for_deals_only():
    # An HTML report source must not emit CSV cost-completeness diagnostics.
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    diags = run_diagnostics(input_from_report(compute_metrics(report)))
    assert "MISSING_COMMISSION" not in _codes(diags)


def test_clean_sample_report_has_no_high_or_blocking():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    diags = run_diagnostics(input_from_report(compute_metrics(report)))
    sev = max_severity(diags)
    assert sev not in (HIGH, BLOCKING)


def test_losing_report_flags_low_sample_and_high_drawdown():
    report = parse_html_report(FIXTURES / "losing_strategy_report.htm")
    diags = run_diagnostics(input_from_report(compute_metrics(report)))
    codes = _codes(diags)
    assert "LOW_SAMPLE_SIZE" in codes
    assert "HIGH_DRAWDOWN" in codes


def test_deals_without_initial_balance_flagged():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    metrics = compute_deals_metrics(parsed, initial_balance=None)
    diags = run_diagnostics(input_from_deals(metrics))
    assert "MISSING_INITIAL_BALANCE" in _codes(diags)


def test_diagnostics_sorted_by_severity_descending():
    diags = run_diagnostics(
        DiagnosticInput(
            source="deals_csv",
            trade_count=10,            # HIGH (low sample)
            drawdown_pct=52.0,         # BLOCKING (high drawdown)
        )
    )
    severities = [d.severity for d in diags]
    ranks = [
        {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "BLOCKING": 4}[s] for s in severities
    ]
    assert ranks == sorted(ranks, reverse=True)


def test_thresholds_are_honoured():
    # With a stricter min-trades, a 40-trade sample becomes a low-sample flag.
    diags = run_diagnostics(
        DiagnosticInput(source="deals_csv", trade_count=40),
        Thresholds(min_trades=50),
    )
    assert "LOW_SAMPLE_SIZE" in _codes(diags)
