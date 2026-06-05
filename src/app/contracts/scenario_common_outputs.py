from __future__ import annotations

from enum import StrEnum


class ScenarioSupportabilityState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    PENDING_REVIEW = "pending_review"
    BLOCKED = "blocked"


class ScenarioPackApprovalStatus(StrEnum):
    APPROVED = "approved"
    NOT_APPROVED = "not_approved"


class ScenarioPackEffectivePeriodStatus(StrEnum):
    ACTIVE = "active"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"


class ScenarioPackApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    PENDING_REVIEW = "pending_review"
    NOT_APPLICABLE = "not_applicable"


__all__ = [
    "ScenarioPackApplicabilityStatus",
    "ScenarioPackApprovalStatus",
    "ScenarioPackEffectivePeriodStatus",
    "ScenarioSupportabilityState",
]
