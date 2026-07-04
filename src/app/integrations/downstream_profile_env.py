from __future__ import annotations

import math
import os
from collections.abc import Iterable

DOWNSTREAM_RUNTIME_FLOAT_SETTINGS = (
    "LOTUS_CORE_TIMEOUT_SECONDS",
    "LOTUS_CORE_KEEPALIVE_EXPIRY_SECONDS",
    "LOTUS_PERFORMANCE_TIMEOUT_SECONDS",
    "LOTUS_PERFORMANCE_KEEPALIVE_EXPIRY_SECONDS",
    "LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS",
)
DOWNSTREAM_RUNTIME_INT_SETTINGS = (
    "LOTUS_CORE_MAX_CONNECTIONS",
    "LOTUS_CORE_MAX_KEEPALIVE_CONNECTIONS",
    "LOTUS_PERFORMANCE_MAX_CONNECTIONS",
    "LOTUS_PERFORMANCE_MAX_KEEPALIVE_CONNECTIONS",
    "LOTUS_PERFORMANCE_ASYNC_MAX_POLLS",
)


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


def invalid_downstream_runtime_setting_issues(
    *,
    float_settings: Iterable[str] = DOWNSTREAM_RUNTIME_FLOAT_SETTINGS,
    int_settings: Iterable[str] = DOWNSTREAM_RUNTIME_INT_SETTINGS,
) -> list[str]:
    issues: list[str] = []
    for name in float_settings:
        if _has_invalid_positive_float_override(name):
            issues.append(f"invalid_downstream_runtime_setting:{name}")
    for name in int_settings:
        if _has_invalid_positive_int_override(name):
            issues.append(f"invalid_downstream_runtime_setting:{name}")
    return issues


def _has_invalid_positive_float_override(name: str) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return False
    try:
        value = float(raw_value)  # monetary-float-allow: timeout/keepalive seconds, not money.
    except ValueError:
        return True
    return not math.isfinite(value) or value <= 0


def _has_invalid_positive_int_override(name: str) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return False
    try:
        value = int(raw_value)
    except ValueError:
        return True
    return value <= 0


__all__ = [
    "DOWNSTREAM_RUNTIME_FLOAT_SETTINGS",
    "DOWNSTREAM_RUNTIME_INT_SETTINGS",
    "env_float_with_default",
    "env_int_with_default",
    "invalid_downstream_runtime_setting_issues",
]
