from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.contracts.scenario import (
    RegimeScenarioPackRequest,
    RegimeScenarioPackResponse,
    ScenarioEvaluationMetadata,
    ScenarioExposureComponent,
    ScenarioPackGovernanceEvidence,
    ScenarioPositionContribution,
    ScenarioResult,
    ScenarioSupportabilityState,
)
from app.services.scenario_governance import (
    SCENARIO_PACK_GOVERNANCE as SCENARIO_PACK_GOVERNANCE,  # noqa: F401
    evaluate_governance_evidence,
    most_severe_supportability,
)
from app.services.scenario_pack_catalog import (
    SCENARIO_PACKS,
    SUPPORTED_BUCKETS,
    ScenarioDefinition,
)


@dataclass(frozen=True)
class _ScenarioPackEvaluation:
    scenario_results: list[ScenarioResult]
    worst_case_loss: float
    breach: bool
    governance_evidence: ScenarioPackGovernanceEvidence
    reason_codes: list[str]
    supportability: ScenarioSupportabilityState


@dataclass(frozen=True)
class _ScenarioPackContext:
    scenario_pack: tuple[ScenarioDefinition, ...]
    exposure_by_bucket: dict[str, float]
    governance_evidence: ScenarioPackGovernanceEvidence
    reason_codes: list[str]
    supportability: ScenarioSupportabilityState


def _scenario_pack_context(
    request: RegimeScenarioPackRequest,
) -> _ScenarioPackContext:
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
    governance = evaluate_governance_evidence(request)
    supportability = most_severe_supportability(
        supportability,
        governance.supportability,
    )
    reason_codes = ["REGIME_SCENARIO_PACK_READY"]
    if unsupported_buckets:
        reason_codes.append("REGIME_SCENARIO_UNSUPPORTED_EXPOSURE_BUCKET")
    reason_codes.extend(governance.reason_codes)
    return _ScenarioPackContext(
        scenario_pack=scenario_pack,
        exposure_by_bucket=exposure_by_bucket,
        governance_evidence=governance.evidence,
        reason_codes=reason_codes,
        supportability=supportability,
    )


def _scenario_results(
    *,
    context: _ScenarioPackContext,
    exposure_components: list[ScenarioExposureComponent],
) -> list[ScenarioResult]:
    return [
        _evaluate_scenario(
            scenario=scenario,
            exposure_by_bucket=context.exposure_by_bucket,
            exposure_components=exposure_components,
        )
        for scenario in context.scenario_pack
    ]


def _supportability_after_breach(
    *,
    breach: bool,
    supportability: ScenarioSupportabilityState,
) -> ScenarioSupportabilityState:
    if breach and supportability == ScenarioSupportabilityState.READY:
        return ScenarioSupportabilityState.PENDING_REVIEW
    return supportability


def _evaluate_scenario_pack_context(
    request: RegimeScenarioPackRequest,
) -> _ScenarioPackEvaluation:
    context = _scenario_pack_context(request)
    scenario_results = _scenario_results(
        context=context,
        exposure_components=request.exposure_components,
    )
    worst_case_loss = max(
        (scenario.expected_loss_pct for scenario in scenario_results),
        default=0.0,
    )
    breach = worst_case_loss > request.maximum_allowed_loss_pct
    reason_codes = [*context.reason_codes]
    if breach:
        reason_codes.append("REGIME_SCENARIO_POLICY_THRESHOLD_BREACH")

    return _ScenarioPackEvaluation(
        scenario_results=scenario_results,
        worst_case_loss=worst_case_loss,
        breach=breach,
        governance_evidence=context.governance_evidence,
        reason_codes=sorted(set(reason_codes)),
        supportability=_supportability_after_breach(
            breach=breach,
            supportability=context.supportability,
        ),
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
