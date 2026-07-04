from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER_DIR = REPO_ROOT / "src" / "app" / "routers"
RUNTIME_PROVIDER = REPO_ROOT / "src" / "app" / "runtime" / "downstream_clients.py"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_routers_use_runtime_composition_boundary_for_downstream_clients() -> None:
    forbidden_modules = {
        "app.dependencies.downstream_clients",
        "app.integrations.lotus_core_client",
        "app.integrations.lotus_performance_client",
    }

    for router_path in ROUTER_DIR.glob("*.py"):
        imports = _imported_modules(router_path)
        assert not (imports & forbidden_modules), router_path


def test_runtime_provider_does_not_construct_concrete_downstream_clients() -> None:
    provider_text = RUNTIME_PROVIDER.read_text(encoding="utf-8")

    assert "app.integrations" not in provider_text
    assert "LotusCoreClient(" not in provider_text
    assert "LotusPerformanceClient(" not in provider_text
