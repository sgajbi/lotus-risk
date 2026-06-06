from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.contracts.scenario import (
    RegimeScenarioPackRequest,
    ScenarioPackApplicabilityStatus,
    ScenarioPackApprovalStatus,
    ScenarioPackEffectivePeriodStatus,
    ScenarioPackGovernanceEvidence,
    ScenarioSupportabilityState,
)


@dataclass(frozen=True)
class ScenarioPackGovernanceDefinition:
    cio_approval_status: ScenarioPackApprovalStatus
    cio_approval_ref: str
    approved_by: str
    approved_at: dt.datetime
    effective_from: dt.date
    effective_to: dt.date
    applicability_scope: tuple[str, ...]
    applicable_portfolio_ids: frozenset[str]
    methodology_ref: str


@dataclass(frozen=True)
class _EffectivePeriodDecision:
    status: ScenarioPackEffectivePeriodStatus
    reason_codes: list[str]
    supportability: ScenarioSupportabilityState


@dataclass(frozen=True)
class _PortfolioApplicabilityDecision:
    status: ScenarioPackApplicabilityStatus
    portfolio_applicability_ref: str | None
    reason_codes: list[str]
    supportability: ScenarioSupportabilityState


@dataclass(frozen=True)
class _CioApprovalDecision:
    reason_codes: list[str]
    supportability: ScenarioSupportabilityState


@dataclass(frozen=True)
class GovernanceEvaluation:
    evidence: ScenarioPackGovernanceEvidence
    reason_codes: list[str]
    supportability: ScenarioSupportabilityState


SCENARIO_PACK_GOVERNANCE: dict[str, ScenarioPackGovernanceDefinition] = {
    "CIO_REGIME_2026_Q2": ScenarioPackGovernanceDefinition(
        cio_approval_status=ScenarioPackApprovalStatus.APPROVED,
        cio_approval_ref="CIO-REGIME-2026-Q2-APPROVAL",
        approved_by="CIO Risk Committee",
        approved_at=dt.datetime(2026, 4, 15, 9, 0, tzinfo=dt.UTC),
        effective_from=dt.date(2026, 4, 1),
        effective_to=dt.date(2026, 6, 30),
        applicability_scope=("DISCRETIONARY_PRIVATE_BANKING_BALANCED",),
        applicable_portfolio_ids=frozenset({"PB_SG_GLOBAL_BAL_001"}),
        methodology_ref="docs/methodologies/metrics/regime-scenario-pack-evaluation.md",
    )
}


def cio_approval_decision(
    *,
    governance: ScenarioPackGovernanceDefinition,
) -> _CioApprovalDecision:
    if governance.cio_approval_status != ScenarioPackApprovalStatus.APPROVED:
        return _CioApprovalDecision(
            reason_codes=["REGIME_SCENARIO_CIO_APPROVAL_NOT_CONFIRMED"],
            supportability=ScenarioSupportabilityState.BLOCKED,
        )
    return _CioApprovalDecision(
        reason_codes=[],
        supportability=ScenarioSupportabilityState.READY,
    )


def effective_period_decision(
    *,
    governance: ScenarioPackGovernanceDefinition,
    as_of_date: dt.date,
) -> _EffectivePeriodDecision:
    if as_of_date < governance.effective_from:
        return _EffectivePeriodDecision(
            status=ScenarioPackEffectivePeriodStatus.NOT_YET_EFFECTIVE,
            reason_codes=["REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION"],
            supportability=ScenarioSupportabilityState.DEGRADED,
        )
    if as_of_date > governance.effective_to:
        return _EffectivePeriodDecision(
            status=ScenarioPackEffectivePeriodStatus.EXPIRED,
            reason_codes=["REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION"],
            supportability=ScenarioSupportabilityState.DEGRADED,
        )
    return _EffectivePeriodDecision(
        status=ScenarioPackEffectivePeriodStatus.ACTIVE,
        reason_codes=[],
        supportability=ScenarioSupportabilityState.READY,
    )


