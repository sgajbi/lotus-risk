"""Real loopback HTTP admission and independent figures; synthetic identity only."""

import logging
import socket
import threading
import time
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
import uvicorn
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.app_factory import create_app
from app.integrations.lotus_core_client import LotusCoreClient
from app.routers import concentration, source_products
from app.security.configuration import PrincipalProviders
from app.security.credential_verification import Ed25519CredentialVerifier
from app.security.models import GrantSet, PrincipalDenied, SecurityProviderUnavailable
from app.services.concentration_engine import calculate_concentration
from app.services.risk_event_cohort_engine import evaluate_risk_event_affected_cohort
from app.services.scenario_engine import evaluate_regime_scenario_pack
from tests.unit.test_principal_credential_verification import (
    AUDIENCE,
    ISSUER,
    NOW,
    Keys,
    Revocations,
    claims,
    signed,
)
from tests.unit.test_principal_provider_boundaries import (
    DECLARED_CALLER_DENIALS,
    INVALID_VERIFIER_DENIALS,
)
from tests.unit.test_principal_resolution import INVALID_IDENTITIES, provider_identity

CONCENTRATION = "/analytics/risk/concentration"
SCENARIO = "/analytics/risk/regime-scenario-pack/evaluate"
COHORT = "/analytics/risk/risk-event-cohorts/evaluate"
CAPABILITIES = {
    CONCENTRATION: "test.concentration",
    SCENARIO: "test.scenario",
    COHORT: "test.cohort",
}


class HttpGrants:
    def __init__(self) -> None:
        self.unavailable = False
        self.raw_failure = False
        self.user_capabilities = frozenset(CAPABILITIES.values())
        self.application_capabilities = self.user_capabilities

    def tenant_members(self, subject: str, tenant_id: str) -> bool:
        if self.raw_failure:
            raise RuntimeError("provider-private-diagnostic")
        if self.unavailable:
            raise SecurityProviderUnavailable()
        return (subject, tenant_id) in {
            ("person-a", "tenant-a"),
            ("application-manage", "tenant-a"),
            ("person-b", "tenant-b"),
            ("application-other", "tenant-b"),
        }

    def grants_for(self, subject: str, tenant_id: str) -> GrantSet:
        return GrantSet(
            self.user_capabilities,
            frozenset({"portfolio-a" if tenant_id == "tenant-a" else "portfolio-b"}),
        )

    def application_grants_for(self, actor: str, tenant_id: str) -> GrantSet:
        return GrantSet(
            self.application_capabilities,
            frozenset({"portfolio-a" if tenant_id == "tenant-a" else "portfolio-b"}),
        )


@dataclass
class HttpRuntime:
    client: httpx.Client
    key: Ed25519PrivateKey
    grants: HttpGrants
    revocations: Revocations
    calls: Counter[str]
    keys: Keys
    identity_verifier: Ed25519CredentialVerifier

    def token(self, **changes: Any) -> str:
        return signed(self.key, claims(**changes))


