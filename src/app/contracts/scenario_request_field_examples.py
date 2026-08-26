from __future__ import annotations

from typing import Any

SCENARIO_EXPOSURES_EXAMPLE: Any = [
    {"bucket": "EQUITY", "weight": 0.55},
    {"bucket": "FIXED_INCOME", "weight": 0.35},
    {"bucket": "CASH", "weight": 0.10},
]

SCENARIO_EXPOSURE_COMPONENTS_EXAMPLE: Any = [
    {
        "security_id": "FO_EQ_AAPL_US",
        "display_name": "Apple Inc.",
        "bucket": "EQUITY",
        "weight": 0.18,
    },
    {
        "security_id": "FO_BOND_UST_2030",
        "display_name": "United States Treasury 3.875% 2030",
        "bucket": "FIXED_INCOME",
        "weight": 0.35,
    },
]

__all__ = [
    "SCENARIO_EXPOSURES_EXAMPLE",
    "SCENARIO_EXPOSURE_COMPONENTS_EXAMPLE",
]
