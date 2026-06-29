# Tool Expansion Roadmap

This roadmap tracks the growth of `mt5-trading-lab` from a single-report analyzer
into a full **Report Intelligence Engine**. Every item preserves the core safety
boundary (see [CORE_SAFETY_BOUNDARY.md](CORE_SAFETY_BOUNDARY.md)): local-first,
offline-first, file-in / file-out, zero runtime dependencies.

## Status legend

- ✅ done · 🚧 in progress · ⏳ deferred

## Phases

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Architecture & safety docs (this set) | ✅ |
| 1 | Metrics engine expansion: recovery factor, average trade, expectancy, drawdown curve, long/short split, symbol distribution, monthly returns; machine-readable `MetricResult` | ✅ |
| 2 | Diagnostics engine: sample-quality, risk, and overfit flags with severity levels | ✅ |
| 3 | JSON output + decision report (`--format markdown\|json\|both`, `--json-out`) | ✅ |
| 4 | Multi-backtest comparison: `compare-reports`, `compare-deals`, risk-adjusted ranking | ✅ |
| 5 | Demo-readiness report: `demo-readiness` (Ready / No / Needs Review) | ✅ |
| 6 | Lightweight local workflow layer: `workflow` (single-review, compare-runs, demo-readiness) | ✅ |
| 7 | Optional MCP wrapper (separate adapter, never required) | ⏳ deferred to a follow-up |

## Design rules carried through every phase

- When data for a metric is insufficient, mark it **unavailable with a reason** —
  never guess.
- Verdicts, diagnostics, and comparison scores are **deterministic and
  explainable**: same input → same output, with every contributing reason listed.
- Ranking is **risk-adjusted**: a high net profit alone never wins.
- New structured output is **additive and backward compatible**: existing
  commands and their default Markdown output are unchanged.

## Out of scope (now and later)

- Live trading or order execution of any kind.
- Broker account connections, MT5 terminal connections, or credential handling.
- A required network service, server component, or background daemon.
- A *required* MCP dependency in the core. (An optional adapter may be added
  later, outside `src/trading_lab/`, and is never required.)
