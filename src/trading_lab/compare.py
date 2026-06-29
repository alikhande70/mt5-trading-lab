"""Multi-backtest comparison: rank several runs risk-adjusted.

Loads several Strategy Tester reports or several deals CSVs, scores each run on a
deterministic, explainable, **risk-adjusted** rubric, and ranks them. A high net
profit alone never wins: the score weighs profit *quality*, drawdown control,
sample quality, stability, and how complete the source data was.

Everything is local and offline — this only reads files you already exported and
reuses the same metrics, diagnostics, and verdict engine as the single-run path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .decision import DecisionReport, build_decision
from .diagnostics import Diagnostic, input_from_deals, input_from_report, run_diagnostics
from .html_report import parse_html_report
from .csv_deals import parse_deals_csv
from .metrics import (
    DealsMetrics,
    Metrics,
    compute_deals_metrics,
    compute_metrics,
    deals_metric_results,
    report_metric_results,
)
from .recommend import REJECT, Recommendation, Thresholds, evaluate, evaluate_core


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class RunScore:
    stability: float
    profit_quality: float
    drawdown_control: float
    sample_quality: float
    report_completeness: float
    total: float  # 0..100, the risk-adjusted overall score

    @property
    def components(self) -> Dict[str, float]:
        return {
            "stability": self.stability,
            "profit_quality": self.profit_quality,
            "drawdown_control": self.drawdown_control,
            "sample_quality": self.sample_quality,
            "report_completeness": self.report_completeness,
        }


@dataclass(frozen=True)
class RunSummary:
    name: str
    source_type: str
    decision: str
    net_profit: Optional[float]
    profit_factor: Optional[float]
    drawdown_pct: Optional[float]
    recovery_factor: Optional[float]
    trade_count: Optional[int]
    win_rate: Optional[float]
    expectancy: Optional[float]
    score: RunScore
    flags: List[str] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonResult:
    runs: List[RunSummary]  # ranked best-first
    best: Optional[str]
    recommendation: str
    reasons: List[str] = field(default_factory=list)


def _completeness(metric_results) -> float:
    if not metric_results:
        return 0.0
    available = sum(1 for r in metric_results if r.available)
    return available / len(metric_results)


def _score(
    profit_factor: Optional[float],
    drawdown_pct: Optional[float],
    trade_count: Optional[int],
    recovery_factor: Optional[float],
    completeness: float,
    diagnostics: List[Diagnostic],
    thresholds: Thresholds,
) -> RunScore:
    codes = {d.code for d in diagnostics}

    # Profit quality: profit factor mapped from 1.0..3.0 onto 0..1, with a
    # penalty when the profit factor is implausibly high (overfit signal).
    if profit_factor is None:
        profit_quality = 0.0
    else:
        profit_quality = _clamp01((profit_factor - 1.0) / 2.0)
        if "UNREALISTIC_PROFIT_FACTOR" in codes:
            profit_quality *= 0.5

    # Drawdown control: 0% -> 1, at/above the hard reject limit -> 0. Unknown
    # drawdown is neutral here (completeness already penalizes missing data).
    if drawdown_pct is None:
        drawdown_control = 0.5
    else:
        drawdown_control = _clamp01(1.0 - drawdown_pct / thresholds.reject_drawdown_pct)

    # Sample quality: full credit at twice the minimum trade count.
    if trade_count is None:
        sample_quality = 0.0
    else:
        sample_quality = _clamp01(trade_count / (thresholds.min_trades * 2))

    # Stability: recovery factor mapped from 0..4 onto 0..1 (unknown -> neutral).
    if recovery_factor is None:
        stability = 0.5
    else:
        stability = _clamp01(recovery_factor / 4.0)

    report_completeness = _clamp01(completeness)
    total = (
        (stability + profit_quality + drawdown_control + sample_quality + report_completeness)
        / 5.0
        * 100.0
    )
    return RunScore(
        stability=stability,
        profit_quality=profit_quality,
        drawdown_control=drawdown_control,
        sample_quality=sample_quality,
        report_completeness=report_completeness,
        total=total,
    )


def _flags(
    net_profit: Optional[float],
    profit_factor: Optional[float],
    drawdown_pct: Optional[float],
    trade_count: Optional[int],
    diagnostics: List[Diagnostic],
    thresholds: Thresholds,
) -> List[str]:
    codes = {d.code for d in diagnostics}
    flags: List[str] = []
    if trade_count is not None and trade_count < thresholds.min_trades:
        flags.append("low-sample")
    if drawdown_pct is not None and drawdown_pct > thresholds.max_drawdown_pct:
        flags.append("high-drawdown")
    if "OVERFIT_RISK" in codes or "UNREALISTIC_PROFIT_FACTOR" in codes:
        flags.append("overfit")
    if (net_profit is not None and net_profit <= 0) or (
        profit_factor is not None and profit_factor < thresholds.reject_profit_factor
    ):
        flags.append("losing")
    return flags


def _summarize_report(path: Path, thresholds: Thresholds) -> RunSummary:
    metrics: Metrics = compute_metrics(parse_html_report(path))
    recommendation: Recommendation = evaluate(metrics, thresholds)
    diagnostics = run_diagnostics(input_from_report(metrics), thresholds)
    completeness = _completeness(report_metric_results(metrics))
    drawdown = metrics.balance_drawdown_relative_pct
    if drawdown is None:
        drawdown = metrics.equity_drawdown_relative_pct
    score = _score(
        metrics.profit_factor,
        drawdown,
        metrics.total_trades,
        metrics.recovery_factor,
        completeness,
        diagnostics,
        thresholds,
    )
    flags = _flags(
        metrics.total_net_profit, metrics.profit_factor, drawdown, metrics.total_trades,
        diagnostics, thresholds,
    )
    return RunSummary(
        name=Path(path).name,
        source_type="strategy_tester_html",
        decision=recommendation.verdict,
        net_profit=metrics.total_net_profit,
        profit_factor=metrics.profit_factor,
        drawdown_pct=drawdown,
        recovery_factor=metrics.recovery_factor,
        trade_count=metrics.total_trades,
        win_rate=metrics.profit_trades_pct,
        expectancy=metrics.expected_payoff,
        score=score,
        flags=flags,
        diagnostics=diagnostics,
    )


def _summarize_deals(
    path: Path,
    thresholds: Thresholds,
    column_overrides: Optional[Dict[str, str]] = None,
    initial_balance: Optional[float] = None,
) -> RunSummary:
    parsed = parse_deals_csv(path, column_overrides=column_overrides)
    metrics: DealsMetrics = compute_deals_metrics(parsed, initial_balance=initial_balance)
    recommendation = evaluate_core(
        total_trades=metrics.total_trades,
        net_profit=metrics.net_profit,
        profit_factor=metrics.profit_factor,
        drawdown_pct=metrics.max_drawdown_pct,
        recovery_factor=None,
        thresholds=thresholds,
    )
    diagnostics = run_diagnostics(input_from_deals(metrics), thresholds)
    completeness = _completeness(deals_metric_results(metrics))
    score = _score(
        metrics.profit_factor,
        metrics.max_drawdown_pct,
        metrics.total_trades,
        metrics.recovery_factor,
        completeness,
        diagnostics,
        thresholds,
    )
    flags = _flags(
        metrics.net_profit, metrics.profit_factor, metrics.max_drawdown_pct,
        metrics.total_trades, diagnostics, thresholds,
    )
    return RunSummary(
        name=Path(path).name,
        source_type="deals_csv",
        decision=recommendation.verdict,
        net_profit=metrics.net_profit,
        profit_factor=metrics.profit_factor,
        drawdown_pct=metrics.max_drawdown_pct,
        recovery_factor=metrics.recovery_factor,
        trade_count=metrics.total_trades,
        win_rate=metrics.win_rate_pct,
        expectancy=metrics.expectancy,
        score=score,
        flags=flags,
        diagnostics=diagnostics,
    )


def _rank_and_recommend(runs: List[RunSummary]) -> ComparisonResult:
    # Deterministic ranking: highest score first, ties broken by name.
    ranked = sorted(runs, key=lambda r: (-r.score.total, r.name))
    if not ranked:
        return ComparisonResult(runs=[], best=None, recommendation="No runs to compare.", reasons=[])

    best = ranked[0]
    reasons: List[str] = []
    demo_ready = best.decision != REJECT and "losing" not in best.flags

    if demo_ready:
        recommendation = (
            f"{best.name} is the strongest candidate (risk-adjusted score "
            f"{best.score.total:.1f}/100, verdict {best.decision})."
        )
        reasons.append(
            "Ranking is risk-adjusted: profit quality, drawdown control, sample "
            "quality, stability, and data completeness — not net profit alone."
        )
        if best.flags:
            reasons.append(
                f"Note the remaining flags on {best.name}: {', '.join(best.flags)}."
            )
    else:
        recommendation = (
            "No run is clearly demo-ready: the top-ranked run is "
            f"{best.name} but it is flagged ({', '.join(best.flags) or best.decision})."
        )
        reasons.append("Improve the candidates (more trades, lower drawdown) and re-compare.")

    return ComparisonResult(runs=ranked, best=best.name, recommendation=recommendation, reasons=reasons)


def compare_reports(paths: List[Path], thresholds: Thresholds = Thresholds()) -> ComparisonResult:
    runs = [_summarize_report(Path(p), thresholds) for p in paths]
    return _rank_and_recommend(runs)


def compare_deals(
    paths: List[Path],
    thresholds: Thresholds = Thresholds(),
    column_overrides: Optional[Dict[str, str]] = None,
    initial_balance: Optional[float] = None,
) -> ComparisonResult:
    runs = [
        _summarize_deals(Path(p), thresholds, column_overrides, initial_balance) for p in paths
    ]
    return _rank_and_recommend(runs)
