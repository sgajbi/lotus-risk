"""Attribution supportability, proved through the endpoint (#293).

The defect these cover was invisible to unit tests of the summary alone: the
summary was internally consistent and said something plausible. It was only
wrong *relative to the period results returned beside it* -- a response whose
`results` carried `error: "Insufficient data"` reported a structural limitation
and `degraded_metric_count: 0`.

So every case here asserts the period results and the summary **together**. A
supportability field is a claim about the payload it travels with; checking it
in isolation asserts that the service is self-consistent, which it was.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.support.historical_attribution_fakes import (
    build_stateless_attribution_payload,
)

# A window containing a single observation. Two are required, so the period
# fails with `Insufficient data` while remaining a well-formed request -- the
# distinction that matters, because an invalid request never reaches this code.
#
# 2026-01-02 specifically: it is the one date in the shared payload carrying a
# single return row. 2026-01-05 and 2026-01-06 each carry two, so a window on
# either satisfies the minimum and decomposes -- which is how this constant was
# wrong the first time, and why the date is pinned with a reason rather than
# looking like an arbitrary pick.
_SINGLE_DAY_PERIOD = {
    "type": "EXPLICIT",
    "name": "ONE_DAY",
    "from_date": "2026-01-02",
    "to_date": "2026-01-02",
}


def _post(payload: dict[str, object]) -> dict[str, Any]:
    response = TestClient(app).post(
        "/analytics/risk/historical-attribution",
        json=payload,
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def _supportability(body: dict[str, Any]) -> dict[str, Any]:
    return dict(body["metadata"]["calculation_supportability"])


def test_a_computed_proxy_is_degraded_and_names_the_limitation() -> None:
    """A clean decomposition is qualified, not broken, and never `ready`.

    Nothing failed, so `degraded_metric_count` is 0 and the entire degradation
    is carried by the reason. That pairing -- degraded with a zero failure count
    -- is the shape a consumer should read as "this computed, and it is a weight
    proxy", distinct from "something went wrong".
    """
    body = _post(build_stateless_attribution_payload())

    ytd = body["results"]["YTD"]
    assert ytd["error"] is None
    assert ytd["attribution_sets"], "the request should have decomposed"

    supportability = _supportability(body)
    assert supportability["state"] == "degraded"
    assert supportability["reason"] == "group_return_series_unavailable"
    assert supportability["degraded_metric_count"] == 0
    assert supportability["evaluated_period_count"] == 1


def test_empty_input_reports_no_observations_and_decomposes_nothing() -> None:
    """No returns means no proxy to qualify, so the limitation must not appear.

    The limitation is a statement about a decomposition. Reporting it for a
    response that decomposed nothing would attach a methodology caveat to an
    absence, and a consumer would show the caveat with no numbers under it.
    """
    payload = build_stateless_attribution_payload()
    payload["stateless_input"]["returns"] = []  # type: ignore[index]

    body = _post(payload)

    assert all(not result["attribution_sets"] for result in body["results"].values())

    supportability = _supportability(body)
    assert supportability["state"] == "empty"
    assert supportability["reason"] == "no_return_observations"
    assert supportability["degraded_metric_count"] == 0


def test_an_insufficient_period_keeps_the_reason_the_operator_can_act_on() -> None:
    """The regression, at the endpoint.

    One period, too few observations, no sets produced. Before the fix this
    reported `group_return_series_unavailable` with `degraded_metric_count: 0`
    -- a limitation nobody can act on today, and a zero failure count printed
    beside a period result carrying an error.

    `insufficient_observations` is actionable: widen the window, or wait for the
    data. That is the difference this asserts.
    """
    payload = build_stateless_attribution_payload()
    payload["stateless_input"]["periods"] = [_SINGLE_DAY_PERIOD]  # type: ignore[index]

    body = _post(payload)

    one_day = body["results"]["ONE_DAY"]
    assert one_day["error"] == "Insufficient data"
    assert one_day["attribution_sets"] == []

    supportability = _supportability(body)
    assert supportability["state"] == "degraded"
    assert supportability["reason"] == "insufficient_observations"
    # The count agrees with the results beside it: one period result carries a
    # deterministic error, so the count is 1. It read 0 before the fix.
    assert supportability["degraded_metric_count"] == 1
    assert supportability["evaluated_period_count"] == 1


def test_a_mixed_response_reports_the_failure_over_the_limitation() -> None:
    """Both conditions hold at once, and the actionable one wins.

    This is the case the precedence exists for, and the one a substituting
    implementation cannot express: the response really does carry both a weight
    proxy and a failed period. `insufficient_observations` outranks the
    structural limitation, so the summary names the failure -- while the
    decomposition that did compute is still returned, and still a proxy.
    """
    payload = build_stateless_attribution_payload()
    periods = list(payload["stateless_input"]["periods"])  # type: ignore[index]
    payload["stateless_input"]["periods"] = [*periods, _SINGLE_DAY_PERIOD]  # type: ignore[index]

    body = _post(payload)

    assert body["results"]["YTD"]["error"] is None
    assert body["results"]["YTD"]["attribution_sets"], "YTD should still decompose"
    assert body["results"]["ONE_DAY"]["error"] == "Insufficient data"

    supportability = _supportability(body)
    assert supportability["state"] == "degraded"
    assert supportability["reason"] == "insufficient_observations"
    assert supportability["degraded_metric_count"] == 1
    assert supportability["evaluated_period_count"] == 2


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("periods", id="insufficient-period"),
        pytest.param("returns", id="empty-returns"),
    ],
)
def test_the_summary_never_claims_ready(mutation: str) -> None:
    """`ready` is the one answer that is wrong in every case here.

    Whatever else varies, a historical-attribution response must never report
    `calculation_complete`: either it decomposed, and the decomposition is a
    weight proxy, or it did not, and there is nothing to call complete. Held
    separately from the specific-reason assertions so that a future change to
    the precedence cannot quietly reintroduce it.
    """
    payload = build_stateless_attribution_payload()
    if mutation == "periods":
        payload["stateless_input"]["periods"] = [_SINGLE_DAY_PERIOD]  # type: ignore[index]
    else:
        payload["stateless_input"]["returns"] = []  # type: ignore[index]

    supportability = _supportability(_post(payload))

    assert supportability["state"] != "ready"
    assert supportability["reason"] != "calculation_complete"
