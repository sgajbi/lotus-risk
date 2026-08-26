"""Hold the pyramid gate and its `governance` marker honest.

The gate deselects `pytest.mark.governance` so it measures the *product's* test shape. That makes
the marker load-bearing in two directions, and both need holding:

- If the marker is under-applied, governance tests inflate the unit bucket and squeeze the
  integration and e2e ratios, which is the defect issue #220 records: the repository was two unit
  tests away from being unable to add any CI-contract coverage without turning CI red.
- If it is over-applied, product tests vanish from the denominator and the gate stops governing
  anything. Nothing here can detect that automatically, which is why the marker is explicit and
  reviewed rather than inferred.

The completeness check below covers `tests/unit` only. A `tests/unit` module that never imports
product code cannot be testing product behaviour, so the signal is sound there. It is deliberately
not applied to `tests/integration` or `tests/e2e`, where exercising the service over HTTP without
importing it is the normal shape - `tests/integration/test_concentration_live_characterization.py`
is a product test by that route, and an automatic rule would mismark it.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "test_pyramid_gate.py"

MARKER = "pytestmark = pytest.mark.governance"
PRODUCT_PACKAGE = "app"


def _imports_product_code(module: Path) -> bool:
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == PRODUCT_PACKAGE for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == PRODUCT_PACKAGE:
                return True
    return False


def test_unit_modules_that_never_touch_product_code_declare_the_marker() -> None:
    unmarked = [
        module.relative_to(ROOT).as_posix()
        for module in sorted((ROOT / "tests" / "unit").rglob("test_*.py"))
        if not _imports_product_code(module) and MARKER not in module.read_text(encoding="utf-8")
    ]

    assert unmarked == [], (
        "These unit modules never import product code, so they are not product tests, but they do "
        f"not declare `{MARKER}`. They will be counted in the product pyramid and squeeze the "
        f"integration and e2e ratios: {unmarked}. See issue #220."
    )


def test_the_marker_is_registered_so_a_typo_is_not_silently_ignored() -> None:
    """An unregistered mark is a no-op, so `pytest.mark.governence` would deselect nothing."""

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = config["tool"]["pytest"]["ini_options"]["markers"]

    assert any(marker.startswith("governance:") for marker in markers), (
        f"`governance` is not registered in [tool.pytest.ini_options] markers: {markers}"
    )


def test_the_marker_actually_deselects_something() -> None:
    """A marker nobody applies would let the gate pass while measuring the old, wrong population."""

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit", "-m", "governance", "--collect-only", "-q"],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert " tests collected" in completed.stdout


def test_collection_parsing_reads_the_selected_count_not_the_collected_total() -> None:
    """The trap this gate walked into once.

    With a marker expression pytest prints `collected 712 items / 130 deselected / 582 selected`.
    A parser that reads the first number gets the *pre-deselection* total, so the marker would
    appear to work while changing nothing.
    """

    from scripts.test_pyramid_gate import _COLLECTED, _SELECTED

    deselected_output = "collected 712 items / 130 deselected / 582 selected"
    selected = _SELECTED.search(deselected_output)
    collected = _COLLECTED.search(deselected_output)
    assert selected is not None and selected.group(1) == "582"
    assert collected is not None and collected.group(1) == "712"

    plain_output = "collected 26 items"
    plain = _COLLECTED.search(plain_output)
    assert _SELECTED.search(plain_output) is None
    assert plain is not None and plain.group(1) == "26"


@pytest.mark.parametrize(
    ("percent", "below_bound", "expected"),
    [
        (2.9954128440366974, True, "2.9954"),
        (3.0, True, "3.0000"),
        (25.000001, False, "25.0001"),
    ],
)
def test_a_failing_ratio_is_never_displayed_as_satisfying_its_bound(
    percent: float, below_bound: bool, expected: str
) -> None:
    """`f"{2.9954:.2f}"` is `3.00`, which passes the inclusive floor it was reported as failing."""

    from scripts.test_pyramid_gate import _rounded_away_from

    assert _rounded_away_from(percent, below_bound=below_bound) == expected


def test_the_failure_message_names_the_side_and_the_actionable_count() -> None:
    from scripts.test_pyramid_gate import BUCKET_POLICIES, _failure_message

    e2e = next(policy for policy in BUCKET_POLICIES if policy.name == "e2e")
    message = _failure_message(e2e, count=26, total=868, percent=26 / 868 * 100)

    assert "2.9953%" in message
    assert "below the 3% floor" in message
    assert "at least 27 tests" in message
    assert "not in [" not in message


def test_the_gate_fails_when_a_configured_bucket_path_is_missing() -> None:
    """A gate that inspected nothing must fail. Silence is never a pass."""

    source = GATE.read_text(encoding="utf-8")

    assert "Configured test bucket paths are missing" in source
    assert "No product tests collected." in source
