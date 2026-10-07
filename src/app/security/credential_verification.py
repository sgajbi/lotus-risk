"""Strict compact-JWS admission with Ed25519 and deployment-trusted keys."""

import base64
import binascii
import json
import re
import time
from collections.abc import Callable, Mapping
from typing import Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.security.models import (
    PrincipalDenied,
    PrincipalKind,
    SecurityProviderUnavailable,
    VerifiedCredential,
)
from app.security.ports import RevocationProvider, TrustedKeyProvider, security_provider_call


def _decode(segment: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        raise ValueError("invalid compact encoding")
    decoded = base64.b64decode(segment + "=" * (-len(segment) % 4), altchars=b"-_", validate=True)
    if base64.urlsafe_b64encode(decoded).decode().rstrip("=") != segment:
        raise ValueError("noncanonical compact encoding")
    return decoded


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("non-JSON numeric constant")


def _object(segment: str) -> dict[str, Any]:
    value = json.loads(
        _decode(segment), object_pairs_hook=_unique_object, parse_constant=_invalid_constant
    )
    if not isinstance(value, dict):
        raise TypeError("object required")
    return value


def _text(claims: Mapping[str, Any], field: str) -> str:
    value = claims.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("invalid text claim")
    if len(value) > 512:
        raise ValueError("unbounded text claim")
    return value


def _compact_parts(credential: str) -> tuple[str, str, bytes, str]:
    if len(credential) > 16_384:
        raise ValueError("unbounded credential")
    header_part, claims_part, signature_part = credential.split(".")
    header = _object(header_part)
    if header.get("alg") != "EdDSA" or set(header) - {"alg", "kid", "typ"}:
        raise ValueError("unsupported protected header")
    if "typ" in header and header["typ"] != "JWT":
        raise ValueError("unsupported credential type")
    signature = _decode(signature_part)
    if len(signature) != 64:
        raise ValueError("invalid signature size")
    return header_part, claims_part, signature, _text(header, "kid")


def _audiences(claims: Mapping[str, Any]) -> list[str]:
    audience = claims.get("aud")
    values = [audience] if isinstance(audience, str) else audience
    if not isinstance(values, list) or not values:
        raise ValueError("invalid audience claim")
    for item in values:
        if not isinstance(item, str) or not item.strip() or item != item.strip():
            raise ValueError("invalid audience claim")
    return values


def _validate_time(claims: Mapping[str, Any], now: float) -> None:
    exp, nbf = claims.get("exp"), claims.get("nbf")
    if type(exp) is not int or (nbf is not None and type(nbf) is not int):
        raise ValueError("integer time claims required")
    if now >= exp or (nbf is not None and now < nbf):
        raise PrincipalDenied("expired_credential")


def _principal_identity(claims: Mapping[str, Any]) -> VerifiedCredential:
    kind = _text(claims, "principal_kind")
    if kind not in {"user", "service", "delegated"}:
        raise ValueError("unknown principal kind")
    actor = _text(claims, "act") if kind == "delegated" else None
    if kind != "delegated" and "act" in claims:
        raise ValueError("actor requires delegated kind")
    tenant = _text(claims, "tenant")
    if len(tenant) > 128:
        raise ValueError("unbounded tenant claim")
    return VerifiedCredential(
        subject=_text(claims, "sub"),
        tenant_id=tenant,
        kind=cast(PrincipalKind, kind),
        credential_id=_text(claims, "jti"),
        actor=actor,
    )


def _public_key(key: Mapping[str, Any]) -> Ed25519PublicKey:
    if key.get("kty") != "OKP" or key.get("crv") != "Ed25519":
        raise ValueError("wrong key type")
    if key.get("alg", "EdDSA") != "EdDSA" or key.get("use", "sig") != "sig":
        raise ValueError("wrong key use")
    return Ed25519PublicKey.from_public_bytes(_decode(_text(key, "x")))


class Ed25519CredentialVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        key_provider: TrustedKeyProvider,
        revocation: RevocationProvider,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not issuer.strip() or not audience.strip():
            raise ValueError("explicit issuer and audience required")
        self._issuer = issuer
        self._audience = audience
        self._keys = key_provider
        self._revocation = revocation
        self._clock = clock

    def verify(self, credential: str) -> VerifiedCredential:
        try:
            header_part, claims_part, signature, kid = _compact_parts(credential)
        except (ValueError, TypeError, binascii.Error, UnicodeError, RecursionError):
            raise PrincipalDenied("malformed_credential") from None
        key = self._key(kid)
        try:
            key.verify(signature, f"{header_part}.{claims_part}".encode("ascii"))
        except (InvalidSignature, UnicodeError):
            raise PrincipalDenied("present_but_unverified") from None
        try:
            claims = _object(claims_part)
            principal = self._claims(claims)
        except (ValueError, TypeError, binascii.Error, UnicodeError, RecursionError):
            raise PrincipalDenied("malformed_credential") from None
        revoked = security_provider_call(
            lambda: self._revocation.is_revoked(principal.credential_id, principal.subject)
        )
        if type(revoked) is not bool:
            raise SecurityProviderUnavailable()
        if revoked:
            raise PrincipalDenied("revoked_principal")
        return principal

    def _key(self, kid: str) -> Ed25519PublicKey:
        document = security_provider_call(self._keys.jwks)
        if not isinstance(document, Mapping):
            raise SecurityProviderUnavailable()
        keys = document.get("keys")
        if not isinstance(keys, list):
            raise PrincipalDenied("unknown_key_id")
        matching = [key for key in keys if isinstance(key, dict) and key.get("kid") == kid]
        if len(matching) != 1:
            raise PrincipalDenied("unknown_key_id")
        try:
            return _public_key(matching[0])
        except (ValueError, TypeError, binascii.Error):
            raise PrincipalDenied("unknown_key_id") from None

    def _claims(self, claims: dict[str, Any]) -> VerifiedCredential:
        if _text(claims, "iss") != self._issuer:
            raise PrincipalDenied("wrong_issuer")
        if self._audience not in _audiences(claims):
            raise PrincipalDenied("wrong_audience")
        _validate_time(claims, self._clock())
        return _principal_identity(claims)
