from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import HTTPException

from app.dependencies.request_context import (
    request_actor_id,
    request_correlation_id,
    request_tenant_id,
    require_portfolio_scope,
)
from app.security.models import GrantSet, ResolvedPrincipal, VerifiedCredential


def test_request_context_reads_correlation_and_actor_headers() -> None:
    request = SimpleNamespace(
        headers={
            "X-Correlation-Id": "corr-risk-context",
            "X-Actor-Id": "advisor-123",
        }
    )

    assert request_correlation_id(cast(Any, request)) == "corr-risk-context"
    assert request_actor_id(cast(Any, request)) == "advisor-123"


def test_request_context_returns_none_when_headers_are_absent() -> None:
    request = SimpleNamespace(headers={})

    assert request_correlation_id(cast(Any, request)) is None
    assert request_actor_id(cast(Any, request)) is None


def test_verified_context_cannot_fall_back_to_authority_headers() -> None:
    request = SimpleNamespace(
        headers={"X-Actor-Id": "forged", "X-Tenant-Id": "foreign"},
        state=SimpleNamespace(),
        app=SimpleNamespace(
            state=SimpleNamespace(principal_security=SimpleNamespace(posture="verified"))
        ),
    )
    for reader in (request_actor_id, request_tenant_id):
        with pytest.raises(HTTPException) as denial:
            reader(cast(Any, request))
        assert denial.value.status_code == 503
    with pytest.raises(HTTPException) as denial:
        require_portfolio_scope(cast(Any, request), [])
    assert denial.value.status_code == 503


def test_verified_context_uses_admitted_identity_and_scope() -> None:
    request = SimpleNamespace(
        headers={"X-Actor-Id": "forged", "X-Tenant-Id": "foreign"},
        state=SimpleNamespace(
            resolved_principal=ResolvedPrincipal(
                VerifiedCredential("person", "tenant", "user", "identity"),
                GrantSet(frozenset({"risk.test"}), frozenset({"portfolio"})),
            )
        ),
    )
    assert request_actor_id(cast(Any, request)) == "person"
    assert request_tenant_id(cast(Any, request)) == "tenant"
    require_portfolio_scope(cast(Any, request), ["portfolio"])
    with pytest.raises(HTTPException) as denial:
        require_portfolio_scope(cast(Any, request), ["portfolio", "foreign"])
    assert denial.value.status_code == 403
