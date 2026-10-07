"""Actual signed bytes, including foreign-key and malformed claim controls."""

import base64
import json
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.security.credential_verification import Ed25519CredentialVerifier
from app.security.models import PrincipalDenied, SecurityProviderUnavailable

NOW = 1_800_000_000
ISSUER = "https://identity.example.test"
AUDIENCE = "lotus-risk"


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def claims(**changes: Any) -> dict[str, Any]:
    return {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "person-a",
        "tenant": "tenant-a",
        "principal_kind": "delegated",
        "act": "application-manage",
        "exp": NOW + 60,
        "nbf": NOW - 60,
        "jti": "credential-a",
        **changes,
    }


def signed(
    key: Ed25519PrivateKey,
    payload: dict[str, Any],
    *,
    kid: str = "test-key",
    raw_payload: bytes | None = None,
    algorithm: str = "EdDSA",
) -> str:
    header = encoded(json.dumps({"alg": algorithm, "kid": kid, "typ": "JWT"}).encode())
    body = encoded(raw_payload if raw_payload is not None else json.dumps(payload).encode())
    message = f"{header}.{body}"
    return message + "." + encoded(key.sign(message.encode()))


class Keys:
    def __init__(self, key: Ed25519PrivateKey) -> None:
        self.document: dict[str, object] = {
            "keys": [
                {
                    "kid": "test-key",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": encoded(key.public_key().public_bytes_raw()),
                }
            ]
        }

    def jwks(self) -> dict[str, object]:
        return self.document


class Revocations:
    def __init__(
        self, *, revoked: bool = False, unavailable: bool = False, raw_failure: bool = False
    ) -> None:
        self.revoked = revoked
        self.unavailable = unavailable
        self.raw_failure = raw_failure

    def is_revoked(self, credential_id: str, subject: str) -> bool:
        if self.raw_failure:
            raise RuntimeError("provider-private-diagnostic")
        if self.unavailable:
            raise SecurityProviderUnavailable()
        return self.revoked


def verifier(
    key: Ed25519PrivateKey, *, revocation: Revocations | None = None
) -> Ed25519CredentialVerifier:
    return Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=Keys(key),
        revocation=revocation or Revocations(),
        clock=lambda: NOW,
    )


@pytest.mark.parametrize("kind", ["user", "service", "delegated"])
def test_signature_verifies_and_retains_principal_kind(kind: str) -> None:
    key = Ed25519PrivateKey.generate()
    payload = claims(principal_kind=kind)
    if kind != "delegated":
        payload.pop("act")
    result = verifier(key).verify(signed(key, payload))
    assert result.kind == kind and result.tenant_id == "tenant-a"


def test_foreign_key_control_is_about_signature_not_shape() -> None:
    trusted, foreign = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    token = signed(foreign, claims())
    with pytest.raises(PrincipalDenied, match="present_but_unverified"):
        verifier(trusted).verify(token)
    assert verifier(foreign).verify(token).subject == "person-a"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"iss": "https://wrong.example.test"}, "wrong_issuer"),
        ({"aud": "lotus-manage"}, "wrong_audience"),
        ({"exp": NOW}, "expired_credential"),
        ({"nbf": NOW + 1}, "expired_credential"),
        ({"exp": True}, "malformed_credential"),
        ({"exp": "tomorrow"}, "malformed_credential"),
        ({"principal_kind": "other"}, "malformed_credential"),
        ({"tenant": " "}, "malformed_credential"),
        ({"tenant": "t" * 129}, "malformed_credential"),
        ({"act": None}, "malformed_credential"),
        ({"aud": []}, "malformed_credential"),
    ],
)
def test_signed_claim_validation_is_strict(changes: dict[str, Any], reason: str) -> None:
    key = Ed25519PrivateKey.generate()
    with pytest.raises(PrincipalDenied, match=reason):
        verifier(key).verify(signed(key, claims(**changes)))


