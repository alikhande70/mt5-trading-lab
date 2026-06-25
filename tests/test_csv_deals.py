from pathlib import Path

import pytest

from trading_lab.csv_deals import DealsParseError, load_column_map, parse_deals_csv

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


def test_balance_and_deposit_rows_are_not_counted_as_trades(tmp_path):
    csv_path = tmp_path / "with_balance.csv"
    csv_path.write_text(
        "Time,Type,Symbol,Profit,Entry\n"
        "2024.01.01 00:00:00,balance,,10000.00,\n"
        "2024.01.02 00:00:00,deposit,,500.00,\n"
        "2024.01.03 09:00:00,buy,EURUSD,50.00,out\n"
        "2024.01.04 09:00:00,sell,EURUSD,-20.00,out\n",
        encoding="utf-8",
    )

    parsed = parse_deals_csv(csv_path)
    assert len(parsed.deals) == 2
    assert {d.profit for d in parsed.deals} == {50.00, -20.00}
    assert any("non-trade history row" in w.lower() for w in parsed.warnings)


def test_credit_and_withdrawal_rows_are_not_counted_as_trades(tmp_path):
    csv_path = tmp_path / "with_credit.csv"
    csv_path.write_text(
        "Time,Type,Symbol,Profit,Entry\n"
        "2024.01.01 00:00:00,credit,,100.00,\n"
        "2024.01.02 00:00:00,withdrawal,,-200.00,\n"
        "2024.01.03 09:00:00,buy,EURUSD,30.00,out\n",
        encoding="utf-8",
    )

    parsed = parse_deals_csv(csv_path)
    assert len(parsed.deals) == 1
    assert parsed.deals[0].profit == pytest.approx(30.00)
    assert any("non-trade history row" in w.lower() for w in parsed.warnings)


def test_commission_and_fee_only_rows_are_not_counted_as_trades(tmp_path):
    csv_path = tmp_path / "with_fees.csv"
    csv_path.write_text(
        "Time,Type,Symbol,Profit,Entry\n"
        "2024.01.01 00:00:00,commission,,-5.00,\n"
        "2024.01.02 00:00:00,monthly fee,,-1.00,\n"
        "2024.01.03 00:00:00,daily interest,,0.50,\n"
        "2024.01.04 09:00:00,buy,EURUSD,40.00,out\n",
        encoding="utf-8",
    )

    parsed = parse_deals_csv(csv_path)
    assert len(parsed.deals) == 1
    assert parsed.deals[0].profit == pytest.approx(40.00)
    assert any("non-trade history row" in w.lower() for w in parsed.warnings)


def test_normal_buy_sell_out_rows_are_still_counted_correctly(tmp_path):
    csv_path = tmp_path / "normal_trades.csv"
    csv_path.write_text(
        "Time,Type,Symbol,Profit,Entry\n"
        "2024.01.01 09:00:00,buy,EURUSD,0.00,in\n"
        "2024.01.01 10:00:00,buy,EURUSD,50.00,out\n"
        "2024.01.02 09:00:00,sell,EURUSD,0.00,in\n"
        "2024.01.02 10:00:00,sell,EURUSD,-20.00,out\n",
        encoding="utf-8",
    )

    parsed = parse_deals_csv(csv_path)
    assert len(parsed.deals) == 2
    assert parsed.deals[0].profit == pytest.approx(50.00)
    assert parsed.deals[1].profit == pytest.approx(-20.00)


def test_all_non_trade_rows_is_rejected(tmp_path):
    csv_path = tmp_path / "all_non_trade.csv"
    csv_path.write_text(
        "Time,Type,Symbol,Profit,Entry\n"
        "2024.01.01 00:00:00,balance,,10000.00,\n"
        "2024.01.02 00:00:00,deposit,,500.00,\n"
        "2024.01.03 00:00:00,credit,,50.00,\n"
        "2024.01.04 00:00:00,withdrawal,,-100.00,\n",
        encoding="utf-8",
    )

    with pytest.raises(DealsParseError):
        parse_deals_csv(csv_path)


def test_load_column_map_reads_valid_file():
    column_map = load_column_map(FIXTURES / "custom_header_column_map.json")
    assert column_map == {
        "time": "Close Time",
        "symbol": "Instrument",
        "volume": "Lots",
        "type": "Operation",
        "entry": "Entry Type",
        "profit": "Result",
        "commission": "Fee",
        "swap": "Overnight",
        "comment": "Note",
    }


def test_load_column_map_rejects_missing_file(tmp_path):
    with pytest.raises(DealsParseError):
        load_column_map(tmp_path / "does_not_exist.json")


