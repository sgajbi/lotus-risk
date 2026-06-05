import pandas as pd

from app.contracts.attribution import AttributionOptions
from app.services.attribution_period_sets import (
    build_period_attribution_sets,
    requires_benchmark_attribution,
)
from app.services.attribution_source_frames import AttributionSourceFrames


def test_requires_benchmark_attribution_for_active_risk_or_tracking_error() -> None:
    assert not requires_benchmark_attribution(
        AttributionOptions(
            attribution_types=["TOTAL_RISK"],
            metrics=["VOLATILITY"],
            grouping_dimensions=["SECTOR"],
        )
    )
    assert requires_benchmark_attribution(
        AttributionOptions(
            attribution_types=["ACTIVE_RISK"],
            metrics=["VOLATILITY"],
            grouping_dimensions=["SECTOR"],
        )
    )
    assert requires_benchmark_attribution(
        AttributionOptions(
            attribution_types=["TOTAL_RISK"],
            metrics=["TRACKING_ERROR"],
            grouping_dimensions=["SECTOR"],
        )
    )


def test_build_period_attribution_sets_keeps_benchmark_flags_with_active_risk() -> None:
    start = pd.Timestamp("2026-01-02")
    end = pd.Timestamp("2026-01-03")
    frames = AttributionSourceFrames(
        returns_df=pd.DataFrame(),
        benchmark_df=pd.DataFrame(),
        exposure_df=pd.DataFrame(
            [
                {
                    "date": start,
                    "grouping_dimension": "SECTOR",
                    "group_key": "TECH",
                    "group_label": "Technology",
                    "weight": 1.0,
                },
                {
                    "date": end,
                    "grouping_dimension": "SECTOR",
                    "group_key": "TECH",
                    "group_label": "Technology",
                    "weight": 1.0,
                },
            ]
        ),
        benchmark_exposure_df=pd.DataFrame(
            columns=["date", "grouping_dimension", "group_key", "group_label", "weight"]
        ),
    )

    period_sets = build_period_attribution_sets(
        options=AttributionOptions(
            attribution_types=["ACTIVE_RISK"],
            metrics=["TRACKING_ERROR"],
            grouping_dimensions=["SECTOR"],
        ),
        frames=frames,
        returns_series=pd.Series([0.01, 0.02], index=[start, end]),
        benchmark_series=pd.Series([0.01, 0.01], index=[start, end]),
        start=start,
        end=end,
    )

    assert len(period_sets) == 1
    assert "grouping:SECTOR:no_exposure_data" in period_sets[0].quality_flags
