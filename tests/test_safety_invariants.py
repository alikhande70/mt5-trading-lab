"""Safety invariant tests for v0.1.0.

These tests are the guardrail for the project's core promise: trading-lab is a
local, offline, file-in / file-out analyzer. It must never grow trade-execution
features, broker credential handling, a network/server component, or a hard MCP
dependency. If anyone adds such code to ``src/`` these tests fail loudly.

They inspect the *source* of the package rather than its runtime behaviour, so
they catch a forbidden feature the moment it is written — before it can ever be
called. Detection is based on Python tokens / AST (not raw substring matching),
so disclaimers in docstrings and help text such as "No order was placed" or
"no broker connection" do NOT trip the checks: only real executable identifiers,
function definitions, and imports count.
"""

from __future__ import annotations

import argparse
import ast
import io
import tokenize
from pathlib import Path
from typing import Dict, List, Set, Tuple

from trading_lab.cli import _build_parser

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def _source_files() -> List[Path]:
    files = [p for p in SRC_DIR.rglob("*.py") if "__pycache__" not in p.parts]
    assert files, f"No source files found under {SRC_DIR}; test setup is wrong."
    return files


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code_identifiers(src: str) -> Set[str]:
    """All NAME tokens (identifiers) in executable code.

    String literals and comments are not NAME tokens, so this deliberately
    ignores text inside docstrings, disclaimers, and ``# comments``.
    """
    names: Set[str] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(src).readline)
        for tok in tokens:
            if tok.type == tokenize.NAME:
                names.add(tok.string)
    except (tokenize.TokenError, IndentationError):
        # Fall back to AST-derived names if tokenizing is interrupted.
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Name):
                names.add(node.id)
    return names


def _defined_function_names(src: str) -> Set[str]:
    names: Set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _imports(src: str) -> Tuple[Set[str], Set[str]]:
    """Return (top-level module roots imported, imported symbol names)."""
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


# --- 1. No order_send anywhere in src/ ---------------------------------------

def test_no_order_send_call_anywhere_in_src():
    """Strict: the literal `order_send(` must not appear anywhere in src/."""
    offenders: List[str] = []
    for path in _source_files():
        if "order_send(" in _read(path):
            offenders.append(str(path.relative_to(SRC_DIR)))
    assert not offenders, f"`order_send(` found in: {offenders}"


def test_no_order_send_identifier_in_executable_code():
    offenders: List[str] = []
    for path in _source_files():
        if "order_send" in _code_identifiers(_read(path)):
            offenders.append(str(path.relative_to(SRC_DIR)))
    assert not offenders, f"`order_send` identifier used in executable code in: {offenders}"


# --- 2. No execution-named functions exist in src/ ---------------------------

FORBIDDEN_FUNCTION_NAMES = {
    "send_order",
    "place_order",
    "execute_trade",
    "modify_order",
    "cancel_order",
    "close_position",
    "close_order",
    "delete_order",
    "order_send",
}


def test_no_execution_named_functions_defined():
    offenders: Dict[str, Set[str]] = {}
    for path in _source_files():
        bad = _defined_function_names(_read(path)) & FORBIDDEN_FUNCTION_NAMES
        if bad:
            offenders[str(path.relative_to(SRC_DIR))] = bad
    assert not offenders, f"Execution-named function definitions found: {offenders}"


# --- 3. No broker credential handling exists in src/ -------------------------

FORBIDDEN_CREDENTIAL_NAMES = {
    "password",
    "account_password",
    "broker_password",
    "mt5_password",
    "login_password",
}


def test_no_credential_identifiers_in_executable_code():
    """Docs may say credentials are unused; src/ must not handle them.

    Only executable identifiers are checked, so a docstring mentioning
    "no password handling" would not trip this.
    """
    offenders: Dict[str, Set[str]] = {}
    for path in _source_files():
        bad = _code_identifiers(_read(path)) & FORBIDDEN_CREDENTIAL_NAMES
        if bad:
            offenders[str(path.relative_to(SRC_DIR))] = bad
    assert not offenders, f"Credential-handling identifiers found in src/: {offenders}"


# --- 4. No network / service / server dependency in src/ ---------------------

FORBIDDEN_NETWORK_MODULES = {
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "fastapi",
    "flask",
    "uvicorn",
    "websockets",
}


def test_no_network_or_server_imports():
    offenders: Dict[str, Set[str]] = {}
    for path in _source_files():
        roots, _ = _imports(_read(path))
        bad = roots & FORBIDDEN_NETWORK_MODULES
        if bad:
            offenders[str(path.relative_to(SRC_DIR))] = bad
    assert not offenders, f"Network/server imports found in src/: {offenders}"


# --- 5. No MCP dependency in src/ --------------------------------------------

FORBIDDEN_MCP_MODULES = {"mcp", "metatrader5_mcp", "mt5_mcp"}
FORBIDDEN_MCP_NAMES = {"FastMCP", "metatrader5_mcp", "mt5_mcp"}


def test_no_mcp_imports():
    offenders: Dict[str, Set[str]] = {}
    for path in _source_files():
        roots, names = _imports(_read(path))
        bad = (roots & FORBIDDEN_MCP_MODULES) | (names & FORBIDDEN_MCP_NAMES)
        if bad:
            offenders[str(path.relative_to(SRC_DIR))] = bad
    assert not offenders, f"MCP imports found in src/ (must be optional, not required): {offenders}"


# --- 6. CLI remains local file-in / file-out only ----------------------------

FORBIDDEN_CLI_COMMANDS = {
    "run-server",
    "daemon",
    "trade",
    "live",
    "execute",
    "send-order",
}


def _cli_subcommand_names() -> Set[str]:
    parser = _build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices.keys())
    return set()


def test_cli_exposes_analyze_report():
    assert "analyze-report" in _cli_subcommand_names()


def test_cli_does_not_expose_execution_commands():
    names = _cli_subcommand_names()
    bad = names & FORBIDDEN_CLI_COMMANDS
    assert not bad, f"CLI exposes forbidden command(s): {bad}"
