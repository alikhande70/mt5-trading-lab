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

#### CSV exports with non-standard column names (v0.3.0+)

If your broker, terminal language, or export method produces a deals CSV
whose headers don't match any built-in English alias, point `analyze-deals`
at a JSON column map instead of editing the CSV by hand:

```bash
python -m trading_lab analyze-deals deals.csv --out report.md \
  --column-map column_map.json
```

`column_map.json` maps canonical field names to your CSV's actual header
labels. Only these canonical names are recognized: `profit`, `type`,
`entry`, `symbol`, `volume`, `commission`, `swap`, `comment`, `time`,
`ticket`, `order`, `deal`.

```json
{
  "profit": "Profit USD",
  "type": "Operation",
  "entry": "Entry",
  "symbol": "Instrument",
  "volume": "Lots",
  "commission": "Commission",
  "swap": "Swap",
  "comment": "Comment"
}
```

For a quick one-off override without a JSON file, use the matching
`--*-column` flags, which take the exact CSV header label and override both
the built-in aliases and `--column-map`:

```bash
python -m trading_lab analyze-deals deals.csv --out report.md \
  --profit-column "Profit USD" --entry-column "Entry Type"
```

Available override flags: `--profit-column`, `--type-column`,
`--entry-column`, `--symbol-column`, `--volume-column`,
`--commission-column`, `--swap-column`, `--comment-column`.

#### Inspecting CSV columns before analysis (v0.4.0+)

Before running a full analysis, you can inspect how `analyze-deals` would
resolve your CSV's header — which raw column maps to which canonical field,
and whether that came from a built-in alias, `--column-map`, or a direct
`--*-column` flag. This only reads the header; it never parses deal rows,
computes metrics, or writes a report file.

```bash
python -m trading_lab analyze-deals deals.csv --list-columns
python -m trading_lab analyze-deals deals.csv --list-columns --column-map column_map.json
python -m trading_lab analyze-deals deals.csv --list-columns --profit-column "Result"
```

Example output:

```
CSV column inspection
File: deals.csv
Delimiter: ,

Raw header    Canonical field    Source

Close Time    time               column-map
Instrument    symbol             column-map
Operation     type               direct override
Entry Type    entry              direct override
Result        profit             direct override
Fee           commission         column-map
Overnight     swap               column-map
Note          comment            column-map

Warnings:

- No issue detected.

Suggested next action:
Run analyze-deals without --list-columns to generate the report.
```

`--list-columns` exits `0` whenever the CSV can be read, even if some
columns are left unmapped — any concerns (an unmapped profit column, or a
header that looks like a type/entry column but isn't mapped) are surfaced as
warnings, not errors, so you can iterate on a column map without re-running
the full analysis each time. It exits `1` only for real read/parse errors:
file not found, an empty CSV, or a missing/invalid/unrecognized
`--column-map` file.

#### Previewing CSV row classification (v0.5.0+)

`--list-columns` only inspects the header. To see how every **data row**
would actually be interpreted — counted as a closed trade, skipped, or
rejected as malformed — before trusting the full analysis, use
`--preview-rows`:

```bash
python -m trading_lab analyze-deals deals.csv --preview-rows
```

```bash
python -m trading_lab analyze-deals deals.csv --preview-rows --max-preview-rows 100
```

```bash
python -m trading_lab analyze-deals deals.csv --preview-rows --column-map column_map.json
```

`--preview-rows` classifies each data row using exactly the same per-row
logic as the full analysis (`parse_deals_csv` and `--preview-rows` share one
row-classification function, so they cannot drift apart) and prints a table
of the decisions plus a summary:

```
CSV row preview
File: deals.csv
Delimiter: ,
Rows inspected: 50

Row    Decision              Reason                        Symbol    Type    Entry    Profit raw    Profit

2      COUNT_CLOSED_TRADE    Closed trade/deal counted.    EURUSD    buy     -        50.00         50.00
3      SKIP_NON_TRADE        Type is a non-trade account operation (balance/deposit/credit/fee/...).    -    balance    -    10000.00    -

Summary:

- Total data rows inspected: 50
- Counted closed trades: 48
- Skipped non-trade rows: 1
- Skipped opening rows: 0
- Skipped missing-profit rows: 1
- Malformed profit rows: 0
- Incomplete rows: 0

Warnings:

- No issue detected.

Errors:

- None.

Suggested next action:
If the counted/skipped rows look correct, run analyze-deals without --preview-rows.
```

Each row gets exactly one decision: `COUNT_CLOSED_TRADE`, `SKIP_NON_TRADE`,
`SKIP_OPENING_ENTRY`, `SKIP_MISSING_PROFIT`, `SKIP_INCOMPLETE_ROW`, or
`ERROR_MALFORMED_PROFIT`. `--preview-rows` never computes strategy metrics
and never writes a Markdown report, even if `--out` is also passed. It
exits `1` if any classified row has a malformed (unparseable) profit value,
or for the same file/CSV/column-map errors as `--list-columns`; otherwise it
exits `0`, including when zero rows are counted (skipped rows are not
errors — review them and adjust your column mapping). `--preview-rows` and
`--list-columns` are mutually exclusive.

In short:

- `--list-columns` — what does the **header** resolve to?
- `--preview-rows` — how would each **row** be counted or skipped?
- `analyze-deals` (no flag) — compute the final metrics and write the report.

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
  csv_deals.py      # parses MT5 deals/trades CSV exports + column mapping
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
- `--preview-rows` classifies rows according to the columns currently
  mapped (built-in aliases, `--column-map`, and/or direct `--*-column`
  flags). It does not judge whether the underlying strategy is good, does
  not compute final performance metrics, does not connect to MT5, and does
  not place trades.

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
