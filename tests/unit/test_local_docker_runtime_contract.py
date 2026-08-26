from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


def test_local_docker_compose_sets_explicit_upstream_urls() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "path: .env" in compose_text
    assert "required: false" in compose_text
    assert (
        "LOTUS_CORE_BASE_URL: ${LOTUS_CORE_BASE_URL:-http://core-control.dev.lotus:8202}"
        in compose_text
    )
    assert (
        "LOTUS_PERFORMANCE_BASE_URL: ${LOTUS_PERFORMANCE_BASE_URL:-http://performance.dev.lotus:8002}"
        in compose_text
    )
    assert '"core-control.dev.lotus:host-gateway"' in compose_text
    assert '"performance.dev.lotus:host-gateway"' in compose_text


def test_env_example_documents_local_docker_upstream_defaults() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "LOTUS_CORE_BASE_URL=http://core-control.dev.lotus:8202" in env_example
    assert "LOTUS_PERFORMANCE_BASE_URL=http://performance.dev.lotus:8002" in env_example
    assert "Canonical hostnames remain the in-code defaults" in env_example
