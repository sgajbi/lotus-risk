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

MARKER_NAME = "governance"
PRODUCT_PACKAGE = "app"


def _is_governance_mark(node: ast.expr) -> bool:
    """Match `pytest.mark.governance` as an expression, not as text."""

    return (
        isinstance(node, ast.Attribute)
        and node.attr == MARKER_NAME
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    )


def _declares_governance_marker(module: Path) -> bool:
    """Whether pytest will actually apply the marker, not whether the text appears.

    A substring search over the source passes when the marker text sits in a comment, a docstring
    or an unrelated string constant, so a module that merely *mentions* the marker would satisfy
    the completeness guard while pytest never deselects it. It also rejects valid forms: an
    annotated assignment, or a list of markers.

    Reading the module-level `pytestmark` binding from the AST answers the question that matters:
    is this module actually marked.
    """

    tree = ast.parse(module.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            targets: list[ast.expr] = [node.target]
        elif isinstance(node, ast.Assign):
            targets = list(node.targets)
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets):
            continue
        value = node.value
        if value is None:
            continue
        candidates = list(value.elts) if isinstance(value, ast.List | ast.Tuple) else [value]
        if any(_is_governance_mark(candidate) for candidate in candidates):
            return True
    return False


def _imports_product_code(module: Path) -> bool:
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == PRODUCT_PACKAGE for alias in node.names):
                return True
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.split(".")[0] == PRODUCT_PACKAGE
        ):
            return True
    return False


#: Modules lifted BYTE-IDENTICALLY from a canonical implementation in another
#: repository. They carry no in-file marker on purpose: editing one to add this
#: repository's convention would fork an estate-wide control and silently stop
#: it receiving canonical fixes, which is how a sibling's copy of this same
#: checker fell 102 lines behind. `tests/unit/conftest.py` marks them at
#: collection time instead, so the pyramid accounting is identical while the
#: file stays comparable to its canonical blob.
#: Retires when the module is no longer a verbatim lift.
CANONICAL_LIFTS = {"tests/unit/test_branch_protection_policy.py"}


def test_unit_modules_that_never_touch_product_code_declare_the_marker() -> None:
    unmarked = [
        path
        for module in sorted((ROOT / "tests" / "unit").rglob("test_*.py"))
        if (path := module.relative_to(ROOT).as_posix()) not in CANONICAL_LIFTS
        and not _imports_product_code(module)
        and not _declares_governance_marker(module)
    ]

    assert unmarked == [], (
        "These unit modules never import product code, so they are not product tests, but they do "
        f"not bind `pytestmark` to `pytest.mark.{MARKER_NAME}`. They will be counted in the "
        f"product pyramid and squeeze the integration and e2e ratios: {unmarked}. See issue #220."
    )


def test_every_canonical_lift_is_marked_at_collection_time() -> None:
    """The exemption above must not become a hole: a module that is exempt from
    the in-file marker still has to BE marked, or it lands in the product
    pyramid exactly as an unmarked module would. This pins the collection-time
    marking that replaces it, and fails if the conftest hook stops covering a
    listed module."""

    conftest = (ROOT / "tests" / "unit" / "conftest.py").read_text(encoding="utf-8")
    for lift in sorted(CANONICAL_LIFTS):
        module_name = Path(lift).stem
        assert module_name in conftest, (
            f"{lift} is exempt from the in-file marker but nothing marks it at collection time; "
            "it would be counted as a product test."
        )
    assert f'add_marker("{MARKER_NAME}")' in conftest or MARKER_NAME in conftest


MARKER_DECLARATION_CASES = {
    "pytestmark = pytest.mark.governance": True,
    "pytestmark = [pytest.mark.governance]": True,
    "pytestmark = (pytest.mark.governance,)": True,
    "pytestmark: object = pytest.mark.governance": True,
    "pytestmark = [pytest.mark.slow, pytest.mark.governance]": True,
    "# pytestmark = pytest.mark.governance": False,
    "NOTE = " + chr(34) + "pytestmark = pytest.mark.governance" + chr(34): False,
    "other = pytest.mark.governance": False,
    "pytestmark = pytest.mark.slow": False,
}


