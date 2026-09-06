"""Collection-time marking for byte-identical canonical lifts.

`tests/unit/test_branch_protection_policy.py` is lifted verbatim from the
canonical branch-protection gate implementation and must stay comparable to
its canonical blob, so it carries no in-file `pytestmark`. Marking it here
keeps this repository's pyramid accounting exact - the module is governance,
not a product test - without touching a file whose whole value is that it has
not been touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

#: Lifted modules that must not be edited to carry an in-file marker.
_CANONICAL_LIFT_MODULES = {"test_branch_protection_policy"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if Path(str(item.fspath)).stem in _CANONICAL_LIFT_MODULES:
            item.add_marker("governance")
