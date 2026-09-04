from app.contracts.attribution import AttributionInputMode, HistoricalAttributionStatelessInput
from app.services.attribution_engine import calculate_historical_attribution


def _request() -> HistoricalAttributionStatelessInput:
    return HistoricalAttributionStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-03", "value": -0.4},
                {"date": "2026-01-04", "value": 0.3},
                {"date": "2026-01-05", "value": 0.6},
                {"date": "2026-01-06", "value": -0.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-03", "value": -0.3},
                {"date": "2026-01-04", "value": 0.2},
                {"date": "2026-01-05", "value": 0.4},
                {"date": "2026-01-06", "value": -0.1},
            ],
            "exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.55,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.45,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-04",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.52,
                },
                {
                    "date": "2026-01-04",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.48,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.54,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.46,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.53,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.47,
                },
            ],
            "benchmark_exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.48,
                },
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.52,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.47,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.53,
                },
                {
                    "date": "2026-01-04",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.49,
                },
                {
                    "date": "2026-01-04",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.51,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.50,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.49,
                },
                {
                    "date": "2026-01-06",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.51,
                },
            ],
            "attribution_options": {
                "attribution_types": ["TOTAL_RISK", "ACTIVE_RISK"],
                "metrics": ["VOLATILITY", "TRACKING_ERROR"],
                "grouping_dimensions": ["SECTOR"],
                "annualization_basis": 252,
            },
        }
    )


def test_attribution_engine_returns_reconciled_sets() -> None:
    response = calculate_historical_attribution(
        _request(), input_mode=AttributionInputMode.STATELESS
    )
    assert response.input_mode == AttributionInputMode.STATELESS
    period = response.results["YTD"]
    assert period.error is None
    assert len(period.attribution_sets) == 4

    total_risk = next(
        s
        for s in period.attribution_sets
        if s.attribution_type == "TOTAL_RISK" and s.metric == "VOLATILITY"
    )
    assert total_risk.total_value is not None
    assert total_risk.reconciled_sum is not None
    assert total_risk.residual is not None
    assert len(total_risk.contributors) == 2

    active_risk = next(
        s
        for s in period.attribution_sets
        if s.attribution_type == "ACTIVE_RISK" and s.metric == "TRACKING_ERROR"
    )
    assert active_risk.total_value is not None
    assert len(active_risk.contributors) == 2


def test_attribution_engine_insufficient_data_sets_period_error() -> None:
    request = HistoricalAttributionStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-02", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [{"date": "2026-01-02", "value": 0.6}],
            "exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "POSITION",
                    "group_key": "A",
                    "weight": 1.0,
                }
            ],
        }
    )
    response = calculate_historical_attribution(request, input_mode=AttributionInputMode.STATELESS)
    assert response.results["YTD"].error == "Insufficient data"


def test_attribution_engine_sets_quality_flag_for_missing_grouping_data() -> None:
    request = HistoricalAttributionStatelessInput.model_validate(
        {
            "scope": {"as_of_date": "2026-01-04", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 0.6},
                {"date": "2026-01-03", "value": -0.4},
                {"date": "2026-01-04", "value": 0.2},
            ],
            "exposure_history": [
                {
                    "date": "2026-01-02",
                    "grouping_dimension": "POSITION",
                    "group_key": "A",
                    "weight": 1.0,
                },
                {
                    "date": "2026-01-03",
                    "grouping_dimension": "POSITION",
                    "group_key": "A",
                    "weight": 1.0,
                },
            ],
            "attribution_options": {
                "attribution_types": ["TOTAL_RISK"],
                "metrics": ["VOLATILITY"],
                "grouping_dimensions": ["SECTOR"],
            },
        }
    )
    response = calculate_historical_attribution(request, input_mode=AttributionInputMode.STATELESS)
    attribution_set = response.results["YTD"].attribution_sets[0]
    assert "grouping:SECTOR:no_exposure_data" in attribution_set.quality_flags
    assert response.metadata.calculation_supportability.state == "degraded"
    assert response.metadata.calculation_supportability.reason == "calculation_quality_issue"
    assert response.metadata.calculation_supportability.degraded_metric_count == 1


def test_every_attribution_metric_states_its_unit_semantics() -> None:
    from typing import get_args

    from app.contracts.attribution import ATTRIBUTION_METRIC_UNIT_SEMANTICS
    from app.contracts.attribution_common_inputs import AttributionMetric

    stated = set(ATTRIBUTION_METRIC_UNIT_SEMANTICS)
    vocabulary = set(get_args(AttributionMetric))
    assert stated == vocabulary, (
        "An attributed value without stated unit semantics is unreadable downstream; "
        f"missing={sorted(vocabulary - stated)}, orphaned={sorted(stated - vocabulary)}"
    )
    assert set(ATTRIBUTION_METRIC_UNIT_SEMANTICS.values()) <= {"decimal_ratio", "unitless"}


def test_attribution_response_metadata_states_unit_semantics_for_requested_metrics() -> None:
    response = calculate_historical_attribution(
        _request(), input_mode=AttributionInputMode.STATELESS
    )

    assert response.metadata.metric_unit_semantics == {
        "VOLATILITY": "decimal_ratio",
        "TRACKING_ERROR": "decimal_ratio",
    }


def test_metadata_refuses_a_unit_map_that_does_not_match_requested_metrics() -> None:
    """The unit map's promise is per requested metric, exactly: a subset leaves
    a requested value unreadable, a superset states units for values the
    response does not carry, and empty-while-requesting is the mock drift the
    review flagged."""

    import pytest

    from app.contracts.attribution_metadata_outputs import HistoricalAttributionMetadata

    def metadata(**overrides: object) -> HistoricalAttributionMetadata:
        fields: dict[str, object] = {
            "request_fingerprint": "fp",
            "covariance_method": "EMPIRICAL",
            "annualization_basis": 252,
            "metric_unit_semantics": {"TRACKING_ERROR": "decimal_ratio"},
            "requested_attribution_types": ["ACTIVE_RISK"],
            "requested_metrics": ["TRACKING_ERROR"],
            "requested_grouping_dimensions": ["SECTOR"],
            "min_observations_policy": "STRICT",
        }
        fields.update(overrides)
        return HistoricalAttributionMetadata(**fields)  # type: ignore[arg-type]

    assert metadata().metric_unit_semantics == {"TRACKING_ERROR": "decimal_ratio"}

    with pytest.raises(ValueError, match="missing=..TRACKING_ERROR"):
        metadata(metric_unit_semantics={})

    with pytest.raises(ValueError, match="surplus=..VOLATILITY"):
        metadata(
            metric_unit_semantics={
                "VOLATILITY": "decimal_ratio",
                "TRACKING_ERROR": "decimal_ratio",
            }
        )

    with pytest.raises(ValueError, match="missing=..VOLATILITY"):
        metadata(requested_metrics=["VOLATILITY", "TRACKING_ERROR"])
