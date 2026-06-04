from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass

from app.contracts.scenario import (
    RegimeScenarioPackRequest,
    RegimeScenarioPackResponse,
    ScenarioEvaluationMetadata,
    ScenarioExposureComponent,
    ScenarioPackApplicabilityStatus,
    ScenarioPackApprovalStatus,
    ScenarioPackEffectivePeriodStatus,
    ScenarioPackGovernanceEvidence,
    ScenarioPositionContribution,
    ScenarioResult,
    ScenarioSupportabilityState,
)


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    display_name: str
    shock_by_bucket: dict[str, float]


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
class _ScenarioPackEvaluation:
    scenario_results: list[ScenarioResult]
    worst_case_loss: float
    breach: bool
    governance_evidence: ScenarioPackGovernanceEvidence
    reason_codes: list[str]
    supportability: ScenarioSupportabilityState


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


SCENARIO_PACKS: dict[str, tuple[ScenarioDefinition, ...]] = {
    "CIO_REGIME_2026_Q2": (
        ScenarioDefinition(
            scenario_id="growth_slowdown",
            display_name="Growth slowdown",
            shock_by_bucket={
                "EQUITY": -0.12,
                "FIXED_INCOME": -0.03,
                "ALTERNATIVES": -0.06,
                "CASH": 0.0,
            },
        ),
        ScenarioDefinition(
            scenario_id="rates_up_inflation",
            display_name="Rates up and inflation persistence",
            shock_by_bucket={
                "EQUITY": -0.08,
                "FIXED_INCOME": -0.07,
                "ALTERNATIVES": -0.04,
                "CASH": 0.0,
            },
        ),
        ScenarioDefinition(
            scenario_id="risk_off_liquidity",
            display_name="Risk-off liquidity shock",
            shock_by_bucket={
                "EQUITY": -0.18,
                "FIXED_INCOME": -0.02,
                "ALTERNATIVES": -0.10,
                "CASH": 0.0,
            },
        ),
    )
}
SUPPORTED_BUCKETS = frozenset({"EQUITY", "FIXED_INCOME", "ALTERNATIVES", "CASH"})
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


def _evaluate_scenario_pack_context(
    request: RegimeScenarioPackRequest,
) -> _ScenarioPackEvaluation:
    scenario_pack = SCENARIO_PACKS[request.scenario_pack_id]
    exposure_by_bucket = {
        exposure.bucket.upper(): exposure.weight for exposure in request.exposures
    }
    unsupported_buckets = sorted(set(exposure_by_bucket) - SUPPORTED_BUCKETS)
    supportability = (
        ScenarioSupportabilityState.DEGRADED
        if unsupported_buckets
        else ScenarioSupportabilityState.READY
    )
    governance_evidence, governance_reason_codes, governance_supportability = (
        _evaluate_governance_evidence(request)
    )
    supportability = _most_severe_supportability(
        supportability,
        governance_supportability,
    )
    scenario_results = [
        _evaluate_scenario(
            scenario=scenario,
            exposure_by_bucket=exposure_by_bucket,
            exposure_components=request.exposure_components,
        )
        for scenario in scenario_pack
    ]
    worst_case_loss = max(
        (scenario.expected_loss_pct for scenario in scenario_results),
        default=0.0,
    )
    breach = worst_case_loss > request.maximum_allowed_loss_pct
    reason_codes = ["REGIME_SCENARIO_PACK_READY"]
    if unsupported_buckets:
        reason_codes.append("REGIME_SCENARIO_UNSUPPORTED_EXPOSURE_BUCKET")
    reason_codes.extend(governance_reason_codes)
    if breach:
        reason_codes.append("REGIME_SCENARIO_POLICY_THRESHOLD_BREACH")
        if supportability == ScenarioSupportabilityState.READY:
            supportability = ScenarioSupportabilityState.PENDING_REVIEW

    return _ScenarioPackEvaluation(
        scenario_results=scenario_results,
        worst_case_loss=worst_case_loss,
        breach=breach,
        governance_evidence=governance_evidence,
        reason_codes=sorted(set(reason_codes)),
        supportability=supportability,
    )


