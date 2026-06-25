# Changelog

All notable changes to this project are documented in this file.

## Next - unreleased

### Added

- JSON output for CSV audit commands:
  - `analyze-deals --list-columns --format json`
  - `analyze-deals --preview-rows --format json`

## v0.5.0 - unreleased

### Added

- HTML/HTM MT5 Strategy Tester report analysis (`analyze-report`).
- CSV deals/trades analysis (`analyze-deals`).
- CSV column mapping via `--column-map`.
- Direct column overrides via `--profit-column`, `--type-column`,
  `--entry-column`, `--symbol-column`, `--volume-column`,
  `--commission-column`, `--swap-column`, `--comment-column`.
- CSV header inspection via `--list-columns`.
- CSV row classification preview via `--preview-rows` and `--max-preview-rows`.
- Row decision engine with explicit decisions:
  - `COUNT_CLOSED_TRADE`
  - `SKIP_NON_TRADE`
  - `SKIP_OPENING_ENTRY`
  - `SKIP_MISSING_PROFIT`
  - `SKIP_INCOMPLETE_ROW`
  - `ERROR_MALFORMED_PROFIT`
- `CHANGELOG.md` and `RELEASE_CHECKLIST.md` for release readiness.
- `docs/USAGE.md` documenting the recommended CSV and HTML workflows.
- CLI smoke tests (`tests/test_cli_smoke.py`) covering the documented
  commands end to end.

### Safety

- No broker connection.
- No `order_send`.
- No order execution.
- No account credentials.
- No network/server dependency.
- No MCP dependency.
- Local file-in / file-out only.

### Known limitations

- CSV formats vary by broker and language.
- Users may need `--list-columns`, `--column-map`, and `--preview-rows`
  before running a full analysis on an unfamiliar CSV layout.
- The tool is not financial advice and does not guarantee demo/live results.
