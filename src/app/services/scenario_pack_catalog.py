from __future__ import annotations

from dataclasses import dataclass


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


__all__ = ["SCENARIO_PACKS", "SUPPORTED_BUCKETS", "ScenarioDefinition"]
