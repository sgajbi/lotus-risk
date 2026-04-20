# Mesh Data Products

## Mesh role

`lotus-risk` is a maturity-wave producer in the Lotus enterprise data mesh.

## Governed product

- Product ID: `lotus-risk:RiskMetricsReport:v1`
- Product role: governed risk metrics report for advisory, reporting, gateway, and Workbench discovery flows
- Source declaration: `contracts/domain-data-products/`
- Trust telemetry: `contracts/trust-telemetry/`

## Platform relationship

`lotus-platform` aggregates the repo-native declaration, validates trust telemetry, applies mesh SLO/access/evidence policies, and includes this product in generated catalog, dependency graph, live certification, maturity matrix, evidence packs, and RFC-0092 operating reports.

## Operating rule

Risk product trust must include freshness, completeness, data quality, lineage, and upstream dependency posture. Do not present risk mesh posture as certified unless platform mesh certification passes.
