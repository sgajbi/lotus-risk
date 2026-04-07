from pathlib import Path


def test_local_docker_compose_sets_explicit_upstream_urls() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert (
        "LOTUS_CORE_BASE_URL: ${LOTUS_CORE_BASE_URL:-http://core-query.dev.lotus}" in compose_text
    )
    assert (
        "LOTUS_PERFORMANCE_BASE_URL: ${LOTUS_PERFORMANCE_BASE_URL:-http://performance.dev.lotus}"
        in compose_text
    )
    assert '"core-query.dev.lotus:host-gateway"' in compose_text
    assert '"performance.dev.lotus:host-gateway"' in compose_text


def test_env_example_documents_local_docker_upstream_defaults() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "LOTUS_CORE_BASE_URL=http://core-query.dev.lotus" in env_example
    assert "LOTUS_PERFORMANCE_BASE_URL=http://performance.dev.lotus" in env_example
    assert "Canonical hostnames remain the in-code defaults" in env_example
