# Install Runbook

A step-by-step guide to install, verify, and use `mt5-trading-lab` from scratch.
The primary target is **Windows + PowerShell** (MetaTrader 5 is Windows-native),
with macOS/Linux equivalents noted where they differ.

Everything here is local and offline: you install a Python package, run it on
files you exported from MT5, and read the Markdown/JSON it writes. Nothing
connects to MT5, a broker, or the network.

---

## 1. Dependency preflight

Confirm the three prerequisites before anything else.

```powershell
py -3 --version      # Python 3.9 or newer (the Windows 'py' launcher)
python --version     # fallback if 'py' is not installed
pip --version        # pip (ships with Python 3.9+)
git --version        # only needed if you clone with git
```

- **Python 3.9+** is required (`pyproject.toml` sets `requires-python = ">=3.9"`).
- On Windows, prefer the **`py -3`** launcher; if it is missing, use `python`.
  The rest of this guide uses `python` once a virtual environment is active.
- There are **no external runtime dependencies** — only the Python standard
  library. `pip install` pulls nothing extra for normal use.

macOS/Linux:

```bash
python3 --version
python3 -m pip --version
git --version
```

---

## 2. Get the project

Clone it (or download and extract the source), then `cd` into it.

```powershell
git clone <repo-url> mt5-trading-lab
cd mt5-trading-lab
```

---

## 3. Windows PowerShell setup (execution policy)

Activating a virtual environment runs a PowerShell script. If activation is
blocked with *"running scripts is disabled on this system"*, allow it **for the
current session only** (does not change machine-wide policy):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This lasts until you close the PowerShell window. Skip it if activation already
works.

---

## 4. Create and activate a virtual environment

A venv keeps this project isolated from your system Python.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Your prompt now shows `(.venv)`. To leave it later, run `deactivate`.

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 5. Install the package

For normal use:

```powershell
pip install -e .
```

To also run the tests (adds `pytest`):

```powershell
pip install -e ".[dev]"
```

`-e` installs in *editable* mode, so the `trading-lab` command and the
`python -m trading_lab` module both point at this source tree.

---

## 6. CLI help checks

Confirm the install works and see every command:

```powershell
python -m trading_lab --version
python -m trading_lab --help
```

Per-command help (each prints its own flags):

```powershell
python -m trading_lab analyze-report --help
python -m trading_lab analyze-deals --help
python -m trading_lab compare-reports --help
python -m trading_lab compare-deals --help
python -m trading_lab demo-readiness --help
python -m trading_lab workflow --help
```

The installed `trading-lab` console script is equivalent to
`python -m trading_lab` everywhere in this guide.

---

## 7. pytest / safety checks

Run the full suite (only needed if you installed the `[dev]` extra):

```powershell
pytest
```

All tests should pass. To run **only the safety guards** — the tests that prove
the core stays local and harmless:

```powershell
pytest tests/test_safety_invariants.py tests/test_core_no_mcp_dependency.py tests/test_core_no_broker_dependency.py
```

These assert, by inspecting the source of `src/trading_lab/`, that the core has:

- no `order_send` / order-execution functions,
- no broker or MT5 terminal import,
- no credential handling,
- no network/server import,
- no MCP dependency.

Smoke-test the engine on the bundled sample fixtures:

```powershell
python -m trading_lab analyze-report tests\fixtures\sample_strategy_tester_report.htm --out report.md --format both --json-out report.json
python -m trading_lab analyze-deals  tests\fixtures\sample_deals.csv --out deals_report.md --format both --json-out deals_report.json
python -m trading_lab compare-reports tests\fixtures\sample_strategy_tester_report.htm tests\fixtures\borderline_strategy_report.htm tests\fixtures\losing_strategy_report.htm --out comparison.md --format both
python -m trading_lab demo-readiness tests\fixtures\sample_strategy_tester_report.htm --out demo_readiness.md --format both
```

(macOS/Linux: use forward slashes, e.g. `tests/fixtures/sample_deals.csv`.)

---

## 8. Exporting HTML/CSV from MetaTrader 5

`mt5-trading-lab` never talks to MT5 — you export files by hand, then analyze
them. MT5 can be **closed** during analysis.

**Strategy Tester report (`.htm` / `.html`):**

1. Run a backtest in the MT5 **Strategy Tester**.
2. On the **Backtest** (results) tab, right-click → **Save as Report**.
3. Save as `.htm`/`.html`. Analyze with `analyze-report`.

**Deals / trades CSV:**

- From the terminal **History** tab: right-click → **Report** → save as CSV; or
- From the Strategy Tester **Deals** tab: right-click → **Save as Report** → CSV.
- Analyze with `analyze-deals`. If the columns are unfamiliar, inspect them first
  with `--list-columns` / `--preview-rows` (see Troubleshooting).

CSV exports vary by broker and terminal language (delimiter, decimal format,
column names). The analyzer handles common English layouts and supports a
`--column-map` for the rest.

---

## 9. Evidence folder structure

Keep each backtest's inputs and the reports you generate together, so a result is
fully reproducible from the files on disk. A simple convention:

```
evidence/
  <strategy-name>/
    <YYYY-MM-DD>/
      report.htm        # exported from MT5 Strategy Tester
      deals.csv         # exported from MT5 History / Deals
      report.md         # produced by: analyze-report ... --format both
      report.json       # machine-readable analysis (see JSON_OUTPUT_SCHEMA.md)
      comparison.md     # if you ran compare-reports / compare-deals
      demo_readiness.md # if you ran demo-readiness
```

Notes:

- The repo's `.gitignore` already ignores `*.htm`/`*.html` and `/reports/`, and
  the whole `/evidence/` folder, so your broker exports and generated reports are
  **not** committed by accident. Keep your evidence local (or in private storage),
  not in the source repo.
- Everything is file-in / file-out: the same input files always produce the same
  reports (timestamps aside), so the folder is a complete audit trail.

---

## 10. Troubleshooting

- **"running scripts is disabled on this system"** when activating the venv — run
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` (Section 3), then
  activate again.
- **`trading-lab` / `python` not found** — the venv isn't active (no `(.venv)` in
  the prompt) or you're using the wrong interpreter. Re-activate, or call
  `python -m trading_lab ...` explicitly.
- **"No usable profit column was found"** — run
  `python -m trading_lab analyze-deals <file.csv> --list-columns` to see how the
  header resolved, then add `--profit-column "<header>"` or a `--column-map`.
- **Rows are all skipped / a trade looks wrong** — run `--preview-rows` to see how
  each row was classified (counted, skipped, or malformed) before trusting the
  totals.
- **Percentage drawdown shows as unavailable** — pass `--initial-balance <amount>`
  to `analyze-deals`; without it, only the absolute drawdown amount is computed
  (the value is reported as unavailable rather than guessed).
- **Odd numbers from a non-English CSV** — exports differ by locale (comma vs dot
  decimals, `;` delimiters). The parser auto-detects common variants; use
  `--column-map` for non-standard headers.

See [USAGE.md](USAGE.md) for the recommended step-by-step workflow and
[EXAMPLES.md](EXAMPLES.md) for copy-paste command examples.
