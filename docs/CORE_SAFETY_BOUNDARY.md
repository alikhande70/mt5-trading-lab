# Core Safety Boundary

The core package `src/trading_lab/` is a pure, local, offline, file-in / file-out
analyzer. This document states the boundary precisely and explains how it is
enforced — not just by convention, but by tests that read the source and fail the
build the moment a forbidden construct appears.

## The invariant

`src/trading_lab/` must **never** contain:

| Forbidden | Examples |
| --- | --- |
| Order execution | `order_send(`, `send_order`, `place_order`, `execute_trade`, `modify_order`, `cancel_order`, `close_position`, `close_order`, `delete_order` |
| Broker / terminal connection | `MetaTrader5` / `metatrader5`, broker SDKs, login/session calls |
| Credential handling | `password`, `account_password`, `broker_password`, `mt5_password`, `login_password` |
| Network / server | `requests`, `httpx`, `aiohttp`, `socket`, `fastapi`, `flask`, `uvicorn`, `websockets` |
| MCP dependency | `mcp`, `metatrader5_mcp`, `mt5_mcp`, `FastMCP` |
| Execution CLI commands | `run-server`, `daemon`, `trade`, `live`, `execute`, `send-order` |

The core has **zero runtime dependencies** (Python standard library only) and
runs once per invocation with no background state.

## How it is enforced

`tests/test_safety_invariants.py` inspects the *source* of every `*.py` file
under `src/` using Python's tokenizer and AST (not raw substring matching), so a
disclaimer in a docstring such as "no order was placed" does **not** trip the
checks — only real executable identifiers, function definitions, and imports
count. It asserts:

1. The literal `order_send(` appears nowhere in `src/`.
2. No execution-named function is defined.
3. No credential identifier is used in executable code.
4. No network/server module is imported.
5. No MCP module is imported.
6. The CLI exposes `analyze-report` and exposes none of the forbidden commands.

Two additional focused guards reinforce the core specifically:

- `tests/test_core_no_mcp_dependency.py` — `src/trading_lab/` imports no MCP
  module under any import form.
- `tests/test_core_no_broker_dependency.py` — `src/trading_lab/` imports no
  broker / MT5 terminal module (`MetaTrader5`, `metatrader5`, common broker SDK
  roots).

If any of these fail, the offending file and symbol are named in the assertion
message.

## Where optional adapters may live

Any optional adapter (for example, a future MCP wrapper) must live **outside**
`src/trading_lab/` — e.g. under `adapters/`. That keeps the safety scan over the
core clean while still allowing an adapter to *import and call* the core. The
dependency direction is one-way: **adapter → core**, never core → adapter. The
core must run identically whether or not any adapter is installed.

## What is allowed to grow

The engine may freely add: more metrics, diagnostics, comparison logic, decision
and demo-readiness reports, JSON output, a thin local workflow layer, fixtures,
and documentation — all of it pure, local, and dependency-free. Strengthening the
analysis never requires weakening the boundary.
