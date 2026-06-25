"""Parser for MetaTrader 5 Strategy Tester / History "Deals" CSV exports.

MT5 lets a user export their closed-trade history as CSV from the terminal's
History tab or the Strategy Tester's Deals tab. Column names, delimiter, and
number formatting vary by broker, terminal language, and export method, so
this module normalizes a handful of common variants rather than assuming one
fixed layout. For exports whose headers don't match any built-in alias, a
caller can pass ``column_overrides`` (canonical field name -> exact CSV
header label) to ``parse_deals_csv``, optionally loaded from a JSON file via
``load_column_map``. ``inspect_deals_csv_columns`` resolves a CSV's header
the same way without parsing any deal rows, for debugging a column layout
before running the full analysis. ``classify_deals_csv_rows`` goes one level
deeper and classifies every data row (counted as a closed trade, skipped for
a specific reason, or flagged as a malformed-profit error) using the same
per-row logic ``parse_deals_csv`` itself uses, so the two can never drift
apart on what counts as a closed trade. Only the standard library (``csv``,
``json``) is used, consistent with the project's zero-runtime-dependency
design.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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


@dataclass(frozen=True)
class ColumnResolution:
    raw_header: str
    canonical_field: Optional[str]
    source: str  # "built-in alias" | "column-map" | "direct override" | "unmapped"


@dataclass(frozen=True)
class ColumnInspection:
    path: Path
    delimiter: str
    columns: List[ColumnResolution]
    warnings: List[str] = field(default_factory=list)
    suggested_next_action: str = ""


# Row classification decisions. Every data row in a deals CSV ends up with
# exactly one of these, from both `parse_deals_csv` and
# `classify_deals_csv_rows` (they share the same per-row logic).
COUNT_CLOSED_TRADE = "COUNT_CLOSED_TRADE"
SKIP_NON_TRADE = "SKIP_NON_TRADE"
SKIP_OPENING_ENTRY = "SKIP_OPENING_ENTRY"
SKIP_MISSING_PROFIT = "SKIP_MISSING_PROFIT"
SKIP_INCOMPLETE_ROW = "SKIP_INCOMPLETE_ROW"
ERROR_MALFORMED_PROFIT = "ERROR_MALFORMED_PROFIT"


@dataclass(frozen=True)
class RowClassification:
    row_number: int
    decision: str
    reason: str
    profit_raw: Optional[str] = None
    profit_value: Optional[float] = None
    type_raw: Optional[str] = None
    entry_raw: Optional[str] = None
    symbol: Optional[str] = None
    volume: Optional[float] = None
    warning: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class RowClassificationSummary:
    total_data_rows: int
    counted_rows: int
    skipped_non_trade_rows: int
    skipped_opening_rows: int
    skipped_missing_profit_rows: int
    malformed_profit_rows: int
    incomplete_rows: int
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RowClassificationResult:
    path: Path
    delimiter: str
    rows: List[RowClassification]
    summary: RowClassificationSummary
    suggested_next_action: str = ""


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


# Canonical field names that a column map / CLI override is allowed to
# target. Kept identical to the canonical values produced by
# `_CANONICAL_BY_ALIAS` above; anything else is rejected with a clear error
# rather than silently ignored.
CANONICAL_TARGETS = frozenset(
    {
        "time",
        "type",
        "symbol",
        "volume",
        "profit",
        "commission",
        "swap",
        "ticket",
        "order",
        "deal",
        "entry",
        "comment",
    }
)


def load_column_map(path) -> Dict[str, str]:
    """Load a JSON column map file: canonical field name -> CSV header label."""
    path = Path(path)
    if not path.exists():
        raise DealsParseError(f"Column map file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise DealsParseError(f"Column map file {path} is not valid UTF-8 text.") from exc
    except json.JSONDecodeError as exc:
        raise DealsParseError(f"Column map file {path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise DealsParseError(
            f"Column map file {path} must contain a JSON object mapping canonical "
            "field names to CSV header labels."
        )

    column_map: Dict[str, str] = {}
    for key, value in data.items():
        if key not in CANONICAL_TARGETS:
            raise DealsParseError(
                f"Unknown canonical column name {key!r} in column map {path}. "
                f"Expected one of: {', '.join(sorted(CANONICAL_TARGETS))}."
            )
        if not isinstance(value, str) or not value.strip():
            raise DealsParseError(
                f"Column map entry {key!r} in {path} must be a non-empty string header label."
            )
        column_map[key] = value
    return column_map


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


# Header slugs that strongly suggest a deal-type/entry-direction column
# (e.g. a broker's "Operation" or "Entry Type" header) even though they
# don't match any built-in alias or column override. Used to warn when such
# a header is left unmapped, since without it non-trade history rows
# (balance/deposit/credit/fee/...) can't be filtered out.
_SUSPICIOUS_TYPE_ENTRY_SLUGS = {
    "type",
    "entry",
    "operation",
    "entry_type",
    "direction",
    "deal_type",
    "order_type",
}


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


def _read_csv_rows(path: Path) -> Tuple[str, List[List[str]]]:
    """Read a deals CSV's delimiter and rows. Shared by `parse_deals_csv` and
    `inspect_deals_csv_columns` so delimiter/encoding handling stays in one place."""
    text = _read_text(path)

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise DealsParseError("The CSV file is empty.")

    delimiter = _detect_delimiter(lines[0])
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise DealsParseError("The CSV file is empty.")
    return delimiter, rows


def _slugify_overrides(overrides: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Validate a canonical-field -> header-label dict and slugify it to
    header-slug -> canonical-field, for matching against slugified CSV headers."""
    by_slug: Dict[str, str] = {}
    for canonical, label in (overrides or {}).items():
        if canonical not in CANONICAL_TARGETS:
            raise DealsParseError(
                f"Unknown canonical column name {canonical!r} in column overrides. "
                f"Expected one of: {', '.join(sorted(CANONICAL_TARGETS))}."
            )
        by_slug[_slugify(label)] = canonical
    return by_slug


