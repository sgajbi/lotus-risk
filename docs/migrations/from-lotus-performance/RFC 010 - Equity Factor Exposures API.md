# RFC 010: Equity Factor Exposures API (Final)

**Status:** Final (For Approval)
**Owner:** Senior Architect
**Reviewers:** Perf Engine, Risk, Platform
**Related:** RFC-009 (Exposure Breakdown), RFC-013 (Active Analytics)

## 1\. Executive Summary

This document specifies the final design for a new, sophisticated **Equity Factor Exposures API** to be implemented at `/portfolio/factorExposure`. This API elevates the platform's analytical capabilities beyond simple categorical breakdowns into the realm of modern, quantitative risk analysis. It provides portfolio managers with the critical ability to understand and manage their portfolio's exposure to common risk factors like **Value, Momentum, Size, and Quality**.

The engine is designed with a powerful dual-methodology approach:

1.  **Holdings-Based**: Aggregating security-level factor exposures for a precise, bottom-up view of the portfolio's risk profile.
2.  **Time-Series Regression**: Regressing historical portfolio returns against factor returns to derive a top-down, behavior-based estimate of factor betas.

The API is highly configurable, supporting both absolute and benchmark-relative analysis, industry neutralization, and optional extensions for **factor risk decomposition** and **factor return contribution**. This feature is a cornerstone of advanced portfolio analysis, enabling managers to control unintended bets, verify strategic tilts, and explain performance through the lens of risk factors.

## 2\. Goals & Non-Goals

### Goals

  * Compute portfolio and benchmark exposures to standard equity style, industry, and country risk factors.
  * Support both a **holdings-based** and a **time-series regression** methodology.
  * Provide **active exposures** (portfolio vs. benchmark).
  * Optionally decompose portfolio risk into **factor vs. specific risk** contributions.
  * Optionally calculate the **contribution to return** from each factor.

### Non-Goals

  * The API will not source factor data (exposures, returns, or covariance matrices); the caller must provide it.
  * The v1 implementation is scoped to **equities** and equity derivatives.
  * It is a stateless, computational API and will not store any results.

## 3\. Methodology

### 3.1. Holdings-Based (HB) Methodology

This bottom-up approach calculates the portfolio's factor exposure as the weighted average of the exposures of its constituent securities.

  * **Portfolio Factor Exposure ($\\beta\_p$)**:
    $$\beta_p = \sum_{j} w_j \cdot x_j$$
    Where $w\_j$ is the weight of security *j* and $x\_j$ is its vector of factor exposures.
  * **Active Exposure**: The portfolio's factor exposure minus the benchmark's: $\\Delta\\beta = \\beta\_p - \\beta\_b$.
  * **Factor Normalization (Optional)**: For advanced use cases, the engine can construct factor exposures from raw descriptors (e.g., Book-to-Price) by performing standard normalization steps like winsorization, z-scoring, and neutralization against other factors (e.g., industry).

### 3.2. Time-Series Regression (TS) Methodology

This top-down approach infers factor exposures by analyzing the historical relationship between portfolio returns and factor returns.

  * **Regression Model**: The engine runs a time-series regression of portfolio excess returns against factor returns over a specified lookback window.
    $$(R_{p,t} - R_{f,t}) = \alpha + \beta_{TS}^T \cdot f_t + \epsilon_t$$
    Where $R\_{p,t}$ is the portfolio return, $R\_{f,t}$ is the risk-free rate, $f\_t$ is the vector of factor returns, and $\\beta\_{TS}$ is the resulting vector of factor exposures (betas). The engine supports **OLS** and **Ridge** estimators.

### 3.3. Optional Extensions

  * **Factor Risk Decomposition**: If a factor covariance matrix ($\\Sigma\_f$) is provided, the engine calculates the portfolio's ex-ante factor variance: $\\sigma^2\_{fac,p} = \\beta\_p^T \\Sigma\_f \\beta\_p$.
  * **Factor Return Contribution**: If factor returns for a period are provided, the contribution of each factor *k* to the portfolio's return is calculated as: $\\text{Contrib}*k = \\sum\_t \\beta\_k \\cdot f*{k,t}$.

## 4\. API Design

### 4.1. Endpoint

