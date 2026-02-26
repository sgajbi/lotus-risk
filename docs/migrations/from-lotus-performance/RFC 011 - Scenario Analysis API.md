# RFC 011: Scenario Analysis API (Final)

**Status:** Final (For Approval)
**Owner:** Senior Architect
**Reviewers:** Perf Engine, Risk, Platform
**Related:** RFC-009 (Exposure Breakdown), RFC-008 (Fixed-Income Metrics)

## 1\. Executive Summary

This document specifies the final design for a new, forward-looking **Scenario Analysis & Stress Tests API** to be implemented at `/analytics/scenario`. The existing and planned services provide a comprehensive view of a portfolio's historical performance and current exposures. This API introduces the critical third pillar of analysis: understanding potential future outcomes by simulating the impact of market shocks.

The engine will provide a powerful, on-demand risk management utility capable of running three distinct types of scenarios: **hypothetical** (user-defined shocks), **historical** (replaying past market events), and **probabilistic** (Monte Carlo simulations). It will calculate the potential Profit & Loss (P\&L) at the instrument, group, and portfolio levels, with clear attribution to the underlying risk factors.

The API is designed for maximum flexibility, allowing users to choose between a fast, **sensitivity-based** approximation (using inputs like delta, gamma, DV01, and beta) and a more precise **full repricing** method for fixed-income instruments. The implementation will be integrated into our existing architecture, reusing foundational components and adhering to our highest standards of correctness, scalability, and resilience.

## 2\. Goals & Non-Goals

### Goals

  * Provide a stateless API to run scenario analysis and stress tests.
  * Support `hypothetical`, `historical`, and `monte_carlo` scenario modes.
  * Compute P\&L using either first/second-order **sensitivities** or **full repricing**.
  * Break down results by **risk factor** and by any **classification dimension** (e.g., asset class, sector).
  * For Monte Carlo mode, compute key tail risk metrics like **VaR (Value at Risk)** and **CVaR (Conditional Value at Risk)**.

### Non-Goals

  * The service will not source market data or sensitivities; the caller must provide all necessary inputs.
  * Advanced greeks for exotic derivatives are out of scope for v1.
  * The engine will not perform portfolio optimization or recommend hedges.

## 3\. Methodology

### 3.1. Valuation Methods

The engine supports two methods for calculating P\&L from a given shock.

1.  **Sensitivity-Based (Default)**: A fast and efficient method that approximates P\&L using an instrument's risk sensitivities.

      * **First-Order (Linear) P\&L**: $\\Delta V \\approx \\sum\_{f} S\_f \\cdot \\Delta f$, where $S\_f$ is the instrument's sensitivity to factor *f* (e.g., DV01, Beta) and $\\Delta f$ is the factor shock.
      * **Second-Order P\&L**: Includes curvature effects for a more accurate approximation: $\\Delta V \\approx \\sum\_{f} S\_f \\cdot \\Delta f + \\frac{1}{2} \\sum\_{f} \\Gamma\_f \\cdot (\\Delta f)^2$, where $\\Gamma\_f$ is the gamma or convexity.

2.  **Full Repricing**: A more accurate but computationally intensive method for fixed-income instruments. Instead of using sensitivities, the engine applies the scenario shocks directly to the yield curve and/or spread curve and fully reprices the instrument's cash flows. This naturally captures convexity and other non-linear effects.

### 3.2. Shock Application by Factor

The engine translates abstract scenario definitions into concrete P\&L calculations.

  * **Rates Shocks**: A parallel shift of `+100bp` is applied to all relevant tenors. The P\&L is calculated as $\\Delta V \\approx - \\sum\_{t} KRD\_t \\cdot (0.01)$. If only DV01 is provided, it's used as an approximation: $\\Delta V \\approx -DV01 \\cdot 100$.
  * **Equity Shocks**: For a shock of `-10%`, the P\&L is calculated as $\\Delta V \\approx \\beta \\cdot MV\_{equity} \\cdot (-0.10)$. For derivatives, the P\&L is $\\Delta V \\approx \\delta \\cdot \\text{UnderlyingNotional} \\cdot (-0.10)$.
  * **Credit & FX Shocks**: Similar logic is applied using Spread DV01 and FX delta sensitivities.

### 3.3. Scenario Modes

  * **Hypothetical**: The user provides an explicit set of shocks in the `scenario.layers` array.
  * **Historical**: The user specifies a historical window (e.g., the 2008 crisis). The engine uses the factor movements from that period (which must be supplied by the caller) as the shocks.
  * **Monte Carlo**: The engine generates thousands of random, correlated factor shocks based on user-provided statistical inputs (mean, volatility, correlation matrix). It calculates the P\&L for each path, creating a distribution of potential outcomes from which VaR and CVaR are derived.