def portfolio_applicability_decision(
    *,
    governance: ScenarioPackGovernanceDefinition,
    portfolio_id: str | None,
) -> _PortfolioApplicabilityDecision:
    if portfolio_id is None:
        return _PortfolioApplicabilityDecision(
            status=ScenarioPackApplicabilityStatus.PENDING_REVIEW,
            portfolio_applicability_ref=None,
            reason_codes=["REGIME_SCENARIO_PORTFOLIO_APPLICABILITY_NOT_CONFIRMED"],
            supportability=ScenarioSupportabilityState.PENDING_REVIEW,
        )
    if portfolio_id in governance.applicable_portfolio_ids:
        return _PortfolioApplicabilityDecision(
            status=ScenarioPackApplicabilityStatus.APPLICABLE,
            portfolio_applicability_ref=f"{governance.cio_approval_ref}-APP-{portfolio_id}",
            reason_codes=[],
            supportability=ScenarioSupportabilityState.READY,
        )
    return _PortfolioApplicabilityDecision(
        status=ScenarioPackApplicabilityStatus.NOT_APPLICABLE,
        portfolio_applicability_ref=None,
        reason_codes=["REGIME_SCENARIO_PORTFOLIO_NOT_APPLICABLE"],
        supportability=ScenarioSupportabilityState.BLOCKED,
    )


def _governance_evidence(
    *,
    governance: ScenarioPackGovernanceDefinition,
    effective_period: _EffectivePeriodDecision,
    portfolio_applicability: _PortfolioApplicabilityDecision,
) -> ScenarioPackGovernanceEvidence:
    return ScenarioPackGovernanceEvidence(
        cio_approval_status=governance.cio_approval_status,
        cio_approval_ref=governance.cio_approval_ref,
        approved_by=governance.approved_by,
        approved_at=governance.approved_at,
        effective_from=governance.effective_from,
        effective_to=governance.effective_to,
        effective_period_status=effective_period.status,
        applicability_status=portfolio_applicability.status,
        applicability_scope=list(governance.applicability_scope),
        portfolio_applicability_ref=portfolio_applicability.portfolio_applicability_ref,
        methodology_ref=governance.methodology_ref,
    )


def evaluate_governance_evidence(
    request: RegimeScenarioPackRequest,
) -> GovernanceEvaluation:
    governance = SCENARIO_PACK_GOVERNANCE[request.scenario_pack_id]
    approval = cio_approval_decision(governance=governance)
    reason_codes: list[str] = [*approval.reason_codes]
    supportability = approval.supportability

    effective_period = effective_period_decision(
        governance=governance,
        as_of_date=request.as_of_date,
    )
    reason_codes.extend(effective_period.reason_codes)
    supportability = most_severe_supportability(
        supportability,
        effective_period.supportability,
    )

    portfolio_applicability = portfolio_applicability_decision(
        governance=governance,
        portfolio_id=request.portfolio_id,
    )
    reason_codes.extend(portfolio_applicability.reason_codes)
    supportability = most_severe_supportability(
        supportability,
        portfolio_applicability.supportability,
    )

    return GovernanceEvaluation(
        evidence=_governance_evidence(
            governance=governance,
            effective_period=effective_period,
            portfolio_applicability=portfolio_applicability,
        ),
        reason_codes=reason_codes,
        supportability=supportability,
    )


def most_severe_supportability(
    left: ScenarioSupportabilityState,
    right: ScenarioSupportabilityState,
) -> ScenarioSupportabilityState:
    severity = {
        ScenarioSupportabilityState.READY: 0,
        ScenarioSupportabilityState.PENDING_REVIEW: 1,
        ScenarioSupportabilityState.DEGRADED: 2,
        ScenarioSupportabilityState.BLOCKED: 3,
    }
    return left if severity[left] >= severity[right] else right
