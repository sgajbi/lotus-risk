from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from collections.abc import Sequence
from typing import Literal, cast

import pandas as pd

from app.contracts.drawdown import (
    DrawdownAnalysisOptions,
    DrawdownEpisode,
    DrawdownInputMode,
    DrawdownMetadata,
    DrawdownPeriodResult,
    RelativeDrawdownContext,
    DrawdownResponse,
    DrawdownStatelessInput,
    DrawdownSummary,
    RelativeDrawdownSummary,
)
from app.contracts.risk import ReturnPoint, RiskCalculationSupportability, RiskRequestPeriod
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_period_results,
)
from app.services.drawdown_series import (
    EpisodeRecord,
    drawdown_from_returns as _drawdown_from_returns,
    drawdown_summary as _drawdown_summary,
    duration_days as _duration_days,
    to_underwater_series as _to_underwater_series,
)
from app.services.risk import helpers as risk_helpers


__all__ = ["_drawdown_summary", "_duration_days", "calculate_drawdown"]


@dataclass(frozen=True)
class _DrawdownInputFrames:
    portfolio: pd.DataFrame
    benchmark: pd.DataFrame


@dataclass(frozen=True)
class _DrawdownPeriodSeries:
    name: str
    start: date
    end: date
    portfolio_returns: pd.Series
    benchmark_returns: pd.Series
    benchmark_available: bool


@dataclass(frozen=True)
class _RelativeBenchmarkResult:
    summary: RelativeDrawdownSummary | None
    context: RelativeDrawdownContext


def _build_returns_df(returns: Sequence[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in returns])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def _filter_period(df: pd.DataFrame, *, start: date, end: date) -> pd.Series:
    filtered = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end)), "value"]
    return filtered


def _period_name(period: RiskRequestPeriod) -> str:
    return period.name or period.type


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


