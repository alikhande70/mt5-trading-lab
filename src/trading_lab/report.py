"""Renders the analysis result as a local Markdown report."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union

from . import __version__
from .metrics import Metrics
from .recommend import Recommendation, Thresholds


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
