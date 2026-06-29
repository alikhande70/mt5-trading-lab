"""Lightweight, local workflow layer.

These are thin orchestration helpers that stitch the existing core functions
into the common review flows. They add no new analysis logic and no new
capability — every workflow is just "parse → metrics → diagnostics → verdict →
render" over local files, returning rendered Markdown. There is no network,
broker, terminal, or order execution anywhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .compare import compare_deals, compare_reports
from .demo_readiness import readiness_for_deals, readiness_for_report
from .html_report import parse_html_report
from .metrics import compute_metrics
from .recommend import Thresholds, evaluate
from .report import (
    render_comparison_markdown,
    render_demo_readiness_markdown,
    render_markdown,
)


def workflow_single_backtest_review(report_path, thresholds: Thresholds = Thresholds()) -> str:
    """Review a single Strategy Tester report and return its Markdown."""
    metrics = compute_metrics(parse_html_report(Path(report_path)))
    recommendation = evaluate(metrics, thresholds)
    return render_markdown(report_path, metrics, recommendation, thresholds)


def workflow_multi_backtest_comparison(
    report_paths: List, thresholds: Thresholds = Thresholds()
) -> str:
    """Compare several Strategy Tester reports and return the Markdown ranking."""
    comparison = compare_reports([Path(p) for p in report_paths], thresholds)
    return render_comparison_markdown(comparison)


def workflow_demo_readiness_review(
    report_path=None,
    deals_path=None,
    thresholds: Thresholds = Thresholds(),
    column_overrides: Optional[Dict[str, str]] = None,
    initial_balance: Optional[float] = None,
) -> str:
    """Assess demo readiness for one backtest (CSV preferred when provided)."""
    if deals_path is not None:
        readiness = readiness_for_deals(
            deals_path, thresholds, column_overrides=column_overrides, initial_balance=initial_balance
        )
        source = deals_path
    elif report_path is not None:
        readiness = readiness_for_report(report_path, thresholds)
        source = report_path
    else:
        raise ValueError("workflow_demo_readiness_review needs a report_path or a deals_path.")
    return render_demo_readiness_markdown(readiness, source)
