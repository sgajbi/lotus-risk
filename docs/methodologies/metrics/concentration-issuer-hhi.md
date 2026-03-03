# Concentration Methodology - Issuer HHI

## Metric
- metric_id: ISSUER_HHI

## Endpoint and Mode Coverage
- endpoint: /analytics/risk/concentration
- supported_modes: stateless, stateful, simulation

## Inputs
- Position values and issuer mapping.
- Issuer grouping and enrichment policy.

## Upstream Data Sources
- Caller mapping and/or lotus-core instrument enrichment.

## Unit Conventions
- Return inputs are percentage points (pp): `1.0` means `+1%`.
- Engine converts to decimal when needed: `r_decimal = r_pp / 100`.
- Output unit follows metric contract (ratio, annualized decimal, drawdown decimal, or HHI scale).

## Methodology and Formulas
1. Resolve issuer key per security (`issuer_id` or `ultimate_parent_issuer_id` by grouping level).
2. Aggregate position values by issuer bucket: `issuer_value_k = sum_{i in k} v_i`.
3. Compute issuer weights: `w_k = |issuer_value_k| / sum_j |issuer_value_j|`.
4. Compute issuer HHI: `ISSUER_HHI = sum_k(w_k^2) * 10000`.
5. Compute issuer HHI delta between proposed and current states.

## Step-by-Step Computation
1. Build issuer mapping using configured enrichment policy and grouping level.
2. Aggregate baseline and proposed positions into issuer buckets.
3. Compute issuer weights and HHI for each state.
4. Compute delta and coverage statistics (covered vs total positions).
5. Emit issuer concentration payload with coverage status and explanatory note if partial.

## Configuration Options
- `issuer_options.grouping_level`
- `issuer_options.enrichment_policy`

## Outputs
- `issuer_concentration.hhi_current`
- `issuer_concentration.hhi_proposed`
- `issuer_concentration.hhi_delta`
- `issuer_concentration.coverage_status`

## Worked Example
- Positions: A=50 (Issuer X), B=30 (Issuer X), C=20 (Issuer Y).
- Issuer totals: X=80, Y=20; total=100.
- Issuer weights: X=0.80, Y=0.20.
- Issuer HHI `=(0.80^2+0.20^2)*10000 = 6800`.
- If proposed issuer totals become X=70,Y=30 then HHI is `5800`, delta `-1000`.