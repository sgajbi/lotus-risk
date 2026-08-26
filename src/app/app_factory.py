from fastapi import FastAPI

from app.api_errors import register_exception_handlers
from app.app_lifecycle import application_lifespan
from app.enterprise_readiness import (
    build_enterprise_audit_middleware,
    validate_enterprise_runtime_config,
)
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.http_observation import build_http_observation_middleware
from app.routers.concentration import router as concentration_router
from app.routers.drawdown import router as drawdown_router
from app.routers.historical_attribution import router as historical_attribution_router
from app.routers.operational import router as operational_router
from app.routers.risk_calculation import router as risk_calculation_router
from app.routers.rolling import router as rolling_router
from app.routers.source_products import router as source_products_router
from app.service_metadata import SERVICE_NAME, SERVICE_VERSION


def create_app() -> FastAPI:
    risk_app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION, lifespan=application_lifespan)
    risk_app.add_middleware(CorrelationIdMiddleware, service_name=SERVICE_NAME)
    validate_enterprise_runtime_config()
    risk_app.middleware("http")(build_enterprise_audit_middleware())
    risk_app.middleware("http")(build_http_observation_middleware())
    register_exception_handlers(risk_app)
    risk_app.include_router(operational_router)
    risk_app.include_router(source_products_router)
    risk_app.include_router(risk_calculation_router)
    risk_app.include_router(drawdown_router)
    risk_app.include_router(rolling_router)
    risk_app.include_router(concentration_router)
    risk_app.include_router(historical_attribution_router)
    return risk_app
