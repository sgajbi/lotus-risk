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
RISK_VOLATILITY_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-volatility.md"
RISK_SHARPE_DOC = REPO_ROOT / "docs" / "methodologies" / "metrics" / "risk-sharpe.md"


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
