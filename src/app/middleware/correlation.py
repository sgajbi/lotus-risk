from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
_SAFE_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_SAFE_TRACEPARENT = re.compile(
    r"^00-(?P<trace_id>[0-9a-f]{32})-(?P<span_id>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)


def _ensure_request_event_logger(logger: logging.Logger) -> None:
    if logger.handlers or logging.getLogger().handlers:
        return
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service_name: str) -> None:
        super().__init__(app)
        self._service_name = service_name
        self._event_logger = logging.getLogger("lotus_risk.request")
        _ensure_request_event_logger(self._event_logger)

    @staticmethod
    def _resolve_trace_id(inbound_trace_id: str | None, traceparent: str | None) -> str:
        if inbound_trace_id and CorrelationIdMiddleware._is_valid_trace_id(inbound_trace_id):
            return inbound_trace_id
        traceparent_match = _SAFE_TRACEPARENT.fullmatch(traceparent or "")
        if traceparent_match and CorrelationIdMiddleware._is_valid_trace_id(
            traceparent_match.group("trace_id")
        ):
            return traceparent_match.group("trace_id")
        return uuid.uuid4().hex

    @staticmethod
    def _resolve_traceparent(traceparent: str | None, trace_id: str) -> str:
        traceparent_match = _SAFE_TRACEPARENT.fullmatch(traceparent or "")
        if traceparent_match and traceparent_match.group("trace_id") == trace_id:
            return traceparent_match.group(0)
        return f"00-{trace_id}-{uuid.uuid4().hex[:16]}-01"

    @staticmethod
    def _is_valid_trace_id(trace_id: str) -> bool:
        return bool(_SAFE_TRACE_ID.fullmatch(trace_id)) and trace_id != "0" * 32

    @staticmethod
    def _resolve_correlation_id(inbound_correlation_id: str | None) -> str:
        if inbound_correlation_id and _SAFE_CORRELATION_ID.fullmatch(inbound_correlation_id):
            return inbound_correlation_id
        return str(uuid.uuid4())

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = self._resolve_correlation_id(request.headers.get("X-Correlation-Id"))
        trace_id = self._resolve_trace_id(
            request.headers.get("X-Trace-Id"), request.headers.get("traceparent")
        )
        traceparent = self._resolve_traceparent(request.headers.get("traceparent"), trace_id)
        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Correlation-Id"] = correlation_id
        response.headers["X-Trace-Id"] = trace_id
        response.headers["traceparent"] = traceparent
        response.headers["X-Service-Name"] = self._service_name
        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.3f}"
        request_observation = {
            "service": self._service_name,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "latency_ms": round(duration_ms, 3),
            "risk": True,
        }
        self._event_logger.info(
            json.dumps(
                {"message": "request_observed", **request_observation},
                separators=(",", ":"),
                sort_keys=True,
            ),
            extra={"request_observation": request_observation},
        )
        return response
