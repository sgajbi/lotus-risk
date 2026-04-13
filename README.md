# lotus-risk

Advanced risk analytics service for Lotus platform.

Repository-local engineering context: `REPOSITORY-ENGINEERING-CONTEXT.md`

## Quick Start

```powershell
make install
make lint
make typecheck
make openapi-gate
make ci
```

`make ci` is the local PR-merge-quality gate. It runs dependency verification, contract governance, migration smoke, project-scoped security audit, split test suites, coverage, and Docker build validation.

```powershell
uvicorn src.app.main:app --reload --port 8130
```

```powershell
docker compose up --build
```

Local Docker runtime notes:
- `lotus-risk` keeps canonical upstream hostnames in code defaults for ingress-routed and non-containerized environments.
- For local Docker Compose runs against host-exposed services, `docker-compose.yml` explicitly points `LOTUS_CORE_BASE_URL` to `http://core-query.dev.lotus:8202` and `LOTUS_PERFORMANCE_BASE_URL` to `http://performance.dev.lotus:8002`, with `extra_hosts` mapping those canonical names back to the local host gateway.
- For direct host-based live validation, use `http://localhost:8130` for `lotus-risk`, `http://localhost:8002` for lotus-performance analytics, and `http://localhost:8202` for lotus-core query.
- See `docs/operations/canonical-local-upstream-urls.md` before overriding upstream URLs; pointing `LOTUS_PERFORMANCE_BASE_URL` at a lotus-core port will produce misleading `404` failures.
- Live risk validation defaults to canonical portfolio `PB_SG_GLOBAL_BAL_001`; see `docs/operations/live-risk-validation-matrix.md` before claiming broader enterprise portfolio-archetype coverage.
- Downstream gateway and Workbench consumers must preserve signed VaR, attribution residuals, issuer active-risk gating, concentration-only simulation support, and audit metadata; see `docs/domain-apis/risk-product-surface-alignment.md`.
- Copy `.env.example` to `.env` only when you need to override those local defaults.
- Stateful lotus-performance integration may complete asynchronously; local defaults use `LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS=1` and `LOTUS_PERFORMANCE_ASYNC_MAX_POLLS=60`.

- CI and governance: .github/workflows/
- Engineering commands: Makefile
- Platform standards docs: docs/standards/

API docs endpoint: /docs
