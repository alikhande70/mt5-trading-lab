# Report Intelligence Engine

`mt5-trading-lab` is a **local-first, offline-first, file-in / file-out report
intelligence engine** for MetaTrader 5 backtests. It reads files you exported by
hand (Strategy Tester `.htm`/`.html` reports and deals/trades CSVs), computes
metrics, runs diagnostics, compares runs, and emits deterministic, auditable
verdicts. Nothing is connected, hosted, or kept running.

## What this project is

- A command-line tool that turns exported MT5 backtest artifacts into:
  - a normalized set of **metrics**,
  - a set of **diagnostics** (sample-quality, risk, and overfit flags),
  - a deterministic **verdict** (`PASS_TO_DEMO` / `NEEDS_REVIEW` / `REJECT`),
  - a **decision report** explaining the verdict,
  - a **demo-readiness** read (Ready / No / Needs Review),
  - a **multi-backtest comparison** that ranks candidates risk-adjusted,
  - both **Markdown** (for humans) and **JSON** (for scripts/agents) output.
- A tool that any agent or CLI consumer can run locally on exported files and
  get a structured, explainable answer it can audit.

## What this project is not

- **Not a trading bot, Expert Advisor, or signal generator.**
- **Not connected to MT5.** It never opens or talks to the terminal.
- **Not connected to a broker.** No broker API, session, or order placement.
- **No order execution.** No `order_send`, `place_order`, `close_position`, etc.
- **No credential handling.** No login, password, API key, or secret, ever.
- **No required network, server, daemon, or MCP dependency.**
- **Not financial advice.** Verdicts are deterministic rules over backtest data.

## Why local-first matters

Backtest review should not require uploading your strategy results anywhere,
running a server, or trusting a remote service. Everything happens on your
machine, on files you already have. There is nothing to deploy and nothing that
phones home.

## Why file-in / file-out matters

Each command reads a local file and writes a local file (or prints to stdout),
then exits. There is no persistent state, no background process, and no hidden
side effect. This makes every run reproducible and auditable: the inputs and the
outputs are both plain files you can diff, version, and inspect.

## Why the core must remain MCP-free

The value of this project is its safety envelope. To keep that guarantee
verifiable, the core package `src/trading_lab/` must never import `mcp`,
`metatrader5`, a broker API, or any network/server library. An **optional** MCP
wrapper may be added later as a *separate* adapter that calls the core; it is
never a dependency of the core and is never required to use the tool. The core
runs identically with or without it.

See [CORE_SAFETY_BOUNDARY.md](CORE_SAFETY_BOUNDARY.md) for the exact boundary and
how it is enforced in code.

## What "report intelligence" means here

More than printing numbers. The engine:

- computes a broad metric set and marks anything it can't derive as
  **unavailable with a reason** rather than guessing;
- flags **sample-quality** problems (too few trades, missing balance/commission/
  swap/symbol data) so a pretty number from a tiny sample is not mistaken for a
  result;
- flags **risk** patterns (high drawdown, fat-tail losses, drawdown clusters,
  unstable equity curves);
- flags **overfit / too-good-to-be-true** signals (unrealistic profit factor,
  high win-rate paired with a poor payoff);
- **compares** several runs and ranks them risk-adjusted, so the highest net
  profit never automatically "wins";
- explains every verdict with the specific metrics and reasons behind it.

## Relationship with `metatrader5-mcp`

`metatrader5-mcp` is a *separate* project that bridges to the MT5 terminal,
MetaEditor, and Strategy Tester. It is the component that may *produce* the
report and CSV files. `mt5-trading-lab` only *consumes* exported files. They are
complementary but decoupled: trading-lab never connects to MT5 itself, and never
depends on `metatrader5-mcp` to function. See
[AGENT_STACK_INTEGRATION.md](AGENT_STACK_INTEGRATION.md).

## Relationship with `cls-agent`

`cls-agent` is a *separate* project (a deterministic EA / CLS companion).
`mt5-trading-lab` is the offline report-intelligence layer that can review the
backtests produced anywhere in that stack. It has no code dependency on
`cls-agent`.

## Optional MCP wrapper philosophy

When (and only when) the core is stable, a thin optional MCP adapter may be added
in a *separate* location outside `src/trading_lab/` (e.g. `adapters/mcp/`). Each
MCP tool would do nothing more than call an existing core function on local
files. The wrapper must not connect to MT5, connect to a broker, execute orders,
read credentials, or stand up a required network service. The core remains the
source of truth and never imports the wrapper. **The MCP wrapper is deferred to a
follow-up; it is not part of the core engine.**
