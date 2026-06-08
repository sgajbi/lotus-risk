from __future__ import annotations

from typing import SupportsFloat


def as_number(number: SupportsFloat) -> float:
    return float(number)


__all__ = ["as_number"]
