# Regime Scenario Pack Evaluation Methodology

## Metric

- product_name: RegimeScenarioPackEvaluation
- product_version: v1
- methodology_version: risk-regime-scenario-pack-evaluation.v1
- metric family: governed CIO regime scenario-pack evaluation
- owner: lotus-risk

This product evaluates caller-supplied portfolio exposure weights against a risk-owned CIO
scenario pack. It returns scenario-level expected loss, worst-case loss, policy-threshold posture,
source-owned CIO approval, effective-period and portfolio-applicability posture, source-owned
supportability, deterministic lineage, and optional per-security contribution rows.

## Endpoint and Mode Coverage

- endpoint: `POST /analytics/risk/regime-scenario-pack/evaluate`
- mode: stateless
- supported pack in current implementation: `CIO_REGIME_2026_Q2`
- response contract: `RegimeScenarioPackResponse`
- downstream consumers must preserve the returned `scenario_results` and
  `scenario_results[].position_contributions` instead of recalculating scenario methodology.
- downstream consumers must preserve `governance_evidence` instead of substituting local CIO
  approval, effective-period, or applicability checks.

The endpoint is not a market forecast, full instrument repricing model, client suitability engine,
client suitability approval, mandate recommendation, or execution/OMS product. It validates only
the bounded scenario-pack governance fields owned by this source product.

## Inputs

| Field | Required | Meaning |
|---|---:|---|
| `scenario_pack_id` | yes | Governed scenario-pack identifier. |
| `portfolio_id` | no | Optional portfolio identifier retained for lineage. |
| `as_of_date` | yes | Business date for the source-owned evaluation. |
| `exposures[]` | yes | Caller-supplied portfolio weights by scenario bucket. |
| `exposure_components[]` | no | Optional position-level rows that reconcile exactly to `exposures[]` by bucket. |
| `maximum_allowed_loss_pct` | yes | Consumer policy threshold for worst-case loss breach posture. |

## Upstream Data Sources

- The caller supplies exposure weights and optional reconciled position components.
- `lotus-risk` owns the scenario pack definitions, scenario identifiers, display names, and
  scenario shocks by bucket.
- `lotus-risk` owns the bounded scenario-pack governance registry used to emit CIO approval,
  effective-period, and portfolio-applicability posture for the current pack.
- The current implementation does not fetch holdings, market prices, factor models, client
  suitability state, mandate recommendation state, OMS acknowledgements, fills, or settlement data.

## Unit Conventions

- `weight` is a decimal portfolio weight. `0.55` means 55% of portfolio value.
- `shock_pct` is a decimal shock ratio. `-0.12` means a 12% loss shock.
- `expected_loss_pct`, `worst_case_loss_pct`, and `contribution_loss_pct` are decimal loss ratios.
  `0.106` means 10.6% expected loss.
- Loss outputs are non-negative and rounded to six decimal places.
- Bucket identifiers are normalized to uppercase before calculation.

## Variable Dictionary

| Symbol | API field | Meaning |
|---|---|---|
| `P` | `scenario_pack_id` | Governed scenario pack. |
| `S` | `scenario_results[].scenario_id` | One scenario inside pack `P`. |
| `b` | `exposures[].bucket` | Scenario exposure bucket, normalized to uppercase. |
| `w_b` | `exposures[].weight` | Portfolio weight for bucket `b`. |
| `q_{i,b}` | `exposure_components[].weight` | Position-level weight for component `i` assigned to bucket `b`. |
| `shock_{S,b}` | `scenario_results[].shock_by_bucket[b]` | Scenario shock for bucket `b` under scenario `S`. |
| `loss_{S,b}` | intermediate | Non-negative bucket loss under scenario `S`. |
| `contribution_{S,i}` | `position_contributions[].contribution_loss_pct` | Non-negative component loss contribution under scenario `S`. |
| `L_S` | `scenario_results[].expected_loss_pct` | Total expected loss under scenario `S`. |
| `L_worst` | `worst_case_loss_pct` | Maximum expected loss across scenarios. |
| `T` | `maximum_allowed_loss_pct` | Consumer policy threshold. |
| `A_P` | `governance_evidence.cio_approval_status` | Source-owned CIO approval status for pack `P`. |
| `E_P` | `governance_evidence.effective_period_status` | Source-owned effective-period posture for `as_of_date`. |
| `G_P` | `governance_evidence.applicability_status` | Source-owned portfolio-applicability posture. |

