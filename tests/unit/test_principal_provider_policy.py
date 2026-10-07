"""Matching-key operation constraints and injected-clock contract controls."""

from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.security.credential_verification import Ed25519CredentialVerifier
from app.security.models import PrincipalDenied, SecurityProviderUnavailable
from tests.unit.test_principal_credential_verification import (
    AUDIENCE,
    ISSUER,
    NOW,
    Keys,
    Revocations,
    claims,
    signed,
)

INVALID_KEY_OPS: list[Any] = [
    None,
    "verify",
    [],
    ["encrypt"],
    ["sign"],
    ["verify", "verify"],
    ["verify", None],
    ["verify", {}],
    ["verify", "encrypt"],
    ["VERIFY"],
    ["verify", ""],
]
INVALID_CLOCKS: list[Any] = [
    float("nan"),
    float("inf"),
    -float("inf"),
    True,
    False,
    None,
    "1800000000",
    10**400,
]


@pytest.mark.parametrize("operations", INVALID_KEY_OPS)
def test_matching_key_operation_constraints_refuse_invalid_material(operations: Any) -> None:
    key = Ed25519PrivateKey.generate()
    provider = Keys(key)
    entries = provider.document["keys"]
    assert isinstance(entries, list)
    entries[0].update(use="sig", key_ops=operations)
    instance = Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=provider,
        revocation=Revocations(),
        clock=lambda: NOW,
    )
    with pytest.raises(SecurityProviderUnavailable):
        instance.verify(signed(key, claims()))


@pytest.mark.parametrize("operations", [None, ["verify"], ["sign", "verify"], ["verify", "sign"]])
def test_absent_or_valid_verification_operations_remain_admitted(
    operations: list[str] | None,
) -> None:
    key = Ed25519PrivateKey.generate()
    provider = Keys(key)
    entries = provider.document["keys"]
    assert isinstance(entries, list)
    if operations is not None:
        entries[0].update(use="sig", key_ops=operations)
    instance = Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=provider,
        revocation=Revocations(),
        clock=lambda: NOW,
    )
    assert instance.verify(signed(key, claims())).subject == "person-a"


@pytest.mark.parametrize("now", INVALID_CLOCKS)
@pytest.mark.parametrize("time_claims", [{"exp": 0}, {"nbf": NOW + 600}])
def test_faulty_clock_never_bypasses_temporal_authority(
    now: Any, time_claims: dict[str, int]
) -> None:
    key = Ed25519PrivateKey.generate()
    instance = Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=Keys(key),
        revocation=Revocations(),
        clock=lambda: now,
    )
    with pytest.raises(SecurityProviderUnavailable):
        instance.verify(signed(key, claims(**time_claims)))


@pytest.mark.parametrize(
    "failure", [RuntimeError("provider-private-diagnostic"), PrincipalDenied("private-clock", 200)]
)
def test_clock_exception_is_provider_unavailability(failure: Exception) -> None:
    def clock() -> float:
        raise failure

    key = Ed25519PrivateKey.generate()
    instance = Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=Keys(key),
        revocation=Revocations(),
        clock=clock,
    )
    with pytest.raises(SecurityProviderUnavailable):
        instance.verify(signed(key, claims()))


@pytest.mark.parametrize(
    ("now", "time_claims", "admitted"),
    [
        (NOW, {}, True),
        (float(NOW), {}, True),
        (NOW + 59.999, {}, True),
        (NOW + 60, {}, False),
        (NOW, {"nbf": NOW}, True),
        (NOW - 0.001, {"nbf": NOW}, False),
    ],
)
def test_finite_clock_retains_exact_expiry_and_not_before_boundaries(
    now: float,
    time_claims: dict[str, int],
    admitted: bool,
) -> None:
    key = Ed25519PrivateKey.generate()
    instance = Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=Keys(key),
        revocation=Revocations(),
        clock=lambda: now,
    )
    credential = signed(key, claims(**time_claims))
    if admitted:
        assert instance.verify(credential).subject == "person-a"
    else:
        with pytest.raises(PrincipalDenied, match="expired_credential") as denial:
            instance.verify(credential)
        assert denial.value.status == 401
