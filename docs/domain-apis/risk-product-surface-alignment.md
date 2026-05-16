# Risk Product-Surface Alignment Contract

## Purpose

This document defines the `lotus-risk` contract that downstream product surfaces must preserve when
they expose risk analytics through `lotus-gateway`, Workbench panels, advisor workflows, reporting,
or AI-assisted summaries.

The goal is analytical truth: downstream consumers may reformat values, but they must not change
risk meaning, hide material reconciliation fields, or offer unsupported modes and dimensions.

## Applies To

- `lotus-gateway` risk API aggregation
- Workbench portfolio risk panels
- advisor and reporting surfaces that call `lotus-risk`
- AI tools that summarize risk responses

## Source Of Truth

- `GET /integration/capabilities`
- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/risk-calculate.md`
- `docs/domain-apis/risk-historical-attribution.md`
- `docs/domain-apis/risk-concentration.md`
- `docs/domain-apis/risk-audit-lineage.md`

## Required Downstream Behavior

### 1. Preserve Signed VaR Semantics

`lotus-risk` reports VaR and expected shortfall as signed return-threshold values in percentage
points. A negative value is an adverse threshold. A positive value can occur when the empirical
return sample is strongly positive.

Downstream surfaces must:

- label VaR as a signed return threshold or equivalent wording,
- avoid presenting the value as an always-positive loss amount,
- make any positive-loss conversion explicit if a consumer intentionally chooses that convention,
- preserve method, confidence, horizon, tail depth, and expected-shortfall detail fields when shown.

Do not relabel a signed `-2.50` percent threshold as `2.50% loss` unless the downstream layer
explicitly records that it converted sign convention for presentation.

### 2. Preserve Attribution Reconciliation

Historical attribution contributor rows are explainability components, not a guaranteed exact
partition of the total metric. Downstream surfaces must display or preserve these fields together:

- `total_value`
- `reconciled_sum`
- `residual`
- `contributors`
- `grouping_dimension`
- `attribution_type`
- `metric`

If a compact UI cannot render all fields, it must preserve them in the backing API payload or detail
drawer. Hiding `residual` while showing only contributors can mislead users into believing the
selected grouping fully explains the metric.

### 3. Preserve Issuer Active-Risk Support Metadata

Stateful historical attribution supports `ACTIVE_RISK` for these grouping dimensions:

- `POSITION`
- `SECTOR`
- `ASSET_CLASS`
- `ISSUER`

Stateful `ACTIVE_RISK + ISSUER` is supported through lotus-performance benchmark exposure context
issuer groups. Downstream surfaces must derive issuer active-risk affordances from lotus-risk
capabilities and historical-attribution metadata instead of maintaining a separate local support
matrix.

The runtime contract enforces unsupported `CUSTOM` grouping with request validation and publishes
current support through `GET /integration/capabilities`.

### 4. Keep Simulation Concentration-Only

Simulation support is concentration-only in the current `lotus-risk` product contract.

`simulation` is currently supported only by:

- `POST /analytics/risk/concentration`

`simulation` is intentionally unsupported by:

- `POST /analytics/risk/calculate`
- `POST /analytics/risk/drawdown`
- `POST /analytics/risk/rolling-metrics`
- `POST /analytics/risk/historical-attribution`

Downstream workflow selectors must derive simulation affordances from `/integration/capabilities`
instead of assuming every risk endpoint supports what-if mode.

### 5. Preserve Audit And Dependency Metadata

Downstream consumers must preserve these response metadata fields for audit and support workflows:

- `lineage_version`
- `request_fingerprint`
- `source_services`
- `upstream_request_fingerprints`
- `benchmark_context`
- `risk_free_context`
- `coverage_ratio`
- `coverage_status`
- `issuer_concentration.coverage_ratio`
- `issuer_concentration.coverage_status`

Product panels may choose not to display every field by default, but gateway and product models must
not drop them if the response is persisted, summarized, or passed to another service.

## Gateway Mapping Requirements

Gateway mappings must:

- pass through `input_mode` and endpoint-specific mode support without broadening capability,
- preserve signed VaR and expected-shortfall sign,
- preserve historical attribution reconciliation fields,
- preserve audit lineage metadata,
- surface deterministic `lotus-risk` error codes/messages without remapping unsupported capability
  into a generic service failure,
- use `/integration/capabilities` as the mode and workflow support source of truth.

## Workbench Panel Requirements

Workbench panels must:

- label VaR as a signed return-threshold metric,
- show attribution residuals with contributor totals or preserve them in a detail surface,
- disable or omit stateful issuer active-risk affordances,
- expose simulation controls only for concentration,
- show coverage warnings when concentration issuer enrichment is partial or missing,
- keep correlation/request identifiers available for support escalation.

## Validation Evidence

Risk-owned validation is enforced by:

- `tests/unit/test_product_surface_alignment_contract.py`
- `tests/integration/test_health.py`
- `tests/integration/test_historical_attribution_endpoint.py`
- `tests/integration/test_risk_calculate.py`
- `tests/integration/test_drawdown_endpoint.py`
- `tests/integration/test_rolling_metrics_endpoint.py`
- `tests/integration/test_concentration_lotus_core_characterization.py`

Cross-repo gateway and Workbench validation should reference this document and attach evidence that
their rendered/API models preserve the same semantics. Until that downstream evidence is attached,
`lotus-risk` owns the contract but not the consumer-side proof.
