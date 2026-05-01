from __future__ import annotations

from app.main import app
from app.observability_contracts import RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS


def test_risk_supportability_openapi_documents_metric_labels() -> None:
    schema = app.openapi()["components"]["schemas"]["RiskCalculationSupportability"]
    metric_labels = schema["properties"]["metric_labels"]

    assert metric_labels["default"] == list(RISK_CALCULATION_SUPPORTABILITY_METRIC_LABELS)
    assert "lotus_risk_calculation_supportability_total" in metric_labels["description"]
    assert (
        "request or response payload fields must not be metric labels"
        in (metric_labels["description"])
    )