@pytest.mark.parametrize(
    "raw",
    [
        b'{"sub":"first","sub":"second"}',
        b"[]",
        b"{",
        b"null",
        b'{"extra":NaN}',
        b'{"extra":Infinity}',
        b"[" * 2000,
    ],
)
def test_duplicate_and_nonobject_signed_claims_refuse(raw: bytes) -> None:
    key = Ed25519PrivateKey.generate()
    with pytest.raises(PrincipalDenied, match="malformed_credential"):
        verifier(key).verify(signed(key, claims(), raw_payload=raw))


@pytest.mark.parametrize("token", ["", "x.y", "a.b.c.d", "a=.b.c", "a.b.c", " "])
def test_invalid_compact_framing_refuses(token: str) -> None:
    with pytest.raises(PrincipalDenied, match="malformed_credential"):
        verifier(Ed25519PrivateKey.generate()).verify(token)


def test_alg_none_and_unknown_key_and_revocation_refuse() -> None:
    key = Ed25519PrivateKey.generate()
    for token, instance, reason in [
        (signed(key, claims(), algorithm="none"), verifier(key), "malformed_credential"),
        (signed(key, claims(), kid="foreign-id"), verifier(key), "unknown_key_id"),
        (
            signed(key, claims()),
            verifier(key, revocation=Revocations(revoked=True)),
            "revoked_principal",
        ),
    ]:
        with pytest.raises(PrincipalDenied, match=reason):
            instance.verify(token)


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"keys": "provider-private-diagnostic"},
        {"keys": [None]},
        {"keys": [{}]},
        {"keys": [{"kty": "OKP", "kid": None}]},
        {"keys": [{"kty": " OKP", "kid": "test-key"}]},
        {"keys": [{"kid": "test-key", "kty": "OKP", "crv": "Ed25519", "x": "broken"}]},
        {"keys": [{"kid": "test-key", "kty": "RSA", "crv": "Ed25519", "x": "broken"}]},
    ],
)
def test_malformed_trusted_key_provider_is_unavailable(document: dict[str, Any]) -> None:
    key = Ed25519PrivateKey.generate()
    provider = Keys(key)
    provider.document = document
    instance = Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=provider,
        revocation=Revocations(),
        clock=lambda: NOW,
    )
    with pytest.raises(SecurityProviderUnavailable):
        instance.verify(signed(key, claims()))


@pytest.mark.parametrize("selection", ["empty", "duplicate", "no-match"])
def test_well_formed_key_selection_failure_remains_unknown_key(selection: str) -> None:
    key = Ed25519PrivateKey.generate()
    provider = Keys(key)
    entries = provider.document["keys"]
    assert isinstance(entries, list)
    entry = entries[0]
    provider.document = {"keys": [] if selection == "empty" else [entry, entry]}
    instance = Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=provider,
        revocation=Revocations(),
        clock=lambda: NOW,
    )
    with pytest.raises(PrincipalDenied, match="unknown_key_id") as denial:
        instance.verify(
            signed(key, claims(), kid="foreign-id" if selection == "no-match" else "test-key")
        )
    assert denial.value.status == 401


def test_signature_failure_precedes_invalid_claims() -> None:
    key = Ed25519PrivateKey.generate()
    foreign = Ed25519PrivateKey.generate()
    with pytest.raises(PrincipalDenied, match="present_but_unverified"):
        verifier(key).verify(signed(foreign, claims(iss="wrong", exp=0)))


def test_provider_identity_bounds_match_actual_signed_claim_vocabulary() -> None:
    key = Ed25519PrivateKey.generate()
    identity = verifier(key).verify(
        signed(
            key,
            claims(
                sub="s" * 512,
                tenant="t" * 128,
                jti="i" * 512,
                act="a" * 512,
            ),
        )
    )
    identity.require_valid_provider_result()
    assert identity.kind == "delegated" and len(identity.tenant_id) == 128
