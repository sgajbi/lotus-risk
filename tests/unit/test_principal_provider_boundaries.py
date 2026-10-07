"""Exception origin, not adapter-controlled status/text, determines public denial."""

from typing import Any

import pytest

from app.security.models import PrincipalDenied, SecurityProviderUnavailable
from app.security.ports import credential_verifier_call, security_provider_call


@pytest.mark.parametrize(
    ("reason", "status"),
    [
        ("provider-private-diagnostic", 200),
        ("unknown_key_id", 401),
        ("capability_not_granted", 403),
        ("provider-private-diagnostic", 503),
    ],
)
def test_external_authority_denials_are_always_unavailable(reason: str, status: int) -> None:
    def provider() -> Any:
        raise PrincipalDenied(reason, status)

    with pytest.raises(SecurityProviderUnavailable):
        security_provider_call(provider)


def test_successful_external_authority_result_is_unchanged() -> None:
    value = object()
    assert security_provider_call(lambda: value) is value
    assert credential_verifier_call(lambda: value) is value


DECLARED_CALLER_DENIALS = [
    ("missing_credential", 401),
    ("malformed_credential", 401),
    ("expired_credential", 401),
    ("wrong_audience", 401),
    ("wrong_issuer", 401),
    ("unknown_key_id", 401),
    ("revoked_principal", 401),
    ("present_but_unverified", 401),
    ("tenant_not_a_member", 403),
    ("capability_not_granted", 403),
    ("portfolio_outside_scope", 403),
    ("delegated_capability_not_held_by_user", 403),
    ("grant_store_unavailable", 503),
]
INVALID_VERIFIER_DENIALS: list[tuple[Any, Any]] = [
    ("provider-private-diagnostic", 200),
    ("provider-private-diagnostic", 401),
    ("provider-private-diagnostic", 503),
    ("unknown_key_id", 200),
    ("expired_credential", 403),
    ("unknown_key_id", 401.0),
    ("unknown_key_id", "401"),
    ("unknown_key_id", True),
    (None, 401),
    ([], 401),
    ({}, 401),
]


@pytest.mark.parametrize(("reason", "status"), DECLARED_CALLER_DENIALS)
def test_declared_verifier_caller_denials_remain_bounded(reason: str, status: int) -> None:
    failure = PrincipalDenied(reason, status)

    def verifier() -> Any:
        raise failure

    with pytest.raises(PrincipalDenied) as denied:
        credential_verifier_call(verifier)
    assert denied.value.reason == reason and denied.value.status == status
    assert denied.value is not failure


@pytest.mark.parametrize(("reason", "status"), INVALID_VERIFIER_DENIALS)
def test_verifier_cannot_select_arbitrary_public_denials(reason: Any, status: Any) -> None:
    def verifier() -> Any:
        raise PrincipalDenied(reason, status)

    with pytest.raises(SecurityProviderUnavailable):
        credential_verifier_call(verifier)


def test_raw_verifier_exception_is_unavailable() -> None:
    def verifier() -> Any:
        raise RuntimeError("provider-private-diagnostic")

    with pytest.raises(SecurityProviderUnavailable):
        credential_verifier_call(verifier)
