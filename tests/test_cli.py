from pathlib import Path

from trading_lab.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_analyze_report_writes_markdown(tmp_path, capsys):
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

    content = out_path.read_text(encoding="utf-8")
    assert "PASS_TO_DEMO" in content
    assert "Profit factor" in content
    assert "No order was placed" in content

    captured = capsys.readouterr()
    assert "Recommendation: PASS_TO_DEMO" in captured.out


def test_analyze_report_rejects_losing_strategy(tmp_path):
    out_path = tmp_path / "report.md"
    exit_code = main(
        [
            "analyze-report",
            str(FIXTURES / "losing_strategy_report.htm"),
            "--out",
            str(out_path),
        ]
    )

    assert exit_code == 0
    content = out_path.read_text(encoding="utf-8")
    assert "REJECT" in content


def test_analyze_report_missing_file_returns_error(tmp_path, capsys):
    exit_code = main(
        [
            "analyze-report",
            str(tmp_path / "does_not_exist.htm"),
            "--out",
            str(tmp_path / "report.md"),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_analyze_report_rejects_unparsable_file(tmp_path):
    bogus = tmp_path / "bogus.htm"
    bogus.write_text("<html><body>not a report</body></html>", encoding="utf-8")

    exit_code = main(
        [
            "analyze-report",
            str(bogus),
            "--out",
            str(tmp_path / "report.md"),
        ]
    )

    assert exit_code == 1


def test_custom_thresholds_change_outcome(tmp_path):
    out_path = tmp_path / "report.md"
    main(
        [
            "analyze-report",
            str(FIXTURES / "sample_strategy_tester_report.htm"),
            "--out",
            str(out_path),
            "--min-profit-factor",
            "5.0",
        ]
    )
    content = out_path.read_text(encoding="utf-8")
    assert "NEEDS_REVIEW" in content


def test_analyze_deals_writes_markdown(tmp_path, capsys):
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

    content = out_path.read_text(encoding="utf-8")
    assert "PASS_TO_DEMO" in content
    assert "Profit factor" in content
    assert "No order was placed" in content

    captured = capsys.readouterr()
    assert "Recommendation: PASS_TO_DEMO" in captured.out


def test_analyze_deals_rejects_losing_strategy(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "losing_deals.csv"),
            "--out",
            str(out_path),
        ]
    )

    assert exit_code == 0
    content = out_path.read_text(encoding="utf-8")
    assert "REJECT" in content


def test_analyze_deals_with_initial_balance(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--out",
            str(out_path),
            "--initial-balance",
            "10000",
        ]
    )

    assert exit_code == 0
    content = out_path.read_text(encoding="utf-8")
    assert "Max drawdown (% of balance)" in content
    assert "n/a" not in content.split("Max drawdown (% of balance):")[1].split("\n")[0]


def test_analyze_deals_without_initial_balance_warns(tmp_path):
    out_path = tmp_path / "deals_report.md"
    main(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--out",
            str(out_path),
        ]
    )

    content = out_path.read_text(encoding="utf-8")
    assert "percentage drawdown is unavailable" in content


def test_analyze_deals_missing_file_returns_error(tmp_path, capsys):
    exit_code = main(
        [
            "analyze-deals",
            str(tmp_path / "does_not_exist.csv"),
            "--out",
            str(tmp_path / "deals_report.md"),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_analyze_deals_rejects_unparsable_file(tmp_path):
    bogus = tmp_path / "bogus.csv"
    bogus.write_text("Time,Symbol,Volume\n2024.01.01,EURUSD,0.10\n", encoding="utf-8")

    exit_code = main(
        [
            "analyze-deals",
            str(bogus),
            "--out",
            str(tmp_path / "deals_report.md"),
        ]
    )

    assert exit_code == 1


def test_analyze_deals_custom_thresholds_change_outcome(tmp_path):
    out_path = tmp_path / "deals_report.md"
    main(
        [
            "analyze-deals",
            str(FIXTURES / "sample_deals.csv"),
            "--out",
            str(out_path),
            "--min-profit-factor",
            "50.0",
        ]
    )
    content = out_path.read_text(encoding="utf-8")
    assert "NEEDS_REVIEW" in content


def test_analyze_deals_profit_only_override_warns_in_report(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--out",
            str(out_path),
            "--profit-column",
            "Result",
        ]
    )

    assert exit_code == 0
    content = out_path.read_text(encoding="utf-8")
    assert "filtering is unavailable" in content


def test_analyze_deals_with_column_map_json(tmp_path):
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
    content = out_path.read_text(encoding="utf-8")
    assert "Total trades" in content


def test_analyze_deals_with_direct_column_overrides(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--out",
            str(out_path),
            "--profit-column",
            "Result",
            "--type-column",
            "Operation",
            "--entry-column",
            "Entry Type",
            "--symbol-column",
            "Instrument",
            "--volume-column",
            "Lots",
            "--commission-column",
            "Fee",
            "--swap-column",
            "Overnight",
            "--comment-column",
            "Note",
        ]
    )

    assert exit_code == 0
    content = out_path.read_text(encoding="utf-8")
    assert "Total trades" in content


def test_analyze_deals_direct_override_wins_over_column_map(tmp_path):
    # Decoy column map points "profit" at the wrong header; the direct
    # --profit-column flag must win and produce the correct result.
    decoy_map = tmp_path / "decoy_map.json"
    decoy_map.write_text('{"profit": "Decoy"}', encoding="utf-8")

    csv_path = tmp_path / "decoy_deals.csv"
    csv_path.write_text(
        "Result,Decoy\n50.00,9999.00\n-20.00,8888.00\n",
        encoding="utf-8",
    )

    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(csv_path),
            "--out",
            str(out_path),
            "--column-map",
            str(decoy_map),
            "--profit-column",
            "Result",
        ]
    )

    assert exit_code == 0
    content = out_path.read_text(encoding="utf-8")
    assert "9999" not in content
    assert "8888" not in content


def test_analyze_deals_missing_column_map_file_returns_error(tmp_path):
    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--out",
            str(out_path),
            "--column-map",
            str(tmp_path / "does_not_exist.json"),
        ]
    )

    assert exit_code == 1


def test_analyze_deals_unknown_column_map_key_returns_error(tmp_path):
    bad_map = tmp_path / "bad_map.json"
    bad_map.write_text('{"foo": "Bar"}', encoding="utf-8")

    out_path = tmp_path / "deals_report.md"
    exit_code = main(
        [
            "analyze-deals",
            str(FIXTURES / "custom_header_deals.csv"),
            "--out",
            str(out_path),
            "--column-map",
            str(bad_map),
        ]
    )

    assert exit_code == 1
