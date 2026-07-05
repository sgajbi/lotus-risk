from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROLLING_TRACKING_ERROR_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "rolling-tracking-error.md"
)
ROLLING_VOLATILITY_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "rolling-volatility.md"
ROLLING_INFORMATION_RATIO_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "rolling-information-ratio.md"
)
ROLLING_SHARPE_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "rolling-sharpe.md"
ROLLING_BETA_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "rolling-beta.md"
ROLLING_MAX_DRAWDOWN_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "rolling-max-drawdown.md"
)
DRAWDOWN_MAX_DRAWDOWN_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "drawdown-max-drawdown.md"
)
DRAWDOWN_AVERAGE_DRAWDOWN_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "drawdown-average-drawdown.md"
)
DRAWDOWN_ULCER_INDEX_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "drawdown-ulcer-index.md"
)
DRAWDOWN_TIME_UNDER_WATER_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "drawdown-time-under-water.md"
)
CONCENTRATION_POSITION_HHI_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "concentration-hhi.md"
)
CONCENTRATION_TOP_POSITION_WEIGHT_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "concentration-top-position-weight.md"
)
CONCENTRATION_TOP_N_CUMULATIVE_WEIGHT_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "concentration-top-n-cumulative-weight.md"
)
CONCENTRATION_ISSUER_HHI_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "concentration-issuer-hhi.md"
)
CONCENTRATION_TOP_ISSUER_WEIGHT_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "concentration-top-issuer-weight.md"
)
RISK_VOLATILITY_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-volatility.md"
RISK_DRAWDOWN_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-drawdown.md"
RISK_SHARPE_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-sharpe.md"
RISK_SORTINO_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-sortino.md"
RISK_VAR_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-var.md"
RISK_BETA_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-beta.md"
RISK_TRACKING_ERROR_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-tracking-error.md"
)
RISK_INFORMATION_RATIO_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-information-ratio.md"
)
ATTRIBUTION_VOLATILITY_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "attribution-volatility.md"
)
ATTRIBUTION_TRACKING_ERROR_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "attribution-tracking-error.md"
)
REGIME_SCENARIO_PACK_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "regime-scenario-pack-evaluation.md"
)


EXPECTED_V3_SECTIONS = [
    "## Metric",
    "## Endpoint and Mode Coverage",
    "## Inputs",
    "## Upstream Data Sources",
    "## Unit Conventions",
    "## Variable Dictionary",
    "## Methodology and Formulas",
    "## Step-by-Step Computation",
    "## Validation and Failure Behavior",
    "## Configuration Options",
    "## Outputs",
    "## Worked Example",
]


def _assert_v3_section_order(text: str) -> None:
    section_positions = [text.index(section) for section in EXPECTED_V3_SECTIONS]
    assert section_positions == sorted(section_positions)


def test_historical_attribution_methodologies_record_quality_flag_supportability() -> None:
    for doc_path in (ATTRIBUTION_VOLATILITY_DOC, ATTRIBUTION_TRACKING_ERROR_DOC):
        text = doc_path.read_text(encoding="utf-8")
        _assert_v3_section_order(text)
        assert "metadata.calculation_supportability" in text
        assert "calculation_quality_issue" in text
        assert "quality flag" in text


