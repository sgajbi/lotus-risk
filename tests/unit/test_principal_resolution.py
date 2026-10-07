"""Membership and delegated scope/capability are refusals, not filters."""

from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.security.configuration import PrincipalProviders, PrincipalSecurityConfiguration
from app.security.models import (
    GrantSet,
    PrincipalDenied,
    SecurityProviderUnavailable,
    VerifiedCredential,
)
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


def test_actual_app_factory_rejects_production_header_trust_and_invents_no_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.app_factory import create_app

    monkeypatch.setenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", "production")
    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", "header-trust")
    with pytest.raises(RuntimeError, match="header_trust_requires_local_or_dev"):
        create_app()
    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", "verified")
    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false")
    app = create_app()
    assert app.state.principal_security.environment == "production"
    assert app.state.principal_providers == PrincipalProviders()
    monkeypatch.setenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", " ")
    with pytest.raises(RuntimeError, match="invalid_deployment_environment"):
        create_app()


@pytest.mark.parametrize(
    ("environment", "posture"),
    [
        (None, None),
        (None, "verified"),
        ("production", None),
        ("", "verified"),
        (" ", "verified"),
        ("production ", "verified"),
        ("unsupported", "verified"),
        ("production", ""),
        ("production", " "),
        ("production", "verified "),
        ("production", "unsupported"),
        ("production", "header-trust"),
    ],
)
def test_enforced_deployment_refuses_implicit_or_invalid_classification(
    monkeypatch: pytest.MonkeyPatch, environment: str | None, posture: str | None
) -> None:
    from app.app_factory import create_app
    from app.enterprise_readiness import validate_enterprise_runtime_config
    from tests.unit.test_enterprise_readiness import _set_valid_enterprise_runtime_config

    _set_valid_enterprise_runtime_config(monkeypatch)
    for name, value in (
        ("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", environment),
        ("LOTUS_RISK_PRINCIPAL_POSTURE", posture),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        create_app()
    with pytest.raises(RuntimeError, match="enterprise_runtime_config_invalid"):
        validate_enterprise_runtime_config()


@pytest.mark.parametrize("environment", ["local", "dev", "test", "staging", "production"])
def test_enforced_explicit_verified_classification_is_accepted(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    from app.app_factory import create_app
    from app.enterprise_readiness import validate_enterprise_runtime_config
    from tests.unit.test_enterprise_readiness import _set_valid_enterprise_runtime_config

    _set_valid_enterprise_runtime_config(monkeypatch)
    monkeypatch.setenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", environment)
    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", "verified")
    assert validate_enterprise_runtime_config() == []
    assert create_app().state.principal_security.environment == environment


@pytest.mark.parametrize("environment", ["local", "dev"])
def test_enforced_explicit_developer_header_trust_is_retained(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "true")
    monkeypatch.setenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", environment)
    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", "header-trust")
    assert PrincipalSecurityConfiguration.from_environment().posture == "header-trust"


def test_non_enforced_developer_defaults_are_retained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false")
    monkeypatch.delenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("LOTUS_RISK_PRINCIPAL_POSTURE", raising=False)
    assert PrincipalSecurityConfiguration.from_environment() == PrincipalSecurityConfiguration(
        "header-trust", "local"
    )


@pytest.mark.parametrize("value", [None, {}, "provider-private-diagnostic"])
def test_invalid_verified_provider_result_refuses_before_grant_lookup(
    monkeypatch: pytest.MonkeyPatch, value: Any
) -> None:
    class InvalidVerifier:
        def verify(self, credential: str) -> Any:
            return value

    store = Grants()
    calls: list[str] = []

    def unexpected_lookup(*args: Any) -> Any:
        calls.append("lookup")
        raise AssertionError("grant lookup preceded provider validation")

    for method in ("tenant_members", "grants_for", "application_grants_for"):
        monkeypatch.setattr(store, method, unexpected_lookup)
    with pytest.raises(PrincipalDenied, match="grant_store_unavailable") as denial:
        resolve_principal(
            credential="synthetic",
            capability="risk.test",
            providers=PrincipalProviders(InvalidVerifier(), store),
        )
    assert denial.value.status == 503 and calls == []


INVALID_TEXT_VALUES: tuple[object, ...] = (
    None,
    1,
    True,
    [],
    {},
    "",
    " ",
    " padded",
    "padded ",
    "x" * 513,
)
INVALID_KIND_VALUES: tuple[object, ...] = (None, 1, True, [], {}, "", "bogus", " user", "user ")
INVALID_IDENTITIES: list[dict[str, Any]] = [
    {field: value}
    for field in ("subject", "tenant_id", "credential_id")
    for value in INVALID_TEXT_VALUES
] + [
    {"tenant_id": "x" * 129},
    *({"kind": value} for value in INVALID_KIND_VALUES),
    *({"actor": value} for value in INVALID_TEXT_VALUES),
    {"kind": "user", "actor": "application-manage"},
    {"kind": "service", "actor": ""},
]


def provider_identity(**changes: Any) -> VerifiedCredential:
    return VerifiedCredential(
        **{
            "subject": "person-a",
            "tenant_id": "tenant-a",
            "kind": "delegated",
            "credential_id": "credential-a",
            "actor": "application-manage",
            **changes,
        }
    )


@pytest.mark.parametrize("changes", INVALID_IDENTITIES)
def test_malformed_identity_fields_refuse_before_membership(
    monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any]
) -> None:
    identity = provider_identity(**changes)

    class InjectedVerifier:
        def verify(self, credential: str) -> VerifiedCredential:
            return identity

    store = Grants()
    calls: list[str] = []

    def unexpected_lookup(*args: Any) -> Any:
        calls.append("lookup")
        raise AssertionError("identity validation must precede lookup")

    for method in ("tenant_members", "grants_for", "application_grants_for"):
        monkeypatch.setattr(store, method, unexpected_lookup)
    with pytest.raises(PrincipalDenied, match="grant_store_unavailable") as denial:
        resolve_principal(
            credential="synthetic",
            capability="risk.test",
            providers=PrincipalProviders(InjectedVerifier(), store),
        )
    assert denial.value.status == 503 and calls == []


@pytest.mark.parametrize("kind", ["user", "service", "delegated"])
def test_valid_provider_identity_preserves_kind_and_delegated_intersection(kind: str) -> None:
    identity = provider_identity(
        kind=kind, actor="application-manage" if kind == "delegated" else None
    )

    class InjectedVerifier:
        def verify(self, credential: str) -> VerifiedCredential:
            return identity

    store = Grants(application_capabilities=frozenset())
    providers = PrincipalProviders(InjectedVerifier(), store)
    if kind == "delegated":
        with pytest.raises(PrincipalDenied, match="capability_not_granted"):
            resolve_principal(credential="synthetic", capability="risk.test", providers=providers)
        admitted = resolve_principal(
            credential="synthetic",
            capability="risk.test",
            providers=PrincipalProviders(InjectedVerifier(), Grants()),
        )
        assert admitted.credential is identity
        assert admitted.grants.portfolio_ids == frozenset({"portfolio-a"})
    else:
        admitted = resolve_principal(
            credential="synthetic", capability="risk.test", providers=providers
        )
        assert admitted.credential is identity and store.application_calls == 0
