# Concentration Methodology - Top Issuer Weight

## Metric
- metric_id: TOP_ISSUER_WEIGHT

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Issuer-aggregated valuation buckets.

## Upstream Data Sources
- Derived from issuer aggregation pipeline.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Aggregate values by issuer bucket.
2. Compute issuer weights: `w_k = |issuer_value_k| / sum_j |issuer_value_j|`.
3. Top issuer metric: `TOP_ISSUER = max_k(w_k)`.
4. Delta: `TOP_ISSUER_delta = TOP_ISSUER_proposed - TOP_ISSUER_current`.

## Step-by-Step Computation
1. Resolve issuer mapping and aggregate values per issuer.
2. Normalize issuer totals into weights.
3. Select maximum issuer weight for each state.
4. Emit delta and coverage context.

## Configuration Options
- Inherited from issuer mapping options.

## Outputs
- `issuer_concentration.top_issuer_weight_current`
- `issuer_concentration.top_issuer_weight_proposed`
- `issuer_concentration.top_issuer_weight_delta`

## Worked Example
- Issuer totals example: X=80, Y=20.
- Total issuer value `100` gives weights X=`0.80`, Y=`0.20`.
- Top issuer weight current = `0.80`.
- If proposed totals are X=70, Y=30, top issuer weight proposed = `0.70`.
- Delta = `0.70 - 0.80 = -0.10`.