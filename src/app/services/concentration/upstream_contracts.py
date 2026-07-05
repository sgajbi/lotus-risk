from __future__ import annotations

from app.integrations.upstream_operations import (
    LOTUS_CORE_CREATE_SIMULATION_SESSION_OPERATION,
    LOTUS_CORE_SNAPSHOT_OPERATION,
)
from app.upstream_errors import UpstreamServiceError, invalid_upstream_payload

LOTUS_CORE_SERVICE = "lotus-core"
CORE_SNAPSHOT_OPERATION = LOTUS_CORE_SNAPSHOT_OPERATION
CREATE_SIMULATION_SESSION_OPERATION = LOTUS_CORE_CREATE_SIMULATION_SESSION_OPERATION


def invalid_core_snapshot_payload(
    *,
    snapshot_mode: str,
    reason: str,
) -> UpstreamServiceError:
    return invalid_upstream_payload(
        service=LOTUS_CORE_SERVICE,
        operation=CORE_SNAPSHOT_OPERATION,
        message=(
            f"lotus-core concentration {snapshot_mode.lower()} snapshot "
            "returned invalid response payload"
        ),
        details={
            "snapshot_mode": snapshot_mode,
            "reason": reason,
        },
    )


def invalid_create_simulation_session_payload(*, reason: str) -> UpstreamServiceError:
    return invalid_upstream_payload(
        service=LOTUS_CORE_SERVICE,
        operation=CREATE_SIMULATION_SESSION_OPERATION,
        message="lotus-core create simulation session returned invalid response payload",
        details={"reason": reason},
    )


__all__ = [
    "CORE_SNAPSHOT_OPERATION",
    "CREATE_SIMULATION_SESSION_OPERATION",
    "LOTUS_CORE_SERVICE",
    "invalid_core_snapshot_payload",
    "invalid_create_simulation_session_payload",
]
