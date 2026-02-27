from __future__ import annotations

import logging
import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service_name: str) -> None:
        super().__init__(app)
        self._service_name = service_name
        self._event_logger = logging.getLogger("lotus_risk.request")

    @staticmethod
    def _resolve_trace_id(inbound_trace_id: str | None, traceparent: str | None) -> str:
        if inbound_trace_id:
            return inbound_trace_id
        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 4 and len(parts[1]) == 32:
                return parts[1]
        return uuid.uuid4().hex

    @staticmethod
    def _resolve_traceparent(traceparent: str | None, trace_id: str) -> str:
        if traceparent:
            return traceparent
        return f"00-{trace_id}-{uuid.uuid4().hex[:16]}-01"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
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
        self._event_logger.info(
            (
                "request_observed service=%s method=%s path=%s status=%s "
                "correlation=%s trace_id=%s latency_ms=%.3f risk=true"
            )
            % (
                self._service_name,
                request.method,
                request.url.path,
                response.status_code,
                correlation_id,
                trace_id,
                duration_ms,
            )
        )
        return response
