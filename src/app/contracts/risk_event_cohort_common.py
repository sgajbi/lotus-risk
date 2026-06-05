from __future__ import annotations

from enum import StrEnum


class RiskEventCohortSupportabilityState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    PENDING_REVIEW = "pending_review"
    BLOCKED = "blocked"


__all__ = ["RiskEventCohortSupportabilityState"]
