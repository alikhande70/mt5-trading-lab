# Diagnostics Reference

The diagnostics engine (`src/trading_lab/diagnostics.py`) flags *quality*
problems with a backtest result — not just its raw numbers. Each finding is a
deterministic `Diagnostic` with a `code`, a `severity`, a `message`, and a
`recommendation`. A rule only fires when the data it needs is present, so a
metric that could not be derived never produces a misleading flag.

## Severity levels

`INFO` < `LOW` < `MEDIUM` < `HIGH` < `BLOCKING`

`BLOCKING` means a hard limit was breached (e.g. drawdown beyond the reject
threshold). Findings are returned sorted most-serious first.

## Diagnostics

| Code | Severity | Fires when | Source |
| --- | --- | --- | --- |
| `LOW_SAMPLE_SIZE` | HIGH | closed-trade count is below `min_trades` | both |
| `MISSING_INITIAL_BALANCE` | MEDIUM | deals analysis without `--initial-balance` (no % drawdown) | deals |
| `MISSING_COMMISSION` | LOW | no commission column present | deals |
| `MISSING_SWAP` | LOW | no swap column present | deals |
| `MISSING_SYMBOL` | INFO | no symbol column present | deals |
| `HIGH_DRAWDOWN` | HIGH / BLOCKING | relative drawdown over the comfort / hard limit | both |
| `FAT_TAIL_LOSS` | MEDIUM | largest loss > 4× the average loss | both |
| `DRAWDOWN_CLUSTER` | MEDIUM | ≥ 5 consecutive losing trades | both |
| `UNSTABLE_EQUITY_CURVE` | MEDIUM | peak drawdown > 50% of final equity | deals |
| `UNREALISTIC_PROFIT_FACTOR` | HIGH | profit factor > 10 (curve-fit / tiny-sample signal) | both |
| `HIGH_WINRATE_LOW_PAYOFF` | MEDIUM | win rate > 70% **and** payoff ratio < 0.7 | both |
| `BAD_RR_PROFILE` | MEDIUM | payoff ratio < 0.5 (losers > 2× winners) | both |
| `OVERFIT_RISK` | HIGH | ≥ 2 overfit / too-good signals present together | both |

## Tunable constants

Sample-size and drawdown limits come from the shared `Thresholds`
(`--min-trades`, `--max-drawdown-pct`), so the CLI flags that tune the verdict
also tune the diagnostics. The remaining constants live next to the rules in
`diagnostics.py` and are documented inline:

- `PROFIT_FACTOR_SANITY_MAX = 10.0`
- `HIGH_WIN_RATE_PCT = 70.0`, `LOW_PAYOFF_RATIO = 0.7`
- `BAD_RR_PAYOFF_RATIO = 0.5`
- `FAT_TAIL_LOSS_MULTIPLE = 4.0`
- `DRAWDOWN_CLUSTER_MIN_STREAK = 5`
- `UNSTABLE_EQUITY_RATIO = 0.5`

## Example finding (JSON)

```json
{
  "code": "LOW_SAMPLE_SIZE",
  "severity": "HIGH",
  "message": "Only 18 closed trades were found, below the 30-trade minimum for a meaningful sample.",
  "recommendation": "Run a longer backtest or test more symbols/timeframes."
}
```

Diagnostics are advisory engineering signals over backtest data. They are not
financial advice and do not guarantee live or demo performance.
