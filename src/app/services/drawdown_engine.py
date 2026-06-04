from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from collections.abc import Sequence
from typing import Literal, cast

import numpy as np
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
    UnderwaterPoint,
)
from app.contracts.risk import ReturnPoint, RiskCalculationSupportability, RiskRequestPeriod
from app.services.audit_lineage import fingerprint_model
from app.services.calculation_supportability import (
    record_operation_supportability,
    supportability_from_period_results,
)
from app.services.risk import helpers as risk_helpers


@dataclass
class _EpisodeRecord:
    peak_date: date
    trough_date: date
    recovery_date: date | None
    depth: float
    days_to_trough: int
    days_to_recovery: int | None
    total_days: int
    is_recovered: bool


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


@dataclass(frozen=True)
class _DrawdownExtremeFields:
    max_drawdown: float
    peak_date: date | None
    trough_date: date | None
    recovery_date: date | None
    is_recovered: bool
    days_to_trough: int
    days_to_recovery: int | None


def _duration_days(start: date, end: date, *, unit: str) -> int:
    if end < start:
        return 0
    if unit == "CALENDAR_DAYS":
        return (end - start).days
    return int(np.busday_count(start.isoformat(), end.isoformat()))


def _build_returns_df(returns: Sequence[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in returns])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def _filter_period(df: pd.DataFrame, *, start: date, end: date) -> pd.Series:
    filtered = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end)), "value"]
    return filtered


def _episode_record_from_segment(
    *,
    dates: list[date],
    values: list[float],
    start_index: int,
    peak_date: date,
    duration_unit: str,
    recovery_index: int | None,
) -> _EpisodeRecord:
    end_index = recovery_index if recovery_index is not None else len(values) - 1
    segment_values = values[start_index : end_index + 1]
    trough_offset = int(np.argmin(segment_values))
    trough_index = start_index + trough_offset
    trough_date = dates[trough_index]
    recovery_date = dates[recovery_index] if recovery_index is not None else None
    terminal_date = recovery_date or dates[-1]
    depth = float(min(segment_values))
    return _EpisodeRecord(
        peak_date=peak_date,
        trough_date=trough_date,
        recovery_date=recovery_date,
        depth=depth,
        days_to_trough=_duration_days(peak_date, trough_date, unit=duration_unit),
        days_to_recovery=(
            _duration_days(trough_date, recovery_date, unit=duration_unit)
            if recovery_date is not None
            else None
        ),
        total_days=_duration_days(peak_date, terminal_date, unit=duration_unit),
        is_recovered=recovery_date is not None,
    )


def _episode_records_from_values(
    *,
    dates: list[date],
    values: list[float],
    duration_unit: str,
) -> list[_EpisodeRecord]:
    episodes: list[_EpisodeRecord] = []
    in_episode = False
    start_index = 0
    peak_date = dates[0]
    for idx, dd_value in enumerate(values):
        if not in_episode and dd_value < 0:
            in_episode = True
            start_index = idx
            peak_date = dates[idx - 1] if idx > 0 else dates[idx]
            continue
        if in_episode and dd_value >= 0:
            episodes.append(
                _episode_record_from_segment(
                    dates=dates,
                    values=values,
                    start_index=start_index,
                    peak_date=peak_date,
                    duration_unit=duration_unit,
                    recovery_index=idx,
                )
            )
            in_episode = False

    if in_episode:
        episodes.append(
            _episode_record_from_segment(
                dates=dates,
                values=values,
                start_index=start_index,
                peak_date=peak_date,
                duration_unit=duration_unit,
                recovery_index=None,
            )
        )
    return episodes


def _build_episodes(drawdown: pd.Series, *, duration_unit: str) -> list[_EpisodeRecord]:
    dates = [cast(pd.Timestamp, index).date() for index in drawdown.index]
    values = [float(value) for value in drawdown]
    if not values:
        return []
    return _episode_records_from_values(
        dates=dates,
        values=values,
        duration_unit=duration_unit,
    )


