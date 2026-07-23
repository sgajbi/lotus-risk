from __future__ import annotations

from datetime import date
from typing import Final

SCHEMA_VERSION: Final = "lotus-risk.idea-opportunity-runtime-evidence.v1"
PROOF_FAMILY: Final = "idea_opportunity_archetype_source_evidence"
RUNTIME_BOUNDARY: Final = "lotus-risk:http-api"
CANONICAL_PORTFOLIO_REF: Final = "canonical-front-office:global_balanced"
CANONICAL_PORTFOLIO_ID: Final = "PB_SG_GLOBAL_BAL_001"
CANONICAL_BENCHMARK_ID: Final = "BMK_PB_GLOBAL_BALANCED_60_40"
CANONICAL_AS_OF_DATE: Final = date(2026, 4, 10)
CANONICAL_CONTRACT_PROVENANCE: Final = {
    "canonicalDemoDataContract": {
        "sourceSystem": "lotus-platform",
        "contractId": "canonical-front-office-demo-data-contract",
        "contractVersion": "1.1.0",
        "governedByRfc": "RFC-0076",
        "sourcePath": (
            "lotus-platform/context/contracts/canonical-front-office-demo-data-contract.json"
        ),
        "contentDigest": (
            "sha256:1b6003b3737236aed040a03ac3f6b7804ccaba83125ccae0ae22e7887f350d55"
        ),
    },
    "canonicalDemoDataInvariants": {
        "sourceSystem": "lotus-platform",
        "contractId": "canonical-front-office-demo-data-invariants",
        "contractVersion": "1.1.0",
        "governedByRfc": "RFC-0076",
        "sourcePath": (
            "lotus-platform/context/contracts/canonical-front-office-demo-data-invariants.json"
        ),
        "contentDigest": (
            "sha256:9575f496c611ee957a001e26a8b36267b48b448548b39b954a099586c8df27ef"
        ),
    },
}

CONSUMER_BLOCKERS_SATISFIED: Final = (
    "opportunity_archetype_live_risk_source_proof_missing",
    "opportunity_archetype_live_risk_volatility_source_proof_missing",
    "opportunity_archetype_drawdown_source_proof_missing",
)
EXPECTED_EXECUTIONS: Final = {
    "concentration_risk": (
        "lotus-risk:ConcentrationRiskReport:v1",
        "/analytics/risk/concentration",
    ),
    "high_volatility": (
        "lotus-risk:RiskMetricsReport:v1",
        "/analytics/risk/calculate",
    ),
    "drawdown_review": (
        "lotus-risk:DrawdownAnalyticsReport:v1",
        "/analytics/risk/drawdown",
    ),
}
EXPECTED_SUMMARY_KEYS: Final = {
    "concentration_risk": (
        "positionHhiCurrent",
        "positionHhiProposed",
        "issuerHhiCurrent",
        "issuerHhiProposed",
        "topIssuerWeightCurrent",
        "coverageStatus",
        "coverageRatioCurrent",
    ),
    "high_volatility": (
        "periodName",
        "volatilityPercent",
        "maxDrawdownPercent",
        "varPercent",
        "trackingErrorPercent",
    ),
    "drawdown_review": (
        "periodName",
        "maxDrawdown",
        "timeUnderWaterDays",
        "ulcerIndex",
        "episodeCount",
    ),
}
REMAINING_CERTIFICATION_BLOCKERS: Final = (
    "opportunity_archetype_data_mesh_not_certified",
    "opportunity_archetype_workbench_product_proof_missing",
    "opportunity_archetype_supported_feature_promotion_missing",
    "opportunity_archetype_client_publication_not_approved",
    "deployment_certification_missing",
    "production_certification_missing",
)
EXPECTED_NON_PROOF_CLAIMS: Final = {
    "officialRiskCalculationOwned": "lotus-risk",
    "ideaCandidatePersistenceObserved": False,
    "dataMeshRuntimeCertified": False,
    "gatewayWorkbenchRuntimeObserved": False,
    "clientPublicationApproved": False,
    "deploymentCertified": False,
    "productionCertified": False,
    "supportedFeaturePromoted": False,
}
EXPECTED_RECEIPT_KEYS: Final = frozenset(
    (
        "productId",
        "route",
        "statusCode",
        "asOfDate",
        "portfolioIdentityDigest",
        "requestPayloadDigest",
        "normalizedResponseDigest",
        "supportabilityState",
        "freshnessBucket",
        "summary",
    )
)