## Methodology and Formulas

For each scenario `S` in the governed pack:

```text
loss_{S,b} = max(-(w_b * shock_{S,b}), 0.0)
L_S = sum(loss_{S,b} for each requested exposure bucket b)
```

If a requested bucket does not exist in the scenario definition, the implementation uses
`shock_{S,b} = 0.0` for that bucket and marks the evaluation degraded with
`REGIME_SCENARIO_UNSUPPORTED_EXPOSURE_BUCKET`.

Worst-case and threshold posture:

```text
L_worst = max(L_S for each scenario S)
breach = L_worst > T
```

When `exposure_components[]` is supplied, every component receives the same bucket shock used by the
scenario-level calculation:

```text
contribution_{S,i} = max(-(q_{i,b} * shock_{S,b}), 0.0)
```

Contribution rows are sorted deterministically by descending `contribution_loss_pct`, then `bucket`,
then `security_id`.

Governance posture:

```text
A_P = approved when the pack registry marks P approved
E_P = active when effective_from <= as_of_date <= effective_to
G_P = applicable when portfolio_id is in the pack applicability registry
```

The current pack is approved by `CIO Risk Committee`, effective from `2026-04-01` through
`2026-06-30`, and applicable to `PB_SG_GLOBAL_BAL_001` under
`DISCRETIONARY_PRIVATE_BANKING_BALANCED` scope.

## Step-by-Step Computation

1. Look up `scenario_pack_id` in the risk-owned `SCENARIO_PACKS` registry.
2. Normalize `exposures[].bucket` to uppercase and build `exposure_by_bucket`.
3. Compare requested buckets with `SUPPORTED_BUCKETS`.
4. Look up source-owned scenario-pack governance in `SCENARIO_PACK_GOVERNANCE`.
5. Validate optional `exposure_components[]` at request-model level:
   - every component bucket must be present in `exposures[]`,
   - component weights must reconcile to the matching exposure bucket within `0.000001`.
6. For each scenario in the pack:
   - get `shock_by_bucket[b]`, defaulting to `0.0` for unsupported requested buckets,
   - compute bucket losses,
   - sum bucket losses into `expected_loss_pct`,
   - compute optional position contribution rows from component weights and bucket shocks.
7. Emit `governance_evidence` from source-owned approval, effective-period, and applicability
   posture.
8. Set `worst_case_loss_pct` to the maximum scenario `expected_loss_pct`.
9. Set `breach` when `worst_case_loss_pct > maximum_allowed_loss_pct`.
10. Emit sorted bounded `reason_codes`.
11. Emit `metadata.request_fingerprint` as a deterministic SHA-256 hash of the canonical request.

## Validation and Failure Behavior

- Unknown `scenario_pack_id` raises `Unsupported scenario_pack_id`.
- Empty `exposures[]` is rejected by request validation.
- Negative exposure or component weights are rejected by request validation.
- `maximum_allowed_loss_pct` must be between `0.0` and `1.0`.
- Component buckets absent from `exposures[]` are rejected.
- Component weights that do not reconcile to exposure bucket weights within `0.000001` are rejected.
- Unsupported exposure buckets do not fail the request; they produce
  `metadata.calculation_supportability = degraded` and
  `REGIME_SCENARIO_UNSUPPORTED_EXPOSURE_BUCKET`.
- Threshold breaches produce `REGIME_SCENARIO_POLICY_THRESHOLD_BREACH`; when no other degraded
  posture exists, supportability becomes `pending_review`.
- A request outside the source-owned effective period produces
  `REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION` and
  `metadata.calculation_supportability = degraded`.
