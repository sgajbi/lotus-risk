from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pandas as pd

from app.contracts.attribution import (
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionStatelessInput,
)
from app.contracts.risk import ReturnPoint


@dataclass(frozen=True)
class AttributionSourceFrames:
    returns_df: pd.DataFrame
    benchmark_df: pd.DataFrame
    exposure_df: pd.DataFrame
    benchmark_exposure_df: pd.DataFrame


def _returns_df(points: list[ReturnPoint]) -> pd.DataFrame:
    df = pd.DataFrame([{"date": point.date, "value": point.value} for point in points])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def _exposure_df(points: list[ExposurePoint]) -> pd.DataFrame:
    columns = ["date", "grouping_dimension", "group_key", "group_label", "weight"]
    df = pd.DataFrame(
        [
            {
                "date": point.date,
                "grouping_dimension": point.grouping_dimension,
                "group_key": point.group_key,
                "group_label": point.group_label,
                "weight": point.weight,
            }
            for point in points
        ],
        columns=columns,
    )
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def build_source_frames(request: HistoricalAttributionStatelessInput) -> AttributionSourceFrames:
    return AttributionSourceFrames(
        returns_df=_returns_df(request.returns),
        benchmark_df=_returns_df(request.benchmark_returns),
        exposure_df=_exposure_df(request.exposure_history),
        benchmark_exposure_df=_exposure_df(request.benchmark_exposure_history),
    )


def window_returns(series_df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    return series_df.loc[(series_df.index >= start) & (series_df.index <= end), "value"]


def pivot_exposure(
    df: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    grouping_dimension: GroupingDimension,
) -> tuple[pd.DataFrame, dict[str, str | None], list[str]]:
    scoped = df.loc[
        (df["date"] >= start)
        & (df["date"] <= end)
        & (df["grouping_dimension"] == grouping_dimension)
    ]
    if scoped.empty:
        return pd.DataFrame(), {}, [f"grouping:{grouping_dimension}:no_exposure_data"]

    labels_raw = scoped.groupby("group_key", as_index=True)["group_label"].last().to_dict()
    labels = {str(key): cast(str | None, value) for key, value in labels_raw.items()}
    weights = scoped.pivot_table(index="date", columns="group_key", values="weight", aggfunc="mean")
    weights = weights.sort_index().fillna(0.0)

    flags: list[str] = []
    sums = weights.sum(axis=1)
    if (sums - 1.0).abs().max() > 0.02:
        flags.append(f"grouping:{grouping_dimension}:weight_not_sum_to_one")
    return weights, labels, flags
