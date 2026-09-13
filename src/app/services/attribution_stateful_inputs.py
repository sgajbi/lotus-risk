from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.contracts.attribution import (
    ExposurePoint,
    GroupingDimension,
    HistoricalAttributionStatefulInput,
    HistoricalAttributionStatelessInput,
)
from app.contracts.downstream_authority import DownstreamAuthority
from app.contracts.risk import ReturnPoint, RiskRequestScope
from app.services.attribution_active_benchmark_exposure import (
    BenchmarkExposureClientProtocol,
    fetch_active_benchmark_exposure_history,
)
from app.services.attribution_contribution_request import build_contribution_request
from app.services.attribution_exposure_history import (
    fetch_stateful_exposure_history,
)
from app.services.attribution_group_evidence import (
    EMPIRICAL_GROUPING_DIMENSION_FIELDS,
    GroupEvidencePack,
    LotusPerformanceContributionClientProtocol,
    parse_group_evidence,
)
from app.services.attribution_period_results import GroupEvidenceByPeriod, period_name
from app.services.attribution_stateful_returns import (
    LotusPerformanceReturnsClientProtocol,
    StatefulReturnsContext,
    build_stateful_returns_request,
    fetch_stateful_returns_context,
    requires_active_attribution,
)
from app.services.risk.period_resolution import resolve_period

__all__ = [
    "LotusCoreClientProtocol",
    "LotusPerformanceClientProtocol",
    "ResolvedStatefulAttributionInputs",
    "StatefulReturnsContext",
    "build_stateful_returns_request",
    "build_stateful_stateless_input",
    "resolve_stateful_attribution_inputs",
]


class LotusPerformanceClientProtocol(
    LotusPerformanceReturnsClientProtocol,
    BenchmarkExposureClientProtocol,
    LotusPerformanceContributionClientProtocol,
    Protocol,
):
    pass


