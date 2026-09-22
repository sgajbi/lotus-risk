# Historical Risk Attribution API Assessment (RFC-0006)

## Endpoint

- `POST /analytics/risk/historical-attribution`

## Purpose

Provide decomposition of historical realized risk and active risk into transparent contributor-level outputs for PB/WM risk explainability.

## Execution Modes

### Stateless (Slice A)

- Status: implemented
- Caller provides return/exposure/grouping inputs directly.

### Stateful (Slice B)

- Status: implemented for approved v1 stateful scope
- Current behavior:
  - caller supplies the admitted tenant in the `X-Tenant-Id` header: a stateful request without a
    non-blank value refuses `401 MISSING_TENANT_AUTHORITY` before any upstream call, and a trimmed
    value over 128 characters refuses `400 INVALID_TENANT_AUTHORITY`; the admitted value is
    forwarded on the returns-series submit and polls, the contribution group-evidence submit and
    polls, benchmark exposure context, and lotus-core position-timeseries reads (instrument
    enrichment stays a tenant-free reference read)
  - `TOTAL_RISK` + `VOLATILITY` stateful path is implemented; only `SECTOR` and `ASSET_CLASS`
    groupings request per-group return evidence from the lotus-performance
    contribution surface (`/performance/contribution`, one `EXPLICIT`-window call per resolved
    period and dimension, same NET/GROSS basis and reporting currency as the returns series).
    Risk uses the source-owned Core reporting-currency valuations with `currency_mode="BASE_ONLY"`;
    it never supplies or invents FX rates. When every Core-expected group has validated evidence
    covering every portfolio return date in the window, the
    set decomposes the genuine group returns and reports
    `risk_basis="empirical_group_returns"`; otherwise the set keeps the weight-proxy
    decomposition with `risk_basis="weight_proxy"` and a bounded
    `group_return_evidence:*` quality flag naming why (producer `UNAVAILABLE`, truncated
    hierarchy, Core group-universe incompleteness, calendar gap, reconciliation breach, or missing period). A date absent from a
    group's evidence on a BUSINESS portfolio-return date is unknown coverage, never zero:
    no calculation date is zero-filled or dropped, and an explicit zero-weight observation is
    the only authoritative zero-exposure evidence. Performance's daily contribution output may
    additionally contain calendar-weekend observations inside the resolved contribution-request
    period, including its leading or trailing weekend outside the first/last BUSINESS return.
    Risk validates those observations (including duplicate and non-finite refusals) but
    does not feed them into business-date covariance. It does not infer a bank-holiday calendar:
    an unlisted weekday or an observation outside the resolved window remains invalid.
    Core remains the authoritative universe: its missing/null `sector` or `asset_class` is the
    canonical `UNKNOWN` group, while Performance's documented
    `emit.include_unclassified=true` output uses `Unclassified` for that same missing source field.
    Risk accepts that producer spelling only as an alias for a Core `UNKNOWN` identity; a literal
    Core `Unclassified` category alongside `UNKNOWN` is ambiguous and a foreign producer category
    is refused as `UPSTREAM_INVALID_RESPONSE`, never relabeled, invented, or dropped. Malformed
    evidence (non-finite values, duplicate dates, duplicate groups, unlisted weekdays, out-of-window
    observations, currency contradictions, malformed containers, or unsupported return/weight
    bases) refuses as `UPSTREAM_INVALID_RESPONSE` rather than silently falling back. `POSITION`
    and `ISSUER` `TOTAL_RISK` stay weight-proxy because their contribution identities cannot be
    safely joined to the Core grouping universe (recorded residual on lotus-risk#291). Unsupported
    `TOTAL_RISK` metrics do not request contribution evidence; `ACTIVE_RISK` remains a weight proxy
    because portfolio-only group returns cannot supply benchmark-group economics.
  - `ACTIVE_RISK` stateful path is implemented for `POSITION`, `SECTOR`, `ASSET_CLASS`, and `ISSUER` grouping dimensions through the lotus-performance benchmark exposure context derived view
  - `ACTIVE_RISK` + `ISSUER` consumes lotus-performance benchmark exposure context issuer rows sourced from lotus-core index-catalog issuer labels
  - `CUSTOM` grouping remains unsupported in stateful mode and is rejected at request validation

### Simulation

- Status: intentionally unsupported in the current production contract
- Reason:
  - historical attribution depends on realized return and exposure history
  - projected holdings snapshots do not by themselves create a valid historical attribution series

## Required Inputs

1. Common:
- `scope.as_of_date`
- `periods[]`
- attribution options (metric, grouping dimensions, covariance method)

2. Stateless:
- portfolio returns
- exposure history by grouping dimensions
- benchmark returns/exposures when active attribution is requested

3. Stateful:
- `portfolio_id`
- `as_of_date`
- optional `client_id`
- optional `reporting_currency`
- attribution options

### Stateful Validation Gates

- request validation rejects these combinations before any upstream call:
  - `grouping_dimensions=["CUSTOM"]`
- request validation currently returns:
  - HTTP `422`
  - `error.code = INVALID_REQUEST`
  - field-level reason in `error.details[]`

## Upstream Dependencies (Stateful)

- lotus-performance:
  - portfolio returns series
  - benchmark series
  - lineage/alignment metadata for return series
  - benchmark exposure context used to align benchmark returns and benchmark exposure weights

- lotus-core:
  - canonical exposure snapshots by date/grouping dimension (system of record)
  - canonical instrument and hierarchy mapping for grouping dimensions (issuer/sector/asset class)
  - benchmark composition, assignment, and classification data as the authoritative source behind lotus-performance's derived benchmark exposure context

### Differing base and reporting currencies

Risk continues to refuse contribution evidence whose declared `group_return.currency` differs from
the returns-series reporting currency. Performance corrected its stateful `BASE_ONLY` producer
labeling under [lotus-performance#527](https://github.com/sgajbi/lotus-performance/issues/527),
merged to main `f597e4d116e69675ec24baa9ba3c938479d24834` with controlled HTTP producer proof.
Risk will not relabel evidence or manufacture FX. That producer delivery is not a joint Risk
consumer acceptance receipt for the differing-currency path; a source-pinned Risk consumer run
with a same-currency control is still required before claiming that acceptance.

## Expected Output Structure

- `source_service`
- `input_mode`
- `scope`
- `results[period_name]`
  - `start_date`
  - `end_date`
  - `attribution_sets[]`
    - `attribution_type`
    - `metric`
    - `grouping_dimension`
    - `total_value`
    - `reconciled_sum`
    - `residual`
    - `contributors[]`
      - `group_key`
      - `group_label`
      - `weight_average`
      - `marginal_contribution`
      - `component_contribution`
      - `percent_contribution`
    - `quality_flags[]`
  - `error`
- `metadata`
  - methodology, covariance, annualization, and requested execution scope
  - `metric_unit_semantics` - REQUIRED unit statement covering exactly the
    requested metrics (key set equals `requested_metrics`, model-enforced)
    (`VOLATILITY` and `TRACKING_ERROR` are `decimal_ratio`: decimal fractions
    of one, so `0.1253` means 12.53%). Governs `total_value`,
    `reconciled_sum`, `residual`, and marginal/component contributions;
    `weight_average` and `percent_contribution` are always decimal fractions
    of one by field contract. Annualization is stated separately by
    `annualization_basis` and does not change how a value is read.
  - `requested_attribution_types`
  - `requested_metrics`
  - `requested_grouping_dimensions`
  - `min_observations_policy`
  - stateful active-risk support contract:
    - `stateful_active_risk_supported_grouping_dimensions`
    - `stateful_active_risk_gated_grouping_dimensions`
    - `stateful_active_risk_gate_reason`

OpenAPI now includes a canonical supported stateful `ACTIVE_RISK` + `SECTOR` example so
clients can see the intended decomposition shape, reconciliation fields, and support metadata
without reverse-engineering runtime responses.

For active-risk attribution, `total_value` is the annualized active-return tracking error.
Contributor rows are covariance-based explainability components. `reconciled_sum` and `residual`
must be shown together because live portfolios can have a material residual when the selected
grouping does not fully explain active-risk dynamics.

## Governance Alignment

- Bounded context: aligned (`lotus-risk` computes attribution; no portfolio construction ownership shift).
- Vocabulary: RFC-0067 canonical naming only.
- Explainability: reconciliation and residual controls are required outputs.
- Testing: contract + characterization + integration characterization + e2e smoke.

## Downstream Consumers

- `lotus-gateway` workbench risk attribution surface consumes this endpoint for front-office
  attribution detail.
- Gateway consumers must preserve:
  - `reconciled_sum`
  - `residual`
  - `quality_flags`
  - the stateful active-risk support metadata in `metadata`
- The `metadata.stateful_active_risk_supported_grouping_dimensions`,
  `metadata.stateful_active_risk_gated_grouping_dimensions`, and
  `metadata.stateful_active_risk_gate_reason` fields are the authoritative support contract.
  Downstream applications should not maintain a divergent local support matrix for active-risk
  grouping dimensions.

## Key Decisions Pending

1. Default covariance estimator and optional EWMA support.
2. v1 grouping dimension set.
3. residual tolerance policy.
4. rolling-window attribution inclusion in v1 or v2.
5. broader live portfolio-archetype validation for issuer active-risk beyond the canonical baseline.

## Current Stateful Active-Risk Support Matrix

- supported:
  - `POSITION`
  - `SECTOR`
  - `ASSET_CLASS`
  - `ISSUER`
- gated: none
- gate reason: `none`

## Live Validation Note

- live platform characterization currently confirms:
  - lotus-risk stateful `TOTAL_RISK` works live for `SECTOR` after aligning exposure history to trading-day return observations
  - lotus-risk stateful `ACTIVE_RISK` works for supported grouping dimensions `POSITION`, `SECTOR`, `ASSET_CLASS`, and `ISSUER`
  - lotus-performance benchmark exposure context works for supported stateful dimensions `POSITION`, `SECTOR`, `ASSET_CLASS`, and `ISSUER`
  - lotus-risk rejects only `CUSTOM` stateful grouping at request validation
