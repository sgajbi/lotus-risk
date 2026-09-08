from __future__ import annotations

from typing import Any

from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response


def build_stateful_attribution_returns_client() -> RecordingLotusPerformanceClient:
    return RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=[
                ("2026-01-02", "0.0100"),
                ("2026-01-05", "-0.0050"),
                ("2026-01-06", "0.0040"),
            ],
            benchmark_returns=[
                ("2026-01-02", "0.0080"),
                ("2026-01-05", "-0.0030"),
                ("2026-01-06", "0.0030"),
            ],
        ),
        benchmark_exposure_context_payload=build_benchmark_exposure_context_response(),
    )


def build_benchmark_exposure_context_response(
    *,
    grouping_dimension: str = "SECTOR",
) -> dict[str, object]:
    if grouping_dimension == "ISSUER":
        rows = [
            {
                "valuation_date": "2026-01-02",
                "component_id": None,
                "grouping_dimension": "ISSUER",
                "group_key": "ISSUER_A",
                "group_label": "Issuer A",
                "weight": "0.55",
            },
            {
                "valuation_date": "2026-01-02",
                "component_id": None,
                "grouping_dimension": "ISSUER",
                "group_key": "ISSUER_B",
                "group_label": "Issuer B",
                "weight": "0.45",
            },
            {
                "valuation_date": "2026-01-05",
                "component_id": None,
                "grouping_dimension": "ISSUER",
                "group_key": "ISSUER_A",
                "group_label": "Issuer A",
                "weight": "0.56",
            },
            {
                "valuation_date": "2026-01-05",
                "component_id": None,
                "grouping_dimension": "ISSUER",
                "group_key": "ISSUER_B",
                "group_label": "Issuer B",
                "weight": "0.44",
            },
            {
                "valuation_date": "2026-01-06",
                "component_id": None,
                "grouping_dimension": "ISSUER",
                "group_key": "ISSUER_A",
                "group_label": "Issuer A",
                "weight": "0.54",
            },
            {
                "valuation_date": "2026-01-06",
                "component_id": None,
                "grouping_dimension": "ISSUER",
                "group_key": "ISSUER_B",
                "group_label": "Issuer B",
                "weight": "0.46",
            },
        ]
    elif grouping_dimension == "ASSET_CLASS":
        rows = [
            {
                "valuation_date": "2026-01-02",
                "component_id": None,
                "grouping_dimension": "ASSET_CLASS",
                "group_key": "ASSET_CLASS_EQUITY",
                "group_label": "EQUITY",
                "weight": "1.00",
            },
            {
                "valuation_date": "2026-01-05",
                "component_id": None,
                "grouping_dimension": "ASSET_CLASS",
                "group_key": "ASSET_CLASS_EQUITY",
                "group_label": "EQUITY",
                "weight": "1.00",
            },
            {
                "valuation_date": "2026-01-06",
                "component_id": None,
                "grouping_dimension": "ASSET_CLASS",
                "group_key": "ASSET_CLASS_EQUITY",
                "group_label": "EQUITY",
                "weight": "1.00",
            },
        ]
    else:
        rows = [
            {
                "valuation_date": "2026-01-02",
                "component_id": None,
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_TECH",
                "group_label": "TECH",
                "weight": "0.55",
            },
            {
                "valuation_date": "2026-01-02",
                "component_id": None,
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_HEALTH",
                "group_label": "HEALTH",
                "weight": "0.45",
            },
            {
                "valuation_date": "2026-01-05",
                "component_id": None,
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_TECH",
                "group_label": "TECH",
                "weight": "0.56",
            },
            {
                "valuation_date": "2026-01-05",
                "component_id": None,
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_HEALTH",
                "group_label": "HEALTH",
                "weight": "0.44",
            },
            {
                "valuation_date": "2026-01-06",
                "component_id": None,
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_TECH",
                "group_label": "TECH",
                "weight": "0.54",
            },
            {
                "valuation_date": "2026-01-06",
                "component_id": None,
                "grouping_dimension": "SECTOR",
                "group_key": "SECTOR_HEALTH",
                "group_label": "HEALTH",
                "weight": "0.46",
            },
        ]
    return {
        "calculation_id": "11111111-1111-1111-1111-111111111111",
        "source_service": "lotus-performance",
        "contract_version": "v1",
        "portfolio_id": "DEMO_DPM_EUR_001",
        "benchmark_id": "BMK_GLOBAL_BALANCED_60_40",
        "benchmark_version": "2026-01-06",
        "as_of_date": "2026-01-06",
        "window": {"start_date": "2026-01-02", "end_date": "2026-01-06"},
        "frequency": "DAILY",
        "reporting_currency": None,
        "rows": rows,
        "page": {"next_page_token": None},
        "metadata": {
            "source_system": "lotus-core",
            "served_by": "lotus-performance",
            "calculation_run_id": "11111111-1111-1111-1111-111111111111",
            "contract_version": "v1",
            "generated_at": "2026-01-06T00:00:00Z",
            "retrieval_metadata": {"benchmark_market_series_chunk_count": 1},
        },
    }


