# Claude Cowork Handoff

You are Claude Cowork. Your job is to run this project **locally on exported
files only**.

- Do **not** connect to MT5.
- Do **not** connect to a broker.
- Do **not** handle credentials.
- Do **not** add order execution.
- Do **not** convert this project into a trading bot.

This project is a local-first, offline-first, file-in / file-out report
intelligence engine. Its safety boundary is enforced by tests (see
[CORE_SAFETY_BOUNDARY.md](CORE_SAFETY_BOUNDARY.md)); keep it intact.

## Steps

1. **Clone the repo.**
   ```bash
   git clone <repo-url> && cd mt5-trading-lab
   ```
2. **Create a Python virtual environment** (Python 3.9+).
   ```bash
   python -m venv .venv && . .venv/bin/activate
   ```
3. **Install the package (with dev extras for tests).**
   ```bash
   pip install -e ".[dev]"
   ```
4. **Run the test suite.**
   ```bash
   pytest
   ```
5. **Analyze a sample HTML report.**
   ```bash
   python -m trading_lab analyze-report tests/fixtures/sample_strategy_tester_report.htm \
     --out report.md --format both --json-out report.json
   ```
6. **Analyze a sample deals CSV.**
   ```bash
   python -m trading_lab analyze-deals tests/fixtures/sample_deals.csv \
     --out deals_report.md --format both --json-out deals_report.json
   ```
7. **Compare several runs.**
   ```bash
   python -m trading_lab compare-reports \
     tests/fixtures/sample_strategy_tester_report.htm \
     tests/fixtures/borderline_strategy_report.htm \
     tests/fixtures/losing_strategy_report.htm \
     --out comparison.md --format both
   ```
8. **Generate a demo-readiness report.**
   ```bash
   python -m trading_lab demo-readiness tests/fixtures/sample_strategy_tester_report.htm \
     --out demo_readiness.md --format both
   ```
9. **Confirm no network / broker / MT5 dependency is required.** The package
   installs with `dependencies = []` and runs entirely offline. The safety tests
   (`tests/test_safety_invariants.py`, `tests/test_core_no_mcp_dependency.py`,
   `tests/test_core_no_broker_dependency.py`) prove the core imports no order
   execution, broker, MT5, credential, network, or MCP code.

## Output you can rely on

- **Markdown** (`*.md`) — human-readable review, comparison, and readiness reports.
- **JSON** (`*.json`) — machine-readable analysis (metrics, diagnostics, verdict,
  data quality) for auditable, deterministic decisions. See
  [JSON_OUTPUT_SCHEMA.md](JSON_OUTPUT_SCHEMA.md).

Everything you produce is a local file derived from a local file. Nothing is
sent anywhere, and no trade is ever placed.
