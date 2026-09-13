"""Producer-owned contribution request construction for stateful attribution."""

from __future__ import annotations

import datetime as dt
from typing import Any

CONTRIBUTION_TOP_N_PER_LEVEL = 1000


def build_contribution_request(
    *,
    portfolio_id: str,
    start_date: dt.date,
    end_date: dt.date,
    dimension_field: str,
    metric_basis: str,
    reporting_currency: str | None,
) -> dict[str, Any]:
    """Pin group evidence to the portfolio return series economics and window."""
    request: dict[str, Any] = {
        "portfolio_id": portfolio_id,
        "report_start_date": start_date.isoformat(),
        "report_end_date": end_date.isoformat(),
        "analyses": [{"period": "EXPLICIT", "frequencies": ["daily"]}],
        "hierarchy": [dimension_field],
        "input_mode": "stateful",
        "stateful_input": {
            "metric_basis": metric_basis,
            "dimensions": [dimension_field] if dimension_field in {"sector", "asset_class"} else [],
        },
        "emit": {
            "by_level": True,
            "threshold_weight": 0.0,
            "top_n_per_level": CONTRIBUTION_TOP_N_PER_LEVEL,
            "include_other": True,
            "include_unclassified": True,
        },
    }
    if reporting_currency:
        request["report_ccy"] = reporting_currency
        # Stateful Performance obtains reporting-currency valuations from Core.
        # BOTH emits local/FX components and requires caller-supplied rates for
        # mixed positions. Risk has neither rates nor authority to invent them.
        request["currency_mode"] = "BASE_ONLY"
    return request


__all__ = ["CONTRIBUTION_TOP_N_PER_LEVEL", "build_contribution_request"]
