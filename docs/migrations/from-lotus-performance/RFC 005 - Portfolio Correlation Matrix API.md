Here is the detailed, refined RFC 005 for approval.

-----

# RFC 005: Portfolio Correlation Matrix API (Final)

**Status:** Final (For Approval)
**Owner:** Senior Architect
**Reviewers:** Perf Engine, Risk, Platform
**Related:** RFC-012 (Risk-Adjusted Returns)

## 1\. Executive Summary

This document specifies the final design for a new **Portfolio Correlation Matrix API** to be implemented at `/portfolio/correlationMatrix`. This API addresses the critical need for portfolio managers to assess **diversification** and the **co-movement** of assets within a portfolio. Understanding these relationships is fundamental to managing portfolio risk.

The engine will provide a robust, on-demand utility to compute a correlation matrix from a set of time series. It is designed for maximum flexibility, supporting both **Pearson (standard)** and **Spearman (rank-based)** correlation. The API can ingest either raw **prices** or pre-calculated **returns** and includes powerful, configurable policies for **data alignment** and **missing value handling**.

In line with our architectural principles, the API is highly configurable, stateless, and follows the established patterns of the lotus-performance suite. It will support advanced features like **pre-aggregation by group** (e.g., sector-level correlations) and **rolling window analysis**. This feature will serve as a key building block for more advanced risk and optimization tools.

## 2\. Goals & Non-Goals

### Goals

  * Provide a robust, numerically stable correlation matrix calculation.
  * Support both **Pearson** and **Spearman** correlation methods.
  * Accept time series of either **prices or returns**, with configurable return derivation logic.
  * Implement transparent and configurable policies for aligning series and handling missing data.
  * Optionally aggregate instrument-level series into groups (e.g., by sector, asset class) before computing correlations.
  * Offer results as a full **matrix** or a flattened **edge list**, with filtering for easier analysis.

### Non-Goals

  * The API is stateless and will not store or schedule calculations.
  * It will not perform advanced covariance matrix adjustments like shrinkage.
  * The caller is responsible for providing all time series data.

## 3\. Methodology

The engine follows a clear, multi-step process to transform raw time series into a correlation matrix.

### 3.1. Input Processing & Return Calculation

The engine first pivots the input series into a wide-format panel (dates x assets). If the `timeseries_kind` is `prices`, it then calculates returns based on the `return_method`:

  * **simple**: $r\_t = (P\_t / P\_{t-1}) - 1$
  * **log**: $r\_t = \\ln(P\_t) - \\ln(P\_{t-1})$

### 3.2. Alignment & Missing Data

A common date index is constructed based on the `alignment.mode`.

  * **`intersection`**: Only dates where all series have a value are kept.
  * **`union`**: All dates across all series are kept, creating gaps (NaNs) for missing data.

Missing data is then handled by the `alignment.missing` policy:

  * **`pairwise_drop`**: For each pair of assets being correlated, only the dates where both have data are used. This maximizes the data used for each individual calculation.
  * **`fill_forward`**: Fills NaN values with the last valid observation, up to a specified limit.

### 3.3. Correlation Calculation

The correlation is computed on the cleaned and aligned return panel.

  * **Pearson (Default)**: Measures the linear relationship between two variables.
    $$\rho(X,Y) = \frac{\text{cov}(X,Y)}{\sigma_X \sigma_Y}$$
  * **Spearman**: Measures the monotonic relationship. It is calculated by converting each series to ranks and then computing the Pearson correlation of the ranks. This method is less sensitive to outliers.

### 3.4. Optional Grouping & Rolling Windows

  * **Grouping**: If a `grouping.dimension` is provided, the engine first aggregates the instrument-level return series into group-level series (e.g., by calculating the cap-weighted average return for each sector) before computing the correlations.
  * **Rolling Window**: If `roll.enabled` is true, the engine applies the entire calculation process to a trailing window of the specified length over the time series, returning the correlation matrix for the most recent period.

## 4\. API Design

### 4.1. Endpoint

`POST /portfolio/correlationMatrix`

### 4.2. Request Schema (Pydantic)

```json
{
  "portfolio_id": "CORR_MATRIX_01",
  "timeseries_kind": "prices",
  "return_method": "log",
  "frequency": "D",
  "correlation": { "method": "pearson" },
  "alignment": {
    "mode": "intersection",
    "missing": "pairwise_drop",
    "min_overlap": 20
  },
  "series": [
    {
      "id": "AAPL",
      "observations": [
        { "date": "2025-01-02", "value": 198.32 },
        { "date": "2025-01-03", "value": 199.50 }
      ]
    },
    {
      "id": "MSFT",
      "observations": [
        { "date": "2025-01-02", "value": 405.10 },
        { "date": "2025-01-03", "value": 406.00 }
      ]
    }
  ],
  "output": {
    "format": "matrix"
  }
}
```

### 4.3. Response Schema

```json
{
  "as_of": null,
  "method": "pearson",
  "frequency": "D",
  "labels": ["AAPL", "MSFT"],
  "matrix": [
    [ 1.0, 0.821 ],
    [ 0.821, 1.0 ]
  ],
  "pairwise_n": [
    [ 252, 251 ],
    [ 251, 252 ]
  ],
  "meta": { ... },
  "diagnostics": { ... },
  "audit": { ... }
}
```

### 4.4. HTTP Semantics & Errors

  * **200 OK**: Successful computation.
  * **400 Bad Request**: Schema or validation errors (e.g., fewer than 2 series provided).
  * **422 Unprocessable Entity**: Request is valid, but data is insufficient (e.g., no pairs meet the `min_overlap` after alignment).
  * **413 Payload Too Large**: Request payload exceeds configured limits.

## 5\. Architecture & Implementation Plan

1.  **Create new modules**:
      * `engine/correlations.py`: To house the core logic for alignment, return calculation, and correlation.
      * `app/models/correlation_requests.py` and `app/models/correlation_responses.py`: To define the API contract.
2.  **Update endpoint router**:
      * Add the `POST /portfolio/correlationMatrix` endpoint to `app/api/endpoints/portfolio.py`.
3.  **Implementation Steps**:
      * First, implement the core data processing pipeline (pivot, align, convert prices to returns).
      * Next, implement the Pearson and Spearman correlation logic using `pandas` or `scipy`.
      * Finally, layer in the optional grouping and rolling window features.

## 6\. Testing & Validation Strategy

  * **Unit Tests**: The new `engine/correlations.py` module must achieve **100% test coverage**. This will include tests for return calculations, all alignment and missing data policies, Pearson vs. Spearman methods, and numerical edge cases (e.g., constant series).
  * **Integration Tests**: API-level tests will validate the end-to-end flow, ensuring all request flags (e.g., `output.format`, `grouping`) correctly shape the response.
  * **Characterization Test**: A test will be created using a realistic set of time series. The API's output will be validated against the output of a trusted library like `pandas.DataFrame.corr` to ensure numerical correctness.
  * **Overall Coverage**: The overall project test coverage must remain at or above **95%**.

## 7\. Acceptance Criteria

The implementation of this RFC is complete when:

1.  This RFC is formally approved by all stakeholders.
2.  All new modules are created and fully integrated into the existing architecture.
3.  The `POST /portfolio/correlationMatrix` endpoint is fully functional, supporting all specified features.
4.  The testing and validation strategy is fully implemented, all tests are passing, and the required coverage targets (**100% for engine**, **≥95% for project**) are met.
5.  The characterization test passes, confirming numerical results match the external reference library.
6.  New documentation is added to `docs/guides/` and `docs/technical/` for the Correlation Matrix API, ensuring documentation remains current.

