"""Tests for `--format json` on the CSV audit commands (--list-columns / --preview-rows).

Plain-text behavior is covered by test_cli.py; these tests only exercise the
JSON rendering path added for scripts/CI consumers.
"""

from __future__ import annotations

import json
from pathlib import Path

from trading_lab import __version__
from trading_lab.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _run_json(args, capsys):
    exit_code = main(args)
    captured = capsys.readouterr()
    return exit_code, captured


def test_list_columns_json_exits_zero(capsys):
    exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--list-columns", "--format", "json"],
        capsys,
    )
    assert exit_code == 0


def test_list_columns_json_prints_only_valid_json_to_stdout(capsys):
    exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--list-columns", "--format", "json"],
        capsys,
    )
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert captured.err == ""
    assert isinstance(payload, dict)


def test_list_columns_json_has_required_keys(capsys):
    _exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--list-columns", "--format", "json"],
        capsys,
    )
    payload = json.loads(captured.out)

    assert payload["command"] == "analyze-deals"
    assert payload["mode"] == "list-columns"
    assert payload["version"] == __version__
    assert payload["file"] == str(FIXTURES / "sample_deals.csv")
    assert "delimiter" in payload
    assert "columns" in payload
    assert "warnings" in payload
    assert "suggested_next_action" in payload


def test_list_columns_json_unmapped_column_has_null_canonical_field(capsys):
    _exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "custom_header_deals.csv"), "--list-columns", "--format", "json"],
        capsys,
    )
    payload = json.loads(captured.out)

    result_column = next(col for col in payload["columns"] if col["raw_header"] == "Result")
    assert result_column["canonical_field"] is None
    assert isinstance(payload["warnings"], list)


def test_preview_rows_json_exits_zero_on_valid_csv(capsys):
    exit_code, captured = _run_json(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--preview-rows",
            "--max-preview-rows",
            "5",
            "--format",
            "json",
        ],
        capsys,
    )
    assert exit_code == 0


def test_preview_rows_json_prints_only_valid_json_to_stdout(capsys):
    exit_code, captured = _run_json(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--preview-rows",
            "--max-preview-rows",
            "5",
            "--format",
            "json",
        ],
        capsys,
    )
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert captured.err == ""
    assert isinstance(payload, dict)


def test_preview_rows_json_has_required_keys(capsys):
    _exit_code, captured = _run_json(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--preview-rows",
            "--max-preview-rows",
            "5",
            "--format",
            "json",
        ],
        capsys,
    )
    payload = json.loads(captured.out)

    assert payload["command"] == "analyze-deals"
    assert payload["mode"] == "preview-rows"
    assert payload["version"] == __version__
    assert payload["file"] == str(FIXTURES / "sample_deals.csv")
    assert "delimiter" in payload
    assert payload["rows_inspected"] == len(payload["rows"])
    assert "summary" in payload
    assert "suggested_next_action" in payload


def test_preview_rows_json_uses_null_for_missing_values(capsys):
    _exit_code, captured = _run_json(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--preview-rows",
            "--max-preview-rows",
            "5",
            "--format",
            "json",
        ],
        capsys,
    )
    payload = json.loads(captured.out)

    counted_row = next(row for row in payload["rows"] if row["decision"] == "COUNT_CLOSED_TRADE")
    assert counted_row["warning"] is None
    assert counted_row["error"] is None


def test_preview_rows_json_malformed_profit_exits_one_but_still_valid_json(tmp_path, capsys):
    csv_path = tmp_path / "bad_profit.csv"
    csv_path.write_text(
        "Symbol,Profit\nEURUSD,50.00\nEURUSD,not-a-number\n",
        encoding="utf-8",
    )

    exit_code, captured = _run_json(
        ["analyze-deals", str(csv_path), "--preview-rows", "--format", "json"],
        capsys,
    )

    assert exit_code == 1
    payload = json.loads(captured.out)
    decisions = [row["decision"] for row in payload["rows"]]
    assert "ERROR_MALFORMED_PROFIT" in decisions
    assert payload["summary"]["malformed_profit_rows"] == 1
    assert payload["summary"]["errors"]


def test_full_analysis_json_with_out_returns_one_and_writes_nothing(tmp_path, capsys):
    out_path = tmp_path / "deals_report.md"
    exit_code, captured = _run_json(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--out",
            str(out_path),
            "--format",
            "json",
        ],
        capsys,
    )

    assert exit_code == 1
    assert "--out is not supported with --format json" in captured.err
    assert not out_path.exists()


def test_format_invalid_value_rejected_by_argparse(capsys):
    exit_code = None
    try:
        main(
            [
                "analyze-deals",
                str(FIXTURES / "sample_deals.csv"),
                "--list-columns",
                "--format",
                "xml",
            ]
        )
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err


