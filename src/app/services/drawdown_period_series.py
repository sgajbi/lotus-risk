from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from collections.abc import Sequence

import pandas as pd

from app.contracts.drawdown import DrawdownStatelessInput
from app.contracts.risk import ReturnPoint, RiskRequestPeriod
from app.services.risk.period_resolution import resolve_period


@dataclass(frozen=True)
class DrawdownInputFrames:
    portfolio: pd.DataFrame
    benchmark: pd.DataFrame


@dataclass(frozen=True)
class DrawdownPeriodSeries:
    name: str
    start: date
    end: date
    portfolio_returns: pd.Series
    benchmark_returns: pd.Series
    benchmark_available: bool


def build_input_frames(request: DrawdownStatelessInput) -> DrawdownInputFrames:
    return DrawdownInputFrames(
        portfolio=build_returns_df(request.returns),
        benchmark=build_returns_df(request.benchmark_returns),
    )


def period_series(
    *,
    frames: DrawdownInputFrames,
    request: DrawdownStatelessInput,
    period: RiskRequestPeriod,
    open_date: date,
) -> DrawdownPeriodSeries:
    start, end = resolve_period(
        period.type,
        request.scope.as_of_date,
        open_date,
        year=period.year,
        from_date=period.from_date,
        to_date=period.to_date,
    )
    benchmark_returns = (
        filter_period(frames.benchmark, start=start, end=end)
        if not frames.benchmark.empty
        else pd.Series(dtype="float64")
    )
    return DrawdownPeriodSeries(
        name=period_name(period),
        start=start,
        end=end,
        portfolio_returns=filter_period(frames.portfolio, start=start, end=end),
        benchmark_returns=benchmark_returns,
        benchmark_available=not frames.benchmark.empty,
    )


def build_returns_df(returns: Sequence[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in returns])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def filter_period(df: pd.DataFrame, *, start: date, end: date) -> pd.Series:
    return df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end)), "value"]


def period_name(period: RiskRequestPeriod) -> str:
    return period.name or period.type


__all__ = [
    "DrawdownInputFrames",
    "DrawdownPeriodSeries",
    "build_input_frames",
    "build_returns_df",
    "filter_period",
    "period_name",
    "period_series",
]
