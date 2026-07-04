import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import Request, Response

from app.contracts.attribution import AttributionInputMode
from app.contracts.drawdown import DrawdownInputMode
from app.contracts.risk import RiskInputMode
from app.contracts.rolling import RollingInputMode
from app.middleware.http_observation import build_http_observation_middleware
from app.routers.drawdown import analytics_risk_drawdown
from app.routers.historical_attribution import analytics_risk_historical_attribution
from app.routers.risk_calculation import analytics_risk_calculate
from app.routers.rolling import analytics_risk_rolling_metrics
from app.runtime.downstream_clients import RuntimeDownstreamClients


def _request(path: str = "/analytics/risk/calculate", method: str = "POST") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "client": ("testclient", 50000),
        }
    )


def test_http_observation_middleware_records_success_and_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[dict[str, object]] = []

    def _record_http_request(*, handler: str, method: str, status_code: int) -> None:
        observed.append({"handler": handler, "method": method, "status_code": status_code})

    monkeypatch.setattr(
        "app.middleware.http_observation.record_http_request",
        _record_http_request,
    )
    middleware = build_http_observation_middleware()
    request = _request("/health", "GET")

    async def _ok(_request: Request) -> Response:
        return Response(status_code=204)

    async def _raise(_request: Request) -> Response:
        raise RuntimeError("forced")

    async def _call_middleware(call_next: Any) -> Response:
        return await middleware(request, call_next)

    response: Response = asyncio.run(_call_middleware(_ok))
    assert response.status_code == 204
    assert observed[-1] == {"handler": "/health", "method": "GET", "status_code": 204}

    with pytest.raises(RuntimeError, match="forced"):
        asyncio.run(_call_middleware(_raise))
    assert observed[-1] == {"handler": "/health", "method": "GET", "status_code": 500}


@pytest.mark.parametrize(
    ("handler", "input_mode", "missing_field", "message"),
    [
        (
            analytics_risk_calculate,
            RiskInputMode.STATELESS,
            "stateless_input",
            "stateless_input is required when input_mode=stateless",
        ),
        (
            analytics_risk_calculate,
            RiskInputMode.STATEFUL,
            "stateful_input",
            "stateful_input is required when input_mode=stateful",
        ),
        (
            analytics_risk_drawdown,
            DrawdownInputMode.STATELESS,
            "stateless_input",
            "stateless_input is required when input_mode=stateless",
        ),
        (
            analytics_risk_drawdown,
            DrawdownInputMode.STATEFUL,
            "stateful_input",
            "stateful_input is required when input_mode=stateful",
        ),
        (
            analytics_risk_rolling_metrics,
            RollingInputMode.STATELESS,
            "stateless_input",
            "stateless_input is required when input_mode=stateless",
        ),
        (
            analytics_risk_rolling_metrics,
            RollingInputMode.STATEFUL,
            "stateful_input",
            "stateful_input is required when input_mode=stateful",
        ),
        (
            analytics_risk_historical_attribution,
            AttributionInputMode.STATELESS,
            "stateless_input",
            "stateless_input is required when input_mode=stateless",
        ),
        (
            analytics_risk_historical_attribution,
            AttributionInputMode.STATEFUL,
            "stateful_input",
            "stateful_input is required when input_mode=stateful",
        ),
    ],
)
def test_analytics_routers_keep_defensive_missing_payload_guards(
    handler: Any,
    input_mode: object,
    missing_field: str,
    message: str,
) -> None:
    payload = SimpleNamespace(
        input_mode=input_mode, stateless_input=object(), stateful_input=object()
    )
    setattr(payload, missing_field, None)

    with pytest.raises(ValueError, match=message):
        asyncio.run(
            handler(
                cast(Any, payload),
                RuntimeDownstreamClients(app_state=SimpleNamespace()),
                None,
            )
        )


@pytest.mark.parametrize(
    ("handler", "path"),
    [
        (analytics_risk_calculate, "/analytics/risk/calculate"),
        (analytics_risk_drawdown, "/analytics/risk/drawdown"),
        (analytics_risk_rolling_metrics, "/analytics/risk/rolling-metrics"),
        (analytics_risk_historical_attribution, "/analytics/risk/historical-attribution"),
    ],
)
def test_analytics_routers_keep_defensive_unsupported_mode_guards(
    handler: Any,
    path: str,
) -> None:
    payload = SimpleNamespace(
        input_mode=SimpleNamespace(value="simulation"),
        stateless_input=object(),
        stateful_input=object(),
    )

    with pytest.raises(ValueError, match=f"Unsupported input_mode=simulation for {path}"):
        asyncio.run(
            handler(
                cast(Any, payload),
                RuntimeDownstreamClients(app_state=SimpleNamespace()),
                None,
            )
        )
