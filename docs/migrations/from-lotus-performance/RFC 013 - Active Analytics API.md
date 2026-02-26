 

# RFC 013: Active Analytics API (Final)

**Status:** Final (For Approval)
**Owner:** Senior Architect
**Reviewers:** Perf Engine, Risk, Platform
**Related:** RFC-006 (Attribution), RFC-009 (Exposure Breakdown), RFC-012 (Risk Metrics)

## 1\. Executive Summary

This document specifies the final design for a new, unified **Active Analytics API** to be implemented at `/portfolio/activeAnalytics`. While the existing services can explain historical active *return* (Attribution) and the planned services can show absolute *exposure* (Exposure Breakdown), there is no single endpoint that provides a comprehensive, benchmark-relative view across a portfolio's composition, risk, and returns.

This API bridges that gap. It provides a powerful, one-stop service for portfolio managers to analyze their active decisions. The engine will compute **active weights**, **Active Share**, **tracking error**, **information ratio**, **up/down capture ratios**, and **group-level active contributions**. Optionally, it can integrate with our factor and fixed-income models to deliver **active factor tilts** and **active duration differentials**.

The API is designed to be highly configurable, allowing users to select only the metrics they need. It supports **snapshot**, **timeseries**, and **rolling-window** analysis. The implementation will reuse existing engine components for maximum efficiency and consistency, adhering to our established architectural patterns and rigorous testing standards.

## 2\. Goals & Non-Goals

### Goals

  * Provide a single endpoint for a comprehensive comparison of a portfolio against its benchmark.
  * Calculate key active weight metrics, including **Active Share** and **top over/underweights**.
  * Compute a full suite of ex-post active return statistics, including **Tracking Error**, **Information Ratio**, and **capture ratios**.
  * Decompose active contributions by any classification dimension (e.g., sector, region).
  * Optionally integrate with factor models to show **active factor tilts** and **ex-ante active risk**.
  * Support snapshot, timeseries, and rolling-window modes.

### Non-Goals

  * This API will not perform Brinson-style attribution (A/S/I), which is the domain of RFC-006.
  * It is a stateless, computational API and will not acquire data from external sources.
  * It will not perform portfolio optimization or rebalancing.

## 3\. Methodology

The engine will perform a series of calculations based on the user's request, using aligned portfolio and benchmark data.

### 3.1. Input Processing & Alignment

The engine first normalizes portfolio and benchmark holdings to generate weights for the `as_of` date. If return series are provided, they are aligned to a common date index, and an active return series ($a\_t = r^{p}\_t - r^{b}\_t$) is created.

### 3.2. Active Weights & Concentration

  * **Active Weight**: The fundamental building block is the active weight for each instrument *j*: $a\_j = w\_j - b\_j$, where *w* is the portfolio weight and *b* is the benchmark weight.
  * **Active Share**: A measure of how different the portfolio is from the benchmark, calculated as: $AS = \\frac{1}{2} \\sum\_j |w\_j - b\_j|$.
  * **Weight Overlap**: A measure of similarity, calculated as: $\\Omega = \\sum\_j \\min(w\_j, b\_j)$.

### 3.3. Active Return Statistics

Using the active return series ($a\_t$), the engine computes a suite of risk-adjusted performance metrics:

  * **Tracking Error (Annualized)**: The standard deviation of active returns, annualized: $TE = \\sqrt{A} \\cdot \\text{stdev}(a\_t)$, where A is the annualization factor.
  * **Information Ratio**: The ratio of annualized active return to tracking error: $IR = \\frac{\\text{mean}(a\_t) \\cdot A}{TE}$.
  * **Up/Down Capture Ratios**: Measures portfolio performance in periods of positive or negative benchmark returns, providing insight into market timing skill.

### 3.4. Group-Level Differentials & Contribution

For a chosen `dimension` (e.g., sector), the engine calculates:

  * **Weight Differential**: The active weight at the group level: $\\Delta w\_i = w\_i - b\_i$.
  * **Active Contribution**: The group's contribution to total active return. To ensure correctness over multiple periods, this is calculated by linking daily active contributions ($c\_{i,t} = w\_{i,t} r^p\_{i,t} - b\_{i,t} r^b\_{i,t}$) using the robust **Carino smoothing algorithm**, reusing the logic from the Contribution engine.

### 3.5. Active Risk & Factor Tilts (Optional)

If factor model data is provided, the engine computes:

  * **Active Factor Tilt**: The difference in exposure to each risk factor: $\\Delta\\beta = \\beta\_p - \\beta\_b$.
  * **Ex-Ante Active Risk (Tracking Error)**: The predicted tracking error based on active factor tilts and active specific risk: $TE\_{ex-ante} \\approx \\sqrt{(\\Delta\\beta)^T \\Sigma\_f (\\Delta\\beta) + \\sigma^2\_{spec,act}}$.