def evaluate_regime_scenario_pack(
    request: RegimeScenarioPackRequest,
) -> RegimeScenarioPackResponse:
    if request.scenario_pack_id not in SCENARIO_PACKS:
        raise ValueError(f"Unsupported scenario_pack_id: {request.scenario_pack_id}")

    evaluation = _evaluate_scenario_pack_context(request)
    return RegimeScenarioPackResponse(
        scenario_pack_id=request.scenario_pack_id,
        portfolio_id=request.portfolio_id,
        as_of_date=request.as_of_date,
        worst_case_loss_pct=round(evaluation.worst_case_loss, 6),
        maximum_allowed_loss_pct=request.maximum_allowed_loss_pct,
        breach=evaluation.breach,
        scenario_results=evaluation.scenario_results,
        governance_evidence=evaluation.governance_evidence,
        reason_codes=evaluation.reason_codes,
        metadata=ScenarioEvaluationMetadata(
            request_fingerprint=_request_fingerprint(request),
            calculation_supportability=evaluation.supportability,
        ),
    )


def _effective_period_decision(
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


def _portfolio_applicability_decision(
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


def _evaluate_governance_evidence(
    request: RegimeScenarioPackRequest,
) -> tuple[ScenarioPackGovernanceEvidence, list[str], ScenarioSupportabilityState]:
    governance = SCENARIO_PACK_GOVERNANCE[request.scenario_pack_id]
    reason_codes: list[str] = []
    supportability = ScenarioSupportabilityState.READY

    if governance.cio_approval_status != ScenarioPackApprovalStatus.APPROVED:
        reason_codes.append("REGIME_SCENARIO_CIO_APPROVAL_NOT_CONFIRMED")
        supportability = ScenarioSupportabilityState.BLOCKED

    effective_period = _effective_period_decision(
        governance=governance,
        as_of_date=request.as_of_date,
    )
    reason_codes.extend(effective_period.reason_codes)
    supportability = _most_severe_supportability(
        supportability,
        effective_period.supportability,
    )

    portfolio_applicability = _portfolio_applicability_decision(
        governance=governance,
        portfolio_id=request.portfolio_id,
    )
    reason_codes.extend(portfolio_applicability.reason_codes)
    supportability = _most_severe_supportability(
        supportability,
        portfolio_applicability.supportability,
    )

    return (
        ScenarioPackGovernanceEvidence(
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
        ),
        reason_codes,
        supportability,
    )


def _most_severe_supportability(
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


def _evaluate_scenario(
    *,
    scenario: ScenarioDefinition,
    exposure_by_bucket: dict[str, float],
    exposure_components: list[ScenarioExposureComponent],
) -> ScenarioResult:
    loss = 0.0
    for bucket, weight in exposure_by_bucket.items():
        shock = scenario.shock_by_bucket.get(bucket, 0.0)
        loss += max(-(weight * shock), 0.0)
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        display_name=scenario.display_name,
        expected_loss_pct=round(loss, 6),
        shock_by_bucket=dict(scenario.shock_by_bucket),
        position_contributions=_evaluate_position_contributions(
            scenario=scenario,
            exposure_components=exposure_components,
        ),
    )


def _evaluate_position_contributions(
    *,
    scenario: ScenarioDefinition,
    exposure_components: list[ScenarioExposureComponent],
) -> list[ScenarioPositionContribution]:
    contributions = [
        ScenarioPositionContribution(
            security_id=component.security_id,
            display_name=component.display_name,
            bucket=component.bucket.upper(),
            weight=component.weight,
            shock_pct=scenario.shock_by_bucket.get(component.bucket.upper(), 0.0),
            contribution_loss_pct=round(
                max(
                    -(
                        component.weight
                        * scenario.shock_by_bucket.get(component.bucket.upper(), 0.0)
                    ),
                    0.0,
                ),
                6,
            ),
        )
        for component in exposure_components
    ]
    return sorted(
        contributions,
        key=lambda row: (-row.contribution_loss_pct, row.bucket, row.security_id),
    )


def _request_fingerprint(request: RegimeScenarioPackRequest) -> str:
    payload = request.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()
