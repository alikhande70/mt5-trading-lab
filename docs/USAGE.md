# Recommended usage workflow

`trading-lab` is a local file-in / file-out analyzer. These are the
recommended sequences for getting trustworthy output from each command —
skipping steps is fine for a familiar CSV layout, but recommended the first
time you analyze a new export.

## Recommended CSV workflow (`analyze-deals`)

1. Run `--list-columns` to see how the CSV header resolves to canonical
   fields (`profit`, `type`, `entry`, `symbol`, ...).
2. If columns are not mapped correctly, create a `column_map.json` or use
   direct `--*-column` overrides (`--profit-column`, `--type-column`,
   `--entry-column`, etc.).
3. Run `--preview-rows` to classify every data row without computing any
   metrics.
4. Check counted vs. skipped rows in the preview summary — confirm the
   counted rows are the closed trades you expect, and that skipped rows are
   skipped for the right reason (non-trade row, opening entry, missing
   profit).
5. Run the full `analyze-deals` (no `--list-columns` / `--preview-rows`
   flag) to compute metrics and write the Markdown report.
6. Review the warnings section in the generated report before trusting the
   metrics — warnings flag things like unmapped commission/swap columns or
   suspicious unmapped type/entry headers.

```bash
python -m trading_lab analyze-deals deals.csv --list-columns
python -m trading_lab analyze-deals deals.csv --preview-rows
python -m trading_lab analyze-deals deals.csv --out deals_report.md
```

## Recommended HTML workflow (`analyze-report`)

1. Export the Strategy Tester report from MT5 as HTML/HTM (right-click the
   report → **Save as Report**).
2. Run `analyze-report` on the exported file.
3. Review the recommendation and the thresholds used to reach it — every
   contributing reason is listed in the generated report.
4. Treat the output as a local screening aid, not financial advice: it
   tells you whether a backtest is worth a closer look or a demo run, not
   whether the strategy will be profitable live.

```bash
python -m trading_lab analyze-report path/to/report.htm --out report.md
```

## Machine-readable JSON output

`analyze-deals` can emit JSON instead of plain text via `--format json`, for
scripts, CI checks, and local agents. There are two kinds of JSON, both
local file-in / stdout-out and both stdlib-only:

**Audit JSON** — `--list-columns` and `--preview-rows`. Assert on column
mapping or row classification without parsing the plain-text tables:

```bash
python -m trading_lab analyze-deals deals.csv --list-columns --format json
python -m trading_lab analyze-deals deals.csv --preview-rows --format json
```

**Full analysis JSON** — `analyze-deals` with no audit flag. Serializes the
same metrics, recommendation, thresholds, and warnings as the Markdown
report (the same computation, not a separate one):

```bash
python -m trading_lab analyze-deals deals.csv --format json
python -m trading_lab analyze-deals deals.csv --format json > deals_report.json
```

Full-analysis JSON prints to **stdout only**. `--out` is the Markdown-report
path and cannot be combined with `--format json` for a full run — doing so
returns a clean CLI error rather than writing JSON into a Markdown-oriented
file. Redirect stdout to a `.json` file instead.

JSON output for `analyze-report` (the HTML Strategy Tester report command)
is **not implemented yet**. In all JSON modes, the JSON payload is the only
thing on stdout on success; errors still go to stderr, and the exit code is
unchanged from the plain-text behavior. Plain text remains the default for
every command.
