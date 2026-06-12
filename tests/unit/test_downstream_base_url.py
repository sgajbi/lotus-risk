from __future__ import annotations

from collections.abc import Callable

import pytest

from app.integrations.downstream_base_url import (
    resolve_downstream_base_url,
    validate_downstream_base_url,
)
from app.integrations.lotus_core_transport import resolve_lotus_core_base_url
from app.integrations.lotus_performance_transport import resolve_lotus_performance_base_url


def test_resolve_downstream_base_url_prefers_explicit_then_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_EXAMPLE_BASE_URL", "https://env.example.test/upstream/")

    assert (
        resolve_downstream_base_url(
            explicit_base_url="http://explicit.example.test/",
            env_name="LOTUS_EXAMPLE_BASE_URL",
            default_base_url="http://default.example.test",
        )
        == "http://explicit.example.test"
    )
    assert (
        resolve_downstream_base_url(
            explicit_base_url=None,
            env_name="LOTUS_EXAMPLE_BASE_URL",
            default_base_url="http://default.example.test",
        )
        == "https://env.example.test/upstream"
    )


@pytest.mark.parametrize(
    ("base_url", "message"),
    [
        ("ftp://upstream.example.test", "must use http or https"),
        ("http://", "must include a valid host"),
        ("http://upstream.example.test:0", "must include a valid host"),
        ("http://upstream.example.test:invalid", "must be a valid downstream base URL"),
        ("http://user:secret@upstream.example.test", "must not include credentials"),
        ("http://upstream.example.test?token=secret", "must not include a query string"),
        ("http://upstream.example.test?", "must not include a query string"),
        ("http://upstream.example.test#fragment", "must not include a query string"),
        ("http://up stream.example.test", "must not include whitespace"),
        (" http://upstream.example.test", "must not include whitespace"),
        ("http://upstream.example.test/\nunsafe", "must not include whitespace"),
    ],
)
def test_validate_downstream_base_url_rejects_unsafe_values_without_echoing_them(
    base_url: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message) as exc_info:
        validate_downstream_base_url(base_url, setting_name="LOTUS_EXAMPLE_BASE_URL")

    assert base_url not in str(exc_info.value)


def test_validate_downstream_base_url_accepts_https_ipv6_and_path_prefixes() -> None:
    assert (
        validate_downstream_base_url(
            "https://[2001:db8::1]:8443/risk-inputs/",
            setting_name="LOTUS_EXAMPLE_BASE_URL",
        )
        == "https://[2001:db8::1]:8443/risk-inputs"
    )


@pytest.mark.parametrize(
    "resolver",
    [resolve_lotus_core_base_url, resolve_lotus_performance_base_url],
)
def test_downstream_transport_resolvers_apply_shared_url_validation(
    resolver: Callable[[str | None], str],
) -> None:
    with pytest.raises(ValueError, match="must not include credentials"):
        resolver("http://user:secret@upstream.example.test")
