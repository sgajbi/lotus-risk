from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


LIVE_TEST_FILES = [
    Path("tests/integration/test_concentration_live_characterization.py"),
    Path("tests/integration/test_drawdown_live_characterization.py"),
    Path("tests/integration/test_historical_attribution_live_characterization.py"),
    Path("tests/integration/test_risk_calculate_live_characterization.py"),
    Path("tests/integration/test_rolling_live_characterization.py"),
]


def test_live_characterization_tests_use_canonical_direct_local_ports() -> None:
    defaults = "\n".join(path.read_text(encoding="utf-8") for path in LIVE_TEST_FILES)

    assert 'LOTUS_RISK_BASE_URL", "http://localhost:8130"' in defaults
    assert 'LOTUS_PERFORMANCE_BASE_URL", "http://localhost:8002"' in defaults
    assert 'LOTUS_CORE_BASE_URL", "http://localhost:8202"' in defaults
    assert "LOTUS_CORE_QUERY_BASE_URL" in defaults

    performance_lines = [
        line
        for line in defaults.splitlines()
        if "LOTUS_PERFORMANCE_BASE_URL" in line or "PERFORMANCE_BASE_URL" in line
    ]
    core_lines = [
        line
        for line in defaults.splitlines()
        if "LOTUS_CORE_BASE_URL" in line or "CORE_BASE_URL" in line
    ]

    assert all(
        "localhost:8201" not in line and "localhost:8202" not in line for line in performance_lines
    )
    assert all("localhost:8002" not in line for line in core_lines)


def test_local_runtime_docs_name_canonical_upstream_ports() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")
    operations_doc = Path("docs/operations/canonical-local-upstream-urls.md").read_text(
        encoding="utf-8"
    )

    for text in (readme, env_example, operations_doc):
        assert "http://performance.dev.lotus:8002" in text
        assert "http://core-control.dev.lotus:8202" in text

    assert "localhost:8201" in operations_doc
    assert "lotus-core query control-plane" in operations_doc
    assert "lotus-performance analytics" in operations_doc
