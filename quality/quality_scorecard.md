# Lotus Risk Quality Scorecard

| Dimension | Current posture | Refactor target |
| --- | --- | --- |
| API modularity | `src/app/main.py` is 10 lines | Split app factory, routers, error metadata, and dependencies |
| Service boundaries | Calculation engines are under `src/app/services` | Keep business logic out of routers and middleware |
| Architecture enforcement | `.importlinter` report-only contracts added | Promote to CI gate after router extraction |
| OpenAPI governance | Existing repo gate plus Spectral config added | Standardize operation IDs and generated OpenAPI lint |
| Tests | 80 Python test files; 374 unit tests collect | Add route-boundary and governance regression tests per slice |
| Security | pip-audit gate exists; Bandit configured | Add report-only Bandit evidence, then enforce new regressions |
| Observability | Metrics/correlation support exists | Consolidate runbook and dashboard/alert evidence |