def _find_suspicious_unmapped_headers(
    header: List[str], canonical_header: List[Optional[str]]
) -> List[str]:
    return [
        col
        for col, canonical in zip(header, canonical_header)
        if canonical is None and _slugify(col) in _SUSPICIOUS_TYPE_ENTRY_SLUGS
    ]


def _resolve_canonical_header(
    header: List[str], column_overrides: Optional[Dict[str, str]]
) -> Tuple[List[Optional[str]], bool, bool, List[str]]:
    """Resolve a CSV header to canonical field names using column_overrides
    (column-map and/or direct --*-column flags, already merged by the
    caller) over the built-in alias table. Shared by `parse_deals_csv` and
    `classify_deals_csv_rows` so both apply identical precedence.
    """
    override_by_slug = _slugify_overrides(column_overrides)
    canonical_header = [
        override_by_slug.get(_slugify(col)) or _CANONICAL_BY_ALIAS.get(_slugify(col))
        for col in header
    ]
    has_type_column = "type" in canonical_header
    has_entry_column = "entry" in canonical_header
    suspicious_unmapped_headers = _find_suspicious_unmapped_headers(header, canonical_header)
    return canonical_header, has_type_column, has_entry_column, suspicious_unmapped_headers


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


def _classify_row(
    row_number: int,
    raw_row: List[str],
    header: List[str],
    canonical_header: List[Optional[str]],
    has_type_column: bool,
    has_entry_column: bool,
) -> Tuple[RowClassification, Dict[str, str]]:
    """Classify a single data row: counted as a closed trade, skipped for a
    specific reason, or flagged as a malformed-profit error. Returns the
    classification plus the canonical-field record built along the way, so
    `parse_deals_csv` can build a `Deal` from it without re-deriving the
    record. Shared by `parse_deals_csv` and `classify_deals_csv_rows` so the
    two can never drift apart on what counts as a closed trade.
    """
    if len(raw_row) < len(header):
        return (
            RowClassification(
                row_number=row_number,
                decision=SKIP_INCOMPLETE_ROW,
                reason="Row has fewer columns than the header; skipped as incomplete.",
            ),
            {},
        )

    record: Dict[str, str] = {}
    for col_name, value in zip(canonical_header, raw_row):
        if col_name and col_name not in record:
            record[col_name] = value.strip()

    type_raw = record.get("type") or None
    entry_raw = record.get("entry") or None
    symbol = record.get("symbol") or None
    volume = _to_float(record.get("volume"))

    # Non-trade account operations (balance/deposit/withdrawal/credit/fee/...)
    # are filtered out before profit parsing, since MT5 history exports often
    # put a real dollar amount in the Profit column for these rows too.
    if has_type_column and _is_non_trade_type(record.get("type", "")):
        return (
            RowClassification(
                row_number=row_number,
                decision=SKIP_NON_TRADE,
                reason="Type is a non-trade account operation (balance/deposit/credit/fee/...).",
                profit_raw=record.get("profit") or None,
                type_raw=type_raw,
                entry_raw=entry_raw,
                symbol=symbol,
                volume=volume,
            ),
            record,
        )

    if has_entry_column and _slugify(record.get("entry", "")) == "in":
        return (
            RowClassification(
                row_number=row_number,
                decision=SKIP_OPENING_ENTRY,
                reason="Entry is 'in' (position-opening); never carries a realized profit.",
                profit_raw=record.get("profit") or None,
                type_raw=type_raw,
                entry_raw=entry_raw,
                symbol=symbol,
                volume=volume,
            ),
            record,
        )

    profit_raw = record.get("profit", "")
    if profit_raw == "":
        return (
            RowClassification(
                row_number=row_number,
                decision=SKIP_MISSING_PROFIT,
                reason=(
                    "No profit value on this row (e.g. a totals/footer line, or the "
                    "profit column isn't mapped)."
                ),
                type_raw=type_raw,
                entry_raw=entry_raw,
                symbol=symbol,
                volume=volume,
            ),
            record,
        )

    profit_value = _to_float(profit_raw)
    if profit_value is None:
        return (
            RowClassification(
                row_number=row_number,
                decision=ERROR_MALFORMED_PROFIT,
                reason="Profit value could not be parsed as a number.",
                profit_raw=profit_raw,
                type_raw=type_raw,
                entry_raw=entry_raw,
                symbol=symbol,
                volume=volume,
                error=f"Row {row_number}: could not parse profit value {profit_raw!r} as a number.",
            ),
            record,
        )

    return (
        RowClassification(
            row_number=row_number,
            decision=COUNT_CLOSED_TRADE,
            reason="Closed trade/deal counted.",
            profit_raw=profit_raw,
            profit_value=profit_value,
            type_raw=type_raw,
            entry_raw=entry_raw,
            symbol=symbol,
            volume=volume,
        ),
        record,
    )


