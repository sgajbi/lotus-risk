from __future__ import annotations

from app.contracts.concentration import (
    ConcentrationRequest,
    ConcentrationResponse,
    ConcentrationRiskProxy,
)

SERVICE_NAME = "lotus-risk"


def _compute_hhi(values: list[float]) -> float:
    total = sum(abs(v) for v in values)
    if total <= 0:
        return 0.0
    weights = [abs(v) / total for v in values]
    return sum(w * w for w in weights) * 10000.0


def calculate_concentration(request: ConcentrationRequest) -> ConcentrationResponse:
    current_values = [
        p.quantity for p in request.current_positions if p.quantity is not None and p.quantity > 0
    ]
    projected_values = [
        p.proposed_quantity
        for p in request.projected_positions
        if p.proposed_quantity is not None and p.proposed_quantity > 0
    ]
    current_hhi = _compute_hhi(current_values)
    proposed_hhi = _compute_hhi(projected_values) if projected_values else current_hhi
    return ConcentrationResponse(
        sourceService=SERVICE_NAME,
        riskProxy=ConcentrationRiskProxy(
            hhiCurrent=round(current_hhi, 6),
            hhiProposed=round(proposed_hhi, 6),
            hhiDelta=round(proposed_hhi - current_hhi, 6),
        ),
    )
