from __future__ import annotations

from typing import Any

TOP_ISSUER_CURRENT_EXAMPLE: dict[str, Any] = {
    "issuer_id": "ULTIMATE_PIMCO",
    "issuer_name": "Pacific Investment Management Company LLC",
    "weight": 0.245075,
}

TOP_ISSUER_PROPOSED_EXAMPLE: dict[str, Any] = {
    "issuer_id": "ULTIMATE_PIMCO",
    "issuer_name": "Pacific Investment Management Company LLC",
    "weight": 0.244585,
}

TOP_POSITION_CURRENT_EXAMPLE: dict[str, Any] = {
    "security_id": "FO_FUND_PIMCO_INC",
    "security_name": "PIMCO GIS Income Fund",
    "weight": 0.23014,
}

TOP_POSITION_PROPOSED_EXAMPLE: dict[str, Any] = {
    "security_id": "FO_FUND_PIMCO_INC",
    "security_name": "PIMCO GIS Income Fund",
    "weight": 0.22968,
}

__all__ = [
    "TOP_ISSUER_CURRENT_EXAMPLE",
    "TOP_ISSUER_PROPOSED_EXAMPLE",
    "TOP_POSITION_CURRENT_EXAMPLE",
    "TOP_POSITION_PROPOSED_EXAMPLE",
]
