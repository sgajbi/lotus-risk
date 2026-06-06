from __future__ import annotations

from typing import Any

SCENARIO_RESULTS_EXAMPLE: Any = [
    {
        "scenario_id": "growth_slowdown",
        "display_name": "Growth slowdown",
        "expected_loss_pct": 0.0765,
        "shock_by_bucket": {"EQUITY": -0.12, "FIXED_INCOME": -0.03},
        "position_contributions": [
            {
                "security_id": "FO_EQ_AAPL_US",
                "display_name": "Apple Inc.",
                "bucket": "EQUITY",
                "weight": 0.18,
                "shock_pct": -0.12,
                "contribution_loss_pct": 0.0216,
            }
        ],
    }
]

SCENARIO_GOVERNANCE_EVIDENCE_EXAMPLE: dict[str, Any] = {
    "cio_approval_status": "approved",
    "cio_approval_ref": "CIO-REGIME-2026-Q2-APPROVAL",
    "approved_by": "CIO Risk Committee",
    "approved_at": "2026-04-15T09:00:00Z",
    "effective_from": "2026-04-01",
    "effective_to": "2026-06-30",
    "effective_period_status": "active",
    "applicability_status": "applicable",
    "applicability_scope": ["DISCRETIONARY_PRIVATE_BANKING_BALANCED"],
    "portfolio_applicability_ref": "CIO-REGIME-2026-Q2-APP-PB_SG_GLOBAL_BAL_001",
    "methodology_ref": "docs/methodologies/metrics/regime-scenario-pack-evaluation.md",
}

SCENARIO_REASON_CODES_EXAMPLE: Any = ["REGIME_SCENARIO_PACK_READY"]

SCENARIO_METADATA_EXAMPLE: dict[str, Any] = {
    "product_name": "RegimeScenarioPackEvaluation",
    "product_version": "v1",
    "source_service": "lotus-risk",
    "lineage_version": "risk-regime-scenario-pack-evaluation.v1",
    "request_fingerprint": "sha256:abc123",
    "calculation_supportability": "ready",
}

__all__ = [
    "SCENARIO_GOVERNANCE_EVIDENCE_EXAMPLE",
    "SCENARIO_METADATA_EXAMPLE",
    "SCENARIO_REASON_CODES_EXAMPLE",
    "SCENARIO_RESULTS_EXAMPLE",
]