def build_sector_position_timeseries_rows() -> list[dict[str, object]]:
    return [
        {
            "security_id": "SEC_A",
            "valuation_date": "2026-01-02",
            "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
            "ending_market_value_portfolio_currency": "60",
        },
        {
            "security_id": "SEC_B",
            "valuation_date": "2026-01-02",
            "dimensions": {"sector": "HEALTH", "asset_class": "EQUITY"},
            "ending_market_value_portfolio_currency": "40",
        },
        {
            "security_id": "SEC_A",
            "valuation_date": "2026-01-05",
            "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
            "ending_market_value_portfolio_currency": "65",
        },
        {
            "security_id": "SEC_B",
            "valuation_date": "2026-01-05",
            "dimensions": {"sector": "HEALTH", "asset_class": "EQUITY"},
            "ending_market_value_portfolio_currency": "35",
        },
    ]


class RecordingHistoricalAttributionCoreClient:
    def __init__(self, *, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = rows or build_sector_position_timeseries_rows()
        self.position_calls: list[dict[str, Any]] = []

    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, object],
        correlation_id: str | None,
    ) -> dict[str, object]:
        self.position_calls.append(
            {
                "portfolio_id": portfolio_id,
                "request_payload": request_payload,
                "correlation_id": correlation_id,
            }
        )
        return {
            "rows": self.rows,
            "page": {"next_page_token": None},
        }

    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, object]:
        return {"records": []}


def build_stateless_attribution_payload() -> dict[str, object]:
    """A stateless attribution request that decomposes cleanly.

    Shared because the supportability cases (#293) need the same well-formed
    request and then vary one thing each -- the returns, or the periods. A
    second copy would let the baseline drift away from the case under test,
    which is how a supportability assertion stops meaning anything.
    """
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": "2026-01-06", "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": [
                {"date": "2026-01-02", "value": 1.0},
                {"date": "2026-01-05", "value": -0.4},
                {"date": "2026-01-06", "value": 0.3},
                {"date": "2026-01-05", "value": 0.6},
                {"date": "2026-01-06", "value": -0.2},
            ],
            "benchmark_returns": [
                {"date": "2026-01-02", "value": 0.8},
                {"date": "2026-01-05", "value": -0.3},
                {"date": "2026-01-06", "value": 0.2},
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
                    "weight": 0.52,
                },
                {
                    "date": "2026-01-06",
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
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_TECH",
                    "group_label": "Technology",
                    "weight": 0.47,
                },
                {
                    "date": "2026-01-05",
                    "grouping_dimension": "SECTOR",
                    "group_key": "SECTOR_HEALTH",
                    "group_label": "Healthcare",
                    "weight": 0.53,
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
        },
    }
