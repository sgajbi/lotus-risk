from __future__ import annotations

from typing import Any

from app.integrations.upstream_operations import LOTUS_CORE_SNAPSHOT_OPERATION
from app.services.audit_lineage import upstream_request_fingerprint
from app.services.concentration.upstream_contracts import LOTUS_CORE_SERVICE


def core_snapshot_upstream_fingerprint(
    *,
    portfolio_id: str,
    snapshot_payload: dict[str, Any],
) -> dict[str, str]:
    return upstream_request_fingerprint(
        service=LOTUS_CORE_SERVICE,
        operation=LOTUS_CORE_SNAPSHOT_OPERATION,
        payload={
            "portfolio_id": portfolio_id,
            "request_payload": snapshot_payload,
        },
    )


__all__ = ["core_snapshot_upstream_fingerprint"]
