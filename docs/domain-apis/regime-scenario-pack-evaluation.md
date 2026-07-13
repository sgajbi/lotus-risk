# Regime Scenario Pack Evaluation

## Endpoint

- `POST /analytics/risk/regime-scenario-pack/evaluate`

## Product Contract

- Product: `RegimeScenarioPackEvaluation:v1`
- Owner: `lotus-risk`
- Mode: `stateless`
- Authoritative domain: risk analytics
- Downstream consumers: `lotus-gateway`, `lotus-manage`, Workbench, reporting, and evidence-pack
  consumers through governed service contracts

## Business Purpose

This endpoint evaluates a portfolio exposure profile against a governed CIO scenario pack. It gives
portfolio construction, advisory oversight, and proof-pack workflows a source-owned stress posture:
worst-case loss, threshold breach state, scenario-by-scenario loss, bounded reason codes, lineage,
optional per-security contribution rows, and bounded CIO approval/effective-period/portfolio
applicability posture.

The endpoint is not a forecasting engine and is not a full instrument repricing model. It applies
risk-owned scenario shocks to caller-supplied exposure weights and, when supplied, reconciled
security-level exposure components.

## Request Inputs

| Field | Required | Meaning |
|---|---:|---|
| `scenario_pack_id` | yes | Governed scenario pack identifier, for example `CIO_REGIME_2026_Q2`. |
| `portfolio_id` | no | Portfolio identifier retained for lineage and downstream evidence. |
| `as_of_date` | yes | Business date for the evaluation. |
| `exposures` | yes | Portfolio weights by scenario bucket. At least one bucket is required, at most 16 buckets are accepted, buckets must be unique after uppercase normalization, each weight must be between 0.0 and 1.0, and weights must sum to 1.0 within 0.000001. |
| `exposure_components` | no | Optional security or instrument rows that reconcile exactly to `exposures` by bucket. Request validation accepts at most 250 component rows, and runtime evaluation applies a scenario-pack-aware cap so at most 250 position contribution rows can be returned across the full response. |
| `maximum_allowed_loss_pct` | yes | Consumer policy threshold for breach evaluation. |

When `exposure_components` is supplied:

1. every component bucket must exist in `exposures`,
2. the sum of component weights by bucket must reconcile to the matching exposure bucket weight,
3. component weights must also sum to 1.0 within `0.000001`,
4. invalid or unreconciled component sets are rejected with request validation errors,
5. the number of components must not multiply across the selected scenario pack into more than
   250 returned contribution rows,
6. downstream consumers must preserve the returned rows instead of recalculating scenario
   contributions.

## Calculation Method

The full auditable methodology is pinned in
[`docs/methodologies/metrics/regime-scenario-pack-evaluation.md`](../methodologies/metrics/regime-scenario-pack-evaluation.md).

For each governed scenario in the pack:

1. normalize each requested exposure bucket to uppercase,
2. apply the scenario shock for that bucket,
3. compute bucket loss as `max(-(weight * shock), 0.0)`,
4. sum bucket losses into `expected_loss_pct`,
5. compute `worst_case_loss_pct` as the maximum expected loss across scenarios,
6. emit source-owned `governance_evidence` for CIO approval, effective-period, and portfolio
   applicability,
7. set `breach` when `worst_case_loss_pct > maximum_allowed_loss_pct`.

When component rows are present, each component receives the shock for its bucket and returns:

```text
contribution_loss_pct = max(-(component.weight * bucket_shock), 0.0)
```

Contribution rows are rounded consistently with the scenario engine and sorted deterministically by
largest loss, then bucket, then security identifier.

## Example

Request excerpt:

```json
{
  "scenario_pack_id": "CIO_REGIME_2026_Q2",
  "portfolio_id": "PB_SG_GLOBAL_BAL_001",
  "as_of_date": "2026-05-03",
  "exposures": [
    {"bucket": "EQUITY", "weight": 0.55},
    {"bucket": "FIXED_INCOME", "weight": 0.35},
    {"bucket": "CASH", "weight": 0.10}
  ],
  "exposure_components": [
    {"security_id": "FO_EQ_AAPL_US", "display_name": "Apple Inc.", "bucket": "EQUITY", "weight": 0.30},
    {"security_id": "FO_EQ_MSFT_US", "display_name": "Microsoft Corp.", "bucket": "EQUITY", "weight": 0.25},
    {"security_id": "FO_BOND_UST_2030", "display_name": "United States Treasury 3.875% 2030", "bucket": "FIXED_INCOME", "weight": 0.35},
    {"security_id": "FO_CASH_USD", "display_name": "US Dollar Cash", "bucket": "CASH", "weight": 0.10}
  ],
  "maximum_allowed_loss_pct": 0.12
}
```

For the `growth_slowdown` scenario, the expected contribution rows include:

| Security | Bucket | Weight | Shock | Contribution loss |
|---|---|---:|---:|---:|
| `FO_EQ_AAPL_US` | `EQUITY` | 0.30 | -0.12 | 0.036 |
| `FO_EQ_MSFT_US` | `EQUITY` | 0.25 | -0.12 | 0.030 |
| `FO_BOND_UST_2030` | `FIXED_INCOME` | 0.35 | -0.03 | 0.0105 |
| `FO_CASH_USD` | `CASH` | 0.10 | 0.00 | 0.0000 |

## Supportability And Failure Behavior

- Unknown scenario packs raise a deterministic validation failure.
- Underallocated, overallocated, duplicate, or over-limit exposure requests fail request
  validation before scenario calculation starts.
- Over-limit `exposure_components` requests fail request validation; component counts that would
  produce more than 250 returned contribution rows across the selected scenario pack fail before
  scenario rows are materialized.
- Unsupported exposure buckets produce a degraded supportability state and bounded reason codes.
- Requests outside the source-owned effective period are degraded with
  `REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION`.
- Requests without portfolio applicability evidence are pending review with
  `REGIME_SCENARIO_PORTFOLIO_APPLICABILITY_NOT_CONFIRMED`.
- Requests for portfolios outside the source-owned applicability registry are blocked with
  `REGIME_SCENARIO_PORTFOLIO_NOT_APPLICABLE`.
- Reconciled component rows are optional; bucket-only requests continue to return no position rows.
- The response includes deterministic request fingerprinting for audit replay.

## Downstream Preservation Rule

Downstream services may format or filter the rows for a user interface, but they must not derive a
different scenario methodology or replace the risk-owned contribution calculation. Stored proof
packs should retain `scenario_results`, `position_contributions`, `reason_codes`, and `metadata` as
source-owned evidence. They should also retain `governance_evidence` instead of validating CIO
approval, effective period, or portfolio applicability locally.
