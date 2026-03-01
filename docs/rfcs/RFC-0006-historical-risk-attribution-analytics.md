# RFC-0006: Historical Risk Attribution Analytics (Industry-Grade, Historical-Only)

## Status

- Accepted (Slice A implemented, Slice B in progress)
- Owner: lotus-risk
- Date: 2026-03-01

## Context

lotus-risk now provides production-grade concentration, drawdown, and rolling risk analytics across stateless and stateful modes. The next highest-value capability for PB/WM is historical risk attribution that explains realized risk and active risk across time, sectors, instruments, and strategy lenses.

This RFC defines a quant-rigorous, audit-ready attribution framework and API contract, aligned with:

- lotus-platform bounded context ownership and service contracts
- RFC-0067 API vocabulary and OpenAPI governance
- institutional expectations for explainability, repeatability, and model risk control

## Design Principles

1. Explanation over black-box scores: every aggregate metric must reconcile to transparent contribution outputs.
2. Deterministic and auditable results: same inputs produce same outputs with explicit metadata and lineage.
3. Separation of responsibilities: lotus-risk computes attribution; upstream services provide canonical portfolio/reference data.
4. Contract-first evolution: explicit schema versioning, stable field semantics, and documented edge-case behavior.
5. Institutional controls: rounding, coverage flags, quality flags, and residual checks are first-class outputs.

## Objectives

1. Provide historical decomposition of realized risk and active risk over configurable periods.
2. Support at least two attribution lenses in v1:
   - component contribution attribution (position/issuer/sector/category dimensions)
   - active risk attribution (portfolio vs benchmark decomposition)
3. Expose period-level and rolling-window attribution outputs with reconciliation checks.
4. Support stateless first, then stateful integration without changing semantic outputs.

## Non-Goals

1. Forward-looking scenario attribution or predictive stress models.
2. Intraday attribution in v1.
3. Replacing portfolio construction logic owned by lotus-core.
4. Replacing performance attribution services outside risk attribution scope.

## Proposed Endpoint

- `POST /analytics/risk/historical-attribution`

### Execution Modes

- `stateless`: v1 Slice A (implemented)
- `stateful`: v1 Slice B (partially implemented)
- `simulation`: deferred

### Request Envelope (Canonical)

- `input_mode`: `stateless | stateful | simulation`
- `stateless_input` (required when stateless)
- `stateful_input` (required when stateful)
- `simulation_input` (reserved; deterministic not-implemented in v1)

## Methodology Scope (v1)

### A) Component Contribution Attribution

For each period and requested grouping dimension:

1. Compute ex-post realized risk metric target, starting with:
   - volatility contribution
   - tracking error contribution (if benchmark available)
2. Decompose total into additive component contributions using covariance-consistent methods:
   - marginal contribution to risk (MCR)
   - component contribution to risk (CCR)
   - percentage contribution to risk (PCR)
3. Ensure reconciliation constraints:
   - sum(CCR) approximately equals total risk metric
   - residual reported explicitly when numerical approximation exists

### B) Active Risk Attribution

For portfolio minus benchmark active return stream:

1. Decompose active risk into contributor sets by requested grouping.
2. Report active contribution terms with benchmark-relative interpretation.
3. Surface deterministic flags when benchmark alignment or coverage is insufficient.

## Quantitative Definitions (v1 Baseline)

Given weights `w`, covariance matrix `Sigma`, portfolio volatility `sigma_p = sqrt(w' * Sigma * w)`:

1. MCR_i = (Sigma * w)_i / sigma_p
2. CCR_i = w_i * MCR_i
3. PCR_i = CCR_i / sigma_p

For active risk, replace `w` with active weights and use active covariance assumptions over aligned series.

All formulas operate in decimal units internally. API values follow platform rounding policy.

## Data Requirements

### Stateless Inputs

1. Scope and period definitions.
2. Portfolio return series and position exposure history for requested grouping dimensions.
3. Optional benchmark return series and benchmark exposures for active attribution.
4. Grouping metadata fields aligned to canonical vocabulary (for example issuer_id, sector_code).

### Stateful Inputs

1. `portfolio_id`, `as_of_date`, period definitions, attribution options.
2. lotus-risk sources canonical return series via lotus-performance contracts.
3. lotus-risk sources canonical exposure snapshots and hierarchy enrichment directly from lotus-core contracts.

## Upstream Contracts Required

### lotus-performance (required)

1. Portfolio historical returns series.
2. Benchmark series for active attribution.
3. Data lineage metadata:
   - source references
   - alignment policy used
   - missing data handling markers

