"""Smoke tests for the CLI examples documented in README.md / RELEASE_CHECKLIST.md.

These don't re-test parsing/metrics logic (see test_csv_deals.py, test_html_report.py,
etc. for that) -- they confirm the documented commands still run end to end:
exit codes, file creation (or deliberate non-creation), and version reporting.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from trading_lab import __version__
from trading_lab.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def test_version_matches_package_metadata():
    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject_text)
    assert match is not None, "pyproject.toml has no [project] version field"
    assert match.group(1) == __version__


def test_cli_version_reports_package_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_smoke_analyze_report_creates_output_file(tmp_path):
    out_path = tmp_path / "report.md"
    exit_code = main(
        [
            "analyze-report",
            str(FIXTURES / "sample_strategy_tester_report.htm"),
            "--out",
            str(out_path),
        ]
    )

    assert exit_code == 0
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8")


def test_smoke_analyze_deals_creates_output_file(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--out",
            str(out_path),
        ]
    )

    assert exit_code == 0
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8")


def test_smoke_analyze_deals_list_columns_exits_zero_no_report(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--out",
            str(out_path),
            "--list-columns",
        ]
    )

    assert exit_code == 0
    assert not out_path.exists()


def test_smoke_analyze_deals_preview_rows_exits_zero_no_report(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--out",
            str(out_path),
            "--preview-rows",
            "--max-preview-rows",
            "5",
        ]
    )

    assert exit_code == 0
    assert not out_path.exists()


def test_smoke_custom_header_csv_works_with_column_map(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--out",
            str(out_path),
            "--column-map",
            str(FIXTURES / "custom_header_column_map.json"),
        ]
    )

    assert exit_code == 0
    assert out_path.exists()


def test_smoke_custom_header_csv_list_columns_with_column_map(tmp_path):
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--list-columns",
            "--column-map",
            str(FIXTURES / "custom_header_column_map.json"),
        ]
    )

    assert exit_code == 0


def test_smoke_custom_header_csv_preview_rows_with_column_map(tmp_path):
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--preview-rows",
            "--column-map",
            str(FIXTURES / "custom_header_column_map.json"),
        ]
    )

    assert exit_code == 0


def test_smoke_invalid_column_map_exits_one(tmp_path):
    bad_map = tmp_path / "bad.json"
    bad_map.write_text("{not valid json", encoding="utf-8")

    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--out",
            str(tmp_path / "deals_report.md"),
            "--column-map",
            str(bad_map),
        ]
    )

    assert exit_code == 1