def test_regime_scenario_pack_methodology_is_auditable_against_engine_contract() -> None:
    text = REGIME_SCENARIO_PACK_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "product_name: RegimeScenarioPackEvaluation",
        "methodology_version: risk-regime-scenario-pack-evaluation.v1",
        "/analytics/risk/regime-scenario-pack/evaluate",
        "CIO_REGIME_2026_Q2",
        "contribution_{S,i} = max(-(q_{i,b} * shock_{S,b}), 0.0)",
        "component weights must reconcile to the matching exposure bucket within `0.000001`",
        "REGIME_SCENARIO_UNSUPPORTED_EXPOSURE_BUCKET",
        "REGIME_SCENARIO_POLICY_THRESHOLD_BREACH",
        "REGIME_SCENARIO_EFFECTIVE_PERIOD_EXCEPTION",
        "REGIME_SCENARIO_PORTFOLIO_APPLICABILITY_NOT_CONFIRMED",
        "REGIME_SCENARIO_PORTFOLIO_NOT_APPLICABLE",
        "governance_evidence.cio_approval_status = approved",
        "governance_evidence.effective_period_status = active",
        "governance_evidence.applicability_status = applicable",
        "metadata.calculation_supportability = ready",
        "scenario_results[].expected_loss_pct = 0.0660 + 0.0105 + 0.0000 = 0.0765",
        "worst_case_loss_pct = 0.1060",
        "FO_EQ_AAPL_US",
        "0.0360",
        "not a market forecast, full instrument repricing model",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_rolling_volatility_methodology_is_auditable_against_engine_contract() -> None:
    text = ROLLING_VOLATILITY_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: ROLLING_VOLATILITY",
        "/analytics/risk/rolling-metrics",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "annualized decimal ratio",
        "ddof=1",
        "`min_obs = W` when `min_observations_policy = STRICT`",
        "`min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`",
        "Constant portfolio returns are valid and produce `0.0`",
        "No benchmark or risk-free dependency is required for `ROLLING_VOLATILITY`",
        "metric_summaries.ROLLING_VOLATILITY.latest",
        "metric_series[].metric_values.ROLLING_VOLATILITY",
        "0.3004995840",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_rolling_tracking_error_methodology_is_auditable_against_engine_contract() -> None:
    text = ROLLING_TRACKING_ERROR_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: ROLLING_TRACKING_ERROR",
        "/analytics/risk/rolling-metrics",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "annualized decimal ratio",
        "ddof=1",
        "`min_obs = W` when `min_observations_policy = STRICT`",
        "`min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`",
        'benchmark_context.reason = "NO_ALIGNED_OBSERVATIONS"',
        "Constant active returns are valid and produce `0.0`",
        "metric_summaries.ROLLING_TRACKING_ERROR.latest",
        "metric_series[].metric_values.ROLLING_TRACKING_ERROR",
        "0.0601026522",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_rolling_information_ratio_methodology_is_auditable_against_engine_contract() -> None:
    text = ROLLING_INFORMATION_RATIO_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: ROLLING_INFORMATION_RATIO",
        "/analytics/risk/rolling-metrics",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "dimensionless annualized ratio",
        "ddof=1",
        "`min_obs = W` when `min_observations_policy = STRICT`",
        "`min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`",
        'benchmark_context.reason = "NO_ALIGNED_OBSERVATIONS"',
        "metric:ROLLING_INFORMATION_RATIO:zero_tracking_error_window",
        "metric_summaries.ROLLING_INFORMATION_RATIO.latest",
        "metric_series[].metric_values.ROLLING_INFORMATION_RATIO",
        "6.9282032303",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_rolling_sharpe_methodology_is_auditable_against_engine_contract() -> None:
    text = ROLLING_SHARPE_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: ROLLING_SHARPE",
        "/analytics/risk/rolling-metrics",
        "lotus-performance",
        "lotus-core",
        "r_decimal = r_pp / 100",
        "dimensionless annualized ratio",
        "ddof=1",
        "`min_obs = W` when `min_observations_policy = STRICT`",
        "`min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`",
        'risk_free_context.reason = "NO_ALIGNED_OBSERVATIONS"',
        "metric:ROLLING_SHARPE:zero_volatility_window",
        "metric_summaries.ROLLING_SHARPE.latest",
        "metric_series[].metric_values.ROLLING_SHARPE",
        "10.0538549820",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_rolling_beta_methodology_is_auditable_against_engine_contract() -> None:
    text = ROLLING_BETA_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: ROLLING_BETA",
        "/analytics/risk/rolling-metrics",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "dimensionless ratio",
        "not used by `ROLLING_BETA`",
        "ddof=1",
        "`min_obs = W` when `min_observations_policy = STRICT`",
        "`min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`",
        'benchmark_context.reason = "NO_ALIGNED_OBSERVATIONS"',
        "metric:ROLLING_BETA:benchmark_variance_zero",
        "metric_summaries.ROLLING_BETA.latest",
        "metric_series[].metric_values.ROLLING_BETA",
        "1.5000000000",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_rolling_max_drawdown_methodology_is_auditable_against_engine_contract() -> None:
    text = ROLLING_MAX_DRAWDOWN_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: ROLLING_MAX_DRAWDOWN",
        "/analytics/risk/rolling-metrics",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "not used by `ROLLING_MAX_DRAWDOWN`",
        "decimal drawdown ratio",
        "`min_obs = W` when `min_observations_policy = STRICT`",
        "`min_obs = 2` when `min_observations_policy = ALLOW_PARTIAL`",
        "No benchmark or risk-free dependency is required for `ROLLING_MAX_DRAWDOWN`",
        "No denominator is used",
        "metric_summaries.ROLLING_MAX_DRAWDOWN.latest",
        "metric_series[].metric_values.ROLLING_MAX_DRAWDOWN",
        "-0.1000000000",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_drawdown_max_drawdown_methodology_is_auditable_against_engine_contract() -> None:
    text = DRAWDOWN_MAX_DRAWDOWN_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: MAX_DRAWDOWN",
        "/analytics/risk/drawdown",
        "`DrawdownAnalyticsReport:v1`",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "decimal drawdown ratios",
        "summary.max_drawdown = depth_max_episode",
        'error = "Insufficient data"',
        "A one-observation or never-underwater period is valid",
        "analysis_options.duration_unit",
        "analysis_options.minimum_episode_depth_bps",
        "results[period].summary.max_drawdown",
        "results[period].episodes[].depth",
        "results[period].underwater_series[].drawdown",
        "-0.2000000000",
        'summary.max_drawdown_peak_date = "2026-01-02"',
        'summary.max_drawdown_recovery_date = "2026-01-06"',
    ]

    for phrase in required_truth:
        assert phrase in text


