# JSON Output Schema

Both `analyze-report` and `analyze-deals` can emit a structured JSON report in
addition to (or instead of) Markdown. This format is intended for scripts, CI
checks, and agents and scripts that need a machine-readable, auditable result.

## How to produce it

```bash
# JSON only
python -m trading_lab analyze-report report.htm --format json --json-out report.json

# Markdown and JSON together
python -m trading_lab analyze-deals deals.csv --format both \
  --out deals_report.md --json-out deals_report.json
```

`--format` accepts `markdown` (default), `json`, or `both`. If `--json-out` is
omitted, the JSON path defaults to `--out` with a `.json` suffix. Default
behavior is unchanged: without `--format`, only Markdown is written.

## Top-level shape

```json
{
  "schema_version": "1.0",
  "tool": { "name": "trading-lab", "version": "0.5.0" },
  "input": {
    "file": "report.htm",
    "type": "strategy_tester_html",
    "parsed_at": "2026-01-01T12:00:00"
  },
  "metrics": { "<name>": { "value": ..., "available": true,
                           "reason_if_unavailable": null,
                           "source": "...", "warnings": [] } },
  "diagnostics": [
    { "code": "LOW_SAMPLE_SIZE", "severity": "HIGH",
      "message": "...", "recommendation": "..." }
  ],
  "verdict": {
    "decision": "PASS_TO_DEMO",
    "confidence": "MEDIUM",
    "blocking_reasons": [],
    "review_reasons": [],
    "passed": ["..."],
    "next_actions": ["..."]
  },
  "warnings": [],
  "assumptions": ["..."],
  "data_quality": {
    "metrics_total": 26,
    "metrics_available": 21,
    "metrics_unavailable": ["equity_curve", "..."]
  },
  "thresholds": { "min_trades": 30, "min_profit_factor": 1.5, "...": "..." }
}
```

## Field notes

- **`input.type`** — `strategy_tester_html` for `analyze-report`, `deals_csv` for
  `analyze-deals`.
- **`input.parsed_at`** — ISO-8601 local timestamp. Injectable in code
  (`build_analysis_payload(..., parsed_at=...)`) so output is deterministic in
  tests.
- **`metrics`** — a map of metric name → `MetricResult`. A metric that could not
  be derived has `available: false`, `value: null`, and a human-readable
  `reason_if_unavailable`. Values are never guessed.
- **`diagnostics`** — see [DIAGNOSTICS_REFERENCE.md](DIAGNOSTICS_REFERENCE.md),
  sorted most-serious first.
- **`verdict.decision`** — `PASS_TO_DEMO` / `NEEDS_REVIEW` / `REJECT`, identical
  to the Markdown verdict. **`confidence`** is `LOW` / `MEDIUM` / `HIGH` based on
  data completeness and finding severity. `blocking_reasons` is populated on
  `REJECT`; `review_reasons` on `NEEDS_REVIEW`.
- **`data_quality`** — counts of available vs. unavailable metrics, plus the
  names of the unavailable ones, so a consumer can gauge how complete the source
  data was.

## Stability

`schema_version` is `"1.0"`. The structure is additive going forward: new keys
may be added, but existing keys keep their meaning. This is a local, offline
serialization of a local analysis — it contacts nothing and contains only what
was in your exported file plus the deterministic analysis of it.
