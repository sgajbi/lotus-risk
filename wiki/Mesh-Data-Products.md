# Mesh Data Products

## Mesh role

`lotus-risk` is a maturity-wave producer in the Lotus enterprise data mesh.

## Governed product

- Product IDs:
  - `lotus-risk:RiskMetricsReport:v1`
  - `lotus-risk:DrawdownAnalyticsReport:v1`
  - `lotus-risk:RollingRiskMetricsReport:v1`
  - `lotus-risk:HistoricalRiskAttributionReport:v1`
  - `lotus-risk:ConcentrationRiskReport:v1`
  - `lotus-risk:RegimeScenarioPackEvaluation:v1`
  - `lotus-risk:RiskEventAffectedCohort:v1`
- Product role: governed risk analytics reports, scenario-pack evaluation outputs, and risk-event
  affected-cohort membership for advisory, reporting, gateway, Workbench discovery, manage
  construction-supportability, and future rebalance-wave trigger flows
- Source declaration: `contracts/domain-data-products/`
- Trust telemetry: `contracts/trust-telemetry/`

## Implementation-backed methodology coverage

`RollingRiskMetricsReport:v1` now has auditable source-owner methodology truth for rolling
volatility, rolling Sharpe, rolling tracking error, and rolling information ratio. The
methodologies are tied to the implemented `/analytics/risk/rolling-metrics` engine and state the
exact percentage-point to decimal conversion, `ddof=1` sample standard deviation, annualization
basis, strict versus partial minimum-observation behavior, warm-up null handling, risk-free and
benchmark date-alignment rules where required, no-aligned-dependency behavior, zero-excess-volatility
Sharpe flagging, zero-tracking-error information-ratio flagging, annualized decimal
volatility output, decimal-ratio tracking-error output, and dimensionless Sharpe and
information-ratio output.

`RegimeScenarioPackEvaluation:v1` now carries source-owned scenario-pack evidence beyond aggregate
loss. When callers provide reconciled `exposure_components`, the product emits per-security
scenario contribution rows alongside worst-case loss, threshold-breach posture, lineage, and
bounded reason codes. The rows are contribution evidence for governed CIO shocks, not full
instrument repricing, and downstream proof packs must preserve them instead of rebuilding scenario
logic outside `lotus-risk`.

```mermaid
flowchart LR
    PERF[lotus-performance<br/>portfolio + benchmark returns]
    RISK[lotus-risk<br/>RollingRiskMetricsReport:v1]
    GW[lotus-gateway<br/>risk composition]
    WB[lotus-workbench<br/>risk workspace]
    MANAGE[lotus-manage<br/>realized outcome source adapter]
    COHORT[lotus-risk<br/>RiskEventAffectedCohort:v1]

    PERF -->|dated return series| RISK
    RISK -->|rolling active-risk metrics + lineage| GW
    GW --> WB
    RISK -->|source-owned scalar + scenario contribution evidence| MANAGE
    COHORT -->|affected portfolios + source refs| MANAGE
```

Audience notes:

- Business users can read rolling volatility as annualized portfolio-return dispersion, rolling
  Sharpe as annualized excess return per unit of portfolio excess-return volatility, rolling
  tracking error as annualized active-return volatility versus the selected benchmark, and rolling
  information ratio as annualized active return per unit of that active risk.
- Operations teams can distinguish warm-up gaps, missing benchmark alignment, and upstream sourcing
  issues from calculation failure; missing risk-free alignment and zero-excess-volatility windows
  are explicit for Sharpe, and zero-tracking-error windows are flagged rather than promoted as valid
  ratios.
- Developers and downstream services must preserve `RollingRiskMetricsReport:v1` values and
  supportability metadata rather than recomputing rolling volatility, Sharpe, tracking error, or
  information ratio locally.
- Developers and downstream services must preserve `RiskEventAffectedCohort:v1` membership,
  exclusions, source refs, and impact scores rather than reconstructing risk-event cohort
  membership locally.
- Developers and downstream services must preserve `RegimeScenarioPackEvaluation:v1` scenario
  results, per-security contribution rows, reason codes, and lineage rather than applying local
  scenario methodology in gateway, Workbench, reporting, or manage proof packs.
- Sales and pre-sales can describe the canonical capability as implementation-backed for supported
  seeded portfolios, while broader portfolio-archetype coverage still depends on live validation
  evidence.

## Platform relationship

`lotus-platform` aggregates the repo-native declaration, validates trust telemetry, applies mesh SLO/access/evidence policies, and includes this product in generated catalog, dependency graph, live certification, maturity matrix, evidence packs, and RFC-0092 operating reports.

## Operating rule

Risk product trust must include freshness, completeness, data quality, lineage, and upstream dependency posture. Do not present risk mesh posture as certified unless platform mesh certification passes.
