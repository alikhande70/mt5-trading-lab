# mt5-trading-lab

A local-first toolkit for analyzing **MetaTrader 5 Strategy Tester** reports.

`trading-lab` parses a report you export by hand from MT5, computes the
metrics that matter for deciding whether a strategy is worth a demo run, and
writes a plain Markdown summary with a recommendation:

- `PASS_TO_DEMO`
- `NEEDS_REVIEW`
- `REJECT`

## Execution model (v0.1.0)

- **Local-only.** Runs entirely on your own Windows laptop/PC (or any OS with
  Python — the report files themselves are portable).
- **Offline-first.** No network calls, no telemetry, no cloud service.
- **No VPS.** Nothing to deploy, host, or keep running 24/7.
- **No broker connection.** No account login, no password handling, no
  `order_send`, no live or automated trading of any kind.
- **MT5 does not need to stay open.** You run a backtest, export a report
  file, and close the terminal. Analysis happens later, offline, on the file.

v0.1.0 deliberately does **not** integrate with `metatrader5-mcp` or any
broker API. A future version may add that as an *optional* local
integration, but the core CLI will keep working without it and without a
VPS.

## How it works

1. Run a backtest in the MT5 Strategy Tester.
2. Export the result: right-click the report → **Save as Report** → save as
   `.htm`/`.html`.
3. Run the analyzer locally:

   ```bash
   python -m trading_lab analyze-report path/to/report.htm --out report.md
   ```

4. Open `report.md`. It contains the extracted metrics, the thresholds used,
   and a recommendation with the specific reasons behind it.

### Analyzing a raw CSV deals/trades export (v0.2.0+)

The HTML summary report only gives you MT5's own aggregate figures. If you
want metrics recomputed directly from the trade ledger, export your closed
trades/deals as CSV (MT5 **History** tab or Strategy Tester **Deals** tab →
right-click → **Save as Report (CSV)**) and run:

```bash
python -m trading_lab analyze-deals path/to/deals.csv --out deals_report.md
```

Optional flags:

```bash
python -m trading_lab analyze-deals deals.csv \
  --out deals_report.md \
  --initial-balance 10000 \
  --min-trades 30 \
  --min-profit-factor 1.5 \
  --max-drawdown-pct 20
```

`--initial-balance` is optional. Without it, the absolute drawdown amount is
still computed, but percentage drawdown is reported as unavailable rather
than guessed. Run `python -m trading_lab analyze-deals --help` for the full
list of flags.

## Installation

Requires Python 3.9+. No external runtime dependencies.

```bash
pip install -e .
```

## Usage

```bash
python -m trading_lab analyze-report path/to/report.htm --out report.md
```

Optional flags to tune the recommendation thresholds:

```bash
python -m trading_lab analyze-report report.htm \
  --out report.md \
  --min-trades 30 \
  --min-profit-factor 1.5 \
  --max-drawdown-pct 20
```

Run `python -m trading_lab analyze-report --help` for the full list.

## What the recommendation checks

The verdict is a deterministic, explainable set of rules over the metrics
MT5 already reports (profit factor, relative drawdown, recovery factor,
trade count, net profit). Every contributing reason is listed in the
generated report, so you can see exactly why a strategy passed, needs a
second look, or was rejected. There is no machine learning, no external
scoring service, and no hidden logic.

## Project layout

```
src/trading_lab/
  html_report.py   # parses MT5 Strategy Tester .htm/.html exports
  csv_deals.py      # parses MT5 deals/trades CSV exports
  metrics.py        # turns parsed fields into typed metrics
  recommend.py      # PASS_TO_DEMO / NEEDS_REVIEW / REJECT rules
  report.py         # renders the Markdown reports
  cli.py            # `analyze-report` / `analyze-deals` commands
tests/
  fixtures/         # sample Strategy Tester report and CSV deals exports used in tests
```

## Known limitations

- MT5 CSV exports vary by broker, terminal language, and export method
  (column names, delimiter, decimal/thousands formatting all differ).
  `analyze-deals` normalizes a set of common **English** MT5 CSV layouts; a
  CSV with an unrecognized profit column or an unfamiliar layout may need
  manual column renaming in a later version.
- No broker connection or live/demo trading is performed by either CLI
  command — both are local file-in / file-out analyzers only.

## Out of scope for v0.1.0+

- Live trading or order execution of any kind.
- Broker account connections or password handling.
- Continuous/background operation, schedulers, or a server component.
- VPS or cloud deployment.
- `metatrader5-mcp` integration (planned as an optional add-on later).

## Development

```bash
pip install -e ".[dev]"
pytest
```
