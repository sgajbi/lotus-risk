from __future__ import annotations

import os


def env_float_with_default(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)  # monetary-float-allow: timeout/keepalive seconds, not money.
    except ValueError:
        return default
    return value if value > 0 else default


def env_int_with_default(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


__all__ = ["env_float_with_default", "env_int_with_default"]
