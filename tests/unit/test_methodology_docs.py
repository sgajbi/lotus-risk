from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROLLING_TRACKING_ERROR_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "rolling-tracking-error.md"
)
ROLLING_INFORMATION_RATIO_DOC = (
    REPO_ROOT / "docs" / "methodologies" / "metrics" / "rolling-information-ratio.md"
)


def test_rolling_tracking_error_methodology_is_auditable_against_engine_contract() -> None:
    text = ROLLING_TRACKING_ERROR_DOC.read_text(encoding="utf-8")

    expected_sections = [
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

    section_positions = [text.index(section) for section in expected_sections]
    assert section_positions == sorted(section_positions)

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

    expected_sections = [
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

    section_positions = [text.index(section) for section in expected_sections]
    assert section_positions == sorted(section_positions)

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