@contextmanager
def loopback(app: Any) -> Iterator[httpx.Client]:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        config = uvicorn.Config(app, host="127.0.0.1", log_level="error", access_log=False)
        server = uvicorn.Server(config)
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not worker.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("owned HTTP server did not start")
                time.sleep(0.01)
            with httpx.Client(
                base_url=f"http://127.0.0.1:{listener.getsockname()[1]}", trust_env=False
            ) as client:
                yield client
        finally:
            server.should_exit = True
            worker.join(timeout=10)
            assert not worker.is_alive(), "owned HTTP server did not stop"


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[HttpRuntime]:
    import json

    monkeypatch.setenv("LOTUS_RISK_PRINCIPAL_POSTURE", "verified")
    monkeypatch.setenv("LOTUS_RISK_DEPLOYMENT_ENVIRONMENT", "local")
    monkeypatch.setenv("ENTERPRISE_ENFORCE_RUNTIME_CONFIG", "false")
    monkeypatch.setenv(
        "ENTERPRISE_CAPABILITY_RULES_JSON",
        json.dumps({f"POST {route}": value for route, value in CAPABILITIES.items()}),
    )
    key = Ed25519PrivateKey.generate()
    grants, revocations = HttpGrants(), Revocations()
    calls: Counter[str] = Counter()

    async def observed_concentration(*args: Any, **kwargs: Any) -> Any:
        calls[CONCENTRATION] += 1
        return await calculate_concentration(*args, **kwargs)

    def observed_scenario(*args: Any, **kwargs: Any) -> Any:
        calls[SCENARIO] += 1
        return evaluate_regime_scenario_pack(*args, **kwargs)

    def observed_cohort(*args: Any, **kwargs: Any) -> Any:
        calls[COHORT] += 1
        return evaluate_risk_event_affected_cohort(*args, **kwargs)

    monkeypatch.setattr(concentration, "calculate_concentration", observed_concentration)
    monkeypatch.setattr(source_products, "evaluate_regime_scenario_pack", observed_scenario)
    monkeypatch.setattr(source_products, "evaluate_risk_event_affected_cohort", observed_cohort)
    keys = Keys(key)
    identity_verifier = Ed25519CredentialVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        key_provider=keys,
        revocation=revocations,
        clock=lambda: NOW,
    )
    app = create_app(principal_providers=PrincipalProviders(identity_verifier, grants))
    with loopback(app) as client:
        yield HttpRuntime(client, key, grants, revocations, calls, keys, identity_verifier)


