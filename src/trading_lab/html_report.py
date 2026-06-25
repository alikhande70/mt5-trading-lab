"""Parser for MetaTrader 5 Strategy Tester HTML/HTM report exports.

MT5 renders its "Results" section as plain HTML tables where each row holds
one or more ``Label:`` / value cell pairs (e.g. ``Profit Factor:`` followed by
``1.33``). Some values pack a second number in parentheses, such as
``500.00 (5.00%)`` for an absolute-plus-relative drawdown, or ``58 (58.00%)``
for a trade count plus its percentage of the total. This module turns those
rows into a flat, queryable structure without needing any third-party HTML
library, since the only guarantee we have about the user's machine is a
plain Python install.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional


class ReportParseError(ValueError):
    """Raised when a file does not look like an MT5 Strategy Tester report."""


@dataclass(frozen=True)
class ParsedValue:
    raw: str
    primary: Optional[float] = None
    primary_is_percent: bool = False
    secondary: Optional[float] = None
    secondary_is_percent: bool = False

    def amount(self) -> Optional[float]:
        """The non-percentage component, e.g. the dollar side of "500.00 (5.00%)"."""
        if self.primary is not None and not self.primary_is_percent:
            return self.primary
        if self.secondary is not None and not self.secondary_is_percent:
            return self.secondary
        return self.primary

    def percent(self) -> Optional[float]:
        """The percentage component, e.g. the "5.00%" side of "500.00 (5.00%)"."""
        if self.primary is not None and self.primary_is_percent:
            return self.primary
        if self.secondary is not None and self.secondary_is_percent:
            return self.secondary
        return None


@dataclass(frozen=True)
class ParsedReport:
    fields: Dict[str, ParsedValue]

    def get(self, key: str) -> Optional[ParsedValue]:
        return self.fields.get(key)

    def text(self, key: str) -> Optional[str]:
        field = self.fields.get(key)
        return field.raw if field else None


class _TableCellParser(HTMLParser):
    """Collects every <tr> as a list of its cells' text content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: List[List[str]] = []
        self._current_row: Optional[List[str]] = None
        self._cell_parts: Optional[List[str]] = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._cell_parts = []
        elif tag == "br" and self._cell_parts is not None:
            self._cell_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell_parts is not None:
            text = " ".join("".join(self._cell_parts).split())
            if self._current_row is not None:
                self._current_row.append(text)
            self._cell_parts = None
        elif tag == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)


def _read_html_file(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    # MT5's exported charset depends on the terminal's language, so sniff the
    # declared <meta charset> before falling back to common defaults.
    head = raw[:2048].decode("ascii", errors="ignore").lower()
    match = re.search(r'charset=["\']?([\w-]+)', head)
    if match:
        try:
            return raw.decode(match.group(1))
        except (LookupError, UnicodeDecodeError):
            pass
    for encoding in ("utf-8", "windows-1252", "windows-1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower())
    return slug.strip("_")


def _extract_pairs(rows: List[List[str]]) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    for row in rows:
        i = 0
        n = len(row)
        while i < n:
            cell = row[i].strip()
            if len(cell) > 1 and cell.endswith(":"):
                key = _slugify(cell[:-1])
                if key and i + 1 < n:
                    if key not in pairs:
                        pairs[key] = row[i + 1].strip()
                    i += 2
                    continue
            i += 1
    return pairs


_PAREN_RE = re.compile(r"\(([^()]*)\)\s*$")
_THOUSANDS_RE = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_COMMA_DECIMAL_RE = re.compile(r"^-?\d+,\d{1,2}$")


def _split_primary_secondary(raw: str):
    match = _PAREN_RE.search(raw)
    if not match:
        return raw.strip(), None
    secondary = match.group(1).strip()
    primary = raw[: match.start()].strip()
    return primary, secondary or None


def _to_number(token: str):
    token = token.strip().replace("\xa0", "").replace(" ", "")
    if not token:
        return None, False
    is_percent = token.endswith("%")
    if is_percent:
        token = token[:-1]
    # MT5 number formatting follows the terminal's locale, so thousands and
    # decimal separators vary (e.g. "1,234.56" vs "1234,56").
    if _THOUSANDS_RE.match(token):
        token = token.replace(",", "")
    elif _COMMA_DECIMAL_RE.match(token):
        token = token.replace(",", ".")
    try:
        return float(token), is_percent
    except ValueError:
        return None, is_percent


def parse_value(raw: str) -> ParsedValue:
    primary_text, secondary_text = _split_primary_secondary(raw)
    primary, primary_is_percent = _to_number(primary_text)
    secondary: Optional[float] = None
    secondary_is_percent = False
    if secondary_text is not None:
        secondary, secondary_is_percent = _to_number(secondary_text)
    return ParsedValue(
        raw=raw,
        primary=primary,
        primary_is_percent=primary_is_percent,
        secondary=secondary,
        secondary_is_percent=secondary_is_percent,
    )


def parse_html_report(path) -> ParsedReport:
    path = Path(path)
    html_text = _read_html_file(path)

    parser = _TableCellParser()
    parser.feed(html_text)

    raw_pairs = _extract_pairs(parser.rows)
    if not raw_pairs:
        raise ReportParseError(
            "No recognizable 'Label:' / value rows were found. "
            "Is this really an MT5 Strategy Tester HTML/HTM report?"
        )

    fields = {key: parse_value(value) for key, value in raw_pairs.items()}
    return ParsedReport(fields=fields)
