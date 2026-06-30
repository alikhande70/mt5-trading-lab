# Local Desktop UI Design

> **Status: design document only — not implemented.** This describes a *possible*
> future optional desktop UI for `mt5-trading-lab`. No GUI code, dependency, or
> CLI change ships with this document. If the UI is ever built, it must preserve
> the project's safety boundary exactly (see
> [CORE_SAFETY_BOUNDARY.md](CORE_SAFETY_BOUNDARY.md)).

## 1. Purpose

Provide a friendly, point-and-click wrapper around the **existing** local file
analysis workflow so that non-technical users can run the same analyses they
would run from the CLI, without typing commands or remembering flags. The UI adds
*convenience only* — it computes nothing new and changes no behavior.

## 2. User problem

The current value of the tool is delivered through a CLI: the user must open a
terminal, know the subcommand names (`analyze-report`, `analyze-deals`, …),
type file paths correctly, and remember flags like `--initial-balance`,
`--format`, `--column-map`. For a trader who is not comfortable with a terminal,
this friction is the main barrier to using the tool at all. A small desktop
window with file pickers and buttons removes that friction while keeping the
exact same underlying analysis.

## 3. Non-goals

The UI is explicitly **not**:

- a replacement for the CLI (the CLI remains the primary, fully-supported interface);
- a connection to MetaTrader 5 or any broker;
- a trading, order-entry, or position-management surface;
- a background service, scheduler, or daemon;
- a cloud or networked application;
- a provider of financial advice or guarantees.

It is only a local front-end that reads files the user already exported and
writes local report files.

## 4. Safety boundaries

The UI inherits and must never weaken the core safety boundary:

- **No order execution** — no `order_send`, `place_order`, or any execution call.
- **No broker connection** — no broker API, login, or session.
- **No MT5 terminal control** — the UI never opens, drives, or talks to the
  MetaTrader 5 terminal; it only reads files the user exported by hand.
- **No credentials** — no login, password, API key, token, or secret is read,
  stored, or transmitted.
- **No daemon / no background process** — every action runs once on demand and
  returns; nothing keeps running.
- **No cloud / no network** — the UI makes no network calls and needs no server.
- **No live trading, no financial advice** — verdicts are deterministic
  engineering reads of backtest files, not recommendations to trade.
- **Local file-in / file-out only** — input is a local exported file; output is a
  local Markdown/JSON file.

These are the same invariants enforced for the core by
`tests/test_safety_invariants.py`, `tests/test_core_no_mcp_dependency.py`, and
`tests/test_core_no_broker_dependency.py`. The UI must not introduce any code
that would violate them.

## 5. Recommended UI technology

