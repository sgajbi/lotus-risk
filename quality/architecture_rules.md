# Lotus Risk Architecture Rules

1. Routers call application services or use cases only.
2. Routers must not call repository, database, HTTP, Kafka, Redis, or downstream adapter APIs directly.
3. Middleware stays thin and business-logic-free.
4. Domain and service modules must not depend on FastAPI, Starlette request/response objects, or
   infrastructure transport models.
5. Infrastructure adapters sit behind narrow service-facing protocols.
6. DTO contracts and persistence/transport models must not leak into domain calculation logic.
7. Downstream errors map through `app.upstream_errors` and API errors map through the standard
   error response envelope.
8. Every request must support and propagate correlation identity.
9. Logs and metrics must use bounded labels and must not expose portfolio, client, trace,
   correlation, request-body, or response-body values as labels.
