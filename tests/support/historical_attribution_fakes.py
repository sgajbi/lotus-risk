from __future__ import annotations

from tests.support.lotus_performance_fakes import RecordingLotusPerformanceClient
from tests.support.returns_series_payloads import build_returns_series_response


def build_stateful_attribution_returns_client() -> RecordingLotusPerformanceClient:
    return RecordingLotusPerformanceClient(
        response_payload=build_returns_series_response(
            portfolio_returns=[
                ("2026-01-02", "0.0100"),
                ("2026-01-03", "-0.0050"),
                ("2026-01-04", "0.0040"),
            ]
        )
    )


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
            "valuation_date": "2026-01-03",
            "dimensions": {"sector": "TECH", "asset_class": "EQUITY"},
            "ending_market_value_portfolio_currency": "65",
        },
        {
            "security_id": "SEC_B",
            "valuation_date": "2026-01-03",
            "dimensions": {"sector": "HEALTH", "asset_class": "EQUITY"},
            "ending_market_value_portfolio_currency": "35",
        },
    ]


class RecordingHistoricalAttributionCoreClient:
    def __init__(self, *, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = rows or build_sector_position_timeseries_rows()
        self.position_calls: list[dict[str, object | None]] = []

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
