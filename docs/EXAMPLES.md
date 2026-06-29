# Examples

All commands below run locally on files you already exported. They read a file
and write a file (or print to stdout); nothing connects to MT5 or a broker.
The `tests/fixtures/` files referenced here ship with the repo.

## Single HTML report → Markdown + JSON

```bash
python -m trading_lab analyze-report tests/fixtures/sample_strategy_tester_report.htm \
  --out report.md --format both --json-out report.json
```

- `report.md` — metrics table, verdict, reasons.
- `report.json` — canonical payload (see [JSON_OUTPUT_SCHEMA.md](JSON_OUTPUT_SCHEMA.md)).

## Single deals CSV → Markdown + JSON

```bash
python -m trading_lab analyze-deals tests/fixtures/sample_deals.csv \
  --initial-balance 10000 --out deals_report.md --format both --json-out deals_report.json
```

Inspect column / row handling first if a CSV is unfamiliar:

```bash
python -m trading_lab analyze-deals tests/fixtures/custom_header_deals.csv \
  --column-map tests/fixtures/custom_header_column_map.json --list-columns
python -m trading_lab analyze-deals tests/fixtures/sample_deals.csv --preview-rows --format json
```

## Compare several runs (risk-adjusted)

```bash
# Reports
python -m trading_lab compare-reports \
  tests/fixtures/sample_strategy_tester_report.htm \
  tests/fixtures/borderline_strategy_report.htm \
  tests/fixtures/losing_strategy_report.htm \
  --out comparison.md --format both

# Deals CSVs
python -m trading_lab compare-deals \
  tests/fixtures/sample_deals.csv \
  tests/fixtures/losing_deals.csv \
  --out comparison.md --initial-balance 10000
```

The ranking is risk-adjusted — the highest net profit does not automatically
win. See [COMPARISON_ENGINE.md](COMPARISON_ENGINE.md).

## Demo-readiness

```bash
# Auto-detects report vs CSV by suffix
python -m trading_lab demo-readiness tests/fixtures/sample_strategy_tester_report.htm \
  --out demo_readiness.md --format both

# Prefer the CSV as the assessed source
python -m trading_lab demo-readiness tests/fixtures/sample_strategy_tester_report.htm \
  --deals tests/fixtures/sample_deals.csv --out demo_readiness.md
```

## Workflows (one command, end-to-end)

```bash
python -m trading_lab workflow single-review \
  --report tests/fixtures/sample_strategy_tester_report.htm --out review.md

python -m trading_lab workflow compare-runs \
  --reports tests/fixtures/sample_strategy_tester_report.htm \
            tests/fixtures/losing_strategy_report.htm --out comparison.md

python -m trading_lab workflow demo-readiness \
  --report tests/fixtures/sample_strategy_tester_report.htm \
  --deals tests/fixtures/sample_deals.csv --out demo.md
```

## Example JSON shape (abridged)

```json
{
  "schema_version": "1.0",
  "input": { "file": "sample_deals.csv", "type": "deals_csv", "parsed_at": "..." },
  "metrics": { "net_profit": { "value": 800.0, "available": true, "source": "deals_csv", "warnings": [] } },
  "diagnostics": [],
  "verdict": { "decision": "PASS_TO_DEMO", "confidence": "MEDIUM", "next_actions": ["..."] },
  "data_quality": { "metrics_total": 29, "metrics_available": 26, "metrics_unavailable": ["monthly_returns"] }
}
```
