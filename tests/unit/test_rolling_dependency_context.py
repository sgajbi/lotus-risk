from app.services.rolling_dependency_context import benchmark_context, risk_free_context


def test_benchmark_context_reports_not_requested() -> None:
    context = benchmark_context(
        ["ROLLING_VOLATILITY"],
        benchmark_series_count=0,
        aligned_benchmark_series_count=0,
    )

    assert context.requested is False
    assert context.available is False
    assert context.aligned is False
    assert context.reason == "NOT_REQUESTED"


def test_benchmark_context_reports_unavailable_and_no_aligned_states() -> None:
    unavailable = benchmark_context(
        ["ROLLING_BETA"],
        benchmark_series_count=0,
        aligned_benchmark_series_count=0,
    )
    no_aligned = benchmark_context(
        ["ROLLING_BETA"],
        benchmark_series_count=3,
        aligned_benchmark_series_count=0,
    )

    assert unavailable.requested is True
    assert unavailable.available is False
    assert unavailable.aligned is False
    assert unavailable.reason == "BENCHMARK_UNAVAILABLE"

    assert no_aligned.requested is True
    assert no_aligned.available is True
    assert no_aligned.aligned is False
    assert no_aligned.reason == "NO_ALIGNED_OBSERVATIONS"


def test_benchmark_context_reports_applied() -> None:
    context = benchmark_context(
        ["ROLLING_TRACKING_ERROR"],
        benchmark_series_count=3,
        aligned_benchmark_series_count=2,
    )

    assert context.requested is True
    assert context.available is True
    assert context.aligned is True
    assert context.reason == "APPLIED"


def test_risk_free_context_reports_not_requested() -> None:
    context = risk_free_context(
        ["ROLLING_VOLATILITY"],
        risk_free_series_count=0,
        aligned_risk_free_series_count=0,
    )

    assert context.requested is False
    assert context.available is False
    assert context.aligned is False
    assert context.reason == "NOT_REQUESTED"


def test_risk_free_context_reports_unavailable_and_no_aligned_states() -> None:
    unavailable = risk_free_context(
        ["ROLLING_SHARPE"],
        risk_free_series_count=0,
        aligned_risk_free_series_count=0,
    )
    no_aligned = risk_free_context(
        ["ROLLING_SHARPE"],
        risk_free_series_count=3,
        aligned_risk_free_series_count=0,
    )

    assert unavailable.requested is True
    assert unavailable.available is False
    assert unavailable.aligned is False
    assert unavailable.reason == "RISK_FREE_UNAVAILABLE"

    assert no_aligned.requested is True
    assert no_aligned.available is True
    assert no_aligned.aligned is False
    assert no_aligned.reason == "NO_ALIGNED_OBSERVATIONS"


def test_risk_free_context_reports_applied() -> None:
    context = risk_free_context(
        ["ROLLING_SHARPE"],
        risk_free_series_count=3,
        aligned_risk_free_series_count=2,
    )

    assert context.requested is True
    assert context.available is True
    assert context.aligned is True
    assert context.reason == "APPLIED"
