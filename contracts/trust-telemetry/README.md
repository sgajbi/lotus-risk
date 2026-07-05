# Lotus Risk Trust Telemetry

This directory contains repo-owned RFC-0087 trust telemetry snapshots for governed `lotus-risk`
domain products.

The current first-wave static snapshot is:

1. `risk-metrics-report.telemetry.v1.json`
   Runtime trust proof for `lotus-risk:RiskMetricsReport:v1`.

The full active-product coverage treatment is machine-readable in:

1. `../trust-telemetry-coverage/lotus-risk-trust-telemetry-coverage.v1.json`

That coverage contract marks `RiskMetricsReport:v1` as the only current
`certified_static_snapshot` and marks the remaining active products as
`pending_static_snapshot` with owner, decision date, and rationale. Runtime raw seeds exposed by
`/ops/trust-telemetry` are operator diagnostics only; they are not platform-certified static trust
evidence unless a matching snapshot or governed coverage treatment says so.

Validate locally with:

```powershell
python scripts\validate_trust_telemetry_contracts.py
python -m pytest tests\unit\test_trust_telemetry.py -q
```

When `../lotus-platform` is available, the test validates the snapshot with the platform
`automation/validate_trust_telemetry.py` contract validator. The repo validator also cross-checks
every active product in `contracts/domain-data-products/lotus-risk-products.v1.json` against a
static telemetry snapshot or explicit coverage treatment so active products cannot be silently
uncertified.
