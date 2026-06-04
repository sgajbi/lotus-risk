from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.observability import record_http_request

MiddlewareNext = Callable[[Request], Awaitable[Response]]
MiddlewareCallable = Callable[[Request, MiddlewareNext], Awaitable[Response]]


def build_http_observation_middleware() -> MiddlewareCallable:
    async def middleware(request: Request, call_next: MiddlewareNext) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            route = request.scope.get("route")
            handler = getattr(route, "path", request.url.path)
            record_http_request(handler=handler, method=request.method, status_code=500)
            raise
        route = request.scope.get("route")
        handler = getattr(route, "path", request.url.path)
        record_http_request(
            handler=handler, method=request.method, status_code=response.status_code
        )
        return response

    return middleware