def test_list_columns_plain_text_behavior_unchanged(capsys):
    exit_code = main(["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--list-columns"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "CSV column inspection" in captured.out
    with_assert_not_json = captured.out
    try:
        json.loads(with_assert_not_json)
        is_json = True
    except json.JSONDecodeError:
        is_json = False
    assert not is_json


def test_preview_rows_plain_text_behavior_unchanged(capsys):
    exit_code = main(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--preview-rows", "--max-preview-rows", "5"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "CSV row preview" in captured.out
    try:
        json.loads(captured.out)
        is_json = True
    except json.JSONDecodeError:
        is_json = False
    assert not is_json


# --- Full analyze-deals analysis JSON (--format json, no audit flag) ---------

REQUIRED_METRIC_KEYS = [
    "total_trades",
    "win_count",
    "loss_count",
    "net_profit",
    "gross_profit",
    "gross_loss",
    "profit_factor",
    "total_commission",
    "total_swap",
    "win_rate_pct",
    "loss_rate_pct",
    "average_win",
    "average_loss",
    "largest_win",
    "largest_loss",
    "payoff_ratio",
    "max_consecutive_wins",
    "max_consecutive_losses",
    "equity_curve",
    "max_drawdown_amount",
    "max_drawdown_pct",
    "initial_balance",
]

REQUIRED_THRESHOLD_KEYS = [
    "min_trades",
    "min_profit_factor",
    "reject_profit_factor",
    "max_drawdown_pct",
    "reject_drawdown_pct",
    "min_recovery_factor",
]


def test_full_analysis_json_exits_zero(capsys):
    exit_code, _captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--format", "json"],
        capsys,
    )
    assert exit_code == 0


def test_full_analysis_json_prints_only_valid_json_to_stdout(capsys):
    exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--format", "json"],
        capsys,
    )
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert captured.err == ""
    assert isinstance(payload, dict)


def test_full_analysis_json_has_required_top_level_keys(capsys):
    _exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--format", "json"],
        capsys,
    )
    payload = json.loads(captured.out)

    for key in (
        "command",
        "mode",
        "version",
        "file",
        "metrics",
        "recommendation",
        "thresholds",
        "warnings",
        "suggested_next_action",
    ):
        assert key in payload
    assert payload["command"] == "analyze-deals"
    assert payload["version"] == __version__
    assert payload["file"] == str(FIXTURES / "sample_deals.csv")


def test_full_analysis_json_mode_is_analysis(capsys):
    _exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--format", "json"],
        capsys,
    )
    payload = json.loads(captured.out)
    assert payload["mode"] == "analysis"


def test_full_analysis_json_metrics_keys_present(capsys):
    _exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--format", "json"],
        capsys,
    )
    payload = json.loads(captured.out)
    for key in REQUIRED_METRIC_KEYS:
        assert key in payload["metrics"], key
    assert isinstance(payload["metrics"]["equity_curve"], list)


def test_full_analysis_json_recommendation_keys_present(capsys):
    _exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--format", "json"],
        capsys,
    )
    payload = json.loads(captured.out)
    recommendation = payload["recommendation"]
    for key in ("verdict", "reasons", "passed"):
        assert key in recommendation
    assert isinstance(recommendation["verdict"], str)
    assert isinstance(recommendation["reasons"], list)
    assert isinstance(recommendation["passed"], list)


def test_full_analysis_json_thresholds_keys_present(capsys):
    _exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--format", "json"],
        capsys,
    )
    payload = json.loads(captured.out)
    for key in REQUIRED_THRESHOLD_KEYS:
        assert key in payload["thresholds"], key


def test_full_analysis_json_without_initial_balance_uses_null(capsys):
    _exit_code, captured = _run_json(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--format", "json"],
        capsys,
    )
    payload = json.loads(captured.out)
    assert payload["metrics"]["initial_balance"] is None
    assert payload["metrics"]["max_drawdown_pct"] is None
    assert any("initial" in w.lower() for w in payload["warnings"])


def test_full_analysis_json_with_initial_balance_is_numeric(capsys):
    _exit_code, captured = _run_json(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--format",
            "json",
            "--initial-balance",
            "10000",
        ],
        capsys,
    )
    payload = json.loads(captured.out)
    assert payload["metrics"]["initial_balance"] == 10000
    assert isinstance(payload["metrics"]["max_drawdown_pct"], (int, float))


def test_full_analysis_json_with_column_map(capsys):
    _exit_code, captured = _run_json(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--format",
            "json",
            "--column-map",
            str(FIXTURES / "custom_header_column_map.json"),
        ],
        capsys,
    )
    payload = json.loads(captured.out)
    assert payload["mode"] == "analysis"
    assert isinstance(payload["metrics"]["total_trades"], int)


def test_full_analysis_text_mode_writes_markdown(tmp_path, capsys):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        ["analyze-deals", str(FIXTURES / "sample_deals.csv"), "--out", str(out_path)]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert content.startswith("# MT5 CSV Deals Analysis")
    # stdout is the human status line, not JSON
    assert "Report written to" in captured.out
