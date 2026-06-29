# Metrics Reference

This is the metric set the engine computes. Each metric is exposed in the JSON
output as a `MetricResult` with `value`, `available`, `reason_if_unavailable`,
`source`, and `warnings`. When a metric cannot be derived from the available
data it is marked `available: false` with a reason — values are never guessed.

"Source" indicates where a metric can come from:

- **HTML** — Strategy Tester `.htm`/`.html` summary (`analyze-report`)
- **CSV** — deals/trades ledger (`analyze-deals`)

## Core profit & loss

| Metric | Source | Notes |
| --- | --- | --- |
| `net_profit` | HTML, CSV | CSV nets commission and swap into the figure |
| `gross_profit` / `gross_loss` | HTML, CSV | |
| `profit_factor` | HTML, CSV | gross profit / abs(gross loss); unavailable with no losses |
| `expected_payoff` | HTML | MT5's expected payoff |
| `average_trade` | CSV | mean P/L per closed trade |
| `expectancy` | CSV | win-prob × avg win + loss-prob × avg loss |

## Risk & drawdown

| Metric | Source | Notes |
| --- | --- | --- |
| `max_drawdown_absolute` | CSV | peak-to-trough of the cumulative-profit curve |
| `max_drawdown_percent` | HTML, CSV | CSV needs `--initial-balance`, else unavailable |
| `recovery_factor` | HTML, CSV | net profit / max drawdown |
| `drawdown_curve` | CSV | per-trade drawdown series |
| `equity_curve` | CSV | cumulative-profit series |
| `sharpe_ratio` | HTML | as reported by MT5 |

## Trade structure

| Metric | Source | Notes |
| --- | --- | --- |
| `trade_count` | HTML, CSV | closed trades |
| `win_rate` / `loss_rate` | HTML, CSV | |
| `win_count` / `loss_count` | CSV | |
| `average_win` / `average_loss` | HTML, CSV | |
| `largest_win` / `largest_loss` | HTML, CSV | |
| `payoff_ratio` | HTML, CSV | average win / abs(average loss) |
| `max_consecutive_wins` / `max_consecutive_losses` | HTML, CSV | |

## Distributions (CSV, when the data is present)

| Metric | Available when | Notes |
| --- | --- | --- |
| `long_short_split` | the type column carries buy/sell | counts of long vs short trades |
| `symbol_distribution` | a symbol column is present | trade count per symbol |
| `monthly_returns` | a time column is present | summed profit per `YYYY-MM` |

These three are marked unavailable (with a reason) when the source CSV does not
carry direction, symbol, or time data, respectively. An HTML summary carries no
per-trade ledger, so the per-trade series (`equity_curve`, `drawdown_curve`,
`monthly_returns`, `symbol_distribution`, `long_short_split`) are always
unavailable from the HTML source.

## Verdict thresholds

The verdict and several diagnostics use tunable thresholds (CLI flags):
`--min-trades`, `--min-profit-factor`, `--max-drawdown-pct`. Hard reject limits
(`reject_profit_factor`, `reject_drawdown_pct`) and `min_recovery_factor` are
part of the `Thresholds` defaults. See the generated report's "Thresholds used"
section for the exact values applied to a given run.
