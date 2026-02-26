# RFC-0002 - Risk Migration Parity Closure

## Summary
This change completes parity migration of risk runtime behavior into `lotus-risk` so it is the authoritative risk implementation.

## What Changed
- Added period normalization and compatibility aliases (`CUSTOM`/`1Y`/`3Y`/`5Y`).
- Added `EXPLICIT` period style with `from/to` compatibility fields.
- Added VaR method parity (`HISTORICAL`, `GAUSSIAN`, `CORNISH_FISHER`).
- Added drawdown metadata parity (`peak_date`, `trough_date`, `max_drawdown_date`).
- Added deterministic benchmark-required behavior for benchmark metrics.
- Added observability parity counters/histograms for metric requests and durations.

## Compatibility Notes
- Existing payloads continue to work.
- Alias input forms are accepted and normalized to canonical internal period semantics.
- Benchmark-metric requests without benchmark series return deterministic null/error metric payloads.
