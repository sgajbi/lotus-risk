"""Actual signed loopback requests for key, clock and router-redirect policy."""

import json
import logging
from collections.abc import Iterator
from functools import partial
from typing import Any

import pytest

from app import enterprise_readiness
from app.enterprise_authorization import required_route_capability
from app.security.models import PrincipalDenied
from tests.e2e.test_verified_risk_authority_http import (
    CAPABILITIES,
    COHORT,
    CONCENTRATION,
    SCENARIO,
    HttpRuntime,
    payload,
)
from tests.e2e.test_verified_risk_authority_http import runtime as http_runtime_fixture
from tests.unit.test_principal_credential_verification import NOW
from tests.unit.test_principal_provider_policy import INVALID_CLOCKS, INVALID_KEY_OPS


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[HttpRuntime]:
    yield from http_runtime_fixture._get_wrapped_function()(monkeypatch)


def assert_economics(result: dict[str, Any], route: str) -> None:
    if route == CONCENTRATION:
        assert result["risk_proxy"]["hhi_current"] == 6250
        assert result["single_position_concentration"]["top_position_weight_current"] == 0.75
    elif route == SCENARIO:
        assert result["worst_case_loss_pct"] == 0.18
        assert result["maximum_allowed_loss_pct"] == 0.12
        assert result["breach"] is True
        assert [item["expected_loss_pct"] for item in result["scenario_results"]] == [
            0.12,
            0.08,
            0.18,
        ]
    else:
        assert route == COHORT
        assert len(result["affected_portfolios"]) == 1
        assert result["affected_portfolios"][0]["impact_score"] == 0.18
        assert result["affected_portfolios"][0]["portfolio_id"] == "portfolio-a"


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_matching_key_and_clock_policy_over_actual_http(
    runtime: HttpRuntime,
    route: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entries = runtime.keys.document["keys"]
    assert isinstance(entries, list)
    matching = entries[0]
    headers = {"Authorization": "Bearer " + runtime.token()}

    def refusal(token: str) -> None:
        with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
            response = runtime.client.post(
                route, json=payload(route), headers={"Authorization": "Bearer " + token}
            )
        assert response.status_code == 503, response.text
        assert "WWW-Authenticate" not in response.headers and "Location" not in response.headers
        assert not runtime.calls
        audits = [record.audit for record in caplog.records if hasattr(record, "audit")]
        assert len(audits) == 1
        assert audits[0]["actor_id"] == audits[0]["tenant_id"] == "unverified"
        assert audits[0]["metadata"] == {"reason": "grant_store_unavailable"}
        for private in (token, "provider-private-diagnostic", "private-clock"):
            assert private not in response.text + str(audits)
        caplog.clear()

    for operations in INVALID_KEY_OPS:
        matching.update(use="sig", key_ops=operations)
        refusal(runtime.token())
    matching.pop("key_ops")
    for now in INVALID_CLOCKS:
        runtime.identity_verifier._clock = partial(lambda value: value, now)
        for time_claims in ({"exp": 0}, {"nbf": NOW + 600}):
            refusal(runtime.token(**time_claims))
    for failure in (
        RuntimeError("provider-private-diagnostic"),
        PrincipalDenied("private-clock", 200),
    ):

        def failing_clock(failure: Exception = failure) -> float:
            raise failure

        runtime.identity_verifier._clock = failing_clock
        refusal(runtime.token())
    runtime.identity_verifier._clock = lambda: float(NOW)
    # An unrelated well-formed key is not selected or assigned this key's operation policy.
    entries.append({**matching, "kid": "unrelated-key", "key_ops": ["encrypt"], "use": "enc"})
    for operations in (None, ["verify"], ["sign", "verify"]):
        if operations is not None:
            matching["key_ops"] = operations
        response = runtime.client.post(route, json=payload(route), headers=headers)
        assert response.status_code == 200, response.text
        assert_economics(response.json(), route)
    assert runtime.calls == {route: 3}
    for now, changes, status in (
        (NOW + 60, {}, 401),
        (NOW - 0.001, {"nbf": NOW}, 401),
        (NOW, {"nbf": NOW}, 200),
    ):
        runtime.identity_verifier._clock = partial(lambda value: value, now)
        response = runtime.client.post(
            route,
            json=payload(route),
            headers={"Authorization": "Bearer " + runtime.token(**changes)},
        )
        assert response.status_code == status, response.text
        if status == 401:
            assert response.headers["WWW-Authenticate"] == "Bearer"
            assert runtime.calls == {route: 3}
        else:
            assert_economics(response.json(), route)
    assert runtime.calls == {route: 4}


@pytest.mark.parametrize("route", list(CAPABILITIES))
def test_single_slash_redirect_retains_canonical_authority_and_exact_request(
    runtime: HttpRuntime,
    route: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = runtime.token()
    headers = {"Authorization": "Bearer " + token}
    body = payload(route)
    url = route + "/?diagnostic=control"
    verified_bytes: list[str] = []
    capability_paths: list[str] = []
    original = runtime.identity_verifier.verify
    original_capability = required_route_capability

    def recording_verifier(credential: str) -> Any:
        verified_bytes.append(credential)
        return original(credential)

    monkeypatch.setattr(runtime.identity_verifier, "verify", recording_verifier)

    def recording_capability(method: str, path: str) -> str | None:
        capability_paths.append(path)
        return original_capability(method, path)

    monkeypatch.setattr(enterprise_readiness, "required_route_capability", recording_capability)
    monkeypatch.setenv(
        "ENTERPRISE_CAPABILITY_RULES_JSON",
        json.dumps(
            {
                f"POST {route}": CAPABILITIES[route],
                f"POST {route}/": "ungranted.slash",
            }
        ),
    )
    redirect = runtime.client.post(url, json=body, headers=headers)
    assert redirect.status_code == 307
    assert (
        redirect.headers["Location"]
        == str(runtime.client.base_url).rstrip("/") + route + "?diagnostic=control"
    )
    assert not runtime.calls and verified_bytes == [token]
    followed = runtime.client.post(url, json=body, headers=headers, follow_redirects=True)
    assert followed.status_code == 200, followed.text
    assert len(followed.history) == 1 and followed.history[0].status_code == 307
    assert followed.request.method == followed.history[0].request.method == "POST"
    assert followed.request.read() == redirect.request.read() == followed.history[0].request.read()
    assert followed.request.headers["Authorization"] == headers["Authorization"]
    assert verified_bytes == [token, token, token]
    assert capability_paths == [route, route, route]
    assert runtime.calls == {route: 1}
    assert_economics(followed.json(), route)
    for invalid_headers in (
        {},
        {"Authorization": "Bearer malformed"},
        {"Authorization": "Bearer " + runtime.token(exp=0)},
    ):
        denied = runtime.client.post(url, json=body, headers=invalid_headers)
        assert denied.status_code == 401 and denied.headers["WWW-Authenticate"] == "Bearer"
        assert "Location" not in denied.headers and runtime.calls == {route: 1}
    runtime.grants.user_capabilities = frozenset()
    denied = runtime.client.post(url, json=body, headers=headers)
    assert denied.status_code == 403 and "Location" not in denied.headers
    assert runtime.calls == {route: 1}
    runtime.grants.user_capabilities = frozenset(CAPABILITIES.values())
    # An unrelated configured rule cannot provide the canonical route's capability.
    monkeypatch.setenv(
        "ENTERPRISE_CAPABILITY_RULES_JSON", json.dumps({"POST /unrelated": CAPABILITIES[route]})
    )
    denied = runtime.client.post(url, json=body, headers=headers)
    assert denied.status_code == 403 and "Location" not in denied.headers
    monkeypatch.setenv(
        "ENTERPRISE_CAPABILITY_RULES_JSON", json.dumps({f"POST {route}": CAPABILITIES[route]})
    )
    foreign = payload(route, "private-foreign")
    if route == CONCENTRATION:
        foreign["stateful_input"] = {
            "portfolio_id": "private-foreign",
            "as_of_date": "2026-05-03",
            "reporting_currency": "USD",
        }
    pending_guard = runtime.client.post(url, json=foreign, headers=headers)
    assert pending_guard.status_code == 307 and runtime.calls == {route: 1}
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="enterprise_readiness"):
        refused = runtime.client.post(url, json=foreign, headers=headers, follow_redirects=True)
    assert refused.status_code == 403 and refused.history[0].status_code == 307
    assert runtime.calls == {route: 1}
    audits = [record.audit for record in caplog.records if hasattr(record, "audit")]
    assert audits[-1]["action"] == "DENY POST " + route
    assert audits[-1]["metadata"]["reason"] == "portfolio_outside_scope"
    assert "private-foreign" not in refused.text + str(audits)
    for unsupported in (route + "//", "/analytics/risk/regime-scenario-pack/jobs/"):
        refused = runtime.client.post(unsupported, json=body, headers=headers)
        assert refused.status_code == 403 and "Location" not in refused.headers
        assert runtime.calls == {route: 1}
