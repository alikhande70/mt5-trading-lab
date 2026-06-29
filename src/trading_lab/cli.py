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
from .compare import compare_deals, compare_reports
from .decision import build_decision
from .demo_readiness import readiness_for_deals, readiness_for_report
from .workflows import (
    workflow_demo_readiness_review,
    workflow_multi_backtest_comparison,
    workflow_single_backtest_review,
)
from .diagnostics import input_from_deals, input_from_report, run_diagnostics
from .html_report import ReportParseError, parse_html_report
from .metrics import (
    compute_deals_metrics,
    compute_metrics,
    deals_metric_results,
    report_metric_results,
)
from .recommend import Thresholds, evaluate, evaluate_core
from .report import (
    render_analysis_json,
    render_column_inspection,
    render_column_inspection_json,
    render_comparison_json,
    render_comparison_markdown,
    render_deals_markdown,
    render_demo_readiness_json,
    render_demo_readiness_markdown,
    render_markdown,
    render_row_preview,
    render_row_preview_json,
)


def _add_threshold_args(parser: argparse.ArgumentParser) -> None:
    """Add the shared verdict-threshold flags to a subcommand parser."""
    parser.add_argument(
        "--min-trades", type=int, default=Thresholds.min_trades,
        help=f"Minimum trade count for a meaningful sample (default: {Thresholds.min_trades}).",
    )
    parser.add_argument(
        "--min-profit-factor", type=float, default=Thresholds.min_profit_factor,
        help=f"Profit factor comfort threshold (default: {Thresholds.min_profit_factor}).",
    )
    parser.add_argument(
        "--max-drawdown-pct", type=float, default=Thresholds.max_drawdown_pct,
        help=f"Relative drawdown comfort threshold, in percent (default: {Thresholds.max_drawdown_pct}).",
    )


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
    analyze.add_argument(
        "--format",
        choices=["markdown", "json", "both"],
        default="markdown",
        help=(
            "Output format (default: markdown). 'json' writes a structured JSON "
            "report instead of Markdown; 'both' writes Markdown and JSON."
        ),
    )
    analyze.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Where to write the JSON report (default: alongside --out with a .json suffix).",
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
    analyze_deals.add_argument(
        "--format",
        choices=["text", "markdown", "json", "both"],
        default="markdown",
        help=(
            "Output format (default: markdown). For the full analysis: 'json' "
            "writes a structured JSON report, 'both' writes Markdown and JSON. "
            "For the --list-columns / --preview-rows audit modes: 'json' emits "
            "machine-readable audit output, anything else stays plain text."
        ),
    )
    analyze_deals.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Where to write the JSON report (default: alongside --out with a .json suffix).",
    )
    analyze_deals.set_defaults(handler=_handle_analyze_deals)

    compare_reports_cmd = subparsers.add_parser(
        "compare-reports",
        help="Compare and rank several Strategy Tester HTML/HTM exports (risk-adjusted).",
    )
    compare_reports_cmd.add_argument(
        "report_paths",
        type=Path,
        nargs="+",
        help="Two or more Strategy Tester reports (.htm/.html) to compare.",
    )
    compare_reports_cmd.add_argument(
        "--out", type=Path, default=Path("comparison.md"),
        help="Where to write the Markdown comparison (default: comparison.md).",
    )
    compare_reports_cmd.add_argument(
        "--format", choices=["markdown", "json", "both"], default="markdown",
        help="Output format (default: markdown).",
    )
    compare_reports_cmd.add_argument(
        "--json-out", type=Path, default=None,
        help="Where to write the JSON comparison (default: alongside --out with a .json suffix).",
    )
    _add_threshold_args(compare_reports_cmd)
    compare_reports_cmd.set_defaults(handler=_handle_compare_reports)

    compare_deals_cmd = subparsers.add_parser(
        "compare-deals",
        help="Compare and rank several deals/trades CSV exports (risk-adjusted).",
    )
    compare_deals_cmd.add_argument(
        "deals_paths",
        type=Path,
        nargs="+",
        help="Two or more deals/trades CSV exports to compare.",
    )
    compare_deals_cmd.add_argument(
        "--out", type=Path, default=Path("comparison.md"),
        help="Where to write the Markdown comparison (default: comparison.md).",
    )
    compare_deals_cmd.add_argument(
        "--format", choices=["markdown", "json", "both"], default="markdown",
        help="Output format (default: markdown).",
    )
    compare_deals_cmd.add_argument(
        "--json-out", type=Path, default=None,
        help="Where to write the JSON comparison (default: alongside --out with a .json suffix).",
    )
    compare_deals_cmd.add_argument(
        "--initial-balance", type=float, default=None,
        help="Starting account balance, used to compute percentage drawdown (optional).",
    )
    compare_deals_cmd.add_argument(
        "--column-map", type=Path, default=None,
        help="Path to a JSON column map applied to every CSV being compared.",
    )
    _add_threshold_args(compare_deals_cmd)
    compare_deals_cmd.set_defaults(handler=_handle_compare_deals)

    demo_cmd = subparsers.add_parser(
        "demo-readiness",
        help="Produce a Ready / No / Needs Review demo-readiness report for one backtest.",
    )
    demo_cmd.add_argument(
        "input_path",
        type=Path,
        help="A Strategy Tester report (.htm/.html) or a deals CSV (auto-detected by suffix).",
    )
    demo_cmd.add_argument(
        "--deals", type=Path, default=None,
        help="A deals CSV to assess instead of the positional input (richer per-trade data).",
    )
    demo_cmd.add_argument(
        "--out", type=Path, default=Path("demo_readiness.md"),
        help="Where to write the Markdown report (default: demo_readiness.md).",
    )
    demo_cmd.add_argument(
        "--format", choices=["markdown", "json", "both"], default="markdown",
        help="Output format (default: markdown).",
    )
    demo_cmd.add_argument(
        "--json-out", type=Path, default=None,
        help="Where to write the JSON report (default: alongside --out with a .json suffix).",
    )
    demo_cmd.add_argument(
        "--initial-balance", type=float, default=None,
        help="Starting account balance for percentage drawdown when assessing a CSV (optional).",
    )
    demo_cmd.add_argument(
        "--column-map", type=Path, default=None,
        help="Path to a JSON column map, used when the assessed source is a CSV.",
    )
    _add_threshold_args(demo_cmd)
    demo_cmd.set_defaults(handler=_handle_demo_readiness)

    workflow_cmd = subparsers.add_parser(
        "workflow",
        help="Run a common review flow end-to-end (single-review, compare-runs, demo-readiness).",
    )
    workflow_sub = workflow_cmd.add_subparsers(dest="workflow_action", required=True)

    wf_single = workflow_sub.add_parser(
        "single-review", help="Review a single Strategy Tester report."
    )
    wf_single.add_argument("--report", type=Path, required=True, help="Strategy Tester report (.htm/.html).")
    wf_single.add_argument("--out", type=Path, default=Path("review.md"), help="Output Markdown (default: review.md).")
    _add_threshold_args(wf_single)
    wf_single.set_defaults(handler=_handle_workflow_single)

    wf_compare = workflow_sub.add_parser(
        "compare-runs", help="Compare several Strategy Tester reports."
    )
    wf_compare.add_argument("--reports", type=Path, nargs="+", required=True, help="Two or more reports.")
    wf_compare.add_argument("--out", type=Path, default=Path("comparison.md"), help="Output Markdown (default: comparison.md).")
    _add_threshold_args(wf_compare)
    wf_compare.set_defaults(handler=_handle_workflow_compare)

    wf_demo = workflow_sub.add_parser(
        "demo-readiness", help="Assess demo readiness for one backtest."
    )
    wf_demo.add_argument("--report", type=Path, default=None, help="Strategy Tester report (.htm/.html).")
    wf_demo.add_argument("--deals", type=Path, default=None, help="Deals CSV (preferred source when provided).")
    wf_demo.add_argument("--out", type=Path, default=Path("demo.md"), help="Output Markdown (default: demo.md).")
    wf_demo.add_argument("--initial-balance", type=float, default=None, help="Starting balance for CSV percentage drawdown.")
    wf_demo.add_argument("--column-map", type=Path, default=None, help="JSON column map for a CSV source.")
    _add_threshold_args(wf_demo)
    wf_demo.set_defaults(handler=_handle_workflow_demo)

    return parser


