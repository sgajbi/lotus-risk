"""Validated per-group return evidence for empirical TOTAL_RISK attribution (#291).

The producer contract is lotus-performance's contribution surface (delivered under
lotus-performance#514): each hierarchy row carries ``group_return`` evidence with a
per-date series of genuine source-valuation group returns beside the beginning-capital
weight that formed them, in percent, under one declared currency — never inferred from
contribution divided by weight.

Boundary rules, recorded on lotus-risk#291:

- Malformed producer evidence (non-finite values, duplicate dates, duplicate group keys,
  observations outside the analysed window, undeclared shapes) is a dependency contract
  failure -> ``UPSTREAM_INVALID_RESPONSE``, never a silent fallback to the weight proxy.
- Declared absence keeps the affected set on the weight proxy, degraded with a bounded
  flag: producer ``UNAVAILABLE`` status, truncated hierarchies (an ``Other`` rollup row),
  and calendar gaps.
- A portfolio return date absent from a group's series is UNKNOWN, never zero: ``READY``
  validates the supplied observations, not calendar completeness, and per-date
  reconciliation passing is not completeness proof. The only authoritative zero-exposure
  evidence is an explicit supplied observation with zero weight.
- Per date with full coverage, ``sum(w_g * r_g)`` must reconcile to the portfolio return
  within ``RECONCILIATION_TOLERANCE_PP``; a breach degrades the set (conflicting
  sources), it is not a caller error.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.attribution import GroupingDimension
from app.contracts.downstream_authority import DownstreamAuthority
from app.contracts.risk import ReturnPoint
from app.integrations.upstream_operations import LOTUS_PERFORMANCE_CONTRIBUTION_OPERATION
from app.upstream_errors import invalid_upstream_payload


class LotusPerformanceContributionClientProtocol(Protocol):
    async def get_contribution(
        self,
        *,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...


#: Grouping dimensions with a producer-side per-group return series. ISSUER has no
#: producer dimension on the contribution surface (recorded residual on #291), and
#: CUSTOM is rejected for stateful attribution before this module is reached.
EMPIRICAL_GROUPING_DIMENSION_FIELDS: Mapping[GroupingDimension, str] = {
    "SECTOR": "sector",
    "ASSET_CLASS": "asset_class",
    "POSITION": "position_id",
}

#: One basis point in percentage-point units: per-date reconciliation bound between the
#: producer's group evidence and the portfolio return series it must decompose.
RECONCILIATION_TOLERANCE_PP = 0.01

#: Emission bounds: no threshold suppression, and a group count beyond this bound is a
#: truncated hierarchy (an ``Other`` rollup row), which keeps the set degraded.
CONTRIBUTION_TOP_N_PER_LEVEL = 1000

FLAG_TRUNCATED = "group_return_evidence:truncated"
FLAG_PERIOD_MISSING = "group_return_evidence:period_missing"
FLAG_RECONCILIATION_BREACH = "group_return_evidence:reconciliation_breach"


def _flag_unavailable() -> str:
    """Return a consumer-owned, bounded public posture for declared source absence.

    Group keys and producer reasons can be arbitrary source data. They remain useful in the
    producer's own diagnostics but must not become an unbounded Risk API vocabulary.
    """
    return "group_return_evidence:unavailable"


def _flag_calendar_incomplete() -> str:
    return "group_return_evidence:calendar_incomplete"


@dataclass(frozen=True)
class GroupReturnObservation:
    observation_date: dt.date
    return_pp: float
    weight_ratio: float


@dataclass(frozen=True)
class GroupReturnSeries:
    group_key: str
    currency: str
    observations: tuple[GroupReturnObservation, ...]


@dataclass(frozen=True)
class GroupEvidencePack:
    """Validated evidence for one grouping dimension over one resolved period window."""

    grouping_dimension: GroupingDimension
    series_by_group: Mapping[str, GroupReturnSeries]
    degradation_flags: tuple[str, ...]

    @property
    def empirical(self) -> bool:
        return not self.degradation_flags and bool(self.series_by_group)


def build_contribution_request(
    *,
    portfolio_id: str,
    start_date: dt.date,
    end_date: dt.date,
    dimension_field: str,
    metric_basis: str,
    reporting_currency: str | None,
) -> dict[str, Any]:
    """Contribution request for one grouping dimension over one explicit period window.

    The basis and currency are pinned to the same values as the portfolio returns-series
    request so the group evidence is decomposable against that series.
    """
    request: dict[str, Any] = {
        "portfolio_id": portfolio_id,
        "report_start_date": start_date.isoformat(),
        "report_end_date": end_date.isoformat(),
        "analyses": [{"period": "EXPLICIT", "frequencies": ["daily"]}],
        "hierarchy": [dimension_field],
        "input_mode": "stateful",
        "stateful_input": {
            "metric_basis": metric_basis,
            "dimensions": (
                [dimension_field] if dimension_field in {"sector", "asset_class"} else []
            ),
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
        request["currency_mode"] = "BOTH"
    return request


def _malformed(message: str) -> Exception:
    return invalid_upstream_payload(
        service="lotus-performance",
        operation=LOTUS_PERFORMANCE_CONTRIBUTION_OPERATION,
        message=f"lotus-performance contribution group evidence: {message}",
    )


def _finite(raw: Any, *, field: str, group_key: str) -> float:
    try:
        number = float(raw)
    except (TypeError, ValueError):
        raise _malformed(f"non-numeric {field} for group {group_key!r}") from None
    if not math.isfinite(number):
        raise _malformed(f"non-finite {field} for group {group_key!r}")
    return number


def _parse_observation_date(value: Any, *, group_key: str) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            pass
    raise _malformed(f"invalid observation date for group {group_key!r}: {value!r}")


def _extract_period_rows(
    response: Mapping[str, Any],
    *,
    dimension_field: str,
) -> list[Mapping[str, Any]] | None:
    results = response.get("results_by_period")
    if not isinstance(results, Mapping):
        return None
    period = results.get("EXPLICIT")
    if not isinstance(period, Mapping):
        return None
    levels = period.get("levels")
    if not isinstance(levels, list):
        return None
    for level in levels:
        if isinstance(level, Mapping) and level.get("name") == dimension_field:
            rows = level.get("rows")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, Mapping)]
            return None
    return None


def _group_key_from_row(row: Mapping[str, Any], *, dimension_field: str) -> str:
    key = row.get("key")
    if not isinstance(key, Mapping):
        raise _malformed("hierarchy row without a key mapping")
    value = key.get(dimension_field)
    if value is None or not str(value).strip():
        raise _malformed(f"hierarchy row without a {dimension_field!r} key value")
    return str(value)


def _validated_series_currency(
    row_evidence: Mapping[str, Any],
    *,
    group_key: str,
    expected_currency: str | None,
) -> str:
    currency = row_evidence.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        raise _malformed(f"READY evidence without a currency for group {group_key!r}")
    if expected_currency is not None and currency != expected_currency:
        raise _malformed(
            f"READY evidence for group {group_key!r} is in {currency}, "
            f"requested {expected_currency}"
        )
    return currency


def _parse_observation(
    raw_point: Any,
    *,
    group_key: str,
    window_dates: frozenset[dt.date],
    seen_dates: set[dt.date],
) -> GroupReturnObservation:
    if not isinstance(raw_point, Mapping):
        raise _malformed(f"non-mapping series point for group {group_key!r}")
    observation_date = _parse_observation_date(raw_point.get("date"), group_key=group_key)
    if observation_date in seen_dates:
        raise _malformed(
            f"duplicate observation date {observation_date.isoformat()} for group {group_key!r}"
        )
    if observation_date not in window_dates:
        raise _malformed(
            f"observation outside the analysed window for group {group_key!r}: "
            f"{observation_date.isoformat()}"
        )
    return GroupReturnObservation(
        observation_date=observation_date,
        return_pp=_finite(raw_point.get("return_pct"), field="return_pct", group_key=group_key),
        weight_ratio=_finite(
            raw_point.get("portfolio_weight_pct"),
            field="portfolio_weight_pct",
            group_key=group_key,
        )
        / 100.0,
    )


def _parse_ready_series(
    row_evidence: Mapping[str, Any],
    *,
    group_key: str,
    expected_currency: str | None,
    window_dates: frozenset[dt.date],
) -> GroupReturnSeries:
    currency = _validated_series_currency(
        row_evidence, group_key=group_key, expected_currency=expected_currency
    )
    raw_series = row_evidence.get("series")
    if not isinstance(raw_series, list) or not raw_series:
        raise _malformed(f"READY evidence without a series for group {group_key!r}")

    observations: dict[dt.date, GroupReturnObservation] = {}
    for raw_point in raw_series:
        observation = _parse_observation(
            raw_point,
            group_key=group_key,
            window_dates=window_dates,
            seen_dates=set(observations),
        )
        observations[observation.observation_date] = observation

    ordered = tuple(observations[key] for key in sorted(observations))
    return GroupReturnSeries(group_key=group_key, currency=currency, observations=ordered)


def _calendar_flags(
    series_by_group: Mapping[str, GroupReturnSeries],
    *,
    portfolio_dates: Sequence[dt.date],
) -> list[str]:
    flags: list[str] = []
    for group_key in sorted(series_by_group):
        observed = {point.observation_date for point in series_by_group[group_key].observations}
        if any(date not in observed for date in portfolio_dates):
            flags.append(_flag_calendar_incomplete())
    return flags


def _reconciliation_flags(
    series_by_group: Mapping[str, GroupReturnSeries],
    *,
    portfolio_returns: Sequence[ReturnPoint],
) -> list[str]:
    """Reconcile fully-covered evidence per date; callers invoke this only when every
    portfolio date has an observation in every group (the calendar check ran first)."""
    observations_by_group = {
        group_key: {point.observation_date: point for point in series.observations}
        for group_key, series in series_by_group.items()
    }
    for point in portfolio_returns:
        decomposed = sum(
            per_date[point.date].weight_ratio * per_date[point.date].return_pp
            for per_date in observations_by_group.values()
        )
        if abs(decomposed - point.value) > RECONCILIATION_TOLERANCE_PP:
            return [FLAG_RECONCILIATION_BREACH]
    return []


def parse_group_evidence(
    response: Mapping[str, Any],
    *,
    grouping_dimension: GroupingDimension,
    dimension_field: str,
    expected_currency: str | None,
    portfolio_returns: Sequence[ReturnPoint],
) -> GroupEvidencePack:
    """Validate one contribution response into evidence for one grouping dimension.

    ``portfolio_returns`` is the period-window slice of the portfolio return series (in
    percentage points) that the evidence must be able to decompose.
    """
    rows = _extract_period_rows(response, dimension_field=dimension_field)
    if rows is None:
        return GroupEvidencePack(
            grouping_dimension=grouping_dimension,
            series_by_group={},
            degradation_flags=(FLAG_PERIOD_MISSING,),
        )

    window_dates = frozenset(point.date for point in portfolio_returns)
    series_by_group, flags = _collect_row_evidence(
        rows,
        dimension_field=dimension_field,
        expected_currency=expected_currency,
        window_dates=window_dates,
    )

    if not series_by_group and not flags:
        flags.append(FLAG_PERIOD_MISSING)

    currencies = {series.currency for series in series_by_group.values()}
    if len(currencies) > 1:
        # One response is computed under one currency policy; mixed declared currencies
        # across groups is producer corruption, not a declared limitation.
        raise _malformed(f"mixed group evidence currencies {sorted(currencies)!r}")

    flags.extend(_calendar_flags(series_by_group, portfolio_dates=sorted(window_dates)))
    if not flags:
        flags.extend(_reconciliation_flags(series_by_group, portfolio_returns=portfolio_returns))

    return GroupEvidencePack(
        grouping_dimension=grouping_dimension,
        series_by_group=series_by_group,
        degradation_flags=tuple(dict.fromkeys(flags)),
    )


def _collect_row_evidence(
    rows: list[Mapping[str, Any]],
    *,
    dimension_field: str,
    expected_currency: str | None,
    window_dates: frozenset[dt.date],
) -> tuple[dict[str, GroupReturnSeries], list[str]]:
    flags: list[str] = []
    series_by_group: dict[str, GroupReturnSeries] = {}
    seen_group_keys: set[str] = set()
    for row in rows:
        if row.get("is_other"):
            flags.append(FLAG_TRUNCATED)
            continue
        group_key = _group_key_from_row(row, dimension_field=dimension_field)
        if group_key in seen_group_keys:
            raise _malformed(f"duplicate hierarchy rows for group {group_key!r}")
        seen_group_keys.add(group_key)
        row_evidence = row.get("group_return")
        if not isinstance(row_evidence, Mapping):
            raise _malformed(f"hierarchy row without group_return evidence for {group_key!r}")
        status = row_evidence.get("status")
        if status == "UNAVAILABLE":
            flags.append(_flag_unavailable())
            continue
        if status != "READY":
            raise _malformed(f"unknown group_return status {status!r} for group {group_key!r}")
        series_by_group[group_key] = _parse_ready_series(
            row_evidence,
            group_key=group_key,
            expected_currency=expected_currency,
            window_dates=window_dates,
        )
    return series_by_group, flags


__all__ = [
    "CONTRIBUTION_TOP_N_PER_LEVEL",
    "EMPIRICAL_GROUPING_DIMENSION_FIELDS",
    "FLAG_PERIOD_MISSING",
    "FLAG_RECONCILIATION_BREACH",
    "FLAG_TRUNCATED",
    "RECONCILIATION_TOLERANCE_PP",
    "GroupEvidencePack",
    "GroupReturnObservation",
    "GroupReturnSeries",
    "LotusPerformanceContributionClientProtocol",
    "build_contribution_request",
    "parse_group_evidence",
]