def test_the_marker_check_is_structural_rather_than_a_substring_match(tmp_path: Path) -> None:
    """A mention of the marker must not count as declaring it, and valid forms must count."""

    for source, expected in MARKER_DECLARATION_CASES.items():
        module = tmp_path / "test_case.py"
        module.write_text("import pytest" + chr(10) * 2 + source + chr(10), encoding="utf-8")
        assert _declares_governance_marker(module) is expected, source


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
    assert "not in [" not in message
    assert "the e2e bucket" in message

    # The under-shoot case the naive form got wrong: 14 of 100 against a 15% floor. Reporting
    # `min * total` advises 15, and 15/101 is 14.85% - still failing. The total moves with the
    # bucket, so two tests are needed.
    integration = next(policy for policy in BUCKET_POLICIES if policy.name == "integration")
    under_shooting = _failure_message(integration, count=14, total=100, percent=14.0)
    assert "Adding 2 product tests" in under_shooting, under_shooting

    # And the mirror: a bucket over its ceiling is cleared by growing the others, not by
    # deleting tests, which would shrink the total and move the ratio the wrong way.
    unit = next(policy for policy in BUCKET_POLICIES if policy.name == "unit")
    over_ceiling = _failure_message(unit, count=86, total=100, percent=86.0)
    assert "Adding 2 product tests to the other buckets" in over_ceiling, over_ceiling


def test_the_gate_fails_when_a_configured_bucket_path_is_missing() -> None:
    """A gate that inspected nothing must fail. Silence is never a pass."""

    source = GATE.read_text(encoding="utf-8")

    assert "Configured test bucket paths are missing" in source
    assert "No product tests collected." in source


# A tree that satisfies every bound, so headroom exists in both directions for each bucket. These
# are the counts this repository measures today; the exactness properties below are about the
# arithmetic, not about these particular numbers.
MEASURED_COUNTS = {"unit": 582, "integration": 128, "e2e": 26}


def test_headroom_is_published_on_every_run_not_only_on_failure() -> None:
    """A ratio near its bound is not visible as a number, only as a distance - issue #220."""

    completed = subprocess.run(
        [sys.executable, str(GATE)], cwd=ROOT, capture_output=True, text=True, check=False
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    for bucket in ("unit", "integration", "e2e"):
        line = next(row for row in completed.stdout.splitlines() if row.startswith(bucket + ":"))
        assert "headroom:" in line, line
        assert "before the floor" in line and "before the ceiling" in line, line


def test_headroom_to_the_floor_is_exact() -> None:
    """One more than the reported headroom must actually breach, and the headroom itself must not."""

    from scripts.test_pyramid_gate import BUCKET_POLICIES, _headroom

    # Each bucket measured against its own count. Using one bucket's count for all three would put
    # unit below its floor and e2e above its ceiling, where the exactness property does not apply
    # because there is no headroom to be exact about.
    total = sum(MEASURED_COUNTS.values())
    for policy in BUCKET_POLICIES:
        count = MEASURED_COUNTS[policy.name]
        to_floor, _ = _headroom(policy, count, total)
        assert to_floor > 0, (policy.name, to_floor)
        assert count / (total + to_floor) >= policy.min_ratio, (policy.name, to_floor)
        assert count / (total + to_floor + 1) < policy.min_ratio, (policy.name, to_floor)


def test_headroom_to_the_ceiling_is_exact() -> None:
    from scripts.test_pyramid_gate import BUCKET_POLICIES, _headroom

    total = sum(MEASURED_COUNTS.values())
    for policy in BUCKET_POLICIES:
        count = MEASURED_COUNTS[policy.name]
        _, to_ceiling = _headroom(policy, count, total)
        assert to_ceiling > 0, (policy.name, to_ceiling)
        assert (count + to_ceiling) / (total + to_ceiling) <= policy.max_ratio, policy.name
        assert (count + to_ceiling + 1) / (total + to_ceiling + 1) > policy.max_ratio, policy.name


def test_the_state_that_produced_this_issue_reports_two() -> None:
    """The incident, pinned to a number.

    On `39514f39` the suite was unit 708 / integration 130 / e2e 26, total 864. Both the 15% and 3%
    floors breach at total 867, so the repository could accept exactly two more tests of any kind
    before CI turned red - and the gate's output said only `15.05%` and `3.01%`. PR #219 added four.
    """

    from scripts.test_pyramid_gate import BUCKET_POLICIES, _headroom

    integration = next(policy for policy in BUCKET_POLICIES if policy.name == "integration")
    e2e = next(policy for policy in BUCKET_POLICIES if policy.name == "e2e")

    assert _headroom(integration, 130, 864)[0] == 2
    assert _headroom(e2e, 26, 864)[0] == 2


def test_headroom_never_reports_a_negative_distance() -> None:
    """A bucket already below its floor has no headroom, not negative headroom."""

    from scripts.test_pyramid_gate import BUCKET_POLICIES, _headroom

    integration = next(policy for policy in BUCKET_POLICIES if policy.name == "integration")
    to_floor, to_ceiling = _headroom(integration, 1, 1000)

    assert to_floor == 0
    assert to_ceiling >= 0