def test_drawdown_average_drawdown_methodology_is_auditable_against_engine_contract() -> None:
    text = DRAWDOWN_AVERAGE_DRAWDOWN_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: AVERAGE_DRAWDOWN",
        "/analytics/risk/drawdown",
        "`DrawdownAnalyticsReport:v1`",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "decimal drawdown ratio",
        "Only strictly underwater observations (`DD_t < 0`) enter the average",
        "summary.average_drawdown = sum(U) / N_U",
        'error = "Insufficient data"',
        "A one-observation or never-underwater period is valid",
        "analysis_options.minimum_episode_depth_bps",
        "results[period].summary.average_drawdown",
        "results[period].summary.time_under_water_days",
        "results[period].underwater_series[].drawdown",
        "-0.0757600000",
        "summary.time_under_water_days = 3",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_drawdown_ulcer_index_methodology_is_auditable_against_engine_contract() -> None:
    text = DRAWDOWN_ULCER_INDEX_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: ULCER_INDEX",
        "/analytics/risk/drawdown",
        "`DrawdownAnalyticsReport:v1`",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "non-negative decimal drawdown ratio",
        "including peak observations where `DD_t = 0`",
        "summary.ulcer_index = sqrt(sum(S_t) / N)",
        'error = "Insufficient data"',
        "A one-observation or never-underwater period is valid",
        "analysis_options.minimum_episode_depth_bps",
        "results[period].summary.ulcer_index",
        "results[period].summary.time_under_water_days",
        "results[period].underwater_series[].drawdown",
        "0.0685096314",
        "mean(S_t)",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_drawdown_time_under_water_methodology_is_auditable_against_engine_contract() -> None:
    text = DRAWDOWN_TIME_UNDER_WATER_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: TIME_UNDER_WATER_DAYS",
        "/analytics/risk/drawdown",
        "`DrawdownAnalyticsReport:v1`",
        "lotus-performance",
        "r_decimal = r_pp / 100",
        "integer count of portfolio return observations",
        "observation-based",
        "not a calendar-day or business-day duration",
        "summary.time_under_water_days = sum(I_t)",
        'error = "Insufficient data"',
        "A one-observation or never-underwater period is valid",
        "analysis_options.duration_unit",
        "analysis_options.minimum_episode_depth_bps",
        "results[period].summary.time_under_water_days",
        "results[period].episodes[].total_days",
        "results[period].underwater_series[].drawdown",
        "Underwater indicators",
        "summary.time_under_water_days = 3",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_concentration_position_hhi_methodology_is_auditable_against_engine_contract() -> None:
    text = CONCENTRATION_POSITION_HHI_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: POSITION_HHI",
        "source_product: ConcentrationAnalyticsReport:v1",
        "/analytics/risk/concentration",
        "`risk_proxy`",
        "lotus-core baseline snapshot",
        "lotus-core simulation session",
        "There is no lotus-performance dependency for position HHI",
        "market_value_base` when present",
        "projected_market_value_base` when present",
        "Missing, non-numeric, zero, and negative values are excluded",
        "Position weights are decimal ratios in `[0, 1]`",
        "`risk_proxy.hhi_*` values are emitted on the conventional Herfindahl-Hirschman `0..10000`",
        "HHI_raw = sum(w_i^2) * 10000",
        "`risk_proxy.hhi_current = round6(HHI_current_raw)`",
        "explicit empty `positions_projected: []`",
        "`UPSTREAM_INVALID_RESPONSE`",
        "A single valid position produces HHI `10000.0`",
        "Equal weights across `N` valid positions produce `10000 / N`",
        "Issuer enrichment coverage does not change `risk_proxy.hhi_*`",
        "`include_cash_positions`",
        "`top_n`",
        "`issuer_grouping_level`",
        "`risk_proxy.hhi_current = 3800.0`",
        "`risk_proxy.hhi_proposed = 4450.0`",
        "`risk_proxy.hhi_delta = 650.0`",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_concentration_top_position_weight_methodology_is_auditable_against_engine_contract() -> (
    None
):
    text = CONCENTRATION_TOP_POSITION_WEIGHT_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: TOP_POSITION_WEIGHT",
        "source_product: ConcentrationRiskReport:v1",
        "/analytics/risk/concentration",
        "`single_position_concentration`",
        "lotus-core baseline snapshot",
        "lotus-core simulation session",
        "There is no lotus-performance dependency for top-position weight",
        "market_value_base` when present",
        "projected_market_value_base` when present",
        "Missing, non-numeric, zero, and negative values are excluded",
        "Output weights are decimal ratios in `[0, 1]`",
        "TOP_raw = max_i(w_i)",
        "`single_position_concentration.top_position_weight_current = round6(TOP_current_raw)`",
        "explicit empty `positions_projected: []`",
        "`UPSTREAM_INVALID_RESPONSE`",
        "lexicographically largest `security_id`",
        "A single valid position produces top-position weight `1.0`",
        "Equal weights across `N` valid positions produce top-position weight `1 / N`",
        "Issuer enrichment coverage does not change `single_position_concentration.top_position_*`",
        "`include_cash_positions`",
        "`top_n`",
        "`issuer_grouping_level`",
        "`single_position_concentration.top_position_weight_current = 0.50`",
        "`single_position_concentration.top_position_weight_proposed = 0.60`",
        "`single_position_concentration.top_position_weight_delta = 0.10`",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_concentration_top_n_cumulative_weight_methodology_is_auditable_against_engine_contract() -> (
    None
):
    text = CONCENTRATION_TOP_N_CUMULATIVE_WEIGHT_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: TOP_N_CUMULATIVE_WEIGHT",
        "source_product: ConcentrationRiskReport:v1",
        "/analytics/risk/concentration",
        "`single_position_concentration`",
        "lotus-core baseline snapshot",
        "lotus-core simulation session",
        "There is no lotus-performance dependency for top-N cumulative weight",
        "`top_n` to an integer in the inclusive range `1..50`",
        "market_value_base` when present",
        "projected_market_value_base` when present",
        "Missing, non-numeric, zero, and negative values are excluded",
        "Output weights are decimal ratios in `[0, 1]`",
        "TOP_N_raw = sum(W_sorted[0:N])",
        "`single_position_concentration.top_n_cumulative_weight_current = round6(TOP_N_current_raw)`",
        "explicit empty `positions_projected: []`",
        "`UPSTREAM_INVALID_RESPONSE`",
        "A single valid position produces top-N cumulative weight `1.0`",
        "If `N` exceeds the number of valid positions",
        "Equal weights across `M` valid positions produce top-N cumulative weight `min(N, M) / M`",
        "Issuer enrichment coverage does not change",
        "`single_position_concentration.top_n_cumulative_weight_*`",
        "`include_cash_positions`",
        "`issuer_grouping_level`",
        "`single_position_concentration.top_n_cumulative_weight_current = 0.80`",
        "`single_position_concentration.top_n_cumulative_weight_proposed = 0.85`",
        "`single_position_concentration.top_n_cumulative_weight_delta = 0.05`",
        "`single_position_concentration.top_n = 2`",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_concentration_issuer_hhi_methodology_is_auditable_against_engine_contract() -> None:
    text = CONCENTRATION_ISSUER_HHI_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: ISSUER_HHI",
        "source_product: ConcentrationRiskReport:v1",
        "/analytics/risk/concentration",
        "`issuer_concentration`",
        "lotus-core instrument enrichment",
        "lotus-core baseline snapshot",
        "lotus-core simulation session",
        "There is no lotus-performance dependency for issuer HHI",
        "legal issuer grouping uses `issuer_id`",
        "ultimate-parent grouping uses `ultimate_parent_issuer_id`",
        "merged policy starts with lotus-core identity and lets caller identity override",
        "market_value_base` when present",
        "projected_market_value_base` when present",
        "Missing, non-numeric, zero, and negative values are excluded",
        "`issuer_concentration.hhi_*` values are emitted on the conventional Herfindahl-Hirschman",
        "ISSUER_HHI_raw = sum_k(w_k^2) * 10000",
        "`issuer_concentration.hhi_current = round6(ISSUER_HHI_current_raw)`",
        "explicit empty `positions_projected: []`",
        "`UPSTREAM_INVALID_RESPONSE`",
        "A single covered issuer bucket produces issuer HHI `10000.0`",
        "Equal weights across `N` covered issuer buckets produce issuer HHI `10000 / N`",
        "Positions without resolved issuer identity are excluded from issuer HHI",
        "`coverage_status = partial`",
        "`metadata.calculation_supportability`",
        "issuer enrichment coverage does",
        "not change `risk_proxy.hhi_*`",
        "`include_cash_positions`",
        "`top_n`",
        "`issuer_concentration.hhi_current = 6800.0`",
        "`issuer_concentration.hhi_proposed = 5800.0`",
        "`issuer_concentration.hhi_delta = -1000.0`",
        "`issuer_concentration.coverage_status = complete`",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_concentration_top_issuer_weight_methodology_is_auditable_against_engine_contract() -> None:
    text = CONCENTRATION_TOP_ISSUER_WEIGHT_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: TOP_ISSUER_WEIGHT",
        "source_product: ConcentrationRiskReport:v1",
        "/analytics/risk/concentration",
        "`issuer_concentration`",
        "lotus-core instrument enrichment",
        "lotus-core baseline snapshot",
        "lotus-core simulation session",
        "There is no lotus-performance dependency for top issuer weight",
        "legal issuer grouping uses `issuer_id`",
        "ultimate-parent grouping uses `ultimate_parent_issuer_id`",
        "merged policy starts with lotus-core identity and lets caller identity override",
        "market_value_base` when present",
        "projected_market_value_base` when present",
        "Missing, non-numeric, zero, and negative values are excluded",
        "Top issuer weights are decimal ratios in `[0, 1]`",
        "TOP_ISSUER_raw = max_k(w_k)",
        "`issuer_concentration.top_issuer_weight_current = round6(TOP_ISSUER_current_raw)`",
        "`issuer_concentration.top_issuer_current.weight = round6(TOP_ISSUER_current_raw)`",
        "explicit empty `positions_projected: []`",
        "`UPSTREAM_INVALID_RESPONSE`",
        "A single covered issuer bucket produces top issuer weight `1.0`",
        "Equal weights across `N` covered issuer buckets produce top issuer weight `1 / N`",
        "lexicographically largest `issuer_id`",
        "Positions without resolved issuer identity are excluded from top issuer weight",
        "`coverage_status = partial`",
        "`metadata.calculation_supportability`",
        "not change `risk_proxy.hhi_*`",
        "`include_cash_positions`",
        "`top_n`",
        "`issuer_concentration.top_issuer_weight_current = 0.80`",
        "`issuer_concentration.top_issuer_weight_proposed = 0.70`",
        "`issuer_concentration.top_issuer_weight_delta = -0.10`",
        '`issuer_concentration.top_issuer_current.issuer_id = "ISSUER_X"`',
        "`issuer_concentration.top_issuer_current.weight = 0.80`",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_risk_volatility_methodology_is_auditable_against_engine_contract() -> None:
    text = RISK_VOLATILITY_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: VOLATILITY",
        "/analytics/risk/calculate",
        "lotus-performance",
        "r_log_pp = ln(1 + r_pp / 100) * 100",
        "details.standard_deviation = std(r_used_pp, ddof=1) / 100",
        "annualized percentage-point output",
        "Frequency resampling compounds percentage-point returns",
        "`AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`",
        'details.error = "Insufficient data"',
        "No benchmark or risk-free dependency is required for `VOLATILITY`",
        "No denominator is used",
        "results[period].metrics.VOLATILITY.value",
        "11.9146968069",
        "0.0075055535",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_risk_drawdown_methodology_is_auditable_against_engine_contract() -> None:
    text = RISK_DRAWDOWN_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: DRAWDOWN",
        "/analytics/risk/calculate",
        "lotus-performance",
        "not used by `DRAWDOWN`",
        "r_decimal = r_pp / 100",
        "signed percentage-point outputs",
        '`metrics.DRAWDOWN.value = null` with `details.error = "Insufficient data"',
        "No benchmark dependency is required for `DRAWDOWN`",
        "No risk-free dependency is required for `DRAWDOWN`",
        "No annualization factor is used for `DRAWDOWN`",
        "results[period].metrics.DRAWDOWN.value",
        "results[period].metrics.DRAWDOWN.details.time_under_water_days",
        "-20.0000000000",
        'details.peak_date = "2026-01-01"',
        "time_under_water_days = 2",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_risk_sharpe_methodology_is_auditable_against_engine_contract() -> None:
    text = RISK_SHARPE_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: SHARPE",
        "/analytics/risk/calculate",
        "lotus-performance",
        "r_log_pp = ln(1 + r_pp / 100) * 100",
        "details.volatility = std(r_used_pp, ddof=1) / 100",
        "details.periodic_risk_free_rate = (1 + rf_annual)^(1 / AF) - 1",
        "`metrics.SHARPE.value` is a dimensionless annualized ratio",
        "`AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`",
        'details.error = "Insufficient data"',
        'details.error = "Zero volatility"',
        "No benchmark dependency is required for `SHARPE`",
        "The denominator is `sigma_decimal`",
        "results[period].metrics.SHARPE.value",
        "4.7688716199",
        "0.0000785849",
        "0.0075055535",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_risk_sortino_methodology_is_auditable_against_engine_contract() -> None:
    text = RISK_SORTINO_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: SORTINO",
        "/analytics/risk/calculate",
        "lotus-performance",
        "r_log_pp = ln(1 + r_pp / 100) * 100",
        "MAR_periodic = (1 + MAR_annual)^(1 / AF) - 1",
        "sigma_down_dec = sqrt(mean(x_t^2 for x_t in D))",
        "`metrics.SORTINO.value` is a dimensionless annualized ratio",
        "`AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`",
        'details.error = "Insufficient data"',
        'details.error = "No downside observations"',
        "No benchmark dependency is required for `SORTINO`",
        "No risk-free dependency is required for `SORTINO`",
        "The denominator is `sigma_down_dec`",
        "results[period].metrics.SORTINO.value",
        "6.1462967894",
        "0.0000785849",
        "0.0036711967",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_risk_var_methodology_is_auditable_against_engine_contract() -> None:
    text = RISK_VAR_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: VAR",
        "/analytics/risk/calculate",
        "lotus-performance",
        "r_log_pp = ln(1 + r_pp / 100) * 100",
        "`HISTORICAL`, `GAUSSIAN`, or `CORNISH_FISHER`",
        "signed return thresholds in percentage points",
        "HISTORICAL`: `VaR_base_pp = percentile(r_used_pp, alpha * 100)`",
        "GAUSSIAN`: `VaR_base_pp = mu_pp + sigma_pp * z_alpha`",
        "`z_cf = z_alpha + ((z_alpha^2 - 1) * S) / 6",
        '`metrics.VAR.value = null` with `details.error = "Insufficient data"',
        "No benchmark dependency is required for `VAR`",
        "No risk-free dependency is required for `VAR`",
        "No annualization factor is used for `VAR`",
        "results[period].metrics.VAR.details.horizon_scale_method",
        "results[period].metrics.VAR.details.expected_shortfall",
        "-3.6000000000",
        "-1.8000000000",
        "-4.0000000000",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_risk_beta_methodology_is_auditable_against_engine_contract() -> None:
    text = RISK_BETA_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: BETA",
        "/analytics/risk/calculate",
        "lotus-performance",
        "r_log_pp = ln(1 + r_pp / 100) * 100",
        "details.covariance = cov(Rp_used_pp, Rb_used_pp, ddof=1)",
        "details.benchmark_variance = var(Rb_used_pp, ddof=1)",
        "`metrics.BETA.value` is a dimensionless slope coefficient",
        'details.error = "Benchmark returns required for benchmark-dependent metric"',
        'details.error = "Insufficient aligned observations"',
        'details.error = "Benchmark variance is zero"',
        "No risk-free dependency is required for `BETA`",
        "The denominator is `Var_b_pp2`",
        "results[period].metrics.BETA.value",
        "2.0000000000",
        "1.1666666667",
        "0.5833333333",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_risk_tracking_error_methodology_is_auditable_against_engine_contract() -> None:
    text = RISK_TRACKING_ERROR_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: TRACKING_ERROR",
        "/analytics/risk/calculate",
        "lotus-performance",
        "r_log_pp = ln(1 + r_pp / 100) * 100",
        "details.active_volatility = std(A_used_pp, ddof=1) / 100",
        "details.annualized_tracking_error = details.active_volatility * sqrt(AF)",
        "`metrics.TRACKING_ERROR.value` is an annualized percentage-point output",
        "`AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`",
        'details.error = "Benchmark returns required for benchmark-dependent metric"',
        'details.error = "Insufficient aligned observations"',
        "Constant active returns are valid and produce `0.0`",
        "No risk-free dependency is required for `TRACKING_ERROR`",
        "No denominator is used",
        "results[period].metrics.TRACKING_ERROR.value",
        "2.7495454169",
        "0.0017320508",
        "0.0274954542",
    ]

    for phrase in required_truth:
        assert phrase in text