## 4\. API Design

### 4.1. Endpoint

`POST /portfolio/activeAnalytics`

### 4.2. Request Schema (Pydantic)

```json
{
  "portfolio_id": "PORT123",
  "as_of": "2025-08-31",
  "mode": "snapshot",
  "dimension": "sector",
  "holdings": {
    "by": "instrument",
    "series": [
      {"instrumentId": "AAPL", "meta": {"sector": "Tech"}, "observations": [{"date": "2025-08-31", "mv": 70000}]}
    ]
  },
  "benchmark_holdings": {
    "series": [
      {"instrumentId": "SPY", "observations": [{"date": "2025-08-31", "mv": 1000000}], "lookthrough": {"weights": {"AAPL": 0.06}}}
    ]
  },
  "returns": {
    "portfolio": [ {"date": "2025-08-31", "value": 0.012} ],
    "benchmark": [ {"date": "2025-08-31", "value": 0.010} ],
    "kind": "returns"
  },
  "factor_model": {
    "exposures": {"portfolio": {"MKT": 1.02}, "benchmark": {"MKT": 1.00}}
  },
  "metrics": {
    "active_share": true,
    "active_return_stats": true,
    "group_differentials": true,
    "top_over_under": {"enabled": true, "k": 5},
    "factor_tilts": true
  }
}
```

### 4.3. Response Schema

```json
{
  "as_of": "2025-08-31",
  "summary": {
    "active_share": 0.34,
    "te_ann": 0.052,
    "ir": 0.36,
    "up_capture": 1.05,
    "down_capture": 0.92
  },
  "weights": {
    "top_overweights": [ {"id": "AAPL", "w_p": 0.07, "w_b": 0.06, "delta": 0.01} ],
    "top_underweights": []
  },
  "groups": [
    {"key": {"sector": "Tech"}, "w_p": 0.28, "w_b": 0.22, "delta_w": 0.06, "active_contribution": 0.0042}
  ],
  "factors": {
    "tilts": {"MKT": 0.02}
  },
  "meta": { ... },
  "diagnostics": { ... },
  "audit": { ... }
}
```

### 4.4. HTTP Semantics & Errors

  * **200 OK**: Successful computation.
  * **400 Bad Request**: Schema validation errors or logically inconsistent requests.
  * **422 Unprocessable Entity**: Request is valid, but data is insufficient (e.g., fewer observations than required for TE calculation).
  * **413 Payload Too Large**: Request payload exceeds configured limits.

## 5\. Architecture & Implementation Plan

1.  **Create new modules**:
      * `engine/active.py`: To house the core logic for calculating all active metrics. This module will reuse helpers from `engine/risk.py` (for TE/IR), `engine/exposure.py` (for grouping), and `engine/contribution.py` (for Carino linking).
      * `app/models/active_requests.py` and `app/models/active_responses.py`: To define the API contract.
2.  **Update endpoint router**:
      * Add the `POST /portfolio/activeAnalytics` endpoint to `app/api/endpoints/portfolio.py`.
3.  **Implement Engine Logic**:
      * First, implement the weight-based metrics (Active Share, differentials).
      * Next, implement the return-based statistics.
      * Finally, add the optional integrations for factor and fixed-income active metrics.

## 6\. Testing & Validation Strategy

  * **Unit Tests**: The new `engine/active.py` module must have **100% test coverage**. This includes tests for Active Share (for both long-only and long/short portfolios), TE/IR calculations, group differential aggregation with Carino linking, and active risk decomposition.
  * **Integration Tests**: API-level tests will validate the end-to-end flow for snapshot, timeseries, and rolling modes. Tests will also ensure the `metrics` toggles correctly shape the response, returning only the requested calculations.
  * **Characterization Test**: A test will be created comparing the API's output for a realistic portfolio against a pre-calculated result from a reference Jupyter notebook to ensure numerical precision and correctness.
  * **Overall Coverage**: The overall project test coverage must remain at or above **95%**.

## 7\. Acceptance Criteria

The implementation of this RFC is complete when:

1.  This RFC is formally approved by all stakeholders.
2.  All new modules (`engine/active.py`, `app/models/active_*.py`) are created and fully integrated.
3.  The `POST /portfolio/activeAnalytics` endpoint is functional and meets all requirements specified in this document.
4.  The testing strategy is fully implemented, with all tests passing and the required coverage targets (**100% for engine**, **≥95% for project**) met.
5.  The characterization test passes, confirming numerical results match the external reference.
6.  New documentation is added to `docs/guides/` and `docs/technical/` for the Active Analytics API, ensuring our documentation stays current with the codebase.
