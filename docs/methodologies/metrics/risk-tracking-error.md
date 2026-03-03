# Risk Metric Methodology - Tracking Error

## Metric
- metric_id: TRACKING_ERROR

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/calculate
- supported_modes: stateless, stateful

## Inputs
- Portfolio returns
- Benchmark returns

## Upstream Data Sources
- Stateless: caller
- Stateful: lotus-performance

## Unit Conventions
- Return contracts are usually in percentage-point units unless the endpoint contract states otherwise.
- Statistical formulas may normalize to decimal returns (r_decimal = r_pp / 100) before computation.
- Output units follow endpoint schema semantics (for example ratio, decimal drawdown, or HHI scale).

## Methodology and Formulas
- active_t = Rp_t - Rb_t
- TE = std(active_t,ddof=1)*sqrt(annual_factor)

## Step-by-Step Computation
1. Resolve period/filter window and applicable alignment policy from the request options.
2. Normalize units and prepare aligned series/matrices required by the metric formula.
3. Apply: active_t = Rp_t - Rb_t
4. Apply: TE = std(active_t,ddof=1)*sqrt(annual_factor)
5. Map computed values to response fields and include deterministic error/quality signals when applicable.

## Configuration Options
- options.frequency
- options.annualization_factor

## Outputs
- results[period].metrics.TRACKING_ERROR.value

## Worked Example
Given:
- Active [%]: [0.1,-0.2,0.1], annual_factor=252 => TE ~= 2.75
Apply:
- Execute the formulas above in the listed order after unit normalization.
Result:
- Populate output fields exactly as listed in the Outputs section.