def test_load_column_map_rejects_invalid_json(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(DealsParseError):
        load_column_map(bad_json)


def test_load_column_map_rejects_unknown_canonical_key(tmp_path):
    bad_map = tmp_path / "unknown_key.json"
    bad_map.write_text('{"profit": "Result", "foo": "Bar"}', encoding="utf-8")

    with pytest.raises(DealsParseError):
        load_column_map(bad_map)


def test_parse_deals_csv_rejects_unknown_canonical_key_in_overrides():
    with pytest.raises(DealsParseError):
        parse_deals_csv(
            FIXTURES / "custom_header_deals.csv",
            column_overrides={"foo": "Result"},
        )


def test_custom_header_csv_without_column_map_is_rejected():
    # "Result" isn't one of the built-in profit aliases, so without an
    # override the parser correctly has no usable profit column.
    with pytest.raises(DealsParseError):
        parse_deals_csv(FIXTURES / "custom_header_deals.csv")


def test_column_map_resolves_non_standard_headers():
    column_map = load_column_map(FIXTURES / "custom_header_column_map.json")
    parsed = parse_deals_csv(FIXTURES / "custom_header_deals.csv", column_overrides=column_map)

    # Full column map (profit + type + entry all mapped): only real closed
    # trades are counted, same as the built-in-alias path.
    assert len(parsed.deals) == 2
    assert {d.profit for d in parsed.deals} == {50.00, -20.00}
    assert parsed.deals[0].commission == pytest.approx(-2.00)
    assert parsed.deals[0].swap == pytest.approx(-0.50)
    assert parsed.deals[0].comment == "Closed in profit"
    assert any("non-trade history row" in w.lower() for w in parsed.warnings)
    assert any("position-opening" in w.lower() for w in parsed.warnings)
    assert not any("filtering is unavailable" in w.lower() for w in parsed.warnings)


def test_direct_column_override_resolves_custom_profit_header():
    # Only overriding "profit" leaves type/entry unrecognized, so every row
    # with a profit value is counted (no type/entry-based filtering) —
    # including the "balance" row. This must NOT happen silently: both a
    # type/entry-filtering warning and a suspicious-unmapped-header warning
    # (for "Operation" and "Entry Type") are required.
    parsed = parse_deals_csv(
        FIXTURES / "custom_header_deals.csv",
        column_overrides={"profit": "Result"},
    )
    assert len(parsed.deals) == 5
    assert {d.profit for d in parsed.deals} == {5000.00, 0.00, 50.00, -20.00}
    assert any("filtering is unavailable" in w.lower() for w in parsed.warnings)
    assert any(
        "operation" in w.lower() and "entry type" in w.lower() for w in parsed.warnings
    )


def test_full_direct_overrides_for_profit_type_entry_count_only_closed_trades():
    # Mapping profit + type + entry directly (as --profit-column/--type-column/
    # --entry-column would) restores full filtering: only real closed trades
    # are counted, and the "filtering is unavailable" warning is not emitted.
    parsed = parse_deals_csv(
        FIXTURES / "custom_header_deals.csv",
        column_overrides={
            "profit": "Result",
            "type": "Operation",
            "entry": "Entry Type",
        },
    )
    assert len(parsed.deals) == 2
    assert {d.profit for d in parsed.deals} == {50.00, -20.00}
    assert not any("filtering is unavailable" in w.lower() for w in parsed.warnings)
    assert any("non-trade history row" in w.lower() for w in parsed.warnings)


def test_built_in_aliases_still_work_without_column_overrides():
    parsed = parse_deals_csv(FIXTURES / "sample_deals.csv")
    assert len(parsed.deals) == 30
    assert not any("filtering is unavailable" in w.lower() for w in parsed.warnings)


def test_unmapped_operation_header_warns_even_without_column_overrides(tmp_path):
    # No column_overrides at all here — "Operation" simply isn't a built-in
    # alias. The suspicious-unmapped-header warning must still fire, since
    # this is exactly the kind of column whose absence lets non-trade rows
    # (like "balance" below) get counted as closed trades.
    csv_path = tmp_path / "operation_unmapped.csv"
    csv_path.write_text(
        "Time,Operation,Symbol,Profit\n"
        "2024.01.01 00:00:00,balance,,10000.00\n"
        "2024.01.02 09:00:00,buy,EURUSD,50.00\n",
        encoding="utf-8",
    )

    parsed = parse_deals_csv(csv_path)
    assert len(parsed.deals) == 2
    assert any("operation" in w.lower() for w in parsed.warnings)
