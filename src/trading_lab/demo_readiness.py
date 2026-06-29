"""Demo-readiness verdict: Ready / Not ready / Needs review.

A focused, decision-oriented read on whether a backtest is ready to move to a
*demo* account for forward testing. It reuses the verdict and diagnostics
already computed locally and presents the evidence behind the call. It makes no
financial promises and places no trades — it is a deterministic engineering
readiness check over exported files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pathlib import Path
from typing import Dict

from .csv_deals import parse_deals_csv
from .decision import DecisionReport, build_decision
from .diagnostics import (
    BLOCKING,
    MEDIUM,
    SEVERITY_RANK,
    Diagnostic,
    input_from_deals,
    input_from_report,
    run_diagnostics,
)
from .html_report import parse_html_report
from .metrics import (
    DealsMetrics,
    Metrics,
    compute_deals_metrics,
    compute_metrics,
    deals_metric_results,
    report_metric_results,
)
from .recommend import PASS_TO_DEMO, REJECT, Thresholds, evaluate, evaluate_core

READY = "READY"
NOT_READY = "NOT_READY"
NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class EvidenceItem:
    label: str
    value: str
    ok: Optional[bool]  # True / False / None (unknown)


@dataclass(frozen=True)
class ReadinessEvidence:
    trade_count: Optional[int] = None
    profit_factor: Optional[float] = None
    drawdown_pct: Optional[float] = None
    recovery_factor: Optional[float] = None
    data_completeness: float = 0.0
    has_initial_balance: bool = True


@dataclass(frozen=True)
class DemoReadiness:
    status: str
    decision: str
    confidence: str
    evidence: List[EvidenceItem] = field(default_factory=list)
    risk_findings: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)


def evidence_from_report(metrics: Metrics) -> ReadinessEvidence:
    drawdown = metrics.balance_drawdown_relative_pct
    if drawdown is None:
        drawdown = metrics.equity_drawdown_relative_pct
    results = report_metric_results(metrics)
    completeness = sum(1 for r in results if r.available) / len(results) if results else 0.0
    return ReadinessEvidence(
        trade_count=metrics.total_trades,
        profit_factor=metrics.profit_factor,
        drawdown_pct=drawdown,
        recovery_factor=metrics.recovery_factor,
        data_completeness=completeness,
        has_initial_balance=metrics.initial_deposit is not None,
    )


def evidence_from_deals(metrics: DealsMetrics) -> ReadinessEvidence:
    results = deals_metric_results(metrics)
    completeness = sum(1 for r in results if r.available) / len(results) if results else 0.0
    return ReadinessEvidence(
        trade_count=metrics.total_trades,
        profit_factor=metrics.profit_factor,
        drawdown_pct=metrics.max_drawdown_pct,
        recovery_factor=metrics.recovery_factor,
        data_completeness=completeness,
        has_initial_balance=metrics.initial_balance is not None,
    )


def _fmt(value: Optional[float], suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    return f"{value}{suffix}"


def _build_evidence(e: ReadinessEvidence, t: Thresholds) -> List[EvidenceItem]:
    items: List[EvidenceItem] = []
    items.append(
        EvidenceItem(
            "Trade count",
            _fmt(e.trade_count),
            None if e.trade_count is None else e.trade_count >= t.min_trades,
        )
    )
    items.append(
        EvidenceItem(
            "Profit factor",
            _fmt(e.profit_factor),
            None if e.profit_factor is None else e.profit_factor >= t.min_profit_factor,
        )
    )
    items.append(
        EvidenceItem(
            "Max drawdown",
            _fmt(e.drawdown_pct, "%"),
            None if e.drawdown_pct is None else e.drawdown_pct <= t.max_drawdown_pct,
        )
    )
    items.append(
        EvidenceItem(
            "Recovery factor",
            _fmt(e.recovery_factor),
            None if e.recovery_factor is None else e.recovery_factor >= t.min_recovery_factor,
        )
    )
    items.append(
        EvidenceItem(
            "Data completeness",
            f"{e.data_completeness * 100:.0f}%",
            e.data_completeness >= 0.6,
        )
    )
    return items


def assess_demo_readiness(
    decision: DecisionReport,
    diagnostics: List[Diagnostic],
    evidence: ReadinessEvidence,
    thresholds: Thresholds = Thresholds(),
) -> DemoReadiness:
    has_blocking = any(d.severity == BLOCKING for d in diagnostics)

    if decision.decision == PASS_TO_DEMO and not has_blocking:
        status = READY
    elif decision.decision == REJECT or has_blocking:
        status = NOT_READY
    else:
        status = NEEDS_REVIEW

    risk_findings = [
        f"[{d.severity}] {d.message}"
        for d in diagnostics
        if SEVERITY_RANK[d.severity] >= SEVERITY_RANK[MEDIUM]
    ]

    return DemoReadiness(
        status=status,
        decision=decision.decision,
        confidence=decision.confidence,
        evidence=_build_evidence(evidence, thresholds),
        risk_findings=risk_findings,
        next_actions=list(decision.next_actions),
    )


def readiness_for_report(path, thresholds: Thresholds = Thresholds()) -> DemoReadiness:
    """End-to-end demo-readiness assessment from a Strategy Tester HTML export."""
    metrics = compute_metrics(parse_html_report(Path(path)))
    recommendation = evaluate(metrics, thresholds)
    diagnostics = run_diagnostics(input_from_report(metrics), thresholds)
    decision = build_decision(recommendation, diagnostics)
    return assess_demo_readiness(decision, diagnostics, evidence_from_report(metrics), thresholds)


def readiness_for_deals(
    path,
    thresholds: Thresholds = Thresholds(),
    column_overrides: Optional[Dict[str, str]] = None,
    initial_balance: Optional[float] = None,
) -> DemoReadiness:
    """End-to-end demo-readiness assessment from a deals/trades CSV export."""
    parsed = parse_deals_csv(Path(path), column_overrides=column_overrides)
    metrics = compute_deals_metrics(parsed, initial_balance=initial_balance)
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
    return assess_demo_readiness(decision, diagnostics, evidence_from_deals(metrics), thresholds)
