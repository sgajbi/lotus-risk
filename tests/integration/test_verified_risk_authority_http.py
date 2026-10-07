"""Real loopback HTTP admission and independent figures; synthetic identity only."""

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
from app.routers import concentration, source_products
from app.security.configuration import PrincipalProviders
from app.security.models import GrantSet, SecurityProviderUnavailable
from app.services.concentration_engine import calculate_concentration
from app.services.risk_event_cohort_engine import evaluate_risk_event_affected_cohort
from app.services.scenario_engine import evaluate_regime_scenario_pack
from tests.unit.test_principal_credential_verification import (
    NOW,
    Revocations,
    claims,
    signed,
    verifier,
)

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
        self.user_capabilities = frozenset(CAPABILITIES.values())
        self.application_capabilities = self.user_capabilities

    def tenant_members(self, subject: str, tenant_id: str) -> bool:
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
    app = create_app(
        principal_providers=PrincipalProviders(verifier(key, revocation=revocations), grants)
    )
    with loopback(app) as client:
        yield HttpRuntime(client, key, grants, revocations, calls)


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
