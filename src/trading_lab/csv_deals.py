"""Parser for MetaTrader 5 Strategy Tester / History "Deals" CSV exports.

MT5 lets a user export their closed-trade history as CSV from the terminal's
History tab or the Strategy Tester's Deals tab. Column names, delimiter, and
number formatting vary by broker, terminal language, and export method, so
this module normalizes a handful of common variants rather than assuming one
fixed layout. Only the standard library ``csv`` module is used, consistent
with the project's zero-runtime-dependency design.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


class DealsParseError(ValueError):
    """Raised when a CSV file does not look like a usable MT5 deals export."""


@dataclass(frozen=True)
class Deal:
    profit: float
    commission: Optional[float] = None
    swap: Optional[float] = None
    symbol: Optional[str] = None
    volume: Optional[float] = None
    comment: Optional[str] = None


@dataclass(frozen=True)
class ParsedDeals:
    deals: List[Deal]
    warnings: List[str] = field(default_factory=list)


# Slugified header variant -> canonical field name.
_CANONICAL_BY_ALIAS: Dict[str, str] = {
    "time": "time",
    "date": "time",
    "open_time": "time",
    "close_time": "time",
    "type": "type",
    "deal_type": "type",
    "order_type": "type",
    "symbol": "symbol",
    "instrument": "symbol",
    "volume": "volume",
    "size": "volume",
    "lots": "volume",
    "lot": "volume",
    "price": "price",
    "open_price": "price",
    "close_price": "price",
    "profit": "profit",
    "net_profit": "profit",
    "p_l": "profit",
    "pnl": "profit",
    "profit_usd": "profit",
    "commission": "commission",
    "comm": "commission",
    "swap": "swap",
    "ticket": "ticket",
    "order": "order",
    "deal": "deal",
    "entry": "entry",
    "direction": "entry",
    "comment": "comment",
    "balance": "balance",
}


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower())
    return slug.strip("_")


# Type-column values that mark a history row as a non-trade account
# operation (deposits, withdrawals, broker credits/fees, ...) rather than a
# closed trade/deal. Matched as whole tokens of the slugified value so that
# e.g. "Daily Interest" or "Monthly fee" are caught without false-matching
# trade types such as "buy limit".
_NON_TRADE_TYPE_TOKENS = {
    "balance",
    "deposit",
    "withdrawal",
    "credit",
    "correction",
    "charge",
    "commission",
    "daily",
    "monthly",
    "fee",
    "tax",
    "dividend",
    "interest",
}


def _is_non_trade_type(type_value: str) -> bool:
    slug = _slugify(type_value)
    if not slug:
        return False
    return bool(set(slug.split("_")) & _NON_TRADE_TYPE_TOKENS)


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    for encoding in ("utf-8", "windows-1252", "windows-1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _detect_delimiter(header_line: str) -> str:
    # Counted on the header row only, since it holds plain labels rather than
    # numbers, so this is unaffected by thousands separators in the data rows.
    return ";" if header_line.count(";") > header_line.count(",") else ","


_THOUSANDS_COMMA_RE = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_THOUSANDS_DOT_RE = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$")
_COMMA_DECIMAL_RE = re.compile(r"^-?\d+,\d{1,2}$")


def _to_float(token: Optional[str]) -> Optional[float]:
    if token is None:
        return None
    token = token.strip().replace("\xa0", "").replace(" ", "")
    if not token:
        return None
    if _THOUSANDS_COMMA_RE.match(token):
        token = token.replace(",", "")
    elif _THOUSANDS_DOT_RE.match(token):
        token = token.replace(".", "").replace(",", ".")
    elif _COMMA_DECIMAL_RE.match(token):
        token = token.replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def parse_deals_csv(path) -> ParsedDeals:
    path = Path(path)
    text = _read_text(path)

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise DealsParseError("The CSV file is empty.")

    delimiter = _detect_delimiter(lines[0])
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise DealsParseError("The CSV file is empty.")

    header = rows[0]
    canonical_header = [_CANONICAL_BY_ALIAS.get(_slugify(col)) for col in header]
    if "profit" not in canonical_header:
        raise DealsParseError(
            "No usable profit column was found. Expected a column such as "
            "'Profit', 'P/L', or 'Net Profit'."
        )

    has_type_column = "type" in canonical_header
    has_entry_column = "entry" in canonical_header
    skipped_opening_deals = 0
    skipped_non_trade_rows = 0
    deals: List[Deal] = []

    for row_index, raw_row in enumerate(rows[1:], start=2):
        if len(raw_row) < len(header):
            continue  # tolerate stray short/blank trailing rows

        record: Dict[str, str] = {}
        for col_name, value in zip(canonical_header, raw_row):
            if col_name and col_name not in record:
                record[col_name] = value.strip()

        # Non-trade account operations (balance/deposit/withdrawal/credit/fee/...)
        # are filtered out before profit parsing, since MT5 history exports often
        # put a real dollar amount in the Profit column for these rows too.
        if has_type_column and _is_non_trade_type(record.get("type", "")):
            skipped_non_trade_rows += 1
            continue

        if has_entry_column and _slugify(record.get("entry", "")) == "in":
            skipped_opening_deals += 1
            continue  # position-opening deal; never carries a realized profit

        profit_raw = record.get("profit", "")
        if profit_raw == "":
            continue  # no profit on this row (e.g. a totals/footer line)

        profit_value = _to_float(profit_raw)
        if profit_value is None:
            raise DealsParseError(
                f"Row {row_index}: could not parse profit value {profit_raw!r} as a number."
            )

        deals.append(
            Deal(
                profit=profit_value,
                commission=_to_float(record.get("commission")),
                swap=_to_float(record.get("swap")),
                symbol=record.get("symbol") or None,
                volume=_to_float(record.get("volume")),
                comment=record.get("comment") or None,
            )
        )

    if not deals:
        raise DealsParseError(
            "No closed trade/deal rows with a usable profit value were found in the CSV."
        )

    warnings: List[str] = []
    if skipped_non_trade_rows:
        warnings.append(f"Skipped {skipped_non_trade_rows} non-trade history row(s).")
    if skipped_opening_deals:
        warnings.append(
            f"Skipped {skipped_opening_deals} position-opening ('in') deal row(s); "
            "only closed/closing deals are counted in the metrics below."
        )
    if "commission" not in canonical_header:
        warnings.append("No commission column found; commission is not reflected in net profit.")
    if "swap" not in canonical_header:
        warnings.append("No swap column found; swap is not reflected in net profit.")

    return ParsedDeals(deals=deals, warnings=warnings)