def _empty_drawdown_summary() -> DrawdownSummary:
    return DrawdownSummary(
        max_drawdown=None,
        max_drawdown_peak_date=None,
        max_drawdown_trough_date=None,
        max_drawdown_recovery_date=None,
        is_recovered=False,
        days_to_trough=None,
        days_to_recovery=None,
        time_under_water_days=0,
        average_drawdown=None,
        ulcer_index=None,
        drawdown_at_risk_95=None,
        conditional_drawdown_at_risk_95=None,
    )


def _tail_drawdown_risk(
    depths: Sequence[float], *, alpha: float
) -> tuple[float | None, float | None]:
    if not depths:
        return None, None
    dar_value = float(np.quantile(np.array(depths), 1.0 - alpha, method="linear"))
    worst_tail = [depth for depth in depths if depth <= dar_value]
    cdar_value = float(np.mean(worst_tail)) if worst_tail else None
    return dar_value, cdar_value


def _average_drawdown(drawdown: pd.Series) -> float:
    dd_values = [float(value) for value in drawdown if float(value) < 0]
    return float(np.mean(dd_values)) if dd_values else 0.0


def _ulcer_index(drawdown: pd.Series) -> float:
    return float(sqrt(float(np.mean(np.square(np.array([float(v) for v in drawdown]))))))


def _drawdown_extreme_fields(episodes: list[_EpisodeRecord]) -> _DrawdownExtremeFields:
    max_episode = min(episodes, key=lambda episode: episode.depth) if episodes else None
    if max_episode is None:
        return _DrawdownExtremeFields(
            max_drawdown=0.0,
            peak_date=None,
            trough_date=None,
            recovery_date=None,
            is_recovered=True,
            days_to_trough=0,
            days_to_recovery=0,
        )
    return _DrawdownExtremeFields(
        max_drawdown=max_episode.depth,
        peak_date=max_episode.peak_date,
        trough_date=max_episode.trough_date,
        recovery_date=max_episode.recovery_date,
        is_recovered=max_episode.is_recovered,
        days_to_trough=max_episode.days_to_trough,
        days_to_recovery=max_episode.days_to_recovery,
    )


def _drawdown_summary(
    drawdown: pd.Series,
    *,
    alpha: float,
    duration_unit: str,
) -> tuple[DrawdownSummary, list[_EpisodeRecord]]:
    if drawdown.empty:
        return _empty_drawdown_summary(), []

    episodes = _build_episodes(drawdown, duration_unit=duration_unit)
    depths = [episode.depth for episode in episodes]
    dar_value, cdar_value = _tail_drawdown_risk(depths, alpha=alpha)
    extreme = _drawdown_extreme_fields(episodes)

    summary = DrawdownSummary(
        max_drawdown=extreme.max_drawdown,
        max_drawdown_peak_date=extreme.peak_date,
        max_drawdown_trough_date=extreme.trough_date,
        max_drawdown_recovery_date=extreme.recovery_date,
        is_recovered=extreme.is_recovered,
        days_to_trough=extreme.days_to_trough,
        days_to_recovery=extreme.days_to_recovery,
        time_under_water_days=int(sum(1 for value in drawdown if float(value) < 0)),
        average_drawdown=_average_drawdown(drawdown),
        ulcer_index=_ulcer_index(drawdown),
        drawdown_at_risk_95=dar_value,
        conditional_drawdown_at_risk_95=cdar_value,
    )
    return summary, episodes


def _to_underwater_series(drawdown: pd.Series) -> list[UnderwaterPoint]:
    points: list[UnderwaterPoint] = []
    for index, value in drawdown.items():
        timestamp = cast(pd.Timestamp, index)
        points.append(UnderwaterPoint(date=timestamp.date(), drawdown=float(value)))
    return points


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


def _drawdown_from_returns(returns: pd.Series) -> pd.Series:
    wealth = (1 + returns / 100.0).cumprod()
    running_peak = wealth.cummax()
    return wealth / running_peak - 1.0


def _episode_models(
    episodes: list[_EpisodeRecord],
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
