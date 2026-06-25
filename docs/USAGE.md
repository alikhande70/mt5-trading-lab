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