def parse_deals_csv(path, column_overrides: Optional[Dict[str, str]] = None) -> ParsedDeals:
    path = Path(path)
    _delimiter, rows = _read_csv_rows(path)
    header = rows[0]

    # column_overrides (from --column-map and/or direct --*-column flags)
    # take precedence over the built-in alias table, so a broker/locale with
    # non-standard headers can still be parsed without editing the CSV.
    canonical_header, has_type_column, has_entry_column, suspicious_unmapped_headers = (
        _resolve_canonical_header(header, column_overrides)
    )
    if "profit" not in canonical_header:
        raise DealsParseError(
            "No usable profit column was found. Expected a column such as "
            "'Profit', 'P/L', or 'Net Profit', or pass --column-map / --profit-column "
            "for a non-standard header."
        )

    skipped_opening_deals = 0
    skipped_non_trade_rows = 0
    deals: List[Deal] = []

    for offset, raw_row in enumerate(rows[1:]):
        row_number = offset + 2
        classification, record = _classify_row(
            row_number, raw_row, header, canonical_header, has_type_column, has_entry_column
        )

        if classification.decision == SKIP_INCOMPLETE_ROW:
            continue  # tolerate stray short/blank trailing rows
        if classification.decision == SKIP_NON_TRADE:
            skipped_non_trade_rows += 1
            continue
        if classification.decision == SKIP_OPENING_ENTRY:
            skipped_opening_deals += 1
            continue  # position-opening deal; never carries a realized profit
        if classification.decision == SKIP_MISSING_PROFIT:
            continue  # no profit on this row (e.g. a totals/footer line)
        if classification.decision == ERROR_MALFORMED_PROFIT:
            raise DealsParseError(classification.error)

        deals.append(
            Deal(
                profit=classification.profit_value,
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
    if column_overrides and not has_type_column and not has_entry_column:
        warnings.append(
            "Only the profit column is mapped; type/entry filtering is unavailable, "
            "so non-trade history rows may be counted unless the CSV contains closed "
            "trades only."
        )
    if suspicious_unmapped_headers:
        labels = ", ".join(repr(col) for col in suspicious_unmapped_headers)
        warnings.append(
            f"Column(s) {labels} look like a deal type/entry column but are not mapped "
            "to 'type' or 'entry'; map them via --column-map or --type-column/"
            "--entry-column, or non-trade history rows may be counted as closed trades."
        )
    if "commission" not in canonical_header:
        warnings.append("No commission column found; commission is not reflected in net profit.")
    if "swap" not in canonical_header:
        warnings.append("No swap column found; swap is not reflected in net profit.")

    return ParsedDeals(deals=deals, warnings=warnings)


def _resolve_override_sources(
    column_map_overrides: Optional[Dict[str, str]],
    direct_overrides: Optional[Dict[str, str]],
) -> Dict[str, Tuple[str, str]]:
    """Header-slug -> (canonical_field, source) for explicit overrides.

    Mirrors the precedence `cli.py` uses when calling `parse_deals_csv`: both
    override sets are merged by canonical field name first (direct overrides
    replace the column-map's label for the same canonical field), so a
    column targeted by both ends up attributed only to "direct override".
    """
    by_canonical: Dict[str, Tuple[str, str]] = {}
    for source, overrides in (
        ("column-map", column_map_overrides),
        ("direct override", direct_overrides),
    ):
        for canonical, label in (overrides or {}).items():
            if canonical not in CANONICAL_TARGETS:
                raise DealsParseError(
                    f"Unknown canonical column name {canonical!r} in column overrides. "
                    f"Expected one of: {', '.join(sorted(CANONICAL_TARGETS))}."
                )
            by_canonical[canonical] = (label, source)

    return {
        _slugify(label): (canonical, source) for canonical, (label, source) in by_canonical.items()
    }


def inspect_deals_csv_columns(
    path,
    column_map_overrides: Optional[Dict[str, str]] = None,
    direct_overrides: Optional[Dict[str, str]] = None,
) -> ColumnInspection:
    """Inspect a deals CSV's header only: how each raw column resolves to a
    canonical field, and why. Used by `analyze-deals --list-columns` to debug
    a column layout before running the full analysis; never parses deal rows
    or computes metrics.
    """
    path = Path(path)
    delimiter, rows = _read_csv_rows(path)
    header = rows[0]

    override_by_slug = _resolve_override_sources(column_map_overrides, direct_overrides)

    columns: List[ColumnResolution] = []
    canonical_header: List[Optional[str]] = []
    for col in header:
        slug = _slugify(col)
        if slug in override_by_slug:
            canonical, source = override_by_slug[slug]
        elif slug in _CANONICAL_BY_ALIAS:
            canonical, source = _CANONICAL_BY_ALIAS[slug], "built-in alias"
        else:
            canonical, source = None, "unmapped"
        canonical_header.append(canonical)
        columns.append(ColumnResolution(raw_header=col, canonical_field=canonical, source=source))

    has_profit = "profit" in canonical_header
    has_type = "type" in canonical_header
    has_entry = "entry" in canonical_header

    warnings: List[str] = []
    if not has_profit:
        warnings.append(
            "No profit column was resolved; map it via --column-map or --profit-column "
            "before running the full analysis."
        )
    if not has_type and not has_entry:
        warnings.append(
            "Type and entry columns are not mapped; non-trade history rows may be "
            "counted as closed trades unless the CSV contains closed trades only."
        )

    suspicious_unmapped_headers = _find_suspicious_unmapped_headers(header, canonical_header)
    if suspicious_unmapped_headers:
        labels = ", ".join(repr(col) for col in suspicious_unmapped_headers)
        warnings.append(
            f"Column(s) {labels} look like a deal type/entry column but are not mapped "
            "to 'type' or 'entry'; map them via --column-map or --type-column/"
            "--entry-column, or non-trade history rows may be counted as closed trades."
        )

    if not has_profit:
        suggested_next_action = (
            "Map the profit column via --column-map or --profit-column, then re-run "
            "with --list-columns to confirm."
        )
    elif warnings:
        suggested_next_action = (
            "Review the warnings above, map any missing columns via --column-map or "
            "the --*-column flags, then run analyze-deals without --list-columns."
        )
    else:
        suggested_next_action = "Run analyze-deals without --list-columns to generate the report."

    return ColumnInspection(
        path=path,
        delimiter=delimiter,
        columns=columns,
        warnings=warnings,
        suggested_next_action=suggested_next_action,
    )


def classify_deals_csv_rows(
    path,
    column_overrides: Optional[Dict[str, str]] = None,
    max_rows: Optional[int] = None,
) -> RowClassificationResult:
    """Classify every data row in a deals CSV: counted as a closed trade,
    skipped for a specific reason, or flagged as a malformed-profit error.
    Used by `analyze-deals --preview-rows` to show exactly how each row would
    be treated before trusting the full analysis. Reuses `_classify_row` —
    the same function `parse_deals_csv` uses — so the two can never drift
    apart on what counts as a closed trade.
    """
    path = Path(path)
    delimiter, rows = _read_csv_rows(path)
    header = rows[0]

    canonical_header, has_type_column, has_entry_column, suspicious_unmapped_headers = (
        _resolve_canonical_header(header, column_overrides)
    )

    data_rows = rows[1:]
    if max_rows is not None:
        data_rows = data_rows[:max_rows]

    classifications: List[RowClassification] = []
    for offset, raw_row in enumerate(data_rows):
        row_number = offset + 2
        classification, _record = _classify_row(
            row_number, raw_row, header, canonical_header, has_type_column, has_entry_column
        )
        classifications.append(classification)

    def _count(decision: str) -> int:
        return sum(1 for c in classifications if c.decision == decision)

    counted_rows = _count(COUNT_CLOSED_TRADE)
    malformed_profit_rows = _count(ERROR_MALFORMED_PROFIT)

    warnings: List[str] = []
    if "profit" not in canonical_header:
        warnings.append(
            "No profit column was resolved; every row is classified as "
            "SKIP_MISSING_PROFIT until profit is mapped via --column-map or --profit-column."
        )
    if column_overrides and not has_type_column and not has_entry_column:
        warnings.append(
            "Only the profit column is mapped; type/entry filtering is unavailable, "
            "so non-trade history rows may be classified as closed trades unless the "
            "CSV contains closed trades only."
        )
    if suspicious_unmapped_headers:
        labels = ", ".join(repr(col) for col in suspicious_unmapped_headers)
        warnings.append(
            f"Column(s) {labels} look like a deal type/entry column but are not mapped "
            "to 'type' or 'entry'; map them via --column-map or --type-column/"
            "--entry-column, or non-trade history rows may be classified as closed trades."
        )

    errors = [c.error for c in classifications if c.error]

    summary = RowClassificationSummary(
        total_data_rows=len(classifications),
        counted_rows=counted_rows,
        skipped_non_trade_rows=_count(SKIP_NON_TRADE),
        skipped_opening_rows=_count(SKIP_OPENING_ENTRY),
        skipped_missing_profit_rows=_count(SKIP_MISSING_PROFIT),
        malformed_profit_rows=malformed_profit_rows,
        incomplete_rows=_count(SKIP_INCOMPLETE_ROW),
        warnings=warnings,
        errors=errors,
    )

    if malformed_profit_rows:
        suggested_next_action = (
            "Fix or remap the profit column for the malformed row(s) above, then re-run "
            "analyze-deals."
        )
    elif counted_rows == 0:
        suggested_next_action = (
            "No closed trades were counted; review the skipped rows above and your "
            "column mapping before running analyze-deals."
        )
    else:
        suggested_next_action = (
            "If the counted/skipped rows look correct, run analyze-deals without --preview-rows."
        )

    return RowClassificationResult(
        path=path,
        delimiter=delimiter,
        rows=classifications,
        summary=summary,
        suggested_next_action=suggested_next_action,
    )