def _resolve_json_path(out: Path, json_out: Optional[Path]) -> Path:
    return json_out if json_out is not None else out.with_suffix(".json")


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
    diagnostics = run_diagnostics(input_from_report(metrics), thresholds)
    decision = build_decision(recommendation, diagnostics)

    write_markdown = args.format in ("markdown", "both")
    write_json = args.format in ("json", "both")

    if write_markdown:
        markdown = render_markdown(args.report_path, metrics, recommendation, thresholds)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")

    if write_json:
        json_path = _resolve_json_path(args.out, args.json_out)
        payload = render_analysis_json(
            args.report_path,
            "strategy_tester_html",
            report_metric_results(metrics),
            diagnostics,
            decision,
            thresholds,
            assumptions=[
                "Metrics are taken as reported in the MT5 Strategy Tester summary.",
            ],
        )
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(payload, encoding="utf-8")

    print(f"Recommendation: {recommendation.verdict}")
    if write_markdown:
        print(f"Report written to: {args.out}")
    if write_json:
        print(f"JSON written to: {_resolve_json_path(args.out, args.json_out)}")
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
        if args.format == "json":
            print(render_column_inspection_json(inspection))
        else:
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
        if args.format == "json":
            print(render_row_preview_json(result))
        else:
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

    diagnostics = run_diagnostics(input_from_deals(metrics), thresholds)
    decision = build_decision(recommendation, diagnostics)

    # 'text' maps to markdown for the full analysis (back-compat: the old
    # default never affected the written report, which was always Markdown).
    write_markdown = args.format in ("markdown", "both", "text")
    write_json = args.format in ("json", "both")

    if write_markdown:
        markdown = render_deals_markdown(
            args.deals_path, metrics, recommendation, thresholds, warnings
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")

    if write_json:
        json_path = _resolve_json_path(args.out, args.json_out)
        payload = render_analysis_json(
            args.deals_path,
            "deals_csv",
            deals_metric_results(metrics),
            diagnostics,
            decision,
            thresholds,
            warnings=warnings,
            assumptions=[
                "Metrics are recomputed from the per-deal CSV ledger.",
                "Drawdown is measured on the cumulative closed-trade profit curve.",
            ],
        )
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(payload, encoding="utf-8")

    print(f"Recommendation: {recommendation.verdict}")
    if write_markdown:
        print(f"Report written to: {args.out}")
    if write_json:
        print(f"JSON written to: {_resolve_json_path(args.out, args.json_out)}")
    return 0


def _write_comparison(args: argparse.Namespace, comparison) -> int:
    write_markdown = args.format in ("markdown", "both")
    write_json = args.format in ("json", "both")

    if write_markdown:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_comparison_markdown(comparison), encoding="utf-8")
    if write_json:
        json_path = _resolve_json_path(args.out, args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(render_comparison_json(comparison), encoding="utf-8")

    print(f"Best candidate: {comparison.best}")
    if write_markdown:
        print(f"Comparison written to: {args.out}")
    if write_json:
        print(f"JSON written to: {_resolve_json_path(args.out, args.json_out)}")
    return 0


def _handle_compare_reports(args: argparse.Namespace) -> int:
    if len(args.report_paths) < 2:
        print("error: compare-reports needs at least two report files.", file=sys.stderr)
        return 1
    missing = [str(p) for p in args.report_paths if not p.exists()]
    if missing:
        print(f"error: report file(s) not found: {', '.join(missing)}", file=sys.stderr)
        return 1

    thresholds = Thresholds(
        min_trades=args.min_trades,
        min_profit_factor=args.min_profit_factor,
        max_drawdown_pct=args.max_drawdown_pct,
    )
    try:
        comparison = compare_reports(args.report_paths, thresholds)
    except ReportParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return _write_comparison(args, comparison)


def _handle_compare_deals(args: argparse.Namespace) -> int:
    if len(args.deals_paths) < 2:
        print("error: compare-deals needs at least two CSV files.", file=sys.stderr)
        return 1
    missing = [str(p) for p in args.deals_paths if not p.exists()]
    if missing:
        print(f"error: deals CSV file(s) not found: {', '.join(missing)}", file=sys.stderr)
        return 1

    column_overrides: Dict[str, str] = {}
    if args.column_map is not None:
        try:
            column_overrides = load_column_map(args.column_map)
        except DealsParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    thresholds = Thresholds(
        min_trades=args.min_trades,
        min_profit_factor=args.min_profit_factor,
        max_drawdown_pct=args.max_drawdown_pct,
    )
    try:
        comparison = compare_deals(
            args.deals_paths,
            thresholds,
            column_overrides=column_overrides or None,
            initial_balance=args.initial_balance,
        )
    except DealsParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return _write_comparison(args, comparison)


def _is_report_path(path: Path) -> bool:
    return path.suffix.lower() in (".htm", ".html")


def _handle_demo_readiness(args: argparse.Namespace) -> int:
    # The CSV given by --deals takes precedence (richer per-trade data); otherwise
    # the positional input is auto-detected as a report or a CSV by its suffix.
    source = args.deals if args.deals is not None else args.input_path
    if not source.exists():
        print(f"error: file not found: {source}", file=sys.stderr)
        return 1

    thresholds = Thresholds(
        min_trades=args.min_trades,
        min_profit_factor=args.min_profit_factor,
        max_drawdown_pct=args.max_drawdown_pct,
    )

    column_overrides: Dict[str, str] = {}
    if args.column_map is not None:
        try:
            column_overrides = load_column_map(args.column_map)
        except DealsParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    try:
        if args.deals is None and _is_report_path(args.input_path):
            readiness = readiness_for_report(source, thresholds)
        else:
            readiness = readiness_for_deals(
                source, thresholds,
                column_overrides=column_overrides or None,
                initial_balance=args.initial_balance,
            )
    except (ReportParseError, DealsParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    write_markdown = args.format in ("markdown", "both")
    write_json = args.format in ("json", "both")

    if write_markdown:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_demo_readiness_markdown(readiness, source), encoding="utf-8")
    if write_json:
        json_path = _resolve_json_path(args.out, args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(render_demo_readiness_json(readiness, source), encoding="utf-8")

    print(f"Demo readiness: {readiness.status}")
    if write_markdown:
        print(f"Report written to: {args.out}")
    if write_json:
        print(f"JSON written to: {_resolve_json_path(args.out, args.json_out)}")
    return 0


def _thresholds_from(args: argparse.Namespace) -> Thresholds:
    return Thresholds(
        min_trades=args.min_trades,
        min_profit_factor=args.min_profit_factor,
        max_drawdown_pct=args.max_drawdown_pct,
    )


def _write_text_out(out: Path, content: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def _handle_workflow_single(args: argparse.Namespace) -> int:
    if not args.report.exists():
        print(f"error: report file not found: {args.report}", file=sys.stderr)
        return 1
    try:
        markdown = workflow_single_backtest_review(args.report, _thresholds_from(args))
    except ReportParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _write_text_out(args.out, markdown)
    print(f"Review written to: {args.out}")
    return 0


def _handle_workflow_compare(args: argparse.Namespace) -> int:
    if len(args.reports) < 2:
        print("error: compare-runs needs at least two report files.", file=sys.stderr)
        return 1
    missing = [str(p) for p in args.reports if not p.exists()]
    if missing:
        print(f"error: report file(s) not found: {', '.join(missing)}", file=sys.stderr)
        return 1
    try:
        markdown = workflow_multi_backtest_comparison(args.reports, _thresholds_from(args))
    except ReportParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _write_text_out(args.out, markdown)
    print(f"Comparison written to: {args.out}")
    return 0


def _handle_workflow_demo(args: argparse.Namespace) -> int:
    if args.report is None and args.deals is None:
        print("error: provide --report and/or --deals.", file=sys.stderr)
        return 1
    source = args.deals if args.deals is not None else args.report
    if not source.exists():
        print(f"error: file not found: {source}", file=sys.stderr)
        return 1

    column_overrides: Dict[str, str] = {}
    if args.column_map is not None:
        try:
            column_overrides = load_column_map(args.column_map)
        except DealsParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    try:
        markdown = workflow_demo_readiness_review(
            report_path=args.report,
            deals_path=args.deals,
            thresholds=_thresholds_from(args),
            column_overrides=column_overrides or None,
            initial_balance=args.initial_balance,
        )
    except (ReportParseError, DealsParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _write_text_out(args.out, markdown)
    print(f"Demo-readiness review written to: {args.out}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
