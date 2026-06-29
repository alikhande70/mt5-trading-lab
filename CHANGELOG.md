# Changelog

All notable changes to this project are documented in this file.

## Next - unreleased

### Added — Report Intelligence Engine

- Expanded metrics engine: recovery factor, average trade, expectancy, drawdown
  curve, long/short split, symbol distribution, and monthly returns, plus a
  machine-readable `MetricResult` layer that marks underivable metrics as
  unavailable with a reason instead of guessing.
- Diagnostics engine (`diagnostics.py`): deterministic sample-quality, risk, and
  overfit / too-good-to-be-true flags with `INFO`/`LOW`/`MEDIUM`/`HIGH`/
  `BLOCKING` severities.
- Structured JSON output and decision report for `analyze-report` /
  `analyze-deals` via `--format markdown|json|both` and `--json-out`
  (default stays Markdown). Includes verdict confidence, blocking/review reasons,
  next actions, and a data-quality summary.
- Risk-adjusted multi-backtest comparison: `compare-reports` and `compare-deals`
  rank runs on a deterministic score (stability, profit quality, drawdown
  control, sample quality, data completeness) — net profit alone never wins.
- Demo-readiness report: `demo-readiness` (Ready / No / Needs Review) backed by
  evidence and risk diagnostics.
- Lightweight local workflow layer: `workflow single-review | compare-runs |
  demo-readiness`.
- New docs: report intelligence overview, core safety boundary, metrics,
  diagnostics, comparison, demo-readiness, JSON schema, optional MCP wrapper
  (deferred), agent-stack integration, Claude Cowork handoff, and examples.
- Additional safety tests: `tests/test_core_no_mcp_dependency.py`,
  `tests/test_core_no_broker_dependency.py`, and a broker/MT5 import guard in
  `tests/test_safety_invariants.py`.

### Added — earlier in this cycle

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
