# mt5-trading-lab

A local-first toolkit for analyzing **MetaTrader 5 Strategy Tester** reports
and trade history exports.

## What this project is

`trading-lab` is a command-line tool that:

- Parses a Strategy Tester report (`.htm`/`.html`) or a deals/trades CSV
  that you export by hand from MT5.
- Computes the metrics that matter for deciding whether a strategy is worth
  a demo run: profit factor, drawdown, recovery factor, trade count, net
  profit.
- Writes a plain Markdown summary with one of three deterministic,
  explainable verdicts:
  - `PASS_TO_DEMO`
  - `NEEDS_REVIEW`
  - `REJECT`
- Lets you inspect and audit how a CSV's columns and rows are interpreted
  (`--list-columns`, `--preview-rows`) before trusting the final numbers.

Everything runs on your own machine, on files you already exported. There
is nothing to deploy, host, or keep running.

## What this project is not

- **Not a trading bot.** It does not generate trading signals or run a
  strategy.
- **Not an Expert Advisor.** It has no relationship to MT5's EA/MQL5
  runtime.
- **Not connected to MT5.** It never opens or talks to the MetaTrader 5
  terminal; it only reads files you exported from it.
- **Not connected to a broker.** No broker API, no broker session, of any
  kind.
- **Does not place orders.** There is no `order_send` and no order-related
  code anywhere in this project (enforced by an automated test suite — see
  [Safety model](#safety-model)).
- **Does not manage live positions.** Nothing here opens, closes, modifies,
  or monitors a live or demo position.
- **Does not store account credentials.** No login, no password, no API
  key, no secret is ever read, stored, or transmitted.
- **Not financial advice.** The recommendation is a deterministic rule
  applied to backtest metrics, not a guarantee of future results.

## Safety model

- **Local-only.** Runs entirely on your own laptop/PC (or any OS with
  Python — the report/CSV files themselves are portable).
- **Offline-first.** No network calls, no telemetry, no cloud service.
- **File-in / file-out.** Every command reads a local file and either
  writes a local Markdown file or prints to stdout. Nothing persists
  between runs beyond the files you explicitly asked for.
- **No VPS.** Nothing to deploy, host, or keep running 24/7.
- **No background daemon.** Every command runs once and exits.
- **No broker connection, no account credentials.** No login, no password
  handling, no `order_send`, no live or automated trading of any kind.
- **No required MCP dependency.** This project does not depend on
  `metatrader5-mcp` or any other MCP server to function.
- **MT5 does not need to stay open.** You run a backtest, export a report
  or CSV, and close the terminal. Analysis happens later, offline, on the
  file.

These constraints are not just documentation — `tests/test_safety_invariants.py`
inspects the source of `src/trading_lab/` (via Python's tokenizer/AST, not
substring matching) and fails the test suite if anyone ever adds
`order_send`, an execution-named function, credential handling, a
network/server import, or an MCP dependency.

## Installation

Requires Python 3.9+. No external runtime dependencies.

```bash
pip install -e .
```

## Quick start

```bash
# HTML/HTM Strategy Tester report
python -m trading_lab analyze-report path/to/report.htm --out report.md

# CSV deals/trades export
python -m trading_lab analyze-deals path/to/deals.csv --out deals_report.md
```

Open the generated Markdown file. It contains the extracted metrics, the
thresholds used, and a recommendation with the specific reasons behind it.

Run `python -m trading_lab --version` to check the installed version, and
`python -m trading_lab <command> --help` for the full flag list of any
command.

## HTML report analysis

1. Run a backtest in the MT5 Strategy Tester.
2. Export the result: right-click the report → **Save as Report** → save as
   `.htm`/`.html`.
3. Run the analyzer locally:

   ```bash
   python -m trading_lab analyze-report path/to/report.htm --out report.md
   ```

4. Open `report.md`. It contains the extracted metrics, the thresholds used,
   and a recommendation with the specific reasons behind it.

Optional flags to tune the recommendation thresholds:

```bash
python -m trading_lab analyze-report report.htm \
  --out report.md \
  --min-trades 30 \
  --min-profit-factor 1.5 \
  --max-drawdown-pct 20
```

Run `python -m trading_lab analyze-report --help` for the full list.

## CSV deals analysis

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

## Inspecting CSV columns

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

## Previewing CSV row classification

`--list-columns` only inspects the header. To see how every **data row**
would actually be interpreted — counted as a closed trade, skipped, or
rejected as malformed — before trusting the full analysis, use
`--preview-rows`:

```bash
python -m trading_lab analyze-deals deals.csv --preview-rows
python -m trading_lab analyze-deals deals.csv --preview-rows --max-preview-rows 100
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

See [docs/USAGE.md](docs/USAGE.md) for the recommended step-by-step workflow
that ties these three together.

## Column mapping

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

Precedence (highest to lowest): direct `--*-column` flag > `--column-map`
entry > built-in alias table.

## Interpreting recommendations

Both `analyze-report` and `analyze-deals` (without `--list-columns` /
`--preview-rows`) end with the same verdict logic, applied to a handful of
metrics:

- `PASS_TO_DEMO` — every automated check passed: enough trades for a
  meaningful sample, positive net profit, profit factor and drawdown within
  the comfort thresholds.
- `NEEDS_REVIEW` — at least one check is borderline (e.g. trade count below
  the minimum, profit factor below the comfort threshold but still
  positive, drawdown above the comfort threshold but below the hard
  limit), or a core metric couldn't be read at all.
- `REJECT` — at least one check failed outright (net loss, profit factor
  below 1.0, or drawdown above the hard limit).

The verdict is a deterministic, explainable set of rules over the metrics
MT5 already reports (profit factor, relative drawdown, recovery factor,
trade count, net profit). Every contributing reason is listed in the
generated report, so you can see exactly why a strategy passed, needs a
second look, or was rejected. There is no machine learning, no external
scoring service, and no hidden logic. The thresholds (`--min-trades`,
`--min-profit-factor`, `--max-drawdown-pct`, ...) are CLI flags, not
hard-coded constants — tune them to your own risk tolerance.

A `PASS_TO_DEMO` verdict means "worth running on a demo account next," not
"guaranteed profitable." Treat every recommendation as a local screening
aid, not financial advice.

## Troubleshooting

- **"No usable profit column was found."** — Run `--list-columns` to see
  which canonical fields were resolved. If `profit` is missing, add
  `--profit-column "<your header>"` or a `--column-map` entry.
- **"No closed trade/deal rows with a usable profit value were found."** —
  Run `--preview-rows` to see why every row was skipped (often
  `SKIP_NON_TRADE` or `SKIP_MISSING_PROFIT` on every row because `type`/
  `entry` aren't mapped). Map the missing columns and re-run.
- **A row's profit looks wrong / a trade is missing.** — Run
  `--preview-rows` and look up that row's `Row` number; the `Decision` and
  `Reason` columns explain exactly why it was counted, skipped, or rejected.
- **`DealsParseError: could not parse profit value ... as a number.`** — A
  row's profit column contains text that isn't a number (after stripping
  thousands separators). Run `--preview-rows` to find the offending row
  (`ERROR_MALFORMED_PROFIT`) and fix or remap that column.
- **Percentage drawdown shows as unavailable.** — Pass
  `--initial-balance <amount>` to `analyze-deals`; without it, only the
  absolute drawdown amount can be computed.
- **`--list-columns` and `--preview-rows` together return an error.** —
  They're mutually exclusive; run one at a time.

## Release status

Current version: **v0.5.0** (unreleased — see [CHANGELOG.md](CHANGELOG.md)).

No git tag or GitHub Release has been created for this version yet. See
[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for the manual steps required
before a tag/release is created.

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
docs/
  USAGE.md          # recommended step-by-step CSV/HTML workflows
```

## Known limitations

- MT5 CSV exports vary by broker, terminal language, and export method
  (column names, delimiter, decimal/thousands formatting all differ).
  `analyze-deals` normalizes a set of common **English** MT5 CSV layouts; a
  CSV with an unrecognized profit column or an unfamiliar layout may need
  manual column renaming or a column map.
- No broker connection or live/demo trading is performed by either CLI
  command — both are local file-in / file-out analyzers only.
- `--preview-rows` classifies rows according to the columns currently
  mapped (built-in aliases, `--column-map`, and/or direct `--*-column`
  flags). It does not judge whether the underlying strategy is good, does
  not compute final performance metrics, does not connect to MT5, and does
  not place trades.
- This tool is not financial advice and does not guarantee demo or live
  trading results.

## Out of scope

- Live trading or order execution of any kind.
- Broker account connections or password handling.
- Continuous/background operation, schedulers, or a server component.
- VPS or cloud deployment.
- `metatrader5-mcp` integration (planned as an optional add-on later, never
  required).
- JSON output, plotting, or new analysis metrics beyond what's documented
  above (kept out to keep the tool auditable and dependency-free).

## Development

```bash
pip install -e ".[dev]"
pytest
```

See [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for the full set of checks
run before any release.
