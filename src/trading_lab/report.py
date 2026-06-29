"""Renders the analysis result as a local Markdown report."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union

from . import __version__
from .compare import ComparisonResult
from .csv_deals import ColumnInspection, RowClassificationResult
from .decision import DecisionReport
from .diagnostics import Diagnostic
from .metrics import DealsMetrics, Metrics, MetricResult
from .recommend import PASS_TO_DEMO, REJECT, Recommendation, Thresholds


def _fmt(value: Optional[Union[int, float]], suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    return f"{value}{suffix}"


def _metric_rows(metrics: Metrics) -> List[Tuple[str, str]]:
    return [
        ("Initial deposit", _fmt(metrics.initial_deposit)),
        ("Total net profit", _fmt(metrics.total_net_profit)),
        ("Gross profit", _fmt(metrics.gross_profit)),
        ("Gross loss", _fmt(metrics.gross_loss)),
        ("Profit factor", _fmt(metrics.profit_factor)),
        ("Expected payoff", _fmt(metrics.expected_payoff)),
        ("Recovery factor", _fmt(metrics.recovery_factor)),
        ("Sharpe ratio", _fmt(metrics.sharpe_ratio)),
        ("Balance drawdown (relative)", _fmt(metrics.balance_drawdown_relative_pct, "%")),
        ("Equity drawdown (relative)", _fmt(metrics.equity_drawdown_relative_pct, "%")),
        ("Total trades", _fmt(metrics.total_trades)),
        ("Profit trades", _fmt(metrics.profit_trades_pct, "%")),
        ("Loss trades", _fmt(metrics.loss_trades_pct, "%")),
        ("Short trades won", _fmt(metrics.short_trades_won_pct, "%")),
        ("Long trades won", _fmt(metrics.long_trades_won_pct, "%")),
        ("Largest profit trade", _fmt(metrics.largest_profit_trade)),
        ("Largest loss trade", _fmt(metrics.largest_loss_trade)),
        ("Average profit trade", _fmt(metrics.average_profit_trade)),
        ("Average loss trade", _fmt(metrics.average_loss_trade)),
        ("Win/loss ratio", _fmt(metrics.win_loss_ratio)),
        ("Max consecutive wins", _fmt(metrics.max_consecutive_wins)),
        ("Max consecutive losses", _fmt(metrics.max_consecutive_losses)),
    ]


def render_markdown(
    source_path,
    metrics: Metrics,
    recommendation: Recommendation,
    thresholds: Thresholds,
    generated_at: Optional[datetime] = None,
) -> str:
    generated_at = generated_at or datetime.now()
    lines: List[str] = []

    lines.append("# MT5 Strategy Tester Report Analysis")
    lines.append("")
    lines.append(f"- **Source report:** `{Path(source_path).name}`")
    lines.append(
        f"- **Generated:** {generated_at.strftime('%Y-%m-%d %H:%M:%S')} "
        f"(local time, trading-lab v{__version__})"
    )
    if metrics.symbol:
        lines.append(f"- **Symbol:** {metrics.symbol}")
    if metrics.period:
        lines.append(f"- **Period:** {metrics.period}")
    lines.append("")

    lines.append(f"## Recommendation: `{recommendation.verdict}`")
    lines.append("")
    lines.append("### Why")
    for reason in recommendation.reasons:
        lines.append(f"- {reason}")

    if recommendation.passed:
        lines.append("")
        lines.append("### Checks passed")
        for item in recommendation.passed:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("## Key metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    for label, value in _metric_rows(metrics):
        lines.append(f"| {label} | {value} |")
    lines.append("")

    lines.append("## Thresholds used")
    lines.append("")
    lines.append(f"- Minimum trades: {thresholds.min_trades}")
    lines.append(
        f"- Minimum profit factor: {thresholds.min_profit_factor:.2f} "
        f"(reject below {thresholds.reject_profit_factor:.2f})"
    )
    lines.append(
        f"- Maximum comfortable drawdown: {thresholds.max_drawdown_pct:.2f}% "
        f"(reject above {thresholds.reject_drawdown_pct:.2f}%)"
    )
    lines.append(f"- Minimum recovery factor: {thresholds.min_recovery_factor:.2f}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*This is an automated, local, rule-based read of your Strategy Tester report. "
        "It is not financial advice and does not guarantee live or demo performance. "
        "No order was placed, no broker was contacted, and no data left this machine.*"
    )

    return "\n".join(lines) + "\n"


def _next_action(verdict: str) -> str:
    if verdict == PASS_TO_DEMO:
        return (
            "Consider moving this strategy to a demo account for forward testing. "
            "This tool does not place any trades; any next step is manual and outside this CLI."
        )
    if verdict == REJECT:
        return (
            "Do not advance this strategy to demo or live trading as-is. "
            "Revisit the strategy logic or parameters before re-testing."
        )
    return (
        "Review the flagged items manually, consider gathering more trade history or "
        "tuning parameters, and re-run this analysis before deciding on demo testing."
    )


def render_deals_markdown(
    source_path,
    metrics: DealsMetrics,
    recommendation: Recommendation,
    thresholds: Thresholds,
    warnings: Optional[List[str]] = None,
    generated_at: Optional[datetime] = None,
) -> str:
    generated_at = generated_at or datetime.now()
    warnings = warnings or []
    lines: List[str] = []

    lines.append("# MT5 CSV Deals Analysis")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"Recommendation **`{recommendation.verdict}`** based on "
        f"{_fmt(metrics.total_trades)} closed trade/deal row(s) parsed from the CSV export below."
    )
    lines.append(
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S')} "
        f"(local time, trading-lab v{__version__})"
    )
    lines.append("")

    lines.append("## CSV file analyzed")
    lines.append("")
    lines.append(f"- **Source file:** `{Path(source_path).name}`")
    if metrics.initial_balance is not None:
        lines.append(f"- **Initial balance (provided):** {_fmt(metrics.initial_balance)}")
    else:
        lines.append("- **Initial balance:** not provided (percentage drawdown unavailable)")
    lines.append("")

    lines.append("## Parsed trade/deal counts")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Total trades | {_fmt(metrics.total_trades)} |")
    lines.append(f"| Winning trades | {_fmt(metrics.win_count)} |")
    lines.append(f"| Losing trades | {_fmt(metrics.loss_count)} |")
    lines.append("")

    lines.append("## Profit metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Net profit | {_fmt(metrics.net_profit)} |")
    lines.append(f"| Gross profit | {_fmt(metrics.gross_profit)} |")
    lines.append(f"| Gross loss | {_fmt(metrics.gross_loss)} |")
    lines.append(f"| Profit factor | {_fmt(metrics.profit_factor)} |")
    lines.append(f"| Total commission | {_fmt(metrics.total_commission)} |")
    lines.append(f"| Total swap | {_fmt(metrics.total_swap)} |")
    lines.append("")

    lines.append("## Win/loss metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Win rate | {_fmt(metrics.win_rate_pct, '%')} |")
    lines.append(f"| Loss rate | {_fmt(metrics.loss_rate_pct, '%')} |")
    lines.append(f"| Average win | {_fmt(metrics.average_win)} |")
    lines.append(f"| Average loss | {_fmt(metrics.average_loss)} |")
    lines.append(f"| Largest win | {_fmt(metrics.largest_win)} |")
    lines.append(f"| Largest loss | {_fmt(metrics.largest_loss)} |")
    lines.append(f"| Payoff ratio | {_fmt(metrics.payoff_ratio)} |")
    lines.append(f"| Max consecutive wins | {_fmt(metrics.max_consecutive_wins)} |")
    lines.append(f"| Max consecutive losses | {_fmt(metrics.max_consecutive_losses)} |")
    lines.append("")

    lines.append("## Drawdown / equity curve summary")
    lines.append("")
    lines.append(f"- **Equity curve points:** {len(metrics.equity_curve)} (cumulative profit per closed deal)")
    lines.append(f"- **Max drawdown (amount):** {_fmt(metrics.max_drawdown_amount)}")
    if metrics.max_drawdown_pct is not None:
        lines.append(f"- **Max drawdown (% of balance):** {_fmt(metrics.max_drawdown_pct, '%')}")
    else:
        lines.append(
            "- **Max drawdown (% of balance):** n/a (pass `--initial-balance` to compute this)"
        )
    lines.append("")

    lines.append("## Strategy recommendation")
    lines.append("")
    lines.append(f"### Recommendation: `{recommendation.verdict}`")
    lines.append("")
    lines.append("### Why")
    for reason in recommendation.reasons:
        lines.append(f"- {reason}")
    if recommendation.passed:
        lines.append("")
        lines.append("### Checks passed")
        for item in recommendation.passed:
            lines.append(f"- {item}")
    lines.append("")
    lines.append("### Thresholds used")
    lines.append(f"- Minimum trades: {thresholds.min_trades}")
    lines.append(
        f"- Minimum profit factor: {thresholds.min_profit_factor:.2f} "
        f"(reject below {thresholds.reject_profit_factor:.2f})"
    )
    lines.append(
        f"- Maximum comfortable drawdown: {thresholds.max_drawdown_pct:.2f}% "
        f"(reject above {thresholds.reject_drawdown_pct:.2f}%)"
    )
    lines.append("")

    lines.append("## Warnings")
    lines.append("")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("## Next suggested action")
    lines.append("")
    lines.append(_next_action(recommendation.verdict))
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*This is an automated, local, rule-based read of your CSV trade/deal export. "
        "It is not financial advice and does not guarantee live or demo performance. "
        "No order was placed, no broker was contacted, and no data left this machine.*"
    )

    return "\n".join(lines) + "\n"


def _metric_results_to_dict(metric_results: List[MetricResult]) -> dict:
    return {
        r.name: {
            "value": r.value,
            "available": r.available,
            "reason_if_unavailable": r.reason_if_unavailable,
            "source": r.source,
            "warnings": list(r.warnings),
        }
        for r in metric_results
    }


def _data_quality(metric_results: List[MetricResult]) -> dict:
    unavailable = [r.name for r in metric_results if not r.available]
    return {
        "metrics_total": len(metric_results),
        "metrics_available": len(metric_results) - len(unavailable),
        "metrics_unavailable": unavailable,
    }


def build_analysis_payload(
    source_path,
    input_type: str,
    metric_results: List[MetricResult],
    diagnostics: List[Diagnostic],
    decision: DecisionReport,
    thresholds: Thresholds,
    warnings: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    parsed_at: Optional[datetime] = None,
) -> dict:
    """Build the canonical, machine-readable analysis payload (a plain dict).

    ``parsed_at`` is injectable so the output is fully deterministic in tests.
    """
    parsed_at = parsed_at or datetime.now()
    return {
        "schema_version": "1.0",
        "tool": {"name": "trading-lab", "version": __version__},
        "input": {
            "file": Path(source_path).name,
            "type": input_type,
            "parsed_at": parsed_at.isoformat(timespec="seconds"),
        },
        "metrics": _metric_results_to_dict(metric_results),
        "diagnostics": [
            {
                "code": d.code,
                "severity": d.severity,
                "message": d.message,
                "recommendation": d.recommendation,
            }
            for d in diagnostics
        ],
        "verdict": {
            "decision": decision.decision,
            "confidence": decision.confidence,
            "blocking_reasons": list(decision.blocking_reasons),
            "review_reasons": list(decision.review_reasons),
            "passed": list(decision.passed),
            "next_actions": list(decision.next_actions),
        },
        "warnings": list(warnings or []),
        "assumptions": list(assumptions or []),
        "data_quality": _data_quality(metric_results),
        "thresholds": {
            "min_trades": thresholds.min_trades,
            "min_profit_factor": thresholds.min_profit_factor,
            "reject_profit_factor": thresholds.reject_profit_factor,
            "max_drawdown_pct": thresholds.max_drawdown_pct,
            "reject_drawdown_pct": thresholds.reject_drawdown_pct,
            "min_recovery_factor": thresholds.min_recovery_factor,
        },
    }


def render_analysis_json(*args, **kwargs) -> str:
    """Serialize :func:`build_analysis_payload` to a JSON string."""
    payload = build_analysis_payload(*args, **kwargs)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_comparison_markdown(
    comparison: ComparisonResult,
    generated_at: Optional[datetime] = None,
) -> str:
    generated_at = generated_at or datetime.now()
    lines: List[str] = []

    lines.append("# MT5 Backtest Comparison")
    lines.append("")
    lines.append(
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S')} "
        f"(local time, trading-lab v{__version__})"
    )
    lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    lines.append(comparison.recommendation)
    for reason in comparison.reasons:
        lines.append(f"- {reason}")
    lines.append("")

    lines.append("## Ranking (risk-adjusted, best first)")
    lines.append("")
    lines.append("| Rank | Run | Score | Verdict | Net profit | Profit factor | Drawdown | Trades | Flags |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for index, run in enumerate(comparison.runs, start=1):
        dd = _fmt(run.drawdown_pct, "%") if run.drawdown_pct is not None else "n/a"
        flags = ", ".join(run.flags) if run.flags else "-"
        lines.append(
            f"| {index} | `{run.name}` | {run.score.total:.1f} | {run.decision} | "
            f"{_fmt(run.net_profit)} | {_fmt(run.profit_factor)} | {dd} | "
            f"{_fmt(run.trade_count)} | {flags} |"
        )
    lines.append("")

    lines.append("## Score breakdown")
    lines.append("")
    lines.append("| Run | Stability | Profit quality | Drawdown control | Sample quality | Completeness |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for run in comparison.runs:
        c = run.score.components
        lines.append(
            f"| `{run.name}` | {c['stability']:.2f} | {c['profit_quality']:.2f} | "
            f"{c['drawdown_control']:.2f} | {c['sample_quality']:.2f} | "
            f"{c['report_completeness']:.2f} |"
        )
    lines.append("")

    lines.append("## Per-run warnings")
    lines.append("")
    for run in comparison.runs:
        lines.append(f"- **`{run.name}`**: " + (", ".join(run.flags) if run.flags else "no flags"))
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Risk-adjusted comparison of local backtest exports. Net profit alone does "
        "not determine the ranking. This is not financial advice; no order was placed "
        "and no broker or terminal was contacted.*"
    )
    return "\n".join(lines) + "\n"


def build_comparison_payload(
    comparison: ComparisonResult,
    generated_at: Optional[datetime] = None,
) -> dict:
    generated_at = generated_at or datetime.now()
    return {
        "schema_version": "1.0",
        "tool": {"name": "trading-lab", "version": __version__},
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "best": comparison.best,
        "recommendation": comparison.recommendation,
        "reasons": list(comparison.reasons),
        "runs": [
            {
                "name": run.name,
                "source_type": run.source_type,
                "decision": run.decision,
                "score": {"total": run.score.total, **run.score.components},
                "net_profit": run.net_profit,
                "profit_factor": run.profit_factor,
                "drawdown_pct": run.drawdown_pct,
                "recovery_factor": run.recovery_factor,
                "trade_count": run.trade_count,
                "win_rate": run.win_rate,
                "expectancy": run.expectancy,
                "flags": list(run.flags),
            }
            for run in comparison.runs
        ],
    }


def render_comparison_json(comparison: ComparisonResult, generated_at: Optional[datetime] = None) -> str:
    return json.dumps(build_comparison_payload(comparison, generated_at), indent=2, ensure_ascii=False) + "\n"


def render_column_inspection(inspection: ColumnInspection) -> str:
    lines: List[str] = []

    lines.append("CSV column inspection")
    lines.append(f"File: {inspection.path}")
    lines.append(f"Delimiter: {inspection.delimiter}")
    lines.append("")

    header_label, canonical_label, source_label = "Raw header", "Canonical field", "Source"
    raw_width = max([len(header_label)] + [len(c.raw_header) for c in inspection.columns]) + 4
    canonical_width = (
        max([len(canonical_label)] + [len(c.canonical_field or "unmapped") for c in inspection.columns])
        + 4
    )

    lines.append(f"{header_label:<{raw_width}}{canonical_label:<{canonical_width}}{source_label}")
    lines.append("")
    for column in inspection.columns:
        canonical_display = column.canonical_field or "unmapped"
        lines.append(f"{column.raw_header:<{raw_width}}{canonical_display:<{canonical_width}}{column.source}")
    lines.append("")

    lines.append("Warnings:")
    lines.append("")
    if inspection.warnings:
        for warning in inspection.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- No issue detected.")
    lines.append("")

    lines.append("Suggested next action:")
    lines.append(inspection.suggested_next_action)

    return "\n".join(lines)


def render_column_inspection_json(inspection: ColumnInspection) -> str:
    """JSON form of `render_column_inspection`, for scripts/CI. Same data,
    machine-readable shape; see docs/USAGE.md for the field reference."""
    payload = {
        "command": "analyze-deals",
        "mode": "list-columns",
        "version": __version__,
        "file": str(inspection.path),
        "delimiter": inspection.delimiter,
        "columns": [
            {
                "raw_header": column.raw_header,
                "canonical_field": column.canonical_field,
                "source": column.source,
            }
            for column in inspection.columns
        ],
        "warnings": list(inspection.warnings),
        "suggested_next_action": inspection.suggested_next_action,
    }
    return json.dumps(payload, indent=2)


def _preview_cell(value: Optional[Union[str, float]]) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def render_row_preview(result: RowClassificationResult) -> str:
    lines: List[str] = []

    lines.append("CSV row preview")
    lines.append(f"File: {result.path}")
    lines.append(f"Delimiter: {result.delimiter}")
    lines.append(f"Rows inspected: {len(result.rows)}")
    lines.append("")

    column_labels = ["Row", "Decision", "Reason", "Symbol", "Type", "Entry", "Profit raw", "Profit"]
    table_rows = [
        [
            str(row.row_number),
            row.decision,
            row.reason,
            _preview_cell(row.symbol),
            _preview_cell(row.type_raw),
            _preview_cell(row.entry_raw),
            _preview_cell(row.profit_raw),
            _preview_cell(row.profit_value),
        ]
        for row in result.rows
    ]

    widths = [
        max([len(column_labels[i])] + [len(table_row[i]) for table_row in table_rows]) + 4
        for i in range(len(column_labels))
    ]

    lines.append("".join(f"{label:<{widths[i]}}" for i, label in enumerate(column_labels)).rstrip())
    lines.append("")
    for table_row in table_rows:
        lines.append(
            "".join(f"{cell:<{widths[i]}}" for i, cell in enumerate(table_row)).rstrip()
        )
    lines.append("")

    summary = result.summary
    lines.append("Summary:")
    lines.append("")
    lines.append(f"- Total data rows inspected: {summary.total_data_rows}")
    lines.append(f"- Counted closed trades: {summary.counted_rows}")
    lines.append(f"- Skipped non-trade rows: {summary.skipped_non_trade_rows}")
    lines.append(f"- Skipped opening rows: {summary.skipped_opening_rows}")
    lines.append(f"- Skipped missing-profit rows: {summary.skipped_missing_profit_rows}")
    lines.append(f"- Malformed profit rows: {summary.malformed_profit_rows}")
    lines.append(f"- Incomplete rows: {summary.incomplete_rows}")
    lines.append("")

    lines.append("Warnings:")
    lines.append("")
    if summary.warnings:
        for warning in summary.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- No issue detected.")
    lines.append("")

    lines.append("Errors:")
    lines.append("")
    if summary.errors:
        for error in summary.errors:
            lines.append(f"- {error}")
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("Suggested next action:")
    lines.append(result.suggested_next_action)

    return "\n".join(lines)


def render_row_preview_json(result: RowClassificationResult) -> str:
    """JSON form of `render_row_preview`, for scripts/CI. Same data,
    machine-readable shape; see docs/USAGE.md for the field reference."""
    payload = {
        "command": "analyze-deals",
        "mode": "preview-rows",
        "version": __version__,
        "file": str(result.path),
        "delimiter": result.delimiter,
        "rows_inspected": len(result.rows),
        "rows": [
            {
                "row_number": row.row_number,
                "decision": row.decision,
                "reason": row.reason,
                "symbol": row.symbol,
                "type_raw": row.type_raw,
                "entry_raw": row.entry_raw,
                "profit_raw": row.profit_raw,
                "profit_value": row.profit_value,
                "volume": row.volume,
                "warning": row.warning,
                "error": row.error,
            }
            for row in result.rows
        ],
        "summary": {
            "total_data_rows": result.summary.total_data_rows,
            "counted_rows": result.summary.counted_rows,
            "skipped_non_trade_rows": result.summary.skipped_non_trade_rows,
            "skipped_opening_rows": result.summary.skipped_opening_rows,
            "skipped_missing_profit_rows": result.summary.skipped_missing_profit_rows,
            "malformed_profit_rows": result.summary.malformed_profit_rows,
            "incomplete_rows": result.summary.incomplete_rows,
            "warnings": list(result.summary.warnings),
            "errors": list(result.summary.errors),
        },
        "suggested_next_action": result.suggested_next_action,
    }
    return json.dumps(payload, indent=2)
