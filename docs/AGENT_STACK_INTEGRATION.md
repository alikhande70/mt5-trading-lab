# Agent Stack Integration

`mt5-trading-lab` is the **offline report-intelligence layer** of a larger stack.
It is intentionally decoupled: it reads files other tools produce and never
connects to a terminal or broker itself.

## The pieces

| Project | Role | Connects to MT5/broker? |
| --- | --- | --- |
| `metatrader5-mcp` | Bridge to the MT5 terminal, MetaEditor, Strategy Tester; can *produce* report/CSV exports | Yes (that is its job) |
| **`mt5-trading-lab`** | Offline report intelligence: parse, metrics, diagnostics, comparison, verdict, demo-readiness | **No** |
| `cls-agent` | Deterministic EA / CLS companion | (separate concern) |
| CLS Companion MCP | Review / testing / reporting layer for `cls-agent` | (separate concern) |

`mt5-trading-lab` has no code dependency on any of these. It is useful on its own
and composes with them only through files.

## How the hand-off works

1. A backtest is run in the MT5 Strategy Tester (manually, or driven by
   `metatrader5-mcp`).
2. The result is exported to a local file: a Strategy Tester `.htm`/`.html`
   report, or a deals/trades `.csv`.
3. `mt5-trading-lab` is pointed at that file and produces a Markdown and/or JSON
   analysis, comparison, or demo-readiness report.
4. An agent (Claude Code / Claude Cowork) reads the JSON output to make an
   auditable, deterministic decision.

```
MT5 Strategy Tester ──export──▶ report.htm / deals.csv ──▶ mt5-trading-lab ──▶ report.md / report.json
        (metatrader5-mcp can drive step 1)                  (local, offline)        (for humans / agents)
```

## How Claude Code can use it

After a backtest is exported, Claude Code can run any command and read the
results — Markdown for humans, JSON for programmatic decisions:

```bash
python -m trading_lab analyze-report report.htm --format both --out r.md --json-out r.json
python -m trading_lab compare-reports a.htm b.htm c.htm --out comparison.md --format both
python -m trading_lab demo-readiness report.htm --deals deals.csv --format json --json-out demo.json
```

## How Claude Cowork can run it locally

See [CLAUDE_COWORK_HANDOFF.md](CLAUDE_COWORK_HANDOFF.md) for the exact local
steps and boundaries. In short: clone, install, run on exported files only — no
MT5 connection, no broker, no credentials, no order execution.

## Why trading-lab must not connect directly

Keeping the connection concern in `metatrader5-mcp` and the analysis concern in
`mt5-trading-lab` is what makes the analysis auditable and safe: the analyzer
provably cannot place a trade, leak a credential, or reach the network, because
it never has the code to do so (enforced by
[the safety tests](CORE_SAFETY_BOUNDARY.md)).
