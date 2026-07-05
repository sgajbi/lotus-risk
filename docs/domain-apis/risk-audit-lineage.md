# Risk Audit Lineage

`lotus-risk` analytics responses expose common audit-lineage metadata so private-banking, model
review, and support teams can reproduce the calculation input and identify upstream dependencies.

## Common Metadata Fields

Every analytics response metadata object includes:

| Field | Meaning |
| --- | --- |
| `lineage_version` | Version of the audit-lineage metadata schema. Current value: `risk_audit_lineage.v1`. |
| `request_fingerprint` | Deterministic SHA-256 fingerprint of the normalized calculation request used by `lotus-risk`. |
| `source_services` | Ordered list of services whose data or calculation path contributed to the response. |
| `upstream_request_fingerprints` | Deterministic fingerprints for upstream calls directly orchestrated by `lotus-risk`, keyed by `service:operation`. |

The fingerprint is not a security token. It is a reproducibility and support handle. Operators can
compare two responses to determine whether the normalized calculation input or upstream request
shape changed without logging full customer payloads.

## Endpoint Behavior

| Endpoint | Stateless Source Services | Stateful / Simulation Source Services |
| --- | --- | --- |
| `risk/calculate` | `lotus-risk` | `lotus-risk`, `lotus-performance`; plus `lotus-core` when Sharpe uses sourced risk-free returns |
| `drawdown` | `lotus-risk` | `lotus-risk`, `lotus-performance` |
| `rolling-metrics` | `lotus-risk` | `lotus-risk`, `lotus-performance`; plus `lotus-core` when risk-free sourcing is required |
| `historical-attribution` | `lotus-risk` | `lotus-risk`, `lotus-performance`, `lotus-core` |
| `concentration` | `lotus-risk` | `lotus-risk`, `lotus-core` |

For stateful `risk/calculate`, Sharpe risk-free treatment uses a direct
`lotus-core:/integration/reference/risk-free-series` upstream request fingerprint. The
`lotus-performance:/integration/returns/series` fingerprint covers portfolio and benchmark returns
only; it must not be used as implicit proof of risk-free source lineage.

## Governance Rules

1. `request_fingerprint` must be deterministic for equivalent normalized inputs.
2. Stateless analytics should report `source_services=["lotus-risk"]`.
3. Stateful analytics must add upstream source services when `lotus-risk` orchestrates upstream data
   access.
4. Do not use fingerprints as proof of authorization or consent.
5. If a new upstream call is added to an analytics path, update `source_services` and
   `upstream_request_fingerprints` in the same slice.
6. Keep methodology-specific metadata, observation counts, alignment context, and coverage ratios in
   endpoint-specific fields; common lineage is not a replacement for those details.
