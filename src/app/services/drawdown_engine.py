from __future__ import annotations

from typing import Literal

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownInputMode,
    DrawdownMetadata,
    DrawdownPeriodResult,
    DrawdownResponse,
    DrawdownStatelessInput,
)
from app.contracts.risk import RiskCalculationSupportability
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_period_results,
)
from app.services.drawdown_periods import build_input_frames, drawdown_period_results
from app.services.drawdown_series import (
    drawdown_summary as _drawdown_summary,
)
from app.services.drawdown_series import (
    duration_days as _duration_days,
)

__all__ = ["_drawdown_summary", "_duration_days", "calculate_drawdown"]


def _build_metadata(
    *,
    request: DrawdownStatelessInput,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
    missing_benchmark_policy: Literal["IGNORE", "REQUIRE"] | None,
    calculation_supportability: RiskCalculationSupportability,
) -> DrawdownMetadata:
    return DrawdownMetadata(
        request_fingerprint=fingerprint_model(request),
        include_underwater_series=analysis_options.include_underwater_series,
        include_episode_list=analysis_options.include_episode_list,
        top_n_episodes=analysis_options.top_n_episodes,
        cdar_alpha=analysis_options.cdar_alpha,
        minimum_episode_depth_bps=analysis_options.minimum_episode_depth_bps,
        duration_unit=analysis_options.duration_unit,
        include_benchmark=include_benchmark,
        missing_benchmark_policy=missing_benchmark_policy,
        calculation_supportability=calculation_supportability,
    )


def _empty_response(
    request: DrawdownStatelessInput,
    *,
    input_mode: DrawdownInputMode,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
    missing_benchmark_policy: Literal["IGNORE", "REQUIRE"] | None,
) -> DrawdownResponse:
    calculation_supportability = supportability_from_period_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results={},
    )
    record_operation_supportability(
        operation="risk/drawdown",
        supportability=calculation_supportability,
    )
    return DrawdownResponse(
        input_mode=input_mode,
        scope=request.scope,
        results={},
        metadata=_build_metadata(
            request=request,
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
            missing_benchmark_policy=missing_benchmark_policy,
            calculation_supportability=calculation_supportability,
        ),
    )


def _drawdown_response(
    *,
    request: DrawdownStatelessInput,
    input_mode: DrawdownInputMode,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
    missing_benchmark_policy: Literal["IGNORE", "REQUIRE"] | None,
    results: dict[str, DrawdownPeriodResult],
) -> DrawdownResponse:
    calculation_supportability = supportability_from_period_results(
        returns=request.returns,
        as_of_date=request.scope.as_of_date,
        results=results,
    )
    record_operation_supportability(
        operation="risk/drawdown",
        supportability=calculation_supportability,
    )
    return DrawdownResponse(
        input_mode=input_mode,
        scope=request.scope,
        results=results,
        metadata=_build_metadata(
            request=request,
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
            missing_benchmark_policy=missing_benchmark_policy,
            calculation_supportability=calculation_supportability,
        ),
    )


def calculate_drawdown(
    request: DrawdownStatelessInput,
    *,
    input_mode: DrawdownInputMode,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None = None,
    missing_benchmark_policy: Literal["IGNORE", "REQUIRE"] | None = None,
) -> DrawdownResponse:
    frames = build_input_frames(request)
    if frames.portfolio.empty:
        return _empty_response(
            request,
            input_mode=input_mode,
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
            missing_benchmark_policy=missing_benchmark_policy,
        )

    return _drawdown_response(
        request=request,
        input_mode=input_mode,
        analysis_options=analysis_options,
        include_benchmark=include_benchmark,
        missing_benchmark_policy=missing_benchmark_policy,
        results=drawdown_period_results(
            request=request,
            frames=frames,
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
        ),
    )