- A request without `portfolio_id` produces
  `REGIME_SCENARIO_PORTFOLIO_APPLICABILITY_NOT_CONFIRMED` and
  `metadata.calculation_supportability = pending_review`.
- A request for a portfolio outside the source-owned applicability registry produces
  `REGIME_SCENARIO_PORTFOLIO_NOT_APPLICABLE` and
  `metadata.calculation_supportability = blocked`.
- Bucket-only requests return empty `position_contributions[]`.

## Configuration Options

The current source-owned scenario pack registry is code-defined:

| Pack | Scenarios |
|---|---|
| `CIO_REGIME_2026_Q2` | `growth_slowdown`, `rates_up_inflation`, `risk_off_liquidity` |

Current supported buckets are `EQUITY`, `FIXED_INCOME`, `ALTERNATIVES`, and `CASH`.

No runtime caller option can override shocks, scenario ids, contribution formula, supportability
classification, governance posture, sorting, or request fingerprinting.

## Outputs

| Output field | Meaning |
|---|---|
| `scenario_results[].expected_loss_pct` | Scenario-level decimal expected loss after six-decimal rounding. |
| `scenario_results[].shock_by_bucket` | Risk-owned shock definitions for the scenario. |
| `scenario_results[].position_contributions[]` | Optional source-owned component contribution rows. |
| `governance_evidence` | Source-owned CIO approval, effective-period, and portfolio-applicability evidence. |
| `worst_case_loss_pct` | Maximum scenario expected loss after six-decimal rounding. |
| `breach` | Whether `worst_case_loss_pct > maximum_allowed_loss_pct`. |
| `reason_codes[]` | Bounded calculation and policy posture reason codes. |
| `metadata.calculation_supportability` | `ready`, `pending_review`, `degraded`, or `blocked` for current implementation paths. |
| `metadata.request_fingerprint` | Deterministic request hash for replay and audit. |

## Worked Example

Input:

| Bucket | `w_b` |
|---|---:|
| `EQUITY` | 0.55 |
| `FIXED_INCOME` | 0.35 |
| `CASH` | 0.10 |

For `growth_slowdown`, the code-defined shocks are:

| Bucket | `shock_{S,b}` | Formula | Bucket loss |
|---|---:|---|---:|
| `EQUITY` | -0.12 | `max(-(0.55 * -0.12), 0.0)` | 0.0660 |
| `FIXED_INCOME` | -0.03 | `max(-(0.35 * -0.03), 0.0)` | 0.0105 |
| `CASH` | 0.00 | `max(-(0.10 * 0.00), 0.0)` | 0.0000 |

Final scenario loss:

```text
scenario_results[].expected_loss_pct = 0.0660 + 0.0105 + 0.0000 = 0.0765
```

With `maximum_allowed_loss_pct = 0.12`, the three current pack scenarios produce:

| Scenario | `expected_loss_pct` |
|---|---:|
| `growth_slowdown` | 0.0765 |
| `rates_up_inflation` | 0.0685 |
| `risk_off_liquidity` | 0.1060 |

Final pack outputs:

```text
worst_case_loss_pct = 0.1060
breach = false
metadata.calculation_supportability = ready
reason_codes = ["REGIME_SCENARIO_PACK_READY"]
governance_evidence.cio_approval_status = approved
governance_evidence.effective_period_status = active
governance_evidence.applicability_status = applicable
```

When the equity exposure is split into `FO_EQ_AAPL_US = 0.30` and `FO_EQ_MSFT_US = 0.25`, the
`growth_slowdown` contribution rows include:

| Security | Bucket | Component weight | Shock | `contribution_loss_pct` |
|---|---|---:|---:|---:|
| `FO_EQ_AAPL_US` | `EQUITY` | 0.30 | -0.12 | 0.0360 |
| `FO_EQ_MSFT_US` | `EQUITY` | 0.25 | -0.12 | 0.0300 |
| `FO_BOND_UST_2030` | `FIXED_INCOME` | 0.35 | -0.03 | 0.0105 |
| `CASH_USD_BOOK_OPERATING` | `CASH` | 0.10 | 0.00 | 0.0000 |
