from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from app.dependencies.request_context import request_actor_id, request_correlation_id


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
