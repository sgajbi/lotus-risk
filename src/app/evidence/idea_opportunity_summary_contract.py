from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from numbers import Real
from typing import Any

from app.evidence.idea_opportunity_constants import EXPECTED_SUMMARY_KEYS


def summary_is_valid(proof_name: str, summary: Any) -> bool:
    if not isinstance(summary, Mapping):
        return False
    required_keys = EXPECTED_SUMMARY_KEYS.get(proof_name)
    if required_keys is None:
        return False
    return (
        set(summary) == set(required_keys)
        and all(summary.get(key) is not None for key in required_keys)
        and _summary_values_are_valid(proof_name, summary)
    )


def _summary_values_are_valid(proof_name: str, summary: Mapping[str, Any]) -> bool:
    if proof_name == "concentration_risk":
        return (
            _number_in_range(summary.get("positionHhiCurrent"), minimum=0, maximum=10_000)
            and _number_in_range(summary.get("positionHhiProposed"), minimum=0, maximum=10_000)
            and _number_in_range(summary.get("issuerHhiCurrent"), minimum=0, maximum=10_000)
            and _number_in_range(summary.get("issuerHhiProposed"), minimum=0, maximum=10_000)
            and _number_in_range(summary.get("topIssuerWeightCurrent"), minimum=0, maximum=1)
            and summary.get("coverageStatus") == "complete"
            and summary.get("coverageRatioCurrent") == 1
        )
    if proof_name == "high_volatility":
        return (
            summary.get("periodName") == "YTD"
            and _number_in_range(summary.get("volatilityPercent"), minimum=0, maximum=100)
            and _number_in_range(summary.get("maxDrawdownPercent"), minimum=-100, maximum=0)
            and _number_in_range(summary.get("varPercent"), minimum=-100, maximum=0)
            and _number_in_range(summary.get("trackingErrorPercent"), minimum=0, maximum=100)
        )
    if proof_name == "drawdown_review":
        return (
            summary.get("periodName") == "YTD"
            and _number_in_range(summary.get("maxDrawdown"), minimum=-1, maximum=0)
            and _whole_number_in_range(summary.get("timeUnderWaterDays"), minimum=0)
            and _number_in_range(summary.get("ulcerIndex"), minimum=0, maximum=1)
            and _whole_number_in_range(summary.get("episodeCount"), minimum=1)
        )
    return False


def _number_in_range(value: Any, *, minimum: int, maximum: int) -> bool:
    if not isinstance(value, Real) or isinstance(value, bool):
        return False
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation:
        return False
    return Decimal(minimum) <= decimal_value <= Decimal(maximum)


def _whole_number_in_range(value: Any, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum
