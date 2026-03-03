# Risk Metric Methodology - Beta

## Metric
- metric_id: BETA

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns (date-aligned)

## Upstream Data Sources
- Stateless: caller benchmark_returns[]
- Stateful: lotus-performance benchmark_returns

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- Beta = Cov(Rp,Rb)/Var(Rb), ddof=1
- Inner date join before calculation

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: Beta = Cov(Rp,Rb)/Var(Rb), ddof=1
4. Apply: Inner date join before calculation
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- options.frequency
- options.use_log_returns

## Outputs
- results[period].metrics.BETA.value
- details.error when benchmark variance is zero

## Worked Example
Given:
- Portfolio approximately 2x benchmark => beta ~= 2.0
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

