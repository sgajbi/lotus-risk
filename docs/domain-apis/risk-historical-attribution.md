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
  - `TOTAL_RISK` stateful path is implemented
  - `ACTIVE_RISK` stateful path is implemented for `POSITION`, `SECTOR`, and `ASSET_CLASS` grouping dimensions through the lotus-performance benchmark exposure context derived view
  - `ACTIVE_RISK` + `ISSUER` remains gated until benchmark issuer exposure semantics are explicitly available and is rejected at request validation
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
  - any stateful request that needs benchmark-relative attribution semantics and includes `ISSUER`
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
5. benchmark issuer exposure semantics for stateful `ACTIVE_RISK` + `ISSUER`.

## Current Stateful Active-Risk Support Matrix

- supported:
  - `POSITION`
  - `SECTOR`
  - `ASSET_CLASS`
- gated:
  - `ISSUER`
- gate reason:
  - benchmark issuer exposure semantics unavailable from the lotus-performance benchmark exposure context

## Live Validation Note

- live platform characterization currently confirms:
  - lotus-risk stateful `TOTAL_RISK` works live for `SECTOR` after aligning exposure history to trading-day return observations
  - lotus-risk stateful `ACTIVE_RISK` works live for supported grouping dimensions `POSITION`, `SECTOR`, and `ASSET_CLASS`
  - lotus-performance benchmark exposure context works for supported stateful dimensions `POSITION`, `SECTOR`, and `ASSET_CLASS`
  - lotus-performance benchmark exposure context rejects `grouping_dimensions=["ISSUER"]`
  - lotus-risk rejects stateful `ACTIVE_RISK` + `ISSUER` at request validation with HTTP `422`
