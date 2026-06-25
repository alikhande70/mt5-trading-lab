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


def test_format_json_without_list_columns_or_preview_rows_returns_one(tmp_path, capsys):
    exit_code, captured = _run_json(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--out",
            str(tmp_path / "deals_report.md"),
            "--format",
            "json",
        ],
        capsys,
    )

    assert exit_code == 1
    assert "--format json" in captured.err
    assert not (tmp_path / "deals_report.md").exists()


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
