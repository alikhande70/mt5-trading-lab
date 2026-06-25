"""Command-line interface: `python -m trading_lab analyze-report ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .html_report import ReportParseError, parse_html_report
from .metrics import compute_metrics
from .recommend import Thresholds, evaluate
from .report import render_markdown


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m trading_lab",
        description=(
            "Local-first analysis of MetaTrader 5 Strategy Tester reports. "
            "Everything runs on this machine: no broker connection, no live "
            "trading, no VPS."
        ),
    )
    parser.add_argument("--version", action="version", version=f"trading-lab {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze-report",
        help="Parse a Strategy Tester HTML/HTM export and write a local Markdown recommendation.",
    )
    analyze.add_argument(
        "report_path",
        type=Path,
        help="Path to the Strategy Tester report exported from MT5 (.htm/.html).",
    )
    analyze.add_argument(
        "--out",
        type=Path,
        default=Path("report.md"),
        help="Where to write the Markdown report (default: report.md).",
    )
    analyze.add_argument(
        "--min-trades",
        type=int,
        default=Thresholds.min_trades,
        help=f"Minimum trade count for a meaningful sample (default: {Thresholds.min_trades}).",
    )
    analyze.add_argument(
        "--min-profit-factor",
        type=float,
        default=Thresholds.min_profit_factor,
        help=f"Profit factor comfort threshold (default: {Thresholds.min_profit_factor}).",
    )
    analyze.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=Thresholds.max_drawdown_pct,
        help=f"Relative drawdown comfort threshold, in percent (default: {Thresholds.max_drawdown_pct}).",
    )
    analyze.set_defaults(handler=_handle_analyze_report)

    return parser


def _handle_analyze_report(args: argparse.Namespace) -> int:
    if not args.report_path.exists():
        print(f"error: report file not found: {args.report_path}", file=sys.stderr)
        return 1

    try:
        parsed = parse_html_report(args.report_path)
    except ReportParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    metrics = compute_metrics(parsed)
    thresholds = Thresholds(
        min_trades=args.min_trades,
        min_profit_factor=args.min_profit_factor,
        max_drawdown_pct=args.max_drawdown_pct,
    )
    recommendation = evaluate(metrics, thresholds)
    markdown = render_markdown(args.report_path, metrics, recommendation, thresholds)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")

    print(f"Recommendation: {recommendation.verdict}")
    print(f"Report written to: {args.out}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
