from __future__ import annotations

from pydantic import BaseModel, Field

from app.trust_telemetry_dependency_models import DeclaredConsumerDependencyTelemetry
from app.trust_telemetry_product_models import ProductTrustTelemetrySeed
from app.trust_telemetry_snapshot_examples import (
    DECLARED_DEPENDENCY_EXAMPLES,
    PRODUCT_TRUST_TELEMETRY_SEED_EXAMPLES,
    TRUST_TELEMETRY_SUMMARY_EXAMPLE,
)
from app.trust_telemetry_summary_models import TrustTelemetryReviewSummary


class DeclaredProductTrustTelemetrySnapshot(BaseModel):
    service: str = Field(
        description="Service identifier publishing the local trust telemetry snapshot.",
        json_schema_extra={"example": "lotus-risk"},
    )
    declaration_source: str = Field(
        description="Repo-native producer declaration file used to resolve the declared products.",
        json_schema_extra={"example": "contracts/domain-data-products/lotus-risk-products.v1.json"},
    )
    declaration_fingerprint: str = Field(
        description="Deterministic fingerprint of the repo-native producer declaration payload.",
        json_schema_extra={
            "example": "sha256:6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c6f36c1f0f3f0f08c"
        },
    )
    consumer_declaration_source: str = Field(
        description="Repo-native consumer declaration file used to resolve declared upstream dependencies.",
        json_schema_extra={
            "example": "contracts/domain-data-products/lotus-risk-consumers.v1.json"
        },
    )
    consumer_declaration_fingerprint: str = Field(
        description="Deterministic fingerprint of the repo-native consumer declaration payload.",
        json_schema_extra={
            "example": "sha256:8d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a18d7411c13a0a25a1"
        },
    )
    declared_dependencies: list[DeclaredConsumerDependencyTelemetry] = Field(
        description="Current repo-native declared upstream dependencies required by lotus-risk.",
        json_schema_extra={"example": DECLARED_DEPENDENCY_EXAMPLES},
    )
    summary: TrustTelemetryReviewSummary = Field(
        description="Operator-facing rollup of declaration counts and current runtime dependency posture.",
        json_schema_extra={"example": TRUST_TELEMETRY_SUMMARY_EXAMPLE},
    )
    products: list[ProductTrustTelemetrySeed] = Field(
        description="Current raw telemetry seeds for each repo-native declared product.",
        json_schema_extra={"example": PRODUCT_TRUST_TELEMETRY_SEED_EXAMPLES},
    )
