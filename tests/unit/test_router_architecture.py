from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


ROUTERS_DIR = Path(__file__).resolve().parents[2] / "src" / "app" / "routers"


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_routers_do_not_import_downstream_infrastructure_clients_directly() -> None:
    violations: list[str] = []
    for router_path in sorted(ROUTERS_DIR.glob("*.py")):
        if router_path.name == "__init__.py":
            continue
        imported_modules = _imported_modules(ast.parse(router_path.read_text(encoding="utf-8")))
        if any(
            module == "app.integrations" or module.startswith("app.integrations.")
            for module in imported_modules
        ):
            violations.append(router_path.relative_to(ROUTERS_DIR.parents[2]).as_posix())

    assert violations == []
