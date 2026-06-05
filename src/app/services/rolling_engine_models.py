from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.contracts.rolling import RollingWindowResult


@dataclass(frozen=True)
class RollingInputFrames:
    portfolio: pd.DataFrame
    benchmark: pd.DataFrame
    risk_free: pd.DataFrame


@dataclass(frozen=True)
class RollingPeriodSeries:
    name: str
    start: date
    end: date
    portfolio_pp: pd.Series
    portfolio_decimal: pd.Series
    benchmark_decimal: pd.Series
    risk_free_decimal: pd.Series


@dataclass(frozen=True)
class RollingWindowCalculation:
    window_result: RollingWindowResult
    quality_flags: set[str]
    aligned_benchmark_series_count: int
    aligned_risk_free_series_count: int


@dataclass(frozen=True)
class RollingPeriodWindowAggregate:
    window_results: list[RollingWindowResult]
    quality_flags: set[str]
    aligned_benchmark_series_count: int
    aligned_risk_free_series_count: int