**Tkinter** (Python's standard-library GUI toolkit) for Phase 1.

## 6. Why Tkinter first

- **Ships with CPython** on most desktop installations — usually nothing extra to
  install.
- **Zero extra runtime dependency** — keeps `pyproject.toml` at `dependencies = []`.
- **No local web server** — no port, no browser, no localhost service to secure.
- **Matches the model** — a single local window that reads/writes local files fits
  the project's local-first / offline-first / file-in-file-out design.
- **Lower attack surface** — no HTTP layer, no templating, no static assets to
  serve, compared with a web dashboard.

## 7. Why not Streamlit / web UI in Phase 1

A Streamlit (or other web) UI introduces:

- a **local web server** and an open port — a networked surface the project
  deliberately avoids;
- an **extra runtime dependency** (and its transitive dependencies);
- a **browser-based** interaction model that is heavier to reason about for safety.

A web UI is therefore **deferred**. It may be reconsidered only as a *later,
optional* alternative, and only after a **separate safety review** confirms it can
be done without weakening the boundary (e.g. bound to loopback only, no external
exposure, no new trading surface). It is not part of Phase 1.

## 8. Main screen layout

A single resizable window, top-to-bottom:

```
+------------------------------------------------------------------+
|  mt5-trading-lab — Local Report Analysis      (design mockup)     |
+------------------------------------------------------------------+
|  Inputs                                                          |
|   Strategy report (.htm/.html): [ ............... ] [ Browse ]   |
|   Deals CSV (.csv):             [ ............... ] [ Browse ]   |
|   Output folder:                [ ............... ] [ Browse ]   |
+------------------------------------------------------------------+
|  Options                                                         |
|   Output format:  ( ) Markdown  ( ) JSON  (•) Both              |
|   Initial balance (optional):   [ ........ ]                     |
|   Min trades [ 30 ]  Min profit factor [ 1.5 ]  Max DD% [ 20 ]   |
|   Column map (optional .json):  [ ........... ] [ Browse ]       |
+------------------------------------------------------------------+
|  Actions                                                        |
|   [ Analyze Report ] [ Analyze Deals ] [ List CSV Columns ]      |
|   [ Preview CSV Rows ] [ Demo Readiness ]                        |
+------------------------------------------------------------------+
|  Output / log                                                   |
|   +----------------------------------------------------------+   |
|   | (command output, verdict, and any errors appear here)    |   |
|   +----------------------------------------------------------+   |
|   [ Open output file ]                            [ Clear ]      |
+------------------------------------------------------------------+
```

There are deliberately **no** broker, MT5, order, login, or "connect" controls.

## 9. Input file selectors

- **Strategy report** picker: native open-file dialog filtered to `*.htm;*.html`.
- **Deals CSV** picker: filtered to `*.csv`.
- Browsing is read-only (the UI never writes to the input files).
- Selected paths are shown in read-only entry fields; the user may also paste a path.

## 10. Output folder selector

- A directory picker for where reports are written.
- Defaults to an `evidence/<strategy>/<YYYY-MM-DD>/` subfolder per the
  [install runbook](INSTALL_RUNBOOK.md) convention; the user can override it.
- The UI creates the folder if it does not exist (it only ever creates the chosen
  output directory and writes report files into it).

## 11. Analysis modes

Each action button corresponds one-to-one to an existing CLI subcommand/flag, so
the UI never does anything the CLI cannot already do:

| Button | Underlying command |
| --- | --- |
| Analyze Report | `analyze-report` |
| Analyze Deals | `analyze-deals` |
| List CSV Columns | `analyze-deals --list-columns` |
| Preview CSV Rows | `analyze-deals --preview-rows` |
| Demo Readiness | `demo-readiness` |
| (Phase 2) Compare Reports / Deals | `compare-reports` / `compare-deals` |

## 12. Analyze Report workflow

1. User selects a `.htm`/`.html` report, an output folder, format, and optional
   thresholds.
2. UI builds the argument list for `analyze-report` (`--out`, `--format`,
   `--json-out`, `--min-trades`, `--min-profit-factor`, `--max-drawdown-pct`).
3. UI runs it (see §21), then shows the verdict and the written file path in the
   log area.

## 13. Analyze Deals workflow

Same shape as Analyze Report, mapping to `analyze-deals` and additionally
exposing: optional `--initial-balance`, the threshold fields, and an optional
`--column-map`. Output format Markdown / JSON / Both as selected.

## 14. CSV List Columns workflow

Maps to `analyze-deals --list-columns` (optionally `--format json`). Runs header
inspection only — no metrics, no report file — and prints the column resolution
table into the log area. Used to debug an unfamiliar CSV before a full run.

## 15. CSV Preview Rows workflow

Maps to `analyze-deals --preview-rows` (optionally `--max-preview-rows`,
`--format json`). Shows how each data row would be classified (counted, skipped,
or malformed) in the log area, without computing metrics or writing a report.

## 16. Demo Readiness workflow

Maps to `demo-readiness`. Accepts either a report (positional) or a `--deals` CSV
(which takes precedence), plus output folder, format, optional `--initial-balance`
and `--column-map`. Shows the Ready / No / Needs Review status and writes the
demo-readiness report.

## 17. Compare Reports / Compare Deals (future workflow)

A **Phase 2** screen that lets the user pick **two or more** `.htm` reports (or
`.csv` files) and maps to `compare-reports` / `compare-deals`, writing the
risk-adjusted ranking report. Multi-file selection and a small results table are
the only additions; the underlying command is unchanged.

## 18. Result display

- The log area shows the command's **stdout** and final **exit status** verbatim.
- The UI surfaces the headline (e.g. `Recommendation: PASS_TO_DEMO`) and the path
  of any written file, parsed from the command output.
- The UI **never invents** numbers or verdicts; it only displays what the command
  produced and the file it wrote. For structured detail it points the user at the
  generated Markdown/JSON.

## 19. Error handling

- A non-zero exit code is shown clearly, with the command's **stderr** printed
  verbatim in the log area (no silent failures, no crashes on bad input).
- Friendly hints for common cases:
  - input file not found → prompt to re-select;
  - "No usable profit column was found" → suggest **List CSV Columns** /
    **Preview CSV Rows** and the column-map field;
  - percentage drawdown unavailable → note that **Initial balance** is optional
    but needed for `%` drawdown.
- Invalid numeric fields are validated before running and flagged inline.

## 20. Evidence folder handling

- Outputs default into `evidence/<strategy>/<YYYY-MM-DD>/` so each run's inputs
  and generated reports stay together as an audit trail.
- The repo's `.gitignore` already ignores `/evidence/`, `*.htm`, and `*.html`, so
  broker exports and generated reports are not committed by accident.
- The UI only ever writes into the user-chosen output folder; it never touches the
  source tree.

## 21. CLI integration strategy

Two options were considered for how the UI invokes the analysis:

- **Option A — direct, in-process Python calls.** The UI builds an argument list
  from the form and calls the existing CLI entry point `trading_lab.cli.main(argv)`
  in-process (capturing stdout/stderr and the integer exit code).
- **Option B — subprocess to the CLI.** The UI spawns
  `python -m trading_lab <args>` as a child process and reads its output.

**Recommendation: Option A for Phase 1.** It is the safer first approach because it:

- spawns **no subprocess and no shell**, so there is no command-injection or
  path-quoting surface from user-supplied file paths;
- reuses the **exact, already-tested** argument parsing and handlers in `cli.py`,
  so GUI behavior cannot drift from CLI behavior;
- stays within a **single local process**, consistent with the offline model;
- is **trivially unit-testable** (build argv → call `main` → assert exit code and
  captured output) without opening a window.

**Tradeoff (documented, not chosen now):** Option B gives stronger process
isolation and guarantees terminal-identical behavior even if the GUI is run in an
odd environment, but it adds process management, argument-quoting concerns, and a
small command-construction surface. It can be revisited later if isolation
becomes a requirement. **Neither option is implemented in this PR.**

## 22. Testing strategy

- Keep all GUI *logic* in thin, importable, headless functions — most importantly
  an **argv-builder** (form state → argument list) and an **output-parser**
  (command stdout → verdict + written-file path). These can be unit-tested without
  creating a Tk window.
- Reuse the existing fixtures in `tests/fixtures/` (e.g.
  `sample_strategy_tester_report.htm`, `sample_deals.csv`) to assert that a given
  form state produces the expected argument list and that a known command output
  parses correctly.
- Widget construction stays minimal and side-effect-free at import time so tests
  can import the module on a headless CI machine.
- No new test files are added in this design PR.

## 23. Packaging strategy

- Invoke via a future module entry point, e.g. `python -m trading_lab.ui`, kept
  **separate** from the core (`src/trading_lab/`) so the core stays GUI-free.
- Because Tkinter is in the standard library, the UI adds **no runtime
  dependency** — `pyproject.toml` stays at `dependencies = []`.
- An optional single-file desktop build (e.g. PyInstaller) may be offered as a
  convenience, but only as a **dev/optional** extra — never a required dependency
  and never part of the core install.

## 24. Future roadmap

- **Phase 1 (Tkinter):** single-file Analyze Report / Analyze Deals, List
  Columns, Preview Rows, Demo Readiness; output format selection; thresholds;
  open-output-file.
- **Phase 2:** Compare Reports / Compare Deals (multi-file) and a workflow screen
  mapping to the `workflow` subcommands; a small results/ranking table.
- **Phase 3 (optional, post-review):** richer result rendering (e.g. read back the
  generated JSON to show a metrics table) — still file-in/file-out, no new core.
- **Web UI:** only if a *separate* safety review approves a loopback-only,
  dependency-justified design. Not on the default path.

## 25. Acceptance criteria for UI Phase 1

A Phase 1 UI is acceptable only if **all** of the following hold:

- It exposes exactly the Phase 1 features below and **no** broker/MT5/order
  controls of any kind.
- It requires **no change to `src/trading_lab/`** core logic (it wraps the
  existing CLI entry point).
- The existing safety tests still pass unchanged, and the UI module itself
  contains no order-execution, broker, MT5, credential, network, or daemon code.
- It adds **no new runtime dependency** (Tkinter is stdlib; `dependencies = []`
  stays).
- It is a **thin wrapper**: every action maps to an existing command run on local
  files, producing local Markdown/JSON output.
- GUI logic (argv-builder, output-parser) is covered by headless unit tests.

### Phase 1 feature list (documented, not built)

- Select `.htm`/`.html` Strategy Tester report.
- Select `.csv` deals/trades export.
- Select output folder.
- Choose output format: Markdown / JSON / Both.
- Optional `initial_balance`.
- Optional thresholds: min trades, min profit factor, max drawdown percent.
- Buttons: **Analyze Report**, **Analyze Deals**, **List CSV Columns**,
  **Preview CSV Rows**, **Demo Readiness**.
- Text area for command output / errors.
- Open the generated output file.
- **No broker / MT5 / order controls of any kind.**