def _build_input_frames(request: DrawdownStatelessInput) -> _DrawdownInputFrames:
    return _DrawdownInputFrames(
        portfolio=_build_returns_df(request.returns),
        benchmark=_build_returns_df(request.benchmark_returns),
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


def _period_series(
    *,
    frames: _DrawdownInputFrames,
    request: DrawdownStatelessInput,
    period: RiskRequestPeriod,
    open_date: date,
) -> _DrawdownPeriodSeries:
    start, end = risk_helpers._resolve_period(
        period.type,
        request.scope.as_of_date,
        open_date,
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    benchmark_returns = (
        _filter_period(frames.benchmark, start=start, end=end)
        if not frames.benchmark.empty
        else pd.Series(dtype="float64")
    )
    return _DrawdownPeriodSeries(
        name=_period_name(period),
        start=start,
        end=end,
        portfolio_returns=_filter_period(frames.portfolio, start=start, end=end),
        benchmark_returns=benchmark_returns,
        benchmark_available=not frames.benchmark.empty,
    )


def _insufficient_period_result(
    period_series: _DrawdownPeriodSeries,
    *,
    include_benchmark: bool | None,
) -> DrawdownPeriodResult:
    return DrawdownPeriodResult(
        start_date=period_series.start,
        end_date=period_series.end,
        portfolio_observation_count=0,
        benchmark_observation_count=0,
        summary=None,
        episodes=[],
        relative_to_benchmark=None,
        relative_to_benchmark_context=RelativeDrawdownContext(
            requested=include_benchmark is True,
            applied=False,
            reason="BENCHMARK_UNAVAILABLE" if include_benchmark is True else "NOT_REQUESTED",
            aligned_observation_count=0,
        ),
        underwater_series=None,
        error="Insufficient data",
    )


def _episode_models(
    episodes: list[EpisodeRecord],
    *,
    analysis_options: DrawdownAnalysisOptions,
) -> list[DrawdownEpisode]:
    min_depth = analysis_options.minimum_episode_depth_bps / 10000.0
    filtered_episodes = [episode for episode in episodes if abs(episode.depth) >= min_depth]
    filtered_episodes = sorted(filtered_episodes, key=lambda episode: episode.depth)[
        : analysis_options.top_n_episodes
    ]
    if not analysis_options.include_episode_list:
        return []
    return [
        DrawdownEpisode(
            episode_id=f"dd_{index + 1:04d}",
            peak_date=episode.peak_date,
            trough_date=episode.trough_date,
            recovery_date=episode.recovery_date,
            depth=episode.depth,
            days_to_trough=episode.days_to_trough,
            days_to_recovery=episode.days_to_recovery,
            total_days=episode.total_days,
            is_recovered=episode.is_recovered,
        )
        for index, episode in enumerate(filtered_episodes)
    ]


def _relative_benchmark_context(
    *,
    include_benchmark: bool | None,
    benchmark_available: bool,
    aligned_observation_count: int | None = None,
) -> RelativeDrawdownContext:
    requested = include_benchmark is True
    if aligned_observation_count is not None:
        return RelativeDrawdownContext(
            requested=requested,
            applied=aligned_observation_count > 0,
            reason="APPLIED" if aligned_observation_count > 0 else "NO_ALIGNED_OBSERVATIONS",
            aligned_observation_count=aligned_observation_count,
        )
    return RelativeDrawdownContext(
        requested=requested,
        applied=False,
        reason=(
            "NO_ALIGNED_OBSERVATIONS"
            if benchmark_available
            else "NOT_REQUESTED"
            if not requested
            else "BENCHMARK_UNAVAILABLE"
        ),
        aligned_observation_count=0,
    )


def _relative_drawdown_summary(active_summary: DrawdownSummary) -> RelativeDrawdownSummary:
    return RelativeDrawdownSummary(
        max_drawdown=active_summary.max_drawdown,
        max_drawdown_peak_date=active_summary.max_drawdown_peak_date,
        max_drawdown_trough_date=active_summary.max_drawdown_trough_date,
        max_drawdown_recovery_date=active_summary.max_drawdown_recovery_date,
        is_recovered=active_summary.is_recovered,
        days_to_trough=active_summary.days_to_trough,
        days_to_recovery=active_summary.days_to_recovery,
        time_under_water_days=active_summary.time_under_water_days or 0,
    )


def _relative_benchmark_result(
    period_series: _DrawdownPeriodSeries,
    *,
    include_benchmark: bool | None,
    analysis_options: DrawdownAnalysisOptions,
) -> _RelativeBenchmarkResult:
    if period_series.benchmark_returns.empty:
        return _RelativeBenchmarkResult(
            summary=None,
            context=_relative_benchmark_context(
                include_benchmark=include_benchmark,
                benchmark_available=period_series.benchmark_available,
            ),
        )

    aligned = pd.merge(
        period_series.portfolio_returns.to_frame("portfolio"),
        period_series.benchmark_returns.to_frame("benchmark"),
        left_index=True,
        right_index=True,
        how="inner",
    )
    relative_context = _relative_benchmark_context(
        include_benchmark=include_benchmark,
        benchmark_available=period_series.benchmark_available,
        aligned_observation_count=len(aligned),
    )
    if aligned.empty:
        return _RelativeBenchmarkResult(summary=None, context=relative_context)

    active_drawdown = _drawdown_from_returns(aligned["portfolio"] - aligned["benchmark"])
    active_summary, _ = _drawdown_summary(
        active_drawdown,
        alpha=float(analysis_options.cdar_alpha),
        duration_unit=analysis_options.duration_unit,
    )
    return _RelativeBenchmarkResult(
        summary=_relative_drawdown_summary(active_summary),
        context=relative_context,
    )


def _calculate_period_result(
    period_series: _DrawdownPeriodSeries,
    *,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
) -> DrawdownPeriodResult:
    if len(period_series.portfolio_returns) < 1:
        return _insufficient_period_result(
            period_series,
            include_benchmark=include_benchmark,
        )

    drawdown = _drawdown_from_returns(period_series.portfolio_returns)
    summary, episodes = _drawdown_summary(
        drawdown,
        alpha=float(analysis_options.cdar_alpha),
        duration_unit=analysis_options.duration_unit,
    )
    relative = _relative_benchmark_result(
        period_series,
        include_benchmark=include_benchmark,
        analysis_options=analysis_options,
    )
    return DrawdownPeriodResult(
        start_date=period_series.start,
        end_date=period_series.end,
        portfolio_observation_count=len(period_series.portfolio_returns),
        benchmark_observation_count=len(period_series.benchmark_returns),
        summary=summary,
        episodes=_episode_models(episodes, analysis_options=analysis_options),
        relative_to_benchmark=relative.summary,
        relative_to_benchmark_context=relative.context,
        underwater_series=(
            _to_underwater_series(drawdown) if analysis_options.include_underwater_series else None
        ),
        error=None,
    )


def _drawdown_period_results(
    *,
    request: DrawdownStatelessInput,
    frames: _DrawdownInputFrames,
    analysis_options: DrawdownAnalysisOptions,
    include_benchmark: bool | None,
) -> dict[str, DrawdownPeriodResult]:
    open_date = cast(pd.Timestamp, frames.portfolio.index.min()).date()
    results: dict[str, DrawdownPeriodResult] = {}
    for period in request.periods:
        period_series = _period_series(
            frames=frames,
            request=request,
            period=period,
            open_date=open_date,
        )
        results[period_series.name] = _calculate_period_result(
            period_series,
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
        )
    return results


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
    frames = _build_input_frames(request)
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
        results=_drawdown_period_results(
            request=request,
            frames=frames,
            analysis_options=analysis_options,
            include_benchmark=include_benchmark,
        ),
    )
