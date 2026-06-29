"""The core package must never depend on a broker or the MT5 terminal.

This guard scans ``src/trading_lab/`` (the core) specifically and asserts that it
imports no MetaTrader5 terminal binding and no broker SDK. trading-lab only ever
reads files you exported; it never connects to a terminal or a broker. Detection
is AST-based (real imports only), so a docstring mentioning "MetaTrader 5" does
not trip it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple

CORE_DIR = Path(__file__).resolve().parents[1] / "src" / "trading_lab"

FORBIDDEN_BROKER_MODULES = {
    "MetaTrader5",
    "metatrader5",
    "mt5",
    "ib_insync",
    "ibapi",
    "ccxt",
    "oandapyV20",
    "alpaca_trade_api",
    "kiteconnect",
}


def _core_files() -> List[Path]:
    files = [p for p in CORE_DIR.rglob("*.py") if "__pycache__" not in p.parts]
    assert files, f"No core source files found under {CORE_DIR}; test setup is wrong."
    return files


def _module_roots(src: str) -> Set[str]:
    roots: Set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_package_imports_no_broker_or_terminal_module():
    offenders: Dict[str, Set[str]] = {}
    for path in _core_files():
        bad = _module_roots(path.read_text(encoding="utf-8")) & FORBIDDEN_BROKER_MODULES
        if bad:
            offenders[str(path.relative_to(CORE_DIR))] = bad
    assert not offenders, (
        "Core package src/trading_lab/ must not import a broker/MT5 terminal "
        f"module. Offenders: {offenders}"
    )
