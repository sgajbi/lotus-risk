# Idea Opportunity Runtime Evidence

This runbook describes the `lotus-risk` producer proof for `lotus-idea` RFC-0002 Slice 16/17
opportunity archetype consumption.

## Scope

The evidence pack proves three Risk-owned HTTP API executions for the canonical opportunity
archetype:

1. `ConcentrationRiskReport:v1` through `POST /analytics/risk/concentration`,
2. `RiskMetricsReport:v1` through `POST /analytics/risk/calculate`,
3. `DrawdownAnalyticsReport:v1` through `POST /analytics/risk/drawdown`.

The artifact is source-safe. It stores request digests, normalized response digests, bounded metric
summaries, supportability state, freshness bucket, and a portfolio identity digest. It does not store
the raw canonical portfolio ID, raw holdings, client identity, position identifiers, issuer
identifiers, correlation IDs, trace IDs, or raw response payloads.

## Generate The Artifact

Start `lotus-risk`, then run:

```powershell
make idea-opportunity-runtime-evidence `
  IDEA_OPPORTUNITY_RISK_BASE_URL=http://localhost:8130 `
  IDEA_OPPORTUNITY_GENERATED_AT_UTC=2026-07-23T06:30:00Z `
  IDEA_OPPORTUNITY_EVIDENCE_OUTPUT=output/idea-opportunity-runtime-evidence/idea-risk-runtime-evidence.json
```

Focused local contract proof:

```powershell
make idea-opportunity-evidence-gate
```

The generated schema is `lotus-risk.idea-opportunity-runtime-evidence.v1`.

## Consumer Boundary

This artifact may clear only the Risk source-proof blockers in `lotus-idea` readiness:

1. `opportunity_archetype_live_risk_source_proof_missing`,
2. `opportunity_archetype_live_risk_volatility_source_proof_missing`,
3. `opportunity_archetype_drawdown_source_proof_missing`.

It does not prove Idea candidate persistence, data-mesh certification, Gateway/Workbench product
runtime, client publication, deployment certification, production certification, or supported-feature
promotion.

## Source Authority

`lotus-risk` remains the official risk methodology and calculation authority. `lotus-idea` may
consume the receipt and source refs, but must not recalculate concentration, volatility, VaR,
tracking error, drawdown, or risk supportability.

