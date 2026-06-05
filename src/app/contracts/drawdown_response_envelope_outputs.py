from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.drawdown_examples import DRAWDOWN_RESPONSE_EXAMPLES
from app.contracts.drawdown_inputs import DrawdownInputMode
from app.contracts.drawdown_metadata_outputs import DrawdownMetadata
from app.contracts.drawdown_period_outputs import DrawdownPeriodResult
from app.contracts.risk import RiskRequestScope


class DrawdownResponse(BaseModel):
    source_service: Literal["lotus-risk"] = Field(
        default="lotus-risk",
        description="Service identifier producing this drawdown analytics response.",
        json_schema_extra={"example": "lotus-risk"},
    )
    input_mode: DrawdownInputMode = Field(
        description="Execution mode used to produce this response.",
        json_schema_extra={"example": "stateful"},
    )
    scope: RiskRequestScope = Field(
        description="Normalized scope context used for drawdown calculations.",
        json_schema_extra={
            "example": {
                "as_of_date": "2026-02-28",
                "reporting_currency": "USD",
                "net_or_gross": "NET",
            }
        },
    )
    results: dict[str, DrawdownPeriodResult] = Field(
        description="Drawdown period results keyed by period name.",
        json_schema_extra={
            "example": {
                "YTD": {
                    "start_date": "2026-01-01",
                    "end_date": "2026-03-31",
                    "summary": {
                        "max_drawdown": -0.084211,
                        "max_drawdown_peak_date": "2026-01-11",
                        "max_drawdown_trough_date": "2026-02-03",
                    },
                    "episodes": [
                        {
                            "episode_id": "dd_0001",
                            "peak_date": "2026-01-11",
                            "trough_date": "2026-02-03",
                            "recovery_date": "2026-02-19",
                            "depth": -0.084211,
                            "days_to_trough": 16,
                            "days_to_recovery": 11,
                            "total_days": 27,
                            "is_recovered": True,
                        }
                    ],
                    "relative_to_benchmark": {
                        "max_drawdown": -0.026414,
                        "max_drawdown_peak_date": "2026-01-04",
                        "max_drawdown_trough_date": "2026-02-15",
                        "time_under_water_days": 74,
                    },
                    "underwater_series": [{"date": "2026-01-02", "drawdown": -0.0121}],
                    "error": None,
                }
            }
        },
    )
    metadata: DrawdownMetadata = Field(
        default_factory=DrawdownMetadata,
        description="Drawdown contract and methodology metadata.",
        json_schema_extra={
            "example": {
                "contract_version": "v1",
                "methodology_version": "drawdown.v1",
                "include_underwater_series": False,
                "include_episode_list": True,
                "top_n_episodes": 5,
                "cdar_alpha": 0.95,
                "minimum_episode_depth_bps": 0.0,
                "duration_unit": "BUSINESS_DAYS",
                "include_benchmark": True,
                "missing_benchmark_policy": "IGNORE",
            }
        },
    )

    model_config = ConfigDict(json_schema_extra={"examples": cast(Any, DRAWDOWN_RESPONSE_EXAMPLES)})


__all__ = ["DrawdownResponse"]
