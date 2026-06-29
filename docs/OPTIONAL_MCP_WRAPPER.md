# Optional MCP Wrapper (deferred)

> **Status: not implemented in this release.** The core Report Intelligence
> Engine ships first and is stable on its own. An optional MCP wrapper is a
> planned, separate follow-up — never a dependency of the core.

## Philosophy

The core package `src/trading_lab/` is a pure, local, offline, file-in /
file-out analyzer with zero runtime dependencies. That safety envelope is the
project's main value, and it is enforced by tests (see
[CORE_SAFETY_BOUNDARY.md](CORE_SAFETY_BOUNDARY.md)).

An MCP wrapper, if and when added, is an **adapter** that lets an MCP client
(such as Claude) call the existing core functions on local files. It is:

- **Optional** — the CLI and library work identically without it.
- **Separate** — it lives *outside* `src/trading_lab/` (e.g. `adapters/mcp/`),
  so the core safety scan stays clean and the core never imports it.
- **One-way** — the dependency direction is adapter → core, never core → adapter.

## Hard rules for the future wrapper

The wrapper must **not**:

- connect to the MT5 terminal,
- connect to a broker,
- place, modify, or cancel orders,
- read or store credentials,
- stand up a *required* network service or daemon,
- bypass the core safety boundary in any way.

Each tool must do nothing more than call an existing core function on a local
file and return the result.

## Planned tool surface (illustrative)

| Tool | Wraps |
| --- | --- |
| `lab_import_report` | parse a Strategy Tester HTML export |
| `lab_import_deals_csv` | parse a deals CSV |
| `lab_inspect_csv_columns` | `--list-columns` |
| `lab_preview_csv_rows` | `--preview-rows` |
| `lab_analyze_report` | `analyze-report` |
| `lab_analyze_deals` | `analyze-deals` |
| `lab_compare_reports` | `compare-reports` |
| `lab_compare_deals` | `compare-deals` |
| `lab_generate_demo_readiness` | `demo-readiness` |
| `lab_generate_decision_report` | the structured decision/JSON output |
| `lab_export_json_summary` | the canonical JSON payload |

## Placement when implemented

```
adapters/mcp/trading_lab_mcp/
  server.py
  tools.py
  README.md
  pyproject.toml      # the wrapper's own deps (mcp), never added to the core
```

Until then, use the CLI and the JSON output — they already give agents an
auditable, machine-readable interface with no server required.
