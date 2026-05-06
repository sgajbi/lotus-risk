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
- Product role: governed risk analytics reports and scenario-pack evaluation outputs for advisory,
  reporting, gateway, Workbench discovery, and manage construction-supportability flows
- Source declaration: `contracts/domain-data-products/`
- Trust telemetry: `contracts/trust-telemetry/`

## Platform relationship

`lotus-platform` aggregates the repo-native declaration, validates trust telemetry, applies mesh SLO/access/evidence policies, and includes this product in generated catalog, dependency graph, live certification, maturity matrix, evidence packs, and RFC-0092 operating reports.

## Operating rule

Risk product trust must include freshness, completeness, data quality, lineage, and upstream dependency posture. Do not present risk mesh posture as certified unless platform mesh certification passes.