def test_risk_information_ratio_methodology_is_auditable_against_engine_contract() -> None:
    text = RISK_INFORMATION_RATIO_DOC.read_text(encoding="utf-8")

    _assert_v3_section_order(text)

    required_truth = [
        "metric_id: INFORMATION_RATIO",
        "/analytics/risk/calculate",
        "lotus-performance",
        "r_log_pp = ln(1 + r_pp / 100) * 100",
        "details.tracking_error = std(A_used_pp, ddof=1) / 100",
        "details.annualized_active_return = details.active_mean_return * AF",
        "details.annualized_tracking_error = details.tracking_error * sqrt(AF)",
        "`metrics.INFORMATION_RATIO.value` is a dimensionless annualized ratio",
        "`AF = 252` for `DAILY`, `52` for `WEEKLY`, and `12` for `MONTHLY`",
        'details.error = "Benchmark returns required for benchmark-dependent metric"',
        'details.error = "Insufficient aligned observations"',
        'details.error = "Tracking error is zero"',
        "No risk-free dependency is required for `INFORMATION_RATIO`",
        "The denominator is `sigma_a_pp`",
        "results[period].metrics.INFORMATION_RATIO.value",
        "6.1481704596",
        "0.0012909944",
        "0.1260000000",
        "0.0204939015",
    ]

    for phrase in required_truth:
        assert phrase in text
