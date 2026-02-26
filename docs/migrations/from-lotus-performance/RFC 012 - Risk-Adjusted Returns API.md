# RFC 012: Risk-Adjusted Returns API (Final)

**Status:** Final (For Approval)
**Owner:** Senior Architect
**Reviewers:** Perf Engine, Risk, Platform
**Related:** RFC-006 (Attribution), RFC-009 (Exposure Breakdown)

## 1\. Executive Summary

This document specifies the final design for a new, comprehensive **Risk-Adjusted Returns & Statistics API** to be implemented at `/analytics/riskMetrics`. While the existing services provide accurate return calculations, this API significantly deepens our "Performance" pillar by introducing a full suite of industry-standard risk and risk-adjusted metrics.

The engine will provide a powerful, on-demand utility to compute **volatility, downside risk, drawdowns, tail risk (VaR/CVaR)**, and a wide array of summary ratios like the **Sharpe Ratio, Sortino Ratio, Information Ratio, and Calmar Ratio**. The API is designed to be highly configurable, supporting both **absolute** and **benchmark-relative** analysis across **snapshot, timeseries, and rolling-window** modes.

This feature is critical for providing a complete performance picture, allowing portfolio managers to assess not just the return, but the *quality* and *riskiness* of that return. The implementation will follow our established architectural patterns, ensuring the engine is robust, correct, and scalable.

## 2\. Goals & Non-Goals

### Goals

  * Provide a stateless API to compute a comprehensive set of risk and risk-adjusted performance statistics from a return series.
  * Support both **absolute** (vs. a risk-free rate) and **active** (vs. a benchmark) metrics.
  * Offer flexible analysis modes: `snapshot` for a single period, `rolling` for time-varying analysis, and `timeseries` for raw data output.
  * Be highly configurable, allowing users to select exactly which metrics to compute.
  * Provide advanced options for tail-risk calculation (historical, parametric, Cornish-Fisher).

### Non-Goals

  * The API is purely computational and will not source or store any time series data.
  * It will not perform portfolio optimization or construction.
  * It will not automatically fetch holdings to derive returns; the caller must supply the return or price series.

## 3\. Methodology

The engine operates on one to three aligned time series: portfolio returns ($r^p\_t$), benchmark returns ($r^b\_t$), and a risk-free rate ($r^f\_t$). An annualization factor, *A*, is used (e.g., 252 for daily, 12 for monthly).

### 3.1. Core Performance & Volatility

  * **Cumulative Return**: $R\_{cum} = \\prod (1+r\_t) - 1$
  * **Annualized Geometric Mean (CAGR)**: $(1+R\_{cum})^{A/T} - 1$
  * **Annualized Volatility**: $\\sigma\_{ann} = \\sqrt{A} \\cdot \\text{stdev}(r\_t)$
  * **Downside Deviation (MAR m)**: Measures volatility of returns below a minimum acceptable return, *m*.
    $D = \\sqrt{A \\cdot \\frac{1}{T}\\sum\_t \\max(m - r\_t, 0)^2 }$

### 3.2. Benchmark-Relative Metrics

  * **Active Return**: $a\_t = r^p\_t - r^b\_t$
  * **Tracking Error (Annualized)**: $\\text{TE} = \\sqrt{A} \\cdot \\text{stdev}(a\_t)$
  * **Beta ($\\beta$) & Alpha ($\\alpha$)**: Standard OLS regression coefficients from the CAPM model: $(r^p\_t - r^f\_t) = \\alpha + \\beta \\cdot (r^b\_t - r^f\_t) + \\epsilon\_t$.

### 3.3. Risk-Adjusted Ratios

  * **Sharpe Ratio**: $\\frac{\\bar{r}^p\_{ann} - \\bar{r}^f\_{ann}}{\\sigma\_{ann}}$
  * **Sortino Ratio**: $\\frac{\\bar{r}^p\_{ann} - \\text{MAR}}{D\_{ann}}$
  * **Information Ratio**: $\\frac{\\bar{a}\_{ann}}{\\text{TE}}$
  * **Calmar Ratio**: $\\frac{\\text{CAGR}}{|\\text{Max Drawdown}|}$

### 3.4. Tail Risk Analysis

  * **Historical VaR/CVaR**: The empirical quantile (VaR) of the return distribution and the average of returns below that quantile (CVaR).
  * **Parametric VaR/CVaR**: Calculated using the mean and standard deviation, assuming a Normal distribution.
  * **Cornish-Fisher VaR**: An enhancement to parametric VaR that adjusts for the skewness and kurtosis of the return distribution.

### 3.5. Drawdown Analysis

