# Lotus Risk Quality Scorecard

| Dimension | Current posture | Refactor target |
| --- | --- | --- |
| API modularity | `src/app/main.py` is 10 lines with app construction delegated to `app_factory` | Keep routers modular and prevent API-entry-point regression |
| Service boundaries | Calculation engines are under `src/app/services` | Keep business logic out of routers and middleware |
| Architecture enforcement | `.importlinter` contracts are available through `make architecture-gate` | Keep contracts green and extend boundaries as modules mature |
| OpenAPI governance | Existing repo gate plus `.spectral.yaml` governance config | Standardize generated OpenAPI lint in CI |
| Tests | 85 Python test files; 431 unit tests collect | Add route-boundary and governance regression tests per slice |
| Security | pip-audit and Bandit are enforced through `make security-audit` | Add targeted negative/security tests for abuse and error leakage |
| Observability | Metrics/correlation support exists | Consolidate runbook and dashboard/alert evidence |
