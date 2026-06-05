from __future__ import annotations

from datetime import date

import pandas as pd

from app.contracts.risk import ReturnPoint, RiskRequestPeriod
from app.contracts.rolling import RollingStatelessInput
from app.services.risk.period_resolution import resolve_period
from app.services.rolling_engine_models import RollingInputFrames, RollingPeriodSeries


def build_rolling_input_frames(request: RollingStatelessInput) -> RollingInputFrames:
    return RollingInputFrames(
        portfolio=_build_returns_df(request.returns),
        benchmark=_build_returns_df(request.benchmark_returns),
        risk_free=_build_returns_df(request.risk_free_returns),
    )


def rolling_period_series(
    *,
    frames: RollingInputFrames,
    request: RollingStatelessInput,
    period: RiskRequestPeriod,
    open_date: date,
) -> RollingPeriodSeries:
    start, end = resolve_period(
        period.type,
        request.scope.as_of_date,
        open_date,
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    portfolio_period_pp = _filter_period(frames.portfolio, start=start, end=end)
    benchmark_period = (
        _filter_period(frames.benchmark, start=start, end=end) / 100.0
        if not frames.benchmark.empty
        else pd.Series(dtype="float64")
    )
    risk_free_period = (
        _filter_period(frames.risk_free, start=start, end=end) / 100.0
        if not frames.risk_free.empty
        else pd.Series(dtype="float64")
    )
    return RollingPeriodSeries(
        name=period.name or period.type,
        start=start,
        end=end,
        portfolio_pp=portfolio_period_pp,
        portfolio_decimal=portfolio_period_pp / 100.0,
        benchmark_decimal=benchmark_period,
        risk_free_decimal=risk_free_period,
    )


def _build_returns_df(returns: list[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in returns])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def _filter_period(df: pd.DataFrame, *, start: date, end: date) -> pd.Series:
    return df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end)), "value"]


__all__ = ["build_rolling_input_frames", "rolling_period_series"]
