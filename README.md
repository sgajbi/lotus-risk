# lotus-risk

Advanced risk analytics service for Lotus platform.

## Quick Start

```powershell
make install
make lint
make typecheck
make openapi-gate
make ci
```

```powershell
uvicorn src.app.main:app --reload --port 8130
```

```powershell
docker compose up --build
```

Local Docker runtime notes:
- `lotus-risk` keeps canonical upstream hostnames in code defaults for ingress-routed and non-containerized environments.
- For local Docker Compose runs against host-exposed services, `docker-compose.yml` explicitly points `LOTUS_CORE_BASE_URL` to `http://core-query.dev.lotus:8202` and `LOTUS_PERFORMANCE_BASE_URL` to `http://performance.dev.lotus:8002`, with `extra_hosts` mapping those canonical names back to the local host gateway.
- Copy `.env.example` to `.env` only when you need to override those local defaults.
- Stateful lotus-performance integration may complete asynchronously; local defaults use `LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS=1` and `LOTUS_PERFORMANCE_ASYNC_MAX_POLLS=60`.

- CI and governance: .github/workflows/
- Engineering commands: Makefile
- Platform standards docs: docs/standards/

API docs endpoint: /docs
