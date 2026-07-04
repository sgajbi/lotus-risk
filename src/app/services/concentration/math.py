from __future__ import annotations

from app.services.concentration.datamodels import (
    IssuerEntry,
    PositionEntry,
    TopIssuerDriverValue,
    TopPositionDriverValue,
)

_ROUND_PRECISION = 6


def _round(value: float) -> float:  # monetary-float-allow: concentration ratio, not money.
    return round(value, _ROUND_PRECISION)


def _compute_hhi(values: list[float]) -> float:
    total = sum(abs(v) for v in values)
    if total <= 0:
        return 0.0
    weights = [abs(v) / total for v in values]
    return sum(w * w for w in weights) * 10000.0


def _single_position_metrics(values: list[float], *, top_n: int) -> tuple[float, float]:
    total = sum(abs(v) for v in values)
    if total <= 0:
        return 0.0, 0.0
    weights = sorted((abs(v) / total for v in values), reverse=True)
    top_weight = weights[0]
    top_n_weight = sum(weights[:top_n])
    return top_weight, top_n_weight


def _top_position_driver(entries: list[PositionEntry]) -> TopPositionDriverValue:
    total = sum(abs(entry.value) for entry in entries)
    if total <= 0 or not entries:
        return TopPositionDriverValue(security_id=None, security_name=None, weight=0.0)
    top_entry = max(entries, key=lambda entry: (abs(entry.value), entry.security_id or ""))
    return TopPositionDriverValue(
        security_id=top_entry.security_id,
        security_name=top_entry.security_name,
        weight=_round(abs(top_entry.value) / total),
    )


def _top_issuer_driver(entries: list[IssuerEntry]) -> TopIssuerDriverValue:
    total = sum(abs(entry.value) for entry in entries)
    if total <= 0 or not entries:
        return TopIssuerDriverValue(issuer_id=None, issuer_name=None, weight=0.0)
    top_entry = max(entries, key=lambda entry: (abs(entry.value), entry.issuer_id or ""))
    return TopIssuerDriverValue(
        issuer_id=top_entry.issuer_id,
        issuer_name=top_entry.issuer_name,
        weight=_round(abs(top_entry.value) / total),
    )


def _coverage_ratio(covered: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return _round(covered / total)


def _uncovered_count(covered: int, total: int) -> int:
    return max(total - covered, 0)
