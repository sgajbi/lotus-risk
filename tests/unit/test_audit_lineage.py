from __future__ import annotations

from datetime import date

import pytest

from app.contracts.attribution import (
    AttributionInputMode,
    HistoricalAttributionStatelessInput,
)
from app.contracts.concentration import ConcentrationRequest
from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownInputMode,
    DrawdownStatelessInput,
)
from app.contracts.risk import (
    ReturnPoint,
    RiskRequestPeriod,
    RiskRequestScope,
    RiskStatelessCalculationInput,
)
from app.contracts.rolling import (
    RollingInputMode,
    RollingOptions,
    RollingStatelessInput,
)
from app.services.attribution_engine import calculate_historical_attribution
from app.services.audit_lineage import fingerprint_payload
from app.services.concentration_engine import calculate_concentration
from app.services.drawdown_engine import calculate_drawdown
from app.services.risk_engine import calculate_risk
from app.services.rolling_engine import calculate_rolling_metrics


def _scope() -> RiskRequestScope:
    return RiskRequestScope(as_of_date=date(2026, 3, 31), reporting_currency="USD")


def _periods() -> list[RiskRequestPeriod]:
    return [RiskRequestPeriod(type="YTD", name="YTD")]


def _returns() -> list[ReturnPoint]:
    return [
        ReturnPoint(date=date(2026, 1, 2), value=0.5),
        ReturnPoint(date=date(2026, 1, 5), value=-0.2),
    ]


def test_fingerprint_payload_is_order_independent_and_change_sensitive() -> None:
    first = fingerprint_payload({"b": [2, 1], "a": {"x": "same"}})
    reordered = fingerprint_payload({"a": {"x": "same"}, "b": [2, 1]})
    changed = fingerprint_payload({"a": {"x": "changed"}, "b": [2, 1]})

    assert first.startswith("sha256:")
    assert first == reordered
    assert first != changed


def test_risk_metadata_includes_reproducible_audit_lineage() -> None:
    request = RiskStatelessCalculationInput(
        scope=_scope(),
        periods=_periods(),
        metrics=["VOLATILITY"],
        portfolio_open_date=date(2026, 1, 2),
        returns=_returns(),
    )

    response = calculate_risk(request)

    assert response.metadata.lineage_version == "risk_audit_lineage.v1"
    assert response.metadata.request_fingerprint == fingerprint_payload(request)
    assert response.metadata.source_services == ["lotus-risk"]
    assert response.metadata.upstream_request_fingerprints == {}


def test_drawdown_metadata_includes_reproducible_audit_lineage() -> None:
    request = DrawdownStatelessInput(scope=_scope(), periods=_periods(), returns=_returns())

    response = calculate_drawdown(
        request,
        input_mode=DrawdownInputMode.STATELESS,
        analysis_options=DrawdownAnalysisOptions(),
    )

    assert response.metadata.request_fingerprint == fingerprint_payload(request)
    assert response.metadata.source_services == ["lotus-risk"]


def test_rolling_metadata_includes_reproducible_audit_lineage() -> None:
    request = RollingStatelessInput(
        scope=_scope(),
        periods=_periods(),
        returns=_returns(),
        rolling_options=RollingOptions(metrics=["ROLLING_VOLATILITY"], window_lengths=[2]),
    )

    response = calculate_rolling_metrics(request, input_mode=RollingInputMode.STATELESS)

    assert response.metadata.request_fingerprint == fingerprint_payload(request)
    assert response.metadata.source_services == ["lotus-risk"]


def test_attribution_metadata_includes_reproducible_audit_lineage() -> None:
    request = HistoricalAttributionStatelessInput(
        scope=_scope(),
        periods=_periods(),
        returns=[],
        exposure_history=[],
    )

    response = calculate_historical_attribution(
        request,
        input_mode=AttributionInputMode.STATELESS,
    )

    assert response.metadata.request_fingerprint == fingerprint_payload(request)
    assert response.metadata.source_services == ["lotus-risk"]


@pytest.mark.asyncio
async def test_concentration_metadata_includes_reproducible_audit_lineage() -> None:
    request = ConcentrationRequest.model_validate(
        {
            "input_mode": "stateless",
            "stateless_input": {
                "current_positions": [
                    {"security_id": "A", "quantity": 10, "issuer_id": "ISSUER_A"},
                    {"security_id": "B", "quantity": 20, "issuer_id": "ISSUER_B"},
                ]
            },
        }
    )

    response = await calculate_concentration(request)

    assert response.metadata is not None
    assert response.metadata.request_fingerprint == fingerprint_payload(request)
    assert response.metadata.source_services == ["lotus-risk"]
    assert response.metadata.generated_at.tzinfo is not None