## 4\. API Design

### 4.1. Endpoint

`POST /analytics/scenario`

### 4.2. Request Schema (Pydantic)

```json
{
  "portfolio_id": "RISK_ANALYSIS_01",
  "as_of": "2025-09-07",
  "mode": "hypothetical",
  "holdings": {
    "by": "instrument",
    "series": [
      {
        "instrumentId": "UST_2030",
        "meta": {"assetClass": "Bond"},
        "observations": [{ "date": "2025-09-07", "mv": 500000.0 }],
        "sensitivities": { "rates": { "dv01": 2500.0, "convexity_dollar": 1200.0 } }
      },
      {
        "instrumentId": "TECH_STOCK",
        "meta": {"assetClass": "Equity"},
        "observations": [{ "date": "2025-09-07", "mv": 500000.0 }],
        "sensitivities": { "equity": { "beta": 1.2 } }
      }
    ]
  },
  "scenario": {
    "name": "Rates Up 50bp, Equity Down 10%",
    "layers": [
      { "type": "rates", "shock": { "style": "parallel", "bump_bp": 50 } },
      { "type": "equity", "index": "SPX", "shock": { "pct": -0.10 } }
    ]
  },
  "valuation": { "method": "sensitivity", "order": "second" },
  "groupBy": ["assetClass"]
}
```

### 4.3. Response Schema

```json
{
  "as_of": "2025-09-07",
  "mode": "hypothetical",
  "scenario": { "name": "Rates Up 50bp, Equity Down 10%" },
  "valuation": { "method": "sensitivity", "order": "second" },
  "portfolio": {
    "mv_before": 1000000.0,
    "mv_after": 936000.0,
    "pnl": -64000.0,
    "return": -0.064
  },
  "by_factor": [
    { "factor": "RATES_PARALLEL", "pnl": -14000.0 },
    { "factor": "SPX", "pnl": -50000.0 }
  ],
  "by_group": [
    { "key": {"assetClass": "Bond"}, "pnl": -14000.0, "return": -0.028 },
    { "key": {"assetClass": "Equity"}, "pnl": -50000.0, "return": -0.10 }
  ],
  "meta": { ... },
  "diagnostics": { ... },
  "audit": { ... }
}
```

### 4.4. HTTP Semantics & Errors

  * **200 OK**: Successful computation.
  * **400 Bad Request**: Schema or validation errors.
  * **422 Unprocessable Entity**: Request is valid, but data is insufficient (e.g., sensitivities missing for all instruments).
  * **413 Payload Too Large**: Request payload exceeds configured limits.

## 5\. Architecture & Implementation Plan

1.  **Create new modules**:
      * `engine/scenarios.py`: To house the core logic for shock application, P\&L calculation, and Monte Carlo simulation.
      * `app/models/scenario_requests.py` and `app/models/scenario_responses.py`: To define the API contract.
2.  **Create new endpoint router**:
      * Create `app/api/endpoints/analytics.py` with a router for `/analytics`.
      * Implement the `POST /analytics/scenario` endpoint.
3.  **Update `main.py`**:
      * Register the new `/analytics` router with the FastAPI application.

## 6\. Testing & Validation Strategy

  * **Unit Tests**: The new `engine/scenarios.py` module must achieve **100% test coverage**. This will include validating P\&L calculations against manual, formula-based results for each sensitivity type (DV01, KRD, beta, delta, convexity), as well as testing the Monte Carlo engine's statistical properties (e.g., mean, variance) with a fixed seed.
  * **Integration Tests**: API-level tests will validate the end-to-end flow for each of the three modes (`hypothetical`, `historical`, `monte_carlo`), ensuring that request flags correctly control the engine's behavior and that the response structure is accurate.
  * **Characterization Test**: A test will be created using a realistic multi-asset portfolio and a composite shock. The API's P\&L results will be validated against a reference calculation from a Jupyter notebook to ensure numerical correctness.
  * **Overall Coverage**: The overall project test coverage must remain at or above **95%**.

## 7\. Acceptance Criteria

The implementation of this RFC is complete when:

1.  This RFC is formally approved by all stakeholders.
2.  All new modules are created and fully integrated into the existing architecture.
3.  The `POST /analytics/scenario` endpoint is fully functional, supporting all three modes and valuation methods as specified.
4.  The testing and validation strategy is fully implemented, all tests are passing, and the required coverage targets (**100% for engine**, **≥95% for project**) are met.
5.  The characterization test passes, confirming numerical results match the external reference.
6.  New documentation is added to `docs/guides/` and `docs/technical/` for the Scenario Analysis API, ensuring documentation remains current.
