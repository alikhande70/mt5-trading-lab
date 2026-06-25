"""Command-line interface: `python -m trading_lab analyze-report ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence

from . import __version__
from .csv_deals import (
    DealsParseError,
    classify_deals_csv_rows,
    inspect_deals_csv_columns,
    load_column_map,
    parse_deals_csv,
)
from .html_report import ReportParseError, parse_html_report
from .metrics import compute_deals_metrics, compute_metrics
from .recommend import Thresholds, evaluate, evaluate_core
from .report import render_column_inspection, render_deals_markdown, render_markdown, render_row_preview


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

    analyze_deals = subparsers.add_parser(
        "analyze-deals",
        help="Parse an MT5 deals/trades CSV export and write a local Markdown recommendation.",
    )
    analyze_deals.add_argument(
        "deals_path",
        type=Path,
        help="Path to the deals/trades CSV exported from MT5 (History tab or Strategy Tester).",
    )
    analyze_deals.add_argument(
        "--out",
        type=Path,
        default=Path("deals_report.md"),
        help="Where to write the Markdown report (default: deals_report.md).",
    )
    analyze_deals.add_argument(
        "--initial-balance",
        type=float,
        default=None,
        help="Starting account balance, used to compute percentage drawdown (optional).",
    )
    analyze_deals.add_argument(
        "--min-trades",
        type=int,
        default=Thresholds.min_trades,
        help=f"Minimum trade count for a meaningful sample (default: {Thresholds.min_trades}).",
    )
    analyze_deals.add_argument(
        "--min-profit-factor",
        type=float,
        default=Thresholds.min_profit_factor,
        help=f"Profit factor comfort threshold (default: {Thresholds.min_profit_factor}).",
    )
    analyze_deals.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=Thresholds.max_drawdown_pct,
        help=f"Relative drawdown comfort threshold, in percent (default: {Thresholds.max_drawdown_pct}).",
    )
    analyze_deals.add_argument(
        "--column-map",
        type=Path,
        default=None,
        help=(
            "Path to a JSON file mapping canonical field names (profit, type, "
            "entry, symbol, volume, commission, swap, comment, time, ticket, "
            "order, deal) to this CSV's actual header labels. Use this for "
            "exports whose column names don't match the built-in English aliases."
        ),
    )
    analyze_deals.add_argument(
        "--profit-column",
        default=None,
        help="Exact CSV header label for the profit column (overrides built-in aliases and --column-map).",
    )
    analyze_deals.add_argument(
        "--type-column",
        default=None,
        help="Exact CSV header label for the deal/order type column (overrides built-in aliases and --column-map).",
    )
    analyze_deals.add_argument(
        "--entry-column",
        default=None,
        help="Exact CSV header label for the entry (in/out) column (overrides built-in aliases and --column-map).",
    )
    analyze_deals.add_argument(
        "--symbol-column",
        default=None,
        help="Exact CSV header label for the symbol/instrument column (overrides built-in aliases and --column-map).",
    )
    analyze_deals.add_argument(
        "--volume-column",
        default=None,
        help="Exact CSV header label for the volume/lots column (overrides built-in aliases and --column-map).",
    )
    analyze_deals.add_argument(
        "--commission-column",
        default=None,
        help="Exact CSV header label for the commission column (overrides built-in aliases and --column-map).",
    )
    analyze_deals.add_argument(
        "--swap-column",
        default=None,
        help="Exact CSV header label for the swap column (overrides built-in aliases and --column-map).",
    )
    analyze_deals.add_argument(
        "--comment-column",
        default=None,
        help="Exact CSV header label for the comment column (overrides built-in aliases and --column-map).",
    )
    analyze_deals.add_argument(
        "--list-columns",
        action="store_true",
        help=(
            "Inspect the CSV header only: print how each raw column resolves to a "
            "canonical field and why, then exit. Does not compute metrics or write a "
            "report; useful for debugging a column layout before --column-map / "
            "--*-column flags."
        ),
    )
    analyze_deals.add_argument(
        "--preview-rows",
        action="store_true",
        help=(
            "Classify each data row (counted as a closed trade, skipped, or "
            "malformed) and print the decisions plus a summary, then exit. Does "
            "not compute metrics or write a report; useful for auditing how a CSV "
            "would be interpreted before trusting the full analysis. Mutually "
            "exclusive with --list-columns."
        ),
    )
    analyze_deals.add_argument(
        "--max-preview-rows",
        type=int,
        default=50,
        help="Maximum number of data rows to classify/display with --preview-rows (default: 50).",
    )
    analyze_deals.set_defaults(handler=_handle_analyze_deals)

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


def _handle_analyze_deals(args: argparse.Namespace) -> int:
    if args.list_columns and args.preview_rows:
        print("error: --list-columns and --preview-rows are mutually exclusive.", file=sys.stderr)
        return 1

    if args.max_preview_rows <= 0:
        print("error: --max-preview-rows must be a positive integer.", file=sys.stderr)
        return 1

    if not args.deals_path.exists():
        print(f"error: deals CSV file not found: {args.deals_path}", file=sys.stderr)
        return 1

    column_map_overrides: Dict[str, str] = {}
    if args.column_map is not None:
        try:
            column_map_overrides = load_column_map(args.column_map)
        except DealsParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    # Direct --*-column flags override both the built-in aliases and --column-map.
    direct_overrides = {
        canonical: label
        for canonical, label in {
            "profit": args.profit_column,
            "type": args.type_column,
            "entry": args.entry_column,
            "symbol": args.symbol_column,
            "volume": args.volume_column,
            "commission": args.commission_column,
            "swap": args.swap_column,
            "comment": args.comment_column,
        }.items()
        if label
    }

    if args.list_columns:
        try:
            inspection = inspect_deals_csv_columns(
                args.deals_path,
                column_map_overrides=column_map_overrides or None,
                direct_overrides=direct_overrides or None,
            )
        except DealsParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(render_column_inspection(inspection))
        return 0

    column_overrides = {**column_map_overrides, **direct_overrides}

    if args.preview_rows:
        try:
            result = classify_deals_csv_rows(
                args.deals_path,
                column_overrides=column_overrides or None,
                max_rows=args.max_preview_rows,
            )
        except DealsParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(render_row_preview(result))
        return 1 if result.summary.malformed_profit_rows else 0

    try:
        parsed = parse_deals_csv(args.deals_path, column_overrides=column_overrides or None)
    except DealsParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    metrics = compute_deals_metrics(parsed, initial_balance=args.initial_balance)
    thresholds = Thresholds(
        min_trades=args.min_trades,
        min_profit_factor=args.min_profit_factor,
        max_drawdown_pct=args.max_drawdown_pct,
    )
    recommendation = evaluate_core(
        total_trades=metrics.total_trades,
        net_profit=metrics.net_profit,
        profit_factor=metrics.profit_factor,
        drawdown_pct=metrics.max_drawdown_pct,
        recovery_factor=None,
        thresholds=thresholds,
    )

    warnings = list(parsed.warnings)
    if args.initial_balance is None:
        warnings.append(
            "No --initial-balance provided; percentage drawdown is unavailable "
            "(only the absolute drawdown amount was computed)."
        )

    markdown = render_deals_markdown(args.deals_path, metrics, recommendation, thresholds, warnings)

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