`POST /portfolio/factorExposure`

### 4.2. Request Schema (Pydantic)

```json
{
  "portfolio_id": "FACTOR_TEST_01",
  "as_of": "2025-09-07",
  "mode": "snapshot",
  "model": {
    "name": "Custom 5-Factor",
    "factors": ["MKT", "SIZE", "VALUE", "MOM", "QUAL"]
  },
  "holdings": {
    "by": "instrument",
    "series": [
      {
        "instrumentId": "AAPL",
        "observations": [{ "date": "2025-09-07", "mv": 100000.0 }],
        "exposures": { "MKT": 1.1, "SIZE": -0.8, "VALUE": -0.5, "MOM": 0.4, "QUAL": 0.9 }
      },
      {
        "instrumentId": "XOM",
        "observations": [{ "date": "2025-09-07", "mv": 80000.0 }],
        "exposures": { "MKT": 0.9, "SIZE": 0.6, "VALUE": 0.7, "MOM": -0.2, "QUAL": 0.4 }
      }
    ]
  },
  "benchmark_holdings": { "series": [] },
  "risk": { "fcm": null },
  "output": { "include_active": true }
}
```

### 4.3. Response Schema

```json
{
  "as_of": "2025-09-07",
  "model": { "name": "Custom 5-Factor" },
  "method": "holdings",
  "portfolio": {
    "exposures": {
      "MKT": 1.011,
      "SIZE": -0.178,
      "VALUE": 0.011,
      "MOM": 0.133,
      "QUAL": 0.678
    },
    "risk": null
  },
  "benchmark": { "exposures": {} },
  "active": { "exposures": { ... } },
  "meta": { ... },
  "diagnostics": { ... },
  "audit": { ... }
}
```

### 4.4. HTTP Semantics & Errors

  * **200 OK**: Successful computation.
  * **400 Bad Request**: Schema or validation errors.
  * **422 Unprocessable Entity**: Request is valid, but data is insufficient (e.g., not enough historical returns for regression, or holdings coverage is too low).
  * **413 Payload Too Large**: Request payload exceeds configured limits.

## 5\. Architecture & Implementation Plan

1.  **Create new modules**:
      * `engine/factors.py`: To house the core logic for both holdings-based aggregation and time-series regression.
      * `app/models/factor_requests.py` and `app/models/factor_responses.py`: To define the API contract.
2.  **Update endpoint router**:
      * Add the `POST /portfolio/factorExposure` endpoint to `app/api/endpoints/portfolio.py`.
3.  **Implementation Steps**:
      * Implement the holdings-based aggregation path first, as it's the most direct.
      * Implement the time-series regression path, adding a dependency on a statistical library like `statsmodels`.
      * Layer in the optional risk and return contribution calculations.

## 6\. Testing & Validation Strategy

  * **Unit Tests**: The new `engine/factors.py` module must achieve **100% test coverage**. This will include tests for the HB aggregation math, the descriptor normalization pipeline, OLS and Ridge regression outputs, and the optional risk/contribution calculations.
  * **Integration Tests**: API-level tests will validate the end-to-end flow for all three modes (`snapshot`, `timeseries`, `regression`), ensuring that request flags correctly control the engine's behavior.
  * **Characterization Test**: A suite of tests will validate the numerical output against trusted external libraries:
      * The holdings-based aggregation will be checked against a reference calculation in a Pandas notebook.
      * The time-series regression output (betas, alpha, R²) will be validated against the output of Python's `statsmodels` library.
  * **Overall Coverage**: The overall project test coverage must remain at or above **95%**.

## 7\. Acceptance Criteria

The implementation of this RFC is complete when:

1.  This RFC is formally approved by all stakeholders.
2.  All new modules are created and fully integrated into the existing architecture.
3.  The `POST /portfolio/factorExposure` endpoint is fully functional, supporting all specified methodologies and features.
4.  The testing and validation strategy is fully implemented, all tests are passing, and the required coverage targets (**100% for engine**, **≥95% for project**) are met.
5.  The characterization tests pass, confirming numerical results match the external reference libraries.
6.  New documentation is added to `docs/guides/` and `docs/technical/` for the Equity Factor Exposures API.