class LotusCoreClientProtocol(Protocol):
    async def get_position_analytics_timeseries(
        self,
        *,
        portfolio_id: str,
        request_payload: dict[str, Any],
        authority: DownstreamAuthority,
    ) -> dict[str, Any]: ...

    # Instrument enrichment is a global reference read and stays tenant-free.
    async def get_instrument_enrichment(
        self,
        *,
        security_ids: list[str],
        correlation_id: str | None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ResolvedStatefulAttributionInputs:
    stateless_input: HistoricalAttributionStatelessInput
    returns_request: dict[str, Any]
    group_evidence: GroupEvidenceByPeriod | None = None
    contribution_requests: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ResolvedGroupEvidence:
    group_evidence: GroupEvidenceByPeriod
    contribution_requests: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _StatefulExposureHistories:
    exposure_history: list[ExposurePoint]
    benchmark_exposure_history: list[ExposurePoint]


def validate_stateful_groupings(grouping_dimensions: list[GroupingDimension]) -> None:
    if "CUSTOM" in grouping_dimensions:
        raise ValueError(
            "stateful historical-attribution does not support grouping_dimension=CUSTOM"
        )


def build_stateful_stateless_input(
    *,
    stateful: HistoricalAttributionStatefulInput,
    returns_context: StatefulReturnsContext,
    exposure_history: list[ExposurePoint],
    benchmark_exposure_history: list[ExposurePoint],
) -> HistoricalAttributionStatelessInput:
    return HistoricalAttributionStatelessInput(
        scope=RiskRequestScope(
            as_of_date=stateful.as_of_date,
            reporting_currency=stateful.reporting_currency,
            net_or_gross=stateful.net_or_gross,
        ),
        periods=stateful.periods,
        returns=returns_context.portfolio_returns,
        benchmark_returns=returns_context.benchmark_returns,
        exposure_history=exposure_history,
        benchmark_exposure_history=benchmark_exposure_history,
        attribution_options=stateful.attribution_options,
    )


async def _stateful_exposure_histories(
    *,
    stateful: HistoricalAttributionStatefulInput,
    core_client: LotusCoreClientProtocol,
    performance_client: LotusPerformanceClientProtocol,
    returns_context: StatefulReturnsContext,
    grouping_dimensions: list[GroupingDimension],
    requires_active: bool,
    authority: DownstreamAuthority,
) -> _StatefulExposureHistories:
    exposure_history = await fetch_stateful_exposure_history(
        stateful=stateful,
        core_client=core_client,
        start_date=returns_context.start_date,
        grouping_dimensions=grouping_dimensions,
        authority=authority,
    )
    benchmark_exposure_history = (
        await fetch_active_benchmark_exposure_history(
            stateful=stateful,
            performance_client=performance_client,
            benchmark_returns=returns_context.benchmark_returns,
            start_date=returns_context.start_date,
            grouping_dimensions=grouping_dimensions,
            authority=authority,
        )
        if requires_active
        else []
    )
    return _StatefulExposureHistories(
        exposure_history=exposure_history,
        benchmark_exposure_history=benchmark_exposure_history,
    )


def _evidence_grouping_dimensions(
    options_grouping_dimensions: list[GroupingDimension],
    attribution_types: list[str],
) -> list[GroupingDimension]:
    """Dimensions whose TOTAL_RISK sets can use producer group-return evidence.

    ISSUER has no producer-side dimension on the contribution surface and stays a
    weight-proxy decomposition (recorded residual on lotus-risk#291).
    """
    if "TOTAL_RISK" not in attribution_types:
        return []
    return [
        dimension
        for dimension in options_grouping_dimensions
        if dimension in EMPIRICAL_GROUPING_DIMENSION_FIELDS
    ]


async def fetch_group_evidence(
    *,
    stateful: HistoricalAttributionStatefulInput,
    performance_client: LotusPerformanceContributionClientProtocol,
    portfolio_returns: list[ReturnPoint],
    exposure_history: list[ExposurePoint],
    evidence_dimensions: list[GroupingDimension],
    authority: DownstreamAuthority,
) -> ResolvedGroupEvidence:
    """Fetch and validate per-group return evidence per resolved period and dimension.

    Period windows are resolved exactly as the engine resolves them (same
    ``resolve_period``, open date = first portfolio observation) so the evidence is
    validated against the same portfolio-date calendar the decomposition will use.
    Periods with fewer than two windowed observations produce no sets, so no evidence
    is fetched for them.
    """
    open_date = min(point.date for point in portfolio_returns)
    evidence: dict[str, dict[GroupingDimension, GroupEvidencePack]] = {}
    contribution_requests: list[dict[str, Any]] = []
    for period in stateful.periods:
        start_date, end_date = resolve_period(
            period.type,
            stateful.as_of_date,
            open_date,
            year=period.year,
            from_date=period.from_date,
            to_date=period.to_date,
        )
        windowed = [point for point in portfolio_returns if start_date <= point.date <= end_date]
        if len(windowed) < 2:
            continue
        per_dimension: dict[GroupingDimension, GroupEvidencePack] = {}
        for dimension in evidence_dimensions:
            dimension_field = EMPIRICAL_GROUPING_DIMENSION_FIELDS[dimension]
            expected_group_key_by_source_key = _expected_group_key_by_source_key(
                exposure_history=exposure_history,
                grouping_dimension=dimension,
                start_date=start_date,
                end_date=end_date,
            )
            request_payload = build_contribution_request(
                portfolio_id=stateful.portfolio_id,
                start_date=start_date,
                end_date=end_date,
                dimension_field=dimension_field,
                metric_basis=stateful.net_or_gross,
                reporting_currency=stateful.reporting_currency,
            )
            response = await performance_client.get_contribution(
                request_payload=request_payload,
                authority=authority,
            )
            contribution_requests.append(request_payload)
            per_dimension[dimension] = parse_group_evidence(
                response,
                grouping_dimension=dimension,
                dimension_field=dimension_field,
                expected_currency=stateful.reporting_currency,
                portfolio_returns=windowed,
                expected_group_key_by_source_key=expected_group_key_by_source_key,
            )
        evidence[period_name(period)] = per_dimension
    return ResolvedGroupEvidence(
        group_evidence=evidence,
        contribution_requests=tuple(contribution_requests),
    )


def _expected_group_key_by_source_key(
    *,
    exposure_history: list[ExposurePoint],
    grouping_dimension: GroupingDimension,
    start_date: date,
    end_date: date,
) -> dict[str, str]:
    """Use the Core-sourced exposure universe as the authoritative group set.

    The contribution endpoint uses the source dimension value (for example
    ``TECH``), while Risk contributor identities retain their canonical grouping
    keys (for example ``SECTOR_TECH``).  A group seen on any date in the
    resolved period is required; its per-date evidence is separately checked by
    the calendar rule.  This catches held zero-return and offsetting groups that
    reconciliation alone cannot reveal.
    """
    result: dict[str, str] = {}
    for point in exposure_history:
        if (
            point.grouping_dimension != grouping_dimension
            or point.date < start_date
            or point.date > end_date
        ):
            continue
        source_key = point.group_label or "UNKNOWN"
        existing = result.setdefault(source_key, point.group_key)
        if existing != point.group_key:
            raise ValueError(
                "lotus-core exposure history has ambiguous source group identity for "
                f"{grouping_dimension}:{source_key}"
            )
    return result


async def resolve_stateful_attribution_inputs(
    stateful: HistoricalAttributionStatefulInput,
    *,
    performance_client: LotusPerformanceClientProtocol,
    core_client: LotusCoreClientProtocol,
    authority: DownstreamAuthority,
) -> ResolvedStatefulAttributionInputs:
    options = stateful.attribution_options
    requested_groupings = options.grouping_dimensions
    validate_stateful_groupings(requested_groupings)

    requires_active = requires_active_attribution(stateful)
    returns_context = await fetch_stateful_returns_context(
        stateful=stateful,
        performance_client=performance_client,
        authority=authority,
    )
    exposure_histories = await _stateful_exposure_histories(
        stateful=stateful,
        core_client=core_client,
        performance_client=performance_client,
        returns_context=returns_context,
        grouping_dimensions=requested_groupings,
        requires_active=requires_active,
        authority=authority,
    )
    evidence_dimensions = _evidence_grouping_dimensions(
        requested_groupings, list(options.attribution_types)
    )
    resolved_group_evidence = (
        await fetch_group_evidence(
            stateful=stateful,
            performance_client=performance_client,
            portfolio_returns=returns_context.portfolio_returns,
            exposure_history=exposure_histories.exposure_history,
            evidence_dimensions=evidence_dimensions,
            authority=authority,
        )
        if evidence_dimensions
        else None
    )
    return ResolvedStatefulAttributionInputs(
        stateless_input=build_stateful_stateless_input(
            stateful=stateful,
            returns_context=returns_context,
            exposure_history=exposure_histories.exposure_history,
            benchmark_exposure_history=exposure_histories.benchmark_exposure_history,
        ),
        returns_request=returns_context.returns_request,
        group_evidence=(
            resolved_group_evidence.group_evidence if resolved_group_evidence else None
        ),
        contribution_requests=(
            resolved_group_evidence.contribution_requests if resolved_group_evidence else ()
        ),
    )
