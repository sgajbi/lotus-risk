# Canonical Local Upstream URLs

This runbook defines the local URL contract for live `lotus-risk` validation.

## Service Ports

| Service | Direct Local URL | Canonical Docker/Ingress Hostname | Purpose |
| --- | --- | --- | --- |
| lotus-risk | `http://localhost:8130` | `http://risk.dev.lotus:8130` | risk analytics API under test |
| lotus-performance analytics | `http://localhost:8002` | `http://performance.dev.lotus:8002` | portfolio returns, benchmark returns, benchmark exposure context |
| lotus-core query | `http://localhost:8202` | `http://core-query.dev.lotus:8202` | portfolio snapshots, enrichment, position analytics history, risk-free reference series |

## Environment Variables

| Variable | Canonical Local Default | Notes |
| --- | --- | --- |
| `LOTUS_RISK_BASE_URL` | `http://localhost:8130` | Used by live characterization tests. |
| `LOTUS_PERFORMANCE_BASE_URL` | `http://localhost:8002` | Must point to lotus-performance analytics, not lotus-core. |
| `LOTUS_CORE_BASE_URL` | `http://localhost:8202` | Must point to lotus-core query. |

`LOTUS_CORE_QUERY_BASE_URL` is accepted only as a backward-compatible live-test fallback. New docs, scripts, and tests should use `LOTUS_CORE_BASE_URL`.

## Docker Compose Contract

`docker-compose.yml` keeps canonical hostnames inside the container and maps them to the host gateway:

1. `LOTUS_PERFORMANCE_BASE_URL=http://performance.dev.lotus:8002`
2. `LOTUS_CORE_BASE_URL=http://core-query.dev.lotus:8202`
3. `performance.dev.lotus:host-gateway`
4. `core-query.dev.lotus:host-gateway`

This lets the container use stable Lotus hostnames while still reaching host-exposed local services.

## Common Misconfiguration

Do not point `LOTUS_PERFORMANCE_BASE_URL` to a lotus-core port. In local runs, `http://localhost:8201` and `http://localhost:8202` are lotus-core service ports, not lotus-performance analytics ports. A wrong performance URL usually appears as `404` for `/integration/returns/series` or `/integration/benchmarks/exposure-context`.

## Validation Commands

Run the fast URL governance checks with:

```powershell
python -m pytest tests/unit/test_local_docker_runtime_contract.py tests/unit/test_canonical_url_governance.py -q
```

Run the full local feature gate with:

```powershell
make check
```