### lotus-core (required)

1. Canonical instrument and hierarchy mappings for grouping dimensions.
2. Portfolio state snapshots where needed for exposure history.

## Output Contract (Proposed)

- `source_service`
- `input_mode`
- `scope`
- `results[period_name]`
  - `start_date`
  - `end_date`
  - `attribution_sets[]`
    - `attribution_type` (`TOTAL_RISK` | `ACTIVE_RISK`)
    - `metric` (`VOLATILITY` | `TRACKING_ERROR`)
    - `grouping_dimension` (`POSITION` | `ISSUER` | `SECTOR` | ...)
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
  - `contract_version`
  - `methodology_version`
  - `covariance_method`
  - `annualization_basis`
  - `lineage_refs`

## Validation and Edge-Case Policy

1. Duplicate period names are rejected.
2. Missing required benchmark data when active attribution requested returns deterministic validation errors.
3. Near-zero total risk denominator behavior:
   - MCR/CCR computed where stable
   - PCR returns null where denominator unstable
   - quality flag emitted
4. Sparse groups with insufficient observations are retained with null values and explicit quality flags.
5. Reconciliation tolerance and residual threshold are output and documented.

## Testing Strategy

1. Contract tests:
   - mode gating
   - schema validation
   - deterministic errors
2. Characterization tests:
   - stable known datasets with fixed expected contributions
   - zero-variance and near-zero denominator cases
   - missing benchmark/exposure cases
3. Integration characterization tests:
   - lotus-performance adapter shape checks
   - alignment/missing-data policy propagation
4. E2E smoke tests:
   - endpoint availability and canonical response envelope

## Delivery Plan

### Slice A (stateless)

1. Define contracts and endpoint.
2. Implement contribution engine (volatility and tracking error attribution).
3. Add full contract + characterization tests.
4. Publish methodology and consumer docs.

### Slice B (stateful)

1. Add lotus-performance adapter.
2. Map upstream canonical payloads into stateless engine input.
3. Add integration characterization and e2e stateful tests.

### Slice C (simulation deferral)

1. Keep simulation mode explicit but not implemented until simulation-history contract is finalized.

## Governance and Vocabulary

1. All fields must be canonical snake_case and RFC-0067 compliant.
2. Every request/response attribute requires description and realistic example.
3. Vocabulary inventory regeneration and validation are mandatory for every schema change.
4. No legacy aliases permitted in new attribution contract.

## Implementation Progress and Pending Work

### Implemented in lotus-risk

1. Stateful adapter for `POST /analytics/risk/historical-attribution` is implemented for:
   - `TOTAL_RISK`
   - `VOLATILITY`
   - grouping dimensions: `POSITION`, `SECTOR`, `ASSET_CLASS`, `ISSUER`
2. Stateful adapter now sources:
   - returns from lotus-performance (`/integration/returns/series`)
   - position timeseries from lotus-core (`/integration/portfolios/{portfolio_id}/analytics/position-timeseries`)
   - issuer enrichment from lotus-core (`/integration/instruments/enrichment-bulk`) when required.
3. Deterministic guardrails are implemented for unsupported stateful combinations in current slice.

### Pending work in lotus-risk

1. Enable stateful `ACTIVE_RISK` and `TRACKING_ERROR` attribution after benchmark exposure-history contract is live.
2. Add full benchmark-exposure mapping path in the stateful adapter.
3. Add stateful e2e test coverage for active-risk path once upstream contract is available.
4. Expand methodology documentation with final active-risk stateful behavior and quality flags.

### Pending upstream dependencies

1. lotus-core:
   - benchmark exposure-history contract with pagination and canonical dimensions.
2. lotus-performance:
   - production-hardened benchmark return-series diagnostics and alignment metadata for attribution use.

## Open Decisions

1. Default covariance estimator in v1:
   - sample covariance vs EWMA option exposure.
2. Initial grouping dimension set for v1:
   - position, issuer, sector, asset_class.
3. Residual tolerance default policy for reconciliation checks.
4. Whether v1 includes rolling attribution windows or period-only output.

## Acceptance Criteria

1. Methodology and formulas are model-review ready and unambiguous.
2. Stateless and stateful contracts are defined with clear upstream responsibilities.
3. Reconciliation outputs and quality flags are mandatory and tested.
4. CI and governance gates pass:
   - lint, typing, tests, pyramid, coverage, openapi quality, no-alias, vocabulary validation.