def payload(route: str, portfolio: str = "portfolio-a") -> dict[str, Any]:
    if route == CONCENTRATION:
        return {
            "input_mode": "stateless",
            "enrichment_policy": "use_caller_only",
            "stateless_input": {
                "current_positions": [
                    {"security_id": "EQ-A", "market_value_base": 75},
                    {"security_id": "EQ-B", "market_value_base": 25},
                ],
                "top_n": 2,
            },
        }
    if route == SCENARIO:
        return {
            "scenario_pack_id": "CIO_REGIME_2026_Q2",
            "portfolio_id": portfolio,
            "as_of_date": "2026-05-03",
            "exposures": [{"bucket": "EQUITY", "weight": 1}],
            "maximum_allowed_loss_pct": 0.12,
        }
    return {
        "risk_event_id": "RISK_EVENT_2026_Q2_RISK_OFF",
        "as_of_date": "2026-05-03",
        "portfolios": [{"portfolio_id": portfolio, "exposure_weights": {"EQUITY": 1}}],
        "minimum_impact_score": 0.12,
    }


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_admitted_registered_http_preserves_independent_economics(
    runtime: HttpRuntime, route: str
) -> None:
    response = runtime.client.post(
        route,
        json=payload(route),
        headers={
            "Authorization": "Bearer " + runtime.token(),
            "X-Tenant-Id": "adversarial-tenant",
            "X-Actor-Id": "adversarial-actor",
            "X-Capabilities": "forged",
            "X-Correlation-Id": "synthetic-admission",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert runtime.calls == {route: 1}
    if route == SCENARIO:
        assert result["worst_case_loss_pct"] == 0.18 and result["maximum_allowed_loss_pct"] == 0.12
        assert result["breach"] is True
        assert [item["expected_loss_pct"] for item in result["scenario_results"]] == [
            0.12,
            0.08,
            0.18,
        ]
        assert result["metadata"]["request_fingerprint"]
    elif route == COHORT:
        assert len(result["affected_portfolios"]) == 1
        assert result["affected_portfolios"][0]["impact_score"] == 0.18
        assert result["affected_portfolios"][0]["portfolio_id"] == "portfolio-a"
        assert result["metadata"]["request_fingerprint"]
    else:
        assert result["risk_proxy"]["hhi_current"] == 6250
        assert result["single_position_concentration"]["top_position_weight_current"] == 0.75


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_bearer_scheme_case_preserves_exact_credentials_and_refusals(
    runtime: HttpRuntime,
    route: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    verified_bytes: list[str] = []
    original = runtime.identity_verifier.verify

    def recording_verifier(credential: str) -> Any:
        verified_bytes.append(credential)
        return original(credential)

    monkeypatch.setattr(runtime.identity_verifier, "verify", recording_verifier)
    credential = runtime.token()
    for scheme in ("Bearer", "bearer", "bEaReR"):
        response = runtime.client.post(
            route, json=payload(route), headers={"Authorization": scheme + " " + credential}
        )
        assert response.status_code == 200, response.text
        result = response.json()
        if route == CONCENTRATION:
            assert result["risk_proxy"]["hhi_current"] == 6250
        elif route == SCENARIO:
            assert result["worst_case_loss_pct"] == 0.18
        else:
            assert result["affected_portfolios"][0]["impact_score"] == 0.18
    assert verified_bytes == [credential] * 3
    assert runtime.calls == {route: 3}

    refusals: list[tuple[list[tuple[str, str]], str]] = [
        ([], "missing_credential"),
        ([("Authorization", "")], "malformed_credential"),
        ([("Authorization", "Bearer")], "malformed_credential"),
        ([("Authorization", "Basic " + credential)], "malformed_credential"),
        ([("Authorization", "bearer  " + credential)], "malformed_credential"),
        (
            [("Authorization", "bearer " + credential), ("Authorization", "Bearer " + credential)],
            "malformed_credential",
        ),
    ]
    for headers, reason in refusals:
        with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
            refused = runtime.client.post(route, json=payload(route), headers=headers)
        assert refused.status_code == 401 and reason in refused.text
        assert runtime.calls == {route: 3}
        audits = [record.audit for record in caplog.records if hasattr(record, "audit")]
        assert audits and audits[-1]["actor_id"] == audits[-1]["tenant_id"] == "unverified"
        assert credential not in refused.text + str(audits)
        caplog.clear()
    # The extra space reaches the verifier unchanged and fails compact-JWS framing.
    assert verified_bytes == [credential] * 3 + [" " + credential]


DENIALS = [
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
    ("grant_store_unavailable", 503),
    ("delegated_capability_not_held_by_user", 403),
]


@pytest.mark.parametrize("route", list(CAPABILITIES))
@pytest.mark.parametrize(("reason", "status"), DENIALS)
def test_every_denial_precedes_protected_operation(
    runtime: HttpRuntime, route: str, reason: str, status: int
) -> None:
    token: str | None = runtime.token()
    body = payload(route)
    if reason == "missing_credential":
        token = None
    elif reason == "malformed_credential":
        token = "not-a-credential"
    elif reason == "expired_credential":
        token = runtime.token(exp=NOW)
    elif reason == "wrong_audience":
        token = runtime.token(aud="other-service")
    elif reason == "wrong_issuer":
        token = runtime.token(iss="https://wrong.example.test")
    elif reason == "unknown_key_id":
        token = signed(runtime.key, claims(), kid="unknown")
    elif reason == "revoked_principal":
        runtime.revocations.revoked = True
    elif reason == "present_but_unverified":
        token = signed(Ed25519PrivateKey.generate(), claims())
    elif reason == "tenant_not_a_member":
        token = runtime.token(tenant="foreign")
    elif reason == "capability_not_granted":
        runtime.grants.user_capabilities = runtime.grants.application_capabilities = frozenset()
    elif reason == "grant_store_unavailable":
        runtime.grants.unavailable = True
    elif reason == "delegated_capability_not_held_by_user":
        runtime.grants.user_capabilities = frozenset()
    elif route == CONCENTRATION:
        body = {
            "input_mode": "stateful",
            "stateful_input": {
                "portfolio_id": "foreign",
                "as_of_date": "2026-05-03",
                "reporting_currency": "USD",
            },
        }
    else:
        body = payload(route, "foreign")
    headers = {
        "X-Tenant-Id": "tenant-a",
        "X-Actor-Id": "person-a",
        "X-Role": "admin",
        "X-Capabilities": ",".join(CAPABILITIES.values()),
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    response = runtime.client.post(route, json=body, headers=headers)
    assert response.status_code == status, response.text
    assert reason in response.text
    assert runtime.calls == {}, "denial ran after protected calculation"
    assert "foreign" not in response.text and "person-a" not in response.text


def test_interleaved_tenants_cannot_use_headers_to_widen_scope(runtime: HttpRuntime) -> None:
    token_b = runtime.token(sub="person-b", tenant="tenant-b", act="application-other")

    def send(index: int) -> int:
        token, portfolio = (
            (runtime.token(), "portfolio-a") if index % 2 else (token_b, "portfolio-b")
        )
        response = runtime.client.post(
            COHORT,
            json=payload(COHORT, portfolio),
            headers={"Authorization": "Bearer " + token, "X-Tenant-Id": "forged"},
        )
        if response.status_code == 200:
            assert response.json()["affected_portfolios"][0]["portfolio_id"] == portfolio
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(send, range(12))) == [200] * 12
    before = sum(runtime.calls.values())
    refusal = runtime.client.post(
        COHORT,
        json=payload(COHORT, "portfolio-a"),
        headers={"Authorization": "Bearer " + token_b, "X-Tenant-Id": "tenant-a"},
    )
    assert refusal.status_code == 403 and sum(runtime.calls.values()) == before


def test_verified_denies_unconfigured_families_and_duplicate_authorization(
    runtime: HttpRuntime,
) -> None:
    headers = [
        ("Authorization", "Bearer " + runtime.token()),
        ("Authorization", "Bearer " + runtime.token()),
    ]
    assert runtime.client.post(SCENARIO, json=payload(SCENARIO), headers=headers).status_code == 401
    assert (
        runtime.client.post(
            "/analytics/risk/regime-scenario-pack/jobs",
            json={},
            headers={"Authorization": "Bearer " + runtime.token()},
        ).status_code
        == 403
    )
    assert runtime.calls == {}


@pytest.mark.parametrize("route", [CONCENTRATION, SCENARIO, COHORT])
@pytest.mark.parametrize("provider", ["revocation", "membership"])
def test_raw_provider_exceptions_are_bounded_unavailability(
    runtime: HttpRuntime,
    route: str,
    provider: str,
) -> None:
    if provider == "revocation":
        runtime.revocations.raw_failure = True
    else:
        runtime.grants.raw_failure = True
    response = runtime.client.post(
        route,
        json=payload(route),
        headers={"Authorization": "Bearer " + runtime.token()},
    )
    assert response.status_code == 503
    assert "grant_store_unavailable" in response.text
    assert "provider-private-diagnostic" not in response.text
    assert runtime.calls == {}


def test_early_refusal_normalizes_diagnostic_correlation_before_audit(
    runtime: HttpRuntime,
    caplog: pytest.LogCaptureFixture,
) -> None:
    rejected = "private-correlation-" * 50
    with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
        response = runtime.client.post(
            SCENARIO,
            json=payload(SCENARIO),
            headers={"X-Correlation-Id": rejected, "X-Actor-Id": "forged-person"},
        )
    assert response.status_code == 401 and runtime.calls == {}
    audit = next(record.audit for record in caplog.records if hasattr(record, "audit"))
    assert audit["actor_id"] == audit["tenant_id"] == "unverified"
    assert audit["correlation_id"] == response.headers["X-Correlation-Id"]
    assert 0 < len(audit["correlation_id"]) <= 128
    assert rejected not in str(audit)


@pytest.mark.parametrize("mode", ["simulation", "stateful", "stateless"])
@pytest.mark.parametrize(
    ("stateful_portfolio", "simulation_portfolio"),
    [
        ("portfolio-a", "foreign"),
        ("foreign", "portfolio-a"),
        ("portfolio-a", "portfolio-a"),
        ("portfolio-a", None),
        (None, "portfolio-a"),
        ("foreign", None),
        (None, "foreign"),
        (None, None),
    ],
)
def test_concentration_checks_every_named_portfolio_before_engine_and_core(
    runtime: HttpRuntime,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    stateful_portfolio: str | None,
    simulation_portfolio: str | None,
) -> None:
    core_calls: list[str] = []

    async def recording_core_boundary(self: LotusCoreClient, **kwargs: Any) -> Any:
        core_calls.append(kwargs["portfolio_id"])
        # Stop at the owned boundary: no external Core I/O or financial-success claim.
        raise ValueError("owned Core recording boundary reached")

    monkeypatch.setattr(LotusCoreClient, "create_simulation_session", recording_core_boundary)
    monkeypatch.setattr(LotusCoreClient, "get_core_snapshot", recording_core_boundary)
    body = payload(CONCENTRATION)
    body["input_mode"] = mode
    for name, portfolio in (
        ("stateful_input", stateful_portfolio),
        ("simulation_input", simulation_portfolio),
    ):
        if portfolio is not None:
            body[name] = {
                "portfolio_id": portfolio,
                "as_of_date": "2026-05-03",
                "reporting_currency": "USD",
            }
            if name == "simulation_input":
                body[name]["simulation_changes"] = []
    response = runtime.client.post(
        CONCENTRATION, json=body, headers={"Authorization": "Bearer " + runtime.token()}
    )
    selected_missing = (mode == "stateful" and stateful_portfolio is None) or (
        mode == "simulation" and simulation_portfolio is None
    )
    if selected_missing:
        assert response.status_code == 422, response.text
        assert runtime.calls == {} and core_calls == []
    elif "foreign" in (stateful_portfolio, simulation_portfolio):
        assert response.status_code == 403, response.text
        assert "portfolio_outside_scope" in response.text
        assert runtime.calls == {} and core_calls == []
    else:
        assert runtime.calls == {CONCENTRATION: 1}
        if mode == "stateless":
            assert response.status_code == 200, response.text
            assert response.json()["risk_proxy"]["hhi_current"] == 6250
            assert core_calls == []
        else:
            assert response.status_code == 400, response.text
            assert core_calls == ["portfolio-a"]


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_key_provider_failures_and_selection_controls_precede_engine(
    runtime: HttpRuntime, route: str, caplog: pytest.LogCaptureFixture
) -> None:
    original = runtime.keys.document
    entries = original["keys"]
    assert isinstance(entries, list)
    entry = entries[0]
    controls: list[tuple[dict[str, object], int]] = [
        ({}, 503),
        ({"keys": "provider-private-diagnostic"}, 503),
        ({"keys": [None]}, 503),
        ({"keys": [{}]}, 503),
        ({"keys": [{**entry, "kid": None}]}, 503),
        ({"keys": [{**entry, "kty": " OKP"}]}, 503),
        ({"keys": [{**entry, "x": "broken"}]}, 503),
        ({"keys": [{**entry, "kty": "RSA"}]}, 503),
        ({"keys": []}, 401),
        ({"keys": [entry, entry]}, 401),
        ({"keys": [{**entry, "kid": "other-key"}]}, 401),
    ]
    credential = runtime.token()
    for document, status in controls:
        runtime.keys.document = document
        with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
            response = runtime.client.post(
                route, json=payload(route), headers={"Authorization": "Bearer " + credential}
            )
        assert response.status_code == status, response.text
        assert ("grant_store_unavailable" if status == 503 else "unknown_key_id") in response.text
        assert runtime.calls == {}
        audits = [record.audit for record in caplog.records if hasattr(record, "audit")]
        assert audits and audits[-1]["actor_id"] == audits[-1]["tenant_id"] == "unverified"
        assert "provider-private-diagnostic" not in response.text + str(audits)
        assert credential not in response.text + str(audits)
        caplog.clear()
    runtime.keys.document = original
    recovered = runtime.client.post(
        route, json=payload(route), headers={"Authorization": "Bearer " + credential}
    )
    assert recovered.status_code == 200, recovered.text
    assert runtime.calls == {route: 1}


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_invalid_verifier_output_precedes_identity_lookup_and_engine(
    runtime: HttpRuntime,
    route: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    grant_calls: list[str] = []
    methods = ("tenant_members", "grants_for", "application_grants_for")
    original_grants = {method: getattr(runtime.grants, method) for method in methods}
    original_verify = runtime.identity_verifier.verify

    def unexpected_lookup(*args: Any) -> Any:
        grant_calls.append("lookup")
        raise AssertionError("grant lookup preceded verifier-result validation")

    for method in methods:
        monkeypatch.setattr(runtime.grants, method, unexpected_lookup)
    credential = runtime.token()
    invalid_results: tuple[object, ...] = (None, {}, "provider-private-diagnostic")
    for value in invalid_results:
        monkeypatch.setattr(
            runtime.identity_verifier, "verify", lambda credential, result=value: result
        )
        with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
            response = runtime.client.post(
                route, json=payload(route), headers={"Authorization": "Bearer " + credential}
            )
        assert response.status_code == 503 and "grant_store_unavailable" in response.text
        assert runtime.calls == {} and grant_calls == []
        audits = [record.audit for record in caplog.records if hasattr(record, "audit")]
        assert audits and audits[-1]["actor_id"] == audits[-1]["tenant_id"] == "unverified"
        assert "provider-private-diagnostic" not in response.text + str(audits)
        assert credential not in response.text + str(audits)
        caplog.clear()
    monkeypatch.setattr(runtime.identity_verifier, "verify", original_verify)
    for method, original in original_grants.items():
        monkeypatch.setattr(runtime.grants, method, original)
    recovered = runtime.client.post(
        route, json=payload(route), headers={"Authorization": "Bearer " + credential}
    )
    assert recovered.status_code == 200, recovered.text
    assert runtime.calls == {route: 1}


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_invalid_identity_fields_precede_lookup_and_engine_with_valid_kind_controls(
    runtime: HttpRuntime,
    route: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    grant_calls: list[str] = []
    methods = ("tenant_members", "grants_for", "application_grants_for")
    original_grants = {method: getattr(runtime.grants, method) for method in methods}

    def unexpected_lookup(*args: Any) -> Any:
        grant_calls.append("lookup")
        raise AssertionError("identity field validation must precede lookup")

    for method in methods:
        monkeypatch.setattr(runtime.grants, method, unexpected_lookup)
    credential = runtime.token()
    for changes in INVALID_IDENTITIES:
        identity = provider_identity(**changes)
        monkeypatch.setattr(
            runtime.identity_verifier, "verify", lambda credential, result=identity: result
        )
        with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
            response = runtime.client.post(
                route, json=payload(route), headers={"Authorization": "Bearer " + credential}
            )
        assert response.status_code == 503 and "grant_store_unavailable" in response.text
        assert runtime.calls == {} and grant_calls == []
        audits = [record.audit for record in caplog.records if hasattr(record, "audit")]
        assert audits and audits[-1]["actor_id"] == audits[-1]["tenant_id"] == "unverified"
        assert credential not in response.text + str(audits)
        assert "application-manage" not in response.text + str(audits)
        caplog.clear()
    for method, original in original_grants.items():
        monkeypatch.setattr(runtime.grants, method, original)
    for kind in ("user", "service", "delegated"):
        identity = provider_identity(
            kind=kind, actor="application-manage" if kind == "delegated" else None
        )
        monkeypatch.setattr(
            runtime.identity_verifier, "verify", lambda credential, result=identity: result
        )
        admitted = runtime.client.post(
            route, json=payload(route), headers={"Authorization": "Bearer " + credential}
        )
        assert admitted.status_code == 200, admitted.text
    assert runtime.calls == {route: 3}
    runtime.grants.application_capabilities = frozenset()
    refused = runtime.client.post(
        route, json=payload(route), headers={"Authorization": "Bearer " + credential}
    )
    assert refused.status_code == 403 and "capability_not_granted" in refused.text
    assert runtime.calls == {route: 3}


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_all_authority_adapter_denials_are_unavailability_not_public_status(
    runtime: HttpRuntime,
    route: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    targets = [
        ("key", runtime.keys, "jwks"),
        ("revocation", runtime.revocations, "is_revoked"),
        ("membership", runtime.grants, "tenant_members"),
        ("user_grants", runtime.grants, "grants_for"),
        ("delegated_membership", runtime.grants, "tenant_members"),
        ("application_grants", runtime.grants, "application_grants_for"),
    ]
    controls = [
        ("provider-private-diagnostic", 200),
        ("unknown_key_id", 401),
        ("capability_not_granted", 403),
        ("provider-private-diagnostic", 503),
    ]
    credential = runtime.token()
    for role, target, method in targets:
        original = getattr(target, method)
        for reason, status in controls:

            def adapter_failure(
                *args: Any,
                selected_role: str = role,
                original_call: Any = original,
                selected_reason: str = reason,
                selected_status: int = status,
            ) -> Any:
                if selected_role == "delegated_membership" and args[0] != "application-manage":
                    return original_call(*args)
                raise PrincipalDenied(selected_reason, selected_status)

            before = runtime.calls.copy()
            with monkeypatch.context() as scoped:
                scoped.setattr(target, method, adapter_failure)
                with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
                    response = runtime.client.post(
                        route,
                        json=payload(route),
                        headers={"Authorization": "Bearer " + credential},
                    )
            assert response.status_code == 503 and "grant_store_unavailable" in response.text
            assert runtime.calls == before
            audits = [record.audit for record in caplog.records if hasattr(record, "audit")]
            assert audits and audits[-1]["actor_id"] == audits[-1]["tenant_id"] == "unverified"
            assert audits[-1]["metadata"]["reason"] == "grant_store_unavailable"
            assert "provider-private-diagnostic" not in response.text + str(audits)
            assert credential not in response.text + str(audits)
            caplog.clear()
        recovered = runtime.client.post(
            route, json=payload(route), headers={"Authorization": "Bearer " + credential}
        )
        assert recovered.status_code == 200, recovered.text
    assert runtime.calls == {route: len(targets)}


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_injected_verifier_denials_must_obey_declared_caller_contract(
    runtime: HttpRuntime,
    route: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    credential = runtime.token()
    for reason, status in [*INVALID_VERIFIER_DENIALS, *DECLARED_CALLER_DENIALS]:

        def verifier_denial(
            credential: str, selected_reason: Any = reason, selected_status: Any = status
        ) -> Any:
            raise PrincipalDenied(selected_reason, selected_status)

        expected_status = status if (reason, status) in DECLARED_CALLER_DENIALS else 503
        # Float 401 compares equal in Python; it is not an integer contract status.
        if type(status) is not int:
            expected_status = 503
        expected_reason = reason if expected_status != 503 else "grant_store_unavailable"
        with monkeypatch.context() as scoped:
            scoped.setattr(runtime.identity_verifier, "verify", verifier_denial)
            with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
                response = runtime.client.post(
                    route, json=payload(route), headers={"Authorization": "Bearer " + credential}
                )
        assert response.status_code == expected_status and expected_reason in response.text
        assert runtime.calls == {}
        audits = [record.audit for record in caplog.records if hasattr(record, "audit")]
        assert audits and audits[-1]["actor_id"] == audits[-1]["tenant_id"] == "unverified"
        assert "provider-private-diagnostic" not in response.text + str(audits)
        assert credential not in response.text + str(audits)
        caplog.clear()
    recovered = runtime.client.post(
        route, json=payload(route), headers={"Authorization": "Bearer " + credential}
    )
    assert recovered.status_code == 200, recovered.text
    assert runtime.calls == {route: 1}
