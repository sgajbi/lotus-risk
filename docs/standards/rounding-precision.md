# Rounding and Precision

- Service: lotus-risk
- Canonical precision policy must be used for monetary outputs.

## Stateful Returns Coverage

Performance owns the v1 returns-series coverage value. Risk requires non-negative counts with
`requested_points = returned_points + missing_points`, and a finite ratio in `[0, 1]`.
Let `r = returned_points / requested_points`; for zero requests, `r = 1`.
Risk admits either the unquantized ratio within absolute `1e-12`, or exactly Python's
`round(r, 8)`, matching Performance's `Decimal(str(round(r, 8)))` JSON serialization.
This is a discrete compatibility rule, not a general eight-decimal error tolerance.

For example, `269/270` admits `0.9962963`; adjacent `0.99629629` does not reconcile.
Risk preserves the received numeric value, missing count, producer identity and freshness.
Admission does not fill missing observations or promote partial/stale evidence to ready/current.
The shared policy applies to calculate, drawdown and rolling metrics.

Implementation and regressions: `src/app/contracts/stateful_returns_source_evidence.py`,
`tests/unit/test_returns_coverage_precision.py`, and
`tests/integration/test_returns_source_admission.py`.
