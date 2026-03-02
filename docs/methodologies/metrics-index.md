# Lotus-Risk Metrics Methodology Index

This index provides one methodology document per Lotus-Risk metric with formulas, inputs/sources, outputs, configuration, supported modes, and worked examples.

## Methodology Standards
- Unit convention:
  - `risk/calculate` request returns are percentage points (`1.0` means `1%`).
  - `rolling` and `attribution` internals normalize returns to decimal before formula application.
  - concentration values use weights in decimal and HHI scaled to `0..10000`.
- Determinism:
  - each metric doc reflects current implementation behavior in `lotus-risk` `main`.
  - deterministic error behaviors are documented for data insufficiency and missing dependencies.
- Domain ownership:
  - `lotus-risk` computes metrics only.
  - upstream systems provide canonical inputs:
    - `lotus-performance`: return series
    - `lotus-core`: portfolio state, instrument/issuer enrichment, exposure history contracts

## Status Matrix
- Fully implemented:
  - all metrics under `risk/calculate`
  - all metrics under `risk/rolling-metrics`
  - all metrics under `risk/concentration`
  - all metrics under `risk/drawdown`
  - `ATTRIBUTION_VOLATILITY` under `risk/historical-attribution`
- Partially implemented:
  - `ATTRIBUTION_TRACKING_ERROR`:
    - stateless supported
    - stateful path blocked pending benchmark exposure-history contract from `lotus-core`

## Risk Calculate Metrics (`/analytics/risk/calculate`)
- [VOLATILITY](./metrics/risk-volatility.md)
- [DRAWDOWN](./metrics/risk-drawdown.md)
- [SHARPE](./metrics/risk-sharpe.md)
- [SORTINO](./metrics/risk-sortino.md)
- [BETA](./metrics/risk-beta.md)
- [TRACKING_ERROR](./metrics/risk-tracking-error.md)
- [INFORMATION_RATIO](./metrics/risk-information-ratio.md)
- [VAR](./metrics/risk-var.md)

## Rolling Metrics (`/analytics/risk/rolling-metrics`)
- [ROLLING_VOLATILITY](./metrics/rolling-volatility.md)
- [ROLLING_SHARPE](./metrics/rolling-sharpe.md)
- [ROLLING_BETA](./metrics/rolling-beta.md)
- [ROLLING_TRACKING_ERROR](./metrics/rolling-tracking-error.md)
- [ROLLING_INFORMATION_RATIO](./metrics/rolling-information-ratio.md)
- [ROLLING_MAX_DRAWDOWN](./metrics/rolling-max-drawdown.md)

## Concentration Metrics (`/analytics/risk/concentration`)
- [POSITION_HHI](./metrics/concentration-hhi.md)
- [TOP_POSITION_WEIGHT](./metrics/concentration-top-position-weight.md)
- [TOP_N_CUMULATIVE_WEIGHT](./metrics/concentration-top-n-cumulative-weight.md)
- [ISSUER_HHI](./metrics/concentration-issuer-hhi.md)
- [TOP_ISSUER_WEIGHT](./metrics/concentration-top-issuer-weight.md)

## Drawdown Analytics Metrics (`/analytics/risk/drawdown`)
- [MAX_DRAWDOWN](./metrics/drawdown-max-drawdown.md)
- [TIME_UNDER_WATER_DAYS](./metrics/drawdown-time-under-water.md)
- [AVERAGE_DRAWDOWN](./metrics/drawdown-average-drawdown.md)
- [ULCER_INDEX](./metrics/drawdown-ulcer-index.md)
- [DRAWDOWN_AT_RISK_AND_CDAR](./metrics/drawdown-dar-cdar.md)
- [RELATIVE_MAX_DRAWDOWN](./metrics/drawdown-relative-max-drawdown.md)

## Historical Attribution Metrics (`/analytics/risk/historical-attribution`)
- [ATTRIBUTION_VOLATILITY](./metrics/attribution-volatility.md)
- [ATTRIBUTION_TRACKING_ERROR](./metrics/attribution-tracking-error.md)

## Notes
- Stateful active tracking-error attribution is currently partial/pending benchmark exposure-history upstream contract.
- All docs are aligned to current implementation in `main`.
