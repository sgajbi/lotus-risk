"""Membership and delegated scope/capability are refusals, not filters."""

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.security.configuration import PrincipalProviders, PrincipalSecurityConfiguration
from app.security.models import GrantSet, PrincipalDenied, SecurityProviderUnavailable
from app.security.resolution import resolve_principal
from tests.unit.test_principal_credential_verification import claims, signed, verifier


class Grants:
    def __init__(
        self,
        *,
        member: bool = True,
        user_capabilities: frozenset[str] = frozenset({"risk.test"}),
        application_capabilities: frozenset[str] = frozenset({"risk.test"}),
        unavailable: bool = False,
    ) -> None:
        self.member = member
        self.unavailable = unavailable
        self.user = GrantSet(user_capabilities, frozenset({"portfolio-a", "person-only"}))
        self.application = GrantSet(
            application_capabilities, frozenset({"portfolio-a", "app-only"})
        )
        self.application_calls = 0

    def tenant_members(self, subject: str, tenant_id: str) -> bool:
        if self.unavailable:
            raise SecurityProviderUnavailable()
        return self.member and tenant_id == "tenant-a"

    def grants_for(self, subject: str, tenant_id: str) -> GrantSet:
        return self.user

    def application_grants_for(self, actor: str, tenant_id: str) -> GrantSet:
        self.application_calls += 1
        return self.application


def test_delegated_intersection_requires_every_portfolio() -> None:
    key = Ed25519PrivateKey.generate()
    result = resolve_principal(
        credential=signed(key, claims()),
        capability="risk.test",
        providers=PrincipalProviders(verifier(key), Grants()),
    )
    assert result.grants.portfolio_ids == frozenset({"portfolio-a"})
    result.require_portfolios(["portfolio-a"])
    for portfolios in [["person-only"], ["app-only"], ["portfolio-a", "foreign"]]:
        with pytest.raises(PrincipalDenied, match="portfolio_outside_scope"):
            result.require_portfolios(portfolios)


@pytest.mark.parametrize(
    ("store", "reason", "status"),
    [
        (None, "grant_store_unavailable", 503),
        (Grants(unavailable=True), "grant_store_unavailable", 503),
        (Grants(member=False), "tenant_not_a_member", 403),
        (Grants(user_capabilities=frozenset()), "delegated_capability_not_held_by_user", 403),
        (Grants(application_capabilities=frozenset()), "capability_not_granted", 403),
    ],
)
def test_resolver_refuses_missing_or_inadequate_authority(
    store: Grants | None, reason: str, status: int
) -> None:
    key = Ed25519PrivateKey.generate()
    with pytest.raises(PrincipalDenied, match=reason) as denial:
        resolve_principal(
            credential=signed(key, claims()),
            capability="risk.test",
            providers=PrincipalProviders(verifier(key), store),
        )
    assert denial.value.status == status


def test_service_does_not_require_application_grants_and_missing_verifier_denies() -> None:
    key = Ed25519PrivateKey.generate()
    payload = claims(principal_kind="service")
    payload.pop("act")
    store = Grants()
    result = resolve_principal(
        credential=signed(key, payload),
        capability="risk.test",
        providers=PrincipalProviders(verifier(key), store),
    )
    assert result.credential.kind == "service" and store.application_calls == 0
    with pytest.raises(PrincipalDenied, match="grant_store_unavailable"):
        resolve_principal(
            credential=signed(key, payload), capability="risk.test", providers=PrincipalProviders()
        )
    with pytest.raises(PrincipalDenied, match="missing_credential"):
        resolve_principal(credential=None, capability="risk.test", providers=PrincipalProviders())


def test_posture_is_deployment_selected_and_no_promoted_header_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", "production")
    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", "header-trust")
    with pytest.raises(RuntimeError, match="header_trust_requires_local_or_dev"):
        PrincipalSecurityConfiguration.from_environment()
    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", "verified")
    assert PrincipalSecurityConfiguration.from_environment().posture == "verified"
    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", "unsupported")
    with pytest.raises(RuntimeError, match="invalid_principal_posture"):
        PrincipalSecurityConfiguration.from_environment()


def test_revocation_outage_and_missing_capability_fail_closed() -> None:
    from tests.unit.test_principal_credential_verification import Revocations

    key = Ed25519PrivateKey.generate()
    with pytest.raises(PrincipalDenied, match="grant_store_unavailable") as denial:
        resolve_principal(
            credential=signed(key, claims()),
            capability="risk.test",
            providers=PrincipalProviders(
                verifier(key, revocation=Revocations(unavailable=True)), Grants()
            ),
        )
    assert denial.value.status == 503
    with pytest.raises(PrincipalDenied, match="capability_not_granted"):
        resolve_principal(
            credential=signed(key, claims()),
            capability=None,
            providers=PrincipalProviders(verifier(key), Grants()),
        )


@pytest.mark.parametrize("value", ["", " ", " risk.test", "risk.test "])
def test_malformed_grant_values_are_not_authority(value: str) -> None:
    with pytest.raises(SecurityProviderUnavailable):
        GrantSet(frozenset({value}), frozenset({"portfolio-a"}))
