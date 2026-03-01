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

- Status: planned (not implemented)
- Caller provides identifiers and options; lotus-risk sources canonical inputs via lotus-performance.

### Simulation

- Status: deferred (not implemented)
- Explicitly rejected in v1 until simulation-history contracts are finalized.

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

## Upstream Dependencies (Stateful)

- lotus-performance:
  - portfolio returns series
  - benchmark series
  - exposure snapshots by date and grouping dimensions
  - lineage/alignment metadata

- lotus-core:
  - indirect via lotus-performance `core_api_ref` for canonical instrument and hierarchy mapping.

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
  - methodology, covariance, annualization, lineage references

## Governance Alignment

- Bounded context: aligned (`lotus-risk` computes attribution; no portfolio construction ownership shift).
- Vocabulary: RFC-0067 canonical naming only.
- Explainability: reconciliation and residual controls are required outputs.
- Testing: contract + characterization + integration characterization + e2e smoke.

## Key Decisions Pending

1. Default covariance estimator and optional EWMA support.
2. v1 grouping dimension set.
3. residual tolerance policy.
4. rolling-window attribution inclusion in v1 or v2.
