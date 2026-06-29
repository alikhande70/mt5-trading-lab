# Comparison Engine

`compare-reports` and `compare-deals` rank several backtests against each other
on a deterministic, **risk-adjusted** rubric. A high net profit alone never wins:
the ranking weighs the *quality* of the result, not just its size.

## Usage

```bash
# Compare Strategy Tester HTML exports
python -m trading_lab compare-reports run1.htm run2.htm run3.htm \
  --out comparison.md --format both

# Compare deals CSV exports (shared column map / initial balance optional)
python -m trading_lab compare-deals run1.csv run2.csv run3.csv \
  --out comparison.md --initial-balance 10000 --column-map column_map.json
```

Both accept two or more files and the same `--min-trades`, `--min-profit-factor`,
`--max-drawdown-pct` threshold flags as the single-run commands. Output is
Markdown by default; `--format json|both` adds a structured JSON comparison.

## Scoring

Each run gets five sub-scores in the range 0–1, summed and normalized to a
**0–100 total**:

```
score = (stability
       + profit_quality
       + drawdown_control
       + sample_quality
       + report_completeness) / 5 * 100
```

| Component | Source | Maps from |
| --- | --- | --- |
| `profit_quality` | profit factor | 1.0 → 0, 3.0 → 1; halved if the profit factor is implausibly high (overfit signal) |
| `drawdown_control` | relative drawdown | 0% → 1, at/above the hard reject limit → 0; unknown → 0.5 |
| `sample_quality` | trade count | full credit at 2× `min_trades` |
| `stability` | recovery factor | 0 → 0, 4 → 1; unknown → 0.5 |
| `report_completeness` | metric availability | fraction of metrics that could be derived |

Because raw net profit is **not** a component (profit quality uses the *ratio*,
not the dollar amount), a large but fragile result cannot outrank a smaller, more
robust one.

## Flags

Each run is flagged independently of its score:

- `low-sample` — trade count below `min_trades`
- `high-drawdown` — relative drawdown above the comfort threshold
- `overfit` — an `OVERFIT_RISK` or `UNREALISTIC_PROFIT_FACTOR` diagnostic fired
- `losing` — net profit ≤ 0 or profit factor below the reject line

## Ranking and recommendation

Runs are sorted by total score, highest first, with ties broken by file name so
the result is fully deterministic. The best candidate is named only as the
strongest *relative* choice; if even the top run is `REJECT` or `losing`, the
recommendation says so plainly rather than endorsing it.

## Output

The Markdown report contains a ranking table, a per-component score breakdown,
per-run flags, and an overall recommendation with reasons. The JSON report
(`build_comparison_payload`) contains the same data in machine-readable form for
scripts and agents. This is a local comparison of files you exported; it is not
financial advice and contacts no broker or terminal.
