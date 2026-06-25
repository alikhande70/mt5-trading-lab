# Release checklist

Follow this checklist **before** tagging any release. It is a manual
process — nothing here runs automatically, and nothing here creates a tag
or a GitHub Release by itself.

## 1. Automated checks

Run from a clean checkout of `main`:

```bash
python -m pytest -q
python -m pytest tests/test_safety_invariants.py -q
python -m trading_lab --version
```

All tests must pass. `--version` must print the version you intend to
release.

## 2. Smoke examples

Run these by hand and confirm the output looks sane (exit codes, file
creation, table/Markdown content):

```bash
python -m trading_lab analyze-report tests/fixtures/sample_strategy_tester_report.htm --out /tmp/report.md
python -m trading_lab analyze-deals tests/fixtures/sample_deals.csv --out /tmp/deals_report.md
python -m trading_lab analyze-deals tests/fixtures/sample_deals.csv --list-columns
python -m trading_lab analyze-deals tests/fixtures/sample_deals.csv --preview-rows --max-preview-rows 5
python -m trading_lab analyze-deals tests/fixtures/custom_header_deals.csv --list-columns --column-map tests/fixtures/custom_header_column_map.json
python -m trading_lab analyze-deals tests/fixtures/custom_header_deals.csv --preview-rows --column-map tests/fixtures/custom_header_column_map.json
```

Expected:

- `analyze-report` and `analyze-deals` (no preview/list flag) write their
  `--out` file and print `Recommendation: ...`.
- `--list-columns` and `--preview-rows` print to stdout only and do **not**
  create a report file.
- The custom-header examples resolve `type`/`entry`/`profit` via the column
  map without errors.

## 3. Safety grep checklist

```bash
grep -rn "order_send" src/ || echo "clean"
grep -rnE "def (send_order|place_order|execute_trade|modify_order|cancel_order|close_position|close_order|delete_order)\(" src/ || echo "clean"
grep -rniE "password|api_key|secret" src/ || echo "clean"
grep -rnE "^import (socket|requests|httpx|aiohttp|flask|fastapi|uvicorn|websockets)" src/ || echo "clean"
grep -rni "mcp" src/ || echo "clean"
```

Every command above must report "clean" (no matches) before release.

## 4. Manual release steps

Only after every check above passes:

1. Verify the working tree is clean (`git status`).
2. Verify `main` is up to date with the remote (`git fetch origin main && git log origin/main -1`).
3. Verify all automated tests pass (step 1 above).
4. Verify the README examples still work as documented (step 2 above).
5. Verify `CHANGELOG.md` is current and matches the version being released.
6. **Then, and only then,** create the tag (e.g. `git tag v0.5.0`) manually.
7. **Then, and only then,** create the GitHub Release manually, using the
   matching `CHANGELOG.md` section as the release notes.

This checklist intentionally does not tag or release anything itself —
tagging and releasing are separate, manual, human-confirmed steps.
