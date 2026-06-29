"""The core package must never depend on MCP.

This guard scans ``src/trading_lab/`` (the core) specifically — distinct from any
optional adapter that may live elsewhere in the repo later. The core must run
identically with or without an MCP wrapper, so it may not import one. Detection
is AST-based (real imports only), not substring matching, so docstrings that
mention "MCP" do not trip it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple

CORE_DIR = Path(__file__).resolve().parents[1] / "src" / "trading_lab"

FORBIDDEN_MCP_MODULES = {"mcp", "fastmcp", "metatrader5_mcp", "mt5_mcp", "modelcontextprotocol"}
FORBIDDEN_MCP_NAMES = {"FastMCP", "metatrader5_mcp", "mt5_mcp"}


def _core_files() -> List[Path]:
    files = [p for p in CORE_DIR.rglob("*.py") if "__pycache__" not in p.parts]
    assert files, f"No core source files found under {CORE_DIR}; test setup is wrong."
    return files


def _imports(src: str) -> Tuple[Set[str], Set[str]]:
    module_roots: Set[str] = set()
    imported_names: Set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_roots.add(alias.name.split(".")[0])
                imported_names.add(alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_roots.add(node.module.split(".")[0])
            for alias in node.names:
                imported_names.add(alias.name)
    return module_roots, imported_names


def test_core_package_imports_no_mcp_module():
    offenders: Dict[str, Set[str]] = {}
    for path in _core_files():
        roots, names = _imports(path.read_text(encoding="utf-8"))
        bad = (roots & FORBIDDEN_MCP_MODULES) | (names & FORBIDDEN_MCP_NAMES)
        if bad:
            offenders[str(path.relative_to(CORE_DIR))] = bad
    assert not offenders, (
        "Core package src/trading_lab/ must not import MCP (it must work without "
        f"any wrapper). Offenders: {offenders}"
    )


def test_core_package_has_no_runtime_dependencies_declared():
    """The core must remain importable on a stdlib-only install."""
    pyproject = (CORE_DIR.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    # The dependencies array must stay empty (no runtime deps, MCP or otherwise).
    assert "dependencies = []" in pyproject
