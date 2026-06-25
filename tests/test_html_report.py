from pathlib import Path

import pytest

from trading_lab.html_report import ReportParseError, parse_html_report, parse_value

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_plain_numbers():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    assert report.get("total_net_profit").amount() == pytest.approx(1234.56)
    assert report.get("profit_factor").amount() == pytest.approx(1.85)
    assert report.get("initial_deposit").amount() == pytest.approx(10000.00)


def test_parses_amount_then_percent():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    field = report.get("balance_drawdown_maximal")
    assert field.amount() == pytest.approx(500.00)
    assert field.percent() == pytest.approx(5.00)


def test_parses_percent_then_amount():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    field = report.get("balance_drawdown_relative")
    assert field.percent() == pytest.approx(5.71)
    assert field.amount() == pytest.approx(500.00)


def test_parses_count_then_percent():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    field = report.get("profit_trades_of_total")
    assert field.amount() == pytest.approx(58)
    assert field.percent() == pytest.approx(58.00)


def test_text_only_fields_are_preserved():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    assert report.text("symbol") == "EURUSD,H1"
    assert report.text("period") == "2023.01.01 - 2023.12.31"


def test_negative_amount_in_parentheses():
    report = parse_html_report(FIXTURES / "sample_strategy_tester_report.htm")
    field = report.get("maximum_consecutive_losses")
    assert field.primary == pytest.approx(4)
    assert field.secondary == pytest.approx(-360.00)


def test_raises_on_unrecognizable_file(tmp_path):
    bogus = tmp_path / "not_a_report.htm"
    bogus.write_text("<html><body><p>hello world</p></body></html>", encoding="utf-8")
    with pytest.raises(ReportParseError):
        parse_html_report(bogus)


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_html_report(tmp_path / "missing.htm")


@pytest.mark.parametrize(
    "raw,primary,primary_pct,secondary,secondary_pct",
    [
        ("1 234.56", 1234.56, False, None, False),
        ("500.00 (5.00%)", 500.00, False, 5.00, True),
        ("5.71% (500.00)", 5.71, True, 500.00, False),
        ("-360.00 (4)", -360.00, False, 4, False),
        ("1,234.56", 1234.56, False, None, False),
    ],
)
def test_parse_value_variants(raw, primary, primary_pct, secondary, secondary_pct):
    parsed = parse_value(raw)
    assert parsed.primary == pytest.approx(primary)
    assert parsed.primary_is_percent is primary_pct
    if secondary is None:
        assert parsed.secondary is None
    else:
        assert parsed.secondary == pytest.approx(secondary)
    assert parsed.secondary_is_percent is secondary_pct
