from __future__ import annotations

import ast
from pathlib import Path

from app.services.concentration.datamodels import PositionEntry, TopPositionDriverValue
from app.services.concentration.math import _top_position_driver


REPO_ROOT = Path(__file__).resolve().parents[2]
CONCENTRATION_MATH = REPO_ROOT / "src" / "app" / "services" / "concentration" / "math.py"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_concentration_math_does_not_import_public_response_dtos() -> None:
    assert all(
        not module.startswith("app.contracts") for module in _imported_modules(CONCENTRATION_MATH)
    )


def test_concentration_math_returns_internal_driver_value() -> None:
    driver = _top_position_driver(
        [
            PositionEntry(security_id="A", security_name="Alpha", value=25.0),
            PositionEntry(security_id="B", security_name="Beta", value=75.0),
        ]
    )

    assert driver == TopPositionDriverValue(
        security_id="B",
        security_name="Beta",
        weight=0.75,
    )
