from pathlib import Path

import pytest

from trading_lab.csv_deals import DealsParseError, parse_deals_csv

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_comma_delimited_csv():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    assert len(parsed.deals) == 30
    assert parsed.deals[0].profit == pytest.approx(50.00)
    assert parsed.deals[0].symbol == "EURUSD"


def test_parses_semicolon_delimited_csv_with_decimal_commas():
    parsed = parse_deals_csv(FIXTURES / "semicolon_deals.csv")
    # 6 closed positions; the 6 "in" (position-opening) rows are skipped.
    assert len(parsed.deals) == 6
    assert parsed.deals[0].profit == pytest.approx(50.00)
    assert parsed.deals[0].commission == pytest.approx(-2.00)
    assert parsed.deals[0].volume == pytest.approx(1.50)
    assert any("opening" in w.lower() for w in parsed.warnings)


def test_handles_utf8_bom(tmp_path):
    content = "Time,Symbol,Profit\n2024.01.01,EURUSD,50.00\n2024.01.02,EURUSD,-20.00\n"
    bom_path = tmp_path / "bom_deals.csv"
    bom_path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

    parsed = parse_deals_csv(bom_path)
    assert len(parsed.deals) == 2
    assert parsed.deals[0].profit == pytest.approx(50.00)


def test_missing_commission_and_swap_columns_warn(tmp_path):
    csv_path = tmp_path / "minimal.csv"
    csv_path.write_text("Symbol,Profit\nEURUSD,50.00\nEURUSD,-20.00\n", encoding="utf-8")

    parsed = parse_deals_csv(csv_path)
    assert len(parsed.deals) == 2
    assert any("commission" in w.lower() for w in parsed.warnings)
    assert any("swap" in w.lower() for w in parsed.warnings)


def test_empty_csv_is_rejected(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(DealsParseError):
        parse_deals_csv(csv_path)


def test_missing_profit_column_is_rejected(tmp_path):
    csv_path = tmp_path / "no_profit.csv"
    csv_path.write_text("Time,Symbol,Volume\n2024.01.01,EURUSD,0.10\n", encoding="utf-8")

    with pytest.raises(DealsParseError):
        parse_deals_csv(csv_path)


def test_malformed_profit_value_is_rejected(tmp_path):
    csv_path = tmp_path / "bad_profit.csv"
    csv_path.write_text("Symbol,Profit\nEURUSD,not-a-number\n", encoding="utf-8")

    with pytest.raises(DealsParseError):
        parse_deals_csv(csv_path)


def test_no_closed_deal_rows_is_rejected(tmp_path):
    csv_path = tmp_path / "all_opening.csv"
    csv_path.write_text(
        "Symbol,Profit,Entry\nEURUSD,0.00,in\nEURUSD,0.00,in\n",
        encoding="utf-8",
    )

    with pytest.raises(DealsParseError):
        parse_deals_csv(csv_path)
