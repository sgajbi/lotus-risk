from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.contracts.mandate_health import (
    MandateRiskHealthContextRequest,
    MandateRiskHealthContextResponse,
    MandateRiskHealthSourceMetric,
    MandateRiskHealthState,
)
from app.contracts.risk import StatelessRiskInput
from app.services.audit_lineage import fingerprint_model
from app.services.risk_engine import calculate_risk


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def evaluate_mandate_risk_health_context(
    request: MandateRiskHealthContextRequest,
) -> MandateRiskHealthContextResponse:
    period_name = request.period.name or request.period.type
    risk_request = StatelessRiskInput(
        scope=request.scope,
        periods=[request.period],
        metrics=["TRACKING_ERROR"],
        portfolio_open_date=request.portfolio_open_date,
        returns=request.returns,
        benchmark_returns=request.benchmark_returns,
    )
    risk_response = calculate_risk(risk_request)
    period_result = risk_response.results[period_name]
    metric = period_result.metrics["TRACKING_ERROR"]
    details = metric.details or {}
    annualized_tracking_error = _to_decimal(details.get("annualized_tracking_error"))
    aligned_observation_count = int(details.get("aligned_observation_count") or 0)

    reason_codes = ["RISK_METHODOLOGY_SOURCE_OWNED"]
    if annualized_tracking_error is None:
        health_state: MandateRiskHealthState = "unavailable"
        threshold_breached = None
        reason_codes.append("MANDATE_RISK_HEALTH_TRACKING_ERROR_UNAVAILABLE")
    else:
        threshold_breached = annualized_tracking_error > request.tracking_error_attention_threshold
        health_state = "attention" if threshold_breached else "ready"
        reason_codes.append("MANDATE_RISK_HEALTH_TRACKING_ERROR_SOURCE_READY")
        if threshold_breached:
            reason_codes.append("MANDATE_RISK_HEALTH_TRACKING_ERROR_THRESHOLD_BREACHED")

    return MandateRiskHealthContextResponse(
        portfolio_id=request.portfolio_id,
        as_of_date=request.scope.as_of_date,
        period_name=period_name,
        health_state=health_state,
        threshold_breached=threshold_breached,
        tracking_error_attention_threshold=request.tracking_error_attention_threshold,
        source_metric=MandateRiskHealthSourceMetric(
            annualized_tracking_error=annualized_tracking_error,
            aligned_observation_count=aligned_observation_count,
        ),
        request_fingerprint=fingerprint_model(request),
        source_request_fingerprint=risk_response.metadata.request_fingerprint or "",
        reason_codes=reason_codes,
    )
