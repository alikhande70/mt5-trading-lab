"""Schema tests for the structured JSON analysis report (Phase 3)."""

from datetime import datetime
from pathlib import Path

from trading_lab.csv_deals import parse_deals_csv
from trading_lab.decision import build_decision
from trading_lab.diagnostics import input_from_deals, input_from_report, run_diagnostics
from trading_lab.html_report import parse_html_report
from trading_lab.metrics import (
    compute_deals_metrics,
    compute_metrics,
    deals_metric_results,
    report_metric_results,
)
from trading_lab.recommend import Thresholds, evaluate, evaluate_core
from trading_lab.report import build_analysis_payload

FIXTURES = Path(__file__).parent / "fixtures"
FIXED_TS = datetime(2026, 1, 1, 12, 0, 0)

TOP_LEVEL_KEYS = {
    "schema_version",
    "tool",
    "input",
    "metrics",
    "diagnostics",
    "verdict",
    "warnings",
    "assumptions",
    "data_quality",
    "thresholds",
}


def _deals_payload(initial_balance=None):
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    metrics = compute_deals_metrics(parsed, initial_balance=initial_balance)
    thresholds = Thresholds()
    recommendation = evaluate_core(
        total_trades=metrics.total_trades,
        net_profit=metrics.net_profit,
        profit_factor=metrics.profit_factor,
        drawdown_pct=metrics.max_drawdown_pct,
        recovery_factor=None,
        thresholds=thresholds,
    )
    diagnostics = run_diagnostics(input_from_deals(metrics), thresholds)
    decision = build_decision(recommendation, diagnostics)
    return build_analysis_payload(
        FIXTURES / "sample_deals.csv",
        "deals_csv",
        deals_metric_results(metrics),
        diagnostics,
        decision,
        thresholds,
        parsed_at=FIXED_TS,
    )


def _report_payload():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    metrics = compute_metrics(report)
    thresholds = Thresholds()
    recommendation = evaluate(metrics, thresholds)
    diagnostics = run_diagnostics(input_from_report(metrics), thresholds)
    decision = build_decision(recommendation, diagnostics)
    return build_analysis_payload(
        FIXTURES / "sample_strategy_tester_report.htm",
        "strategy_tester_html",
        report_metric_results(metrics),
        diagnostics,
        decision,
        thresholds,
        parsed_at=FIXED_TS,
    )


def test_payload_has_all_top_level_keys():
    payload = _deals_payload()
    assert set(payload.keys()) == TOP_LEVEL_KEYS


def test_input_block_is_well_formed():
    payload = _deals_payload()
    assert payload["input"]["type"] == "deals_csv"
    assert payload["input"]["file"] == "sample_deals.csv"
    assert payload["input"]["parsed_at"] == FIXED_TS.isoformat(timespec="seconds")
    assert payload["schema_version"] == "1.0"
    assert payload["tool"]["name"] == "trading-lab"


def test_metrics_entries_are_machine_readable():
    payload = _deals_payload()
    net = payload["metrics"]["net_profit"]
    assert set(net.keys()) == {"value", "available", "reason_if_unavailable", "source", "warnings"}
    assert net["available"] is True
    assert net["source"] == "deals_csv"


def test_unavailable_metric_has_reason_and_null_value():
    payload = _deals_payload(initial_balance=None)
    dd_pct = payload["metrics"]["max_drawdown_percent"]
    assert dd_pct["available"] is False
    assert dd_pct["value"] is None
    assert dd_pct["reason_if_unavailable"]


def test_verdict_block_structure():
    payload = _deals_payload()
    verdict = payload["verdict"]
    assert set(verdict.keys()) == {
        "decision",
        "confidence",
        "blocking_reasons",
        "review_reasons",
        "passed",
        "next_actions",
    }
    assert verdict["decision"] in {"PASS_TO_DEMO", "NEEDS_REVIEW", "REJECT"}
    assert verdict["confidence"] in {"LOW", "MEDIUM", "HIGH"}
    assert verdict["next_actions"]


def test_diagnostics_entries_are_structured():
    report = parse_html_report(FIXTURES / "losing_strategy_report.htm")
    metrics = compute_metrics(report)
    thresholds = Thresholds()
    diagnostics = run_diagnostics(input_from_report(metrics), thresholds)
    decision = build_decision(evaluate(metrics, thresholds), diagnostics)
    payload = build_analysis_payload(
        "losing_strategy_report.htm",
        "strategy_tester_html",
        report_metric_results(metrics),
        diagnostics,
        decision,
        thresholds,
        parsed_at=FIXED_TS,
    )
    assert payload["diagnostics"]  # losing strategy must surface findings
    first = payload["diagnostics"][0]
    assert set(first.keys()) == {"code", "severity", "message", "recommendation"}


def test_data_quality_counts_match_metrics():
    payload = _report_payload()
    dq = payload["data_quality"]
    available = sum(1 for m in payload["metrics"].values() if m["available"])
    assert dq["metrics_total"] == len(payload["metrics"])
    assert dq["metrics_available"] == available
    assert len(dq["metrics_unavailable"]) == dq["metrics_total"] - dq["metrics_available"]


def test_payload_is_deterministic_with_fixed_timestamp():
    assert _deals_payload() == _deals_payload()
