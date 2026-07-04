from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGURATION_DOC = REPO_ROOT / "docs" / "configuration.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def test_configuration_document_pins_runtime_owned_settings_and_safe_url_policy() -> None:
    text = CONFIGURATION_DOC.read_text(encoding="utf-8")

    required_terms = (
        "LOTUS_CORE_BASE_URL",
        "LOTUS_CORE_MAX_CONNECTIONS",
        "LOTUS_CORE_MAX_KEEPALIVE_CONNECTIONS",
        "LOTUS_PERFORMANCE_BASE_URL",
        "LOTUS_PERFORMANCE_ASYNC_MAX_POLLS",
        "ENTERPRISE_ENFORCE_AUTHZ",
        "ENTERPRISE_ENFORCE_RUNTIME_CONFIG",
        "ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES",
        "ENTERPRISE_INGRESS_MAX_BODY_BYTES",
        "ENTERPRISE_ASGI_MAX_BODY_BYTES",
        "ENTERPRISE_TRUSTED_INGRESS_SECRET",
        "X-Lotus-Trusted-Ingress",
        "machine-readable",
        "Content-Length",
        "exclude embedded credentials",
        "never includes a rejected URL value",
        "SOURCE_FILE_MAX_LINES",
        "application construction fails closed",
        "bounded issue codes only",
        "missing_capability_rule",
        "most specific path rule wins",
    )
    for term in required_terms:
        assert term in text


def test_env_example_exposes_downstream_pool_controls() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")

    for dependency in ("LOTUS_CORE", "LOTUS_PERFORMANCE"):
        assert f"{dependency}_MAX_CONNECTIONS=100" in text
        assert f"{dependency}_MAX_KEEPALIVE_CONNECTIONS=20" in text
        assert f"{dependency}_KEEPALIVE_EXPIRY_SECONDS=5" in text
