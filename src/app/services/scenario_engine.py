from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.contracts.scenario import (
    RegimeScenarioPackRequest,
    RegimeScenarioPackResponse,
    ScenarioEvaluationMetadata,
    ScenarioResult,
    ScenarioSupportabilityState,
)


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    display_name: str
    shock_by_bucket: dict[str, float]


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


def evaluate_regime_scenario_pack(
    request: RegimeScenarioPackRequest,
) -> RegimeScenarioPackResponse:
    scenario_pack = SCENARIO_PACKS.get(request.scenario_pack_id)
    if scenario_pack is None:
        raise ValueError(f"Unsupported scenario_pack_id: {request.scenario_pack_id}")

    exposure_by_bucket = {
        exposure.bucket.upper(): exposure.weight for exposure in request.exposures
    }
    unsupported_buckets = sorted(set(exposure_by_bucket) - SUPPORTED_BUCKETS)
    supportability = (
        ScenarioSupportabilityState.DEGRADED
        if unsupported_buckets
        else ScenarioSupportabilityState.READY
    )
    scenario_results = [
        _evaluate_scenario(
            scenario=scenario,
            exposure_by_bucket=exposure_by_bucket,
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
    if breach:
        reason_codes.append("REGIME_SCENARIO_POLICY_THRESHOLD_BREACH")
        if supportability == ScenarioSupportabilityState.READY:
            supportability = ScenarioSupportabilityState.PENDING_REVIEW

    return RegimeScenarioPackResponse(
        scenario_pack_id=request.scenario_pack_id,
        portfolio_id=request.portfolio_id,
        as_of_date=request.as_of_date,
        worst_case_loss_pct=round(worst_case_loss, 6),
        maximum_allowed_loss_pct=request.maximum_allowed_loss_pct,
        breach=breach,
        scenario_results=scenario_results,
        reason_codes=sorted(set(reason_codes)),
        metadata=ScenarioEvaluationMetadata(
            request_fingerprint=_request_fingerprint(request),
            calculation_supportability=supportability,
        ),
    )


def _evaluate_scenario(
    *,
    scenario: ScenarioDefinition,
    exposure_by_bucket: dict[str, float],
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
    )


def _request_fingerprint(request: RegimeScenarioPackRequest) -> str:
    payload = request.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()
