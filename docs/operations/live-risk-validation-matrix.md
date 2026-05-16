# Live Risk Validation Matrix

This runbook defines the governed live portfolio matrix used to prove `lotus-risk`
against bank-relevant portfolio archetypes.

## Current Truth

The default live characterization suite validates one canonical portfolio:

| Archetype | Portfolio ID | As Of Date | Status | Notes |
| --- | --- | --- | --- | --- |
| `global_balanced` | `PB_SG_GLOBAL_BAL_001` | `2026-03-31` | validated | Canonical private-banking portfolio used for the current live analytics baseline. Live proof includes concentration stateful HHI, top-position, top-issuer, and issuer-coverage reconciliation; rolling-metrics stateful `ROLLING_SHARPE` plus adjacent rolling volatility, beta, tracking error, information ratio, max drawdown, and multi-window time-series emission; and historical-attribution stateful `TOTAL_RISK` plus supported `ACTIVE_RISK` groupings `POSITION`, `SECTOR`, `ASSET_CLASS`, and `ISSUER`. |

This is strong canonical evidence, but it is not a complete enterprise portfolio universe.
Additional archetypes must be backed by real seeded portfolio IDs before they can be counted as
validated.

## Required Enterprise Archetypes

| Archetype | Current Status | Expected Purpose |
| --- | --- | --- |
| `global_balanced` | registered by default | Canonical private-banking balanced mandate. |
| `equity_heavy` | pending seeded portfolio ID | High equity beta, high benchmark sensitivity, larger downside tails. |
| `fixed_income_heavy` | pending seeded portfolio ID | Lower volatility, rate-sensitive risk-free and duration behavior. |
| `cash_heavy` | pending seeded portfolio ID | Near-zero realized volatility and low concentration-risk edge cases. |
| `multi_currency` | pending seeded portfolio ID | Reporting-currency and FX conversion supportability. |
| `short_history` | pending seeded portfolio ID | Minimum-observation and partial-window behavior. |
| `sparse_benchmark` | pending seeded portfolio ID | Benchmark alignment, tracking error, and information-ratio gaps. |
| `high_concentration` | pending seeded portfolio ID | Single-name/issuer concentration and HHI stress behavior. |

## Endpoint Coverage Target

Each registered case should declare which endpoints it can validate:

1. `risk/calculate`,
2. `drawdown`,
3. `concentration`,
4. `rolling-metrics`,
5. `historical-attribution`.

If a portfolio intentionally cannot support an endpoint, record that as a supportability note rather
than silently skipping it.

## Configuration

Single canonical portfolio override:

```powershell
$env:LOTUS_RISK_LIVE_PORTFOLIO_ID = "PB_SG_GLOBAL_BAL_001"
$env:LOTUS_RISK_LIVE_AS_OF_DATE = "2026-03-31"
```

Full matrix override:

```powershell
$env:LOTUS_RISK_LIVE_PORTFOLIO_MATRIX_JSON = @'
[
  {
    "portfolio_id": "PB_SG_GLOBAL_BAL_001",
    "archetype": "global_balanced",
    "label": "Canonical Singapore global balanced portfolio",
    "as_of_date": "2026-03-31",
    "supported_endpoints": [
      "risk/calculate",
      "drawdown",
      "concentration",
      "rolling-metrics",
      "historical-attribution"
    ],
    "supportability_note": "validated live"
  }
]
'@
```

The parser for this contract lives in `tests/support/live_portfolio_matrix.py`.

## Governance Rules

1. Do not add an archetype to the validated matrix without a real seeded portfolio ID.
2. Do not claim endpoint coverage for an archetype unless the endpoint has passed live validation.
3. Preserve `PB_SG_GLOBAL_BAL_001` as the default canonical portfolio until the platform contract
   approves a replacement.
4. Keep unsupported endpoint/archetype combinations visible as governed limitations.
5. Prefer expanding the matrix through `LOTUS_RISK_LIVE_PORTFOLIO_MATRIX_JSON` before editing
   individual endpoint tests.
