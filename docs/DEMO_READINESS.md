# Demo-Readiness Report

`demo-readiness` answers one focused question about a single backtest: **is it
ready to move to a demo account for forward testing?** The answer is one of
**Ready (Yes)**, **Not ready (No)**, or **Needs review**, backed by the evidence
behind the call. It is a deterministic engineering readiness check — not
financial advice, and it places no trades.

## Usage

```bash
# Auto-detects HTML report vs CSV by file suffix
python -m trading_lab demo-readiness report.htm --out demo_readiness.md
python -m trading_lab demo-readiness deals.csv --out demo_readiness.md

# Assess a CSV explicitly (richer per-trade data); --format adds JSON
python -m trading_lab demo-readiness report.htm --deals deals.csv \
  --initial-balance 10000 --format both --out demo_readiness.md
```

If `--deals` is given, that CSV is the assessed source (it carries per-trade
data); otherwise the positional input is auto-detected. The same threshold flags
(`--min-trades`, `--min-profit-factor`, `--max-drawdown-pct`) apply.

## How the status is decided

| Status | When |
| --- | --- |
| `READY` | verdict is `PASS_TO_DEMO` **and** no `BLOCKING` diagnostic fired |
| `NOT_READY` | verdict is `REJECT` **or** any `BLOCKING` diagnostic fired |
| `NEEDS_REVIEW` | anything in between (e.g. `NEEDS_REVIEW` verdict) |

## Evidence

The report lists each check with its value and an OK marker (`yes` / `no` / `—`
when unknown):

- **Trade count** — at or above `min_trades`?
- **Profit factor** — at or above the comfort threshold?
- **Max drawdown** — within the comfort threshold?
- **Recovery factor** — at or above the minimum?
- **Data completeness** — at least 60% of metrics derivable?

It also lists every risk diagnostic at MEDIUM severity or above, and the
next-action guidance from the decision report.

## Output

Markdown by default; `--format json|both` adds a machine-readable
`build_demo_readiness_payload` document (status, decision, confidence, evidence,
risk findings, next actions) for scripts and agents. No financial advice is
given and no broker, terminal, or order placement is involved.