The engine calculates the portfolio's equity curve over time to identify periods of loss.

  * **Max Drawdown**: The largest peak-to-trough decline.
  * **Average Drawdown**: The average of all drawdown periods.
  * **Ulcer Index**: A measure of the depth and duration of drawdowns.

## 4\. API Design

### 4.1. Endpoint

`POST /analytics/riskMetrics`

### 4.2. Request Schema (Pydantic)

```json
{
  "portfolio_id": "RISK_METRICS_01",
  "as_of": "2025-09-07",
  "mode": "snapshot",
  "timeseries_kind": "returns",
  "frequency": "M",
  "portfolio": {
    "label": "MyPortfolio",
    "observations": [ {"date": "2024-09-30", "value": 0.015}, {"date": "2024-10-31", "value": -0.02}, ... ]
  },
  "benchmark": {
    "label": "MyBenchmark",
    "observations": [ {"date": "2024-09-30", "value": 0.012}, {"date": "2024-10-31", "value": -0.018}, ... ]
  },
  "risk_free": {
    "observations": [ {"date": "2024-09-30", "value": 0.003}, ... ]
  },
  "alignment": { "mode": "intersection", "min_obs": 12 },
  "metrics": {
    "volatility": true,
    "sharpe": true,
    "tracking_error": true,
    "information_ratio": true,
    "tail": { "enabled": true, "method": "historical", "levels": [0.95, 0.99] },
    "drawdowns": { "enabled": true, "ulcer": true }
  },
  "conventions": { "annualization": { "periods_per_year": 12 } }
}
```

### 4.3. Response Schema

```json
{
  "as_of": "2025-09-07",
  "window": { "start": "2024-10-31", "end": "2025-09-07", "n_obs": 12 },
  "portfolio": {
    "cagr": 0.085,
    "vol_ann": 0.152,
    "sharpe": 0.36,
    "tail": {
      "VaR": { "0.95": -0.051, "0.99": -0.082 },
      "CVaR": { "0.95": -0.065, "0.99": -0.098 }
    },
    "drawdowns": { "max": -0.125, "ulcer": 0.045 }
  },
  "active": {
    "mean_ann": 0.015,
    "tracking_error": 0.045,
    "information_ratio": 0.33
  },
  "meta": { ... },
  "diagnostics": { ... },
  "audit": { ... }
}
```

### 4.4. HTTP Semantics & Errors

  * **200 OK**: Successful computation.
  * **400 Bad Request**: Schema or validation errors.
  * **422 Unprocessable Entity**: Request is valid, but data is insufficient (e.g., fewer observations than `min_obs` after alignment).
  * **413 Payload Too Large**: Request payload exceeds configured limits.

## 5\. Architecture & Implementation Plan

1.  **Create new modules**:
      * `engine/risk.py`: To house the core logic for calculating all statistical metrics.
      * `app/models/risk_requests.py` and `app/models/risk_responses.py`: To define the API contract.
2.  **Update endpoint router**:
      * Add the `POST /analytics/riskMetrics` endpoint to `app/api/endpoints/analytics.py`.
3.  **Implementation Steps**:
      * Implement the pre-processing logic for aligning and cleaning time series.
      * Implement each metric as a separate, pure function.
      * Create orchestrator functions for `snapshot` and `rolling` modes.

## 6\. Testing & Validation Strategy

  * **Unit Tests**: The new `engine/risk.py` module must achieve **100% test coverage**. This will include tests for each individual metric, validating its output against known results from financial formulas and trusted libraries. Edge cases like insufficient data or zero volatility must be covered.
  * **Integration Tests**: API-level tests will validate the end-to-end flow, ensuring the `metrics` toggles correctly shape the response and that all `mode` and `convention` settings are respected.
  * **Characterization Test**: A test will be created using a realistic, multi-year return series. The API's output for all key metrics (Sharpe, Max Drawdown, VaR, IR, etc.) will be validated against a reference calculation from a well-regarded open-source financial library (e.g., `empyrical`) to ensure numerical correctness.
  * **Overall Coverage**: The overall project test coverage must remain at or above **95%**.

## 7\. Acceptance Criteria

The implementation of this RFC is complete when:

1.  This RFC is formally approved by all stakeholders.
2.  All new modules are created and fully integrated into the existing architecture.
3.  The `POST /analytics/riskMetrics` endpoint is fully functional, supporting all specified metrics, modes, and conventions.
4.  The testing and validation strategy is fully implemented, all tests are passing, and the required coverage targets (**100% for engine**, **≥95% for project**) are met.
5.  The characterization test passes, confirming numerical results match the external reference library.
6.  New documentation is added to `docs/guides/` and `docs/technical/` for the Risk-Adjusted Returns API, ensuring documentation remains current.
