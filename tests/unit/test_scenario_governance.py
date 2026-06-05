from __future__ import annotations

import datetime as dt

from app.contracts.scenario import (
    RegimeScenarioPackRequest,
    ScenarioPackApprovalStatus,
    ScenarioSupportabilityState,
)
from app.services.scenario_governance import (
    ScenarioPackGovernanceDefinition,
    effective_period_decision,
    evaluate_governance_evidence,
    most_severe_supportability,
    portfolio_applicability_decision,
)


def _governance() -> ScenarioPackGovernanceDefinition:
    return ScenarioPackGovernanceDefinition(
        cio_approval_status=ScenarioPackApprovalStatus.APPROVED,
        cio_approval_ref="CIO-TEST-APPROVAL",
        approved_by="CIO Risk Committee",
        approved_at=dt.datetime(2026, 4, 15, 9, 0, tzinfo=dt.UTC),
        effective_from=dt.date(2026, 4, 1),
        effective_to=dt.date(2026, 6, 30),
        applicability_scope=("DISCRETIONARY_PRIVATE_BANKING_BALANCED",),
        applicable_portfolio_ids=frozenset({"PB_SG_GLOBAL_BAL_001"}),
        methodology_ref="docs/methodologies/metrics/regime-scenario-pack-evaluation.md",
    )


def _request(**overrides: object) -> RegimeScenarioPackRequest:
    payload: dict[str, object] = {
        "scenario_pack_id": "CIO_REGIME_2026_Q2",
        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
        "as_of_date": "2026-05-03",
        "maximum_allowed_loss_pct": 0.12,
        "exposures": [
            {"bucket": "EQUITY", "weight": 0.55},
            {"bucket": "FIXED_INCOME", "weight": 0.35},
            {"bucket": "CASH", "weight": 0.10},
        ],
    }
    payload.update(overrides)
    return RegimeScenarioPackRequest.model_validate(payload)


def test_effective_period_decision_covers_active_not_yet_and_expired_states() -> None:
    governance = _governance()

    active = effective_period_decision(governance=governance, as_of_date=dt.date(2026, 5, 3))
    not_yet = effective_period_decision(
        governance=governance,
        as_of_date=dt.date(2026, 3, 31),
    )
    expired = effective_period_decision(
        governance=governance,
        as_of_date=dt.date(2026, 7, 1),
    )

    assert active.status == "active"
    assert active.reason_codes == []
    assert active.supportability == ScenarioSupportabilityState.READY

    assert not_yet.status == "not_yet_effective"
    assert not_yet.reason_codes == ["REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION"]
    assert not_yet.supportability == ScenarioSupportabilityState.DEGRADED

    assert expired.status == "expired"
    assert expired.reason_codes == ["REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION"]
    assert expired.supportability == ScenarioSupportabilityState.DEGRADED


def test_portfolio_applicability_decision_covers_scope_states() -> None:
    governance = _governance()

    applicable = portfolio_applicability_decision(
        governance=governance,
        portfolio_id="PB_SG_GLOBAL_BAL_001",
    )
    pending = portfolio_applicability_decision(governance=governance, portfolio_id=None)
    not_applicable = portfolio_applicability_decision(
        governance=governance,
        portfolio_id="PB_OTHER",
    )

    assert applicable.status == "applicable"
    assert applicable.portfolio_applicability_ref == ("CIO-TEST-APPROVAL-APP-PB_SG_GLOBAL_BAL_001")
    assert applicable.supportability == ScenarioSupportabilityState.READY

    assert pending.status == "pending_review"
    assert pending.reason_codes == ["REGIME_SCENARIO_PORTFOLIO_APPLICABILITY_NOT_CONFIRMED"]
    assert pending.supportability == ScenarioSupportabilityState.PENDING_REVIEW

    assert not_applicable.status == "not_applicable"
    assert not_applicable.reason_codes == ["REGIME_SCENARIO_PORTFOLIO_NOT_APPLICABLE"]
    assert not_applicable.supportability == ScenarioSupportabilityState.BLOCKED


def test_evaluate_governance_evidence_builds_contract_payload() -> None:
    evaluation = evaluate_governance_evidence(_request())

    assert evaluation.reason_codes == []
    assert evaluation.supportability == ScenarioSupportabilityState.READY
    assert evaluation.evidence.cio_approval_ref == "CIO-REGIME-2026-Q2-APPROVAL"
    assert evaluation.evidence.effective_period_status == "active"
    assert evaluation.evidence.applicability_status == "applicable"
    assert evaluation.evidence.portfolio_applicability_ref == (
        "CIO-REGIME-2026-Q2-APPROVAL-APP-PB_SG_GLOBAL_BAL_001"
    )


def test_most_severe_supportability_preserves_blocking_precedence() -> None:
    assert (
        most_severe_supportability(
            ScenarioSupportabilityState.PENDING_REVIEW,
            ScenarioSupportabilityState.DEGRADED,
        )
        == ScenarioSupportabilityState.DEGRADED
    )
    assert (
        most_severe_supportability(
            ScenarioSupportabilityState.BLOCKED,
            ScenarioSupportabilityState.DEGRADED,
        )
        == ScenarioSupportabilityState.BLOCKED
    )
