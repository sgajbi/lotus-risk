# lotus-risk

Authoritative risk analytics service for the Lotus ecosystem.

Repository-local engineering context: `REPOSITORY-ENGINEERING-CONTEXT.md`

`lotus-risk` owns the risk analytics contract for Lotus. It calculates portfolio risk metrics,
realized drawdown analytics, rolling historical risk diagnostics, concentration analytics, and
historical risk attribution. It is consumed primarily through `lotus-gateway`, but the service
itself remains the domain authority for risk meaning, supportability posture, and audit lineage.

## What This Repository Owns

`lotus-risk` owns:

1. risk analytics calculations and response contracts,
2. stateful and stateless execution paths for approved analytics workflows,
3. concentration simulation support,
4. supportability and decomposition payloads used by gateway and Workbench,
5. audit lineage and upstream request-fingerprint metadata for risk responses,
6. integration capability publication for downstream orchestration.

`lotus-risk` does not own:

1. portfolio, holdings, or transaction truth,
2. benchmark and returns authority that belongs to `lotus-performance`,
3. portfolio snapshot and reference-data authority that belongs to `lotus-core`,
4. UI affordance decisions in `lotus-workbench`,
5. experience composition that belongs in `lotus-gateway`.

## Current Product Shape

`lotus-risk` is a mature domain-service surface with a compact but high-value public API.

Current primary workflows:

1. `POST /analytics/risk/calculate`
2. `POST /analytics/risk/drawdown`
3. `POST /analytics/risk/rolling-metrics`
4. `POST /analytics/risk/historical-attribution`
5. `POST /analytics/risk/concentration`
6. `GET /integration/capabilities`
7. `GET /ops`

Important posture limits:

1. concentration is the only workflow that currently supports `simulation`,
2. stateful historical attribution remains `partial` because `ACTIVE_RISK + ISSUER` is intentionally gated,
3. live validation defaults to canonical portfolio `PB_SG_GLOBAL_BAL_001`,
4. broader enterprise-bank claims require more seeded archetypes and attached evidence.

## Architectural Shape

The service is a FastAPI application with explicit operational, integration, and risk-analytics
surfaces.

Core areas:

1. `src/app/contracts/`
   typed request and response contracts for risk workflows, operational endpoints, and capability publication.
2. `src/app/services/`
   analytics engines, mode adapters, lineage helpers, and domain calculations.
3. `src/app/integrations/`
   upstream clients for `lotus-core` and `lotus-performance`.
4. `src/app/main.py`
   public API surface and endpoint grouping.
5. `docs/domain-apis/`
   endpoint-by-endpoint contract and product-surface alignment guidance.
6. `docs/methodologies/`
   metric methodology definitions.
7. `docs/operations/` and `docs/runbooks/`
   local runtime, CI, and live validation guidance.

Execution model:

1. stateless requests consume caller-supplied risk inputs directly,
2. stateful requests source governed upstream inputs from `lotus-performance` and `lotus-core`,
3. responses preserve methodology, supportability, and lineage metadata so downstream surfaces do not have to reconstruct analytics meaning.

## Repository Layout

- `src/` application code
- `tests/` unit, integration, and e2e validation
- `scripts/` governance and quality gates
- `docs/domain-apis/` API contracts and downstream alignment rules
- `docs/methodologies/` metric methodology definitions
- `docs/operations/` and `docs/runbooks/` runtime and validation guidance
- `docs/rfcs/` local RFC inventory
- `docs/standards/` repo-local standards
- `wiki/` canonical source pages for the repository wiki

## Quick Start

Install dependencies and run the fast local gate:

```powershell
make install
make check
```

Run the API directly:

```powershell
uvicorn src.app.main:app --reload --port 8130
```

Run the prod-shaped local Docker stack:

```powershell
docker compose up --build
```

API docs are available at `http://localhost:8130/docs`.

Canonical direct local upstream URLs for live characterization and operator checks:

- `lotus-performance` analytics: `http://performance.dev.lotus:8002`
- `lotus-core` query control-plane: `http://core-control.dev.lotus:8202`

## Common Commands

- `make install` - install development dependencies
- `make check` - fast local gate
- `make ci` - PR-grade local gate
- `make test-unit` - unit suite
- `make test-integration` - integration suite
- `make test-e2e` - e2e suite
- `make migration-apply` - governed migration contract check
- `make docker-build` - Docker build validation

## Validation and CI

`lotus-risk` follows the Lotus lane model:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

Repo-native validation mapping:

- fast local gate: `make check`
- PR-grade gate: `make ci`
- split suites: `make test-unit`, `make test-integration`, `make test-e2e`

The enforced gates currently include:

1. lint,
2. no-alias contract governance,
3. typecheck,
4. OpenAPI quality,
5. API vocabulary validation,
6. migration smoke,
7. test-pyramid validation,
8. security audit,
9. coverage-backed testing,
10. Docker build validation.

## Integration Contract

Downstream services should normally consume `lotus-risk` through `lotus-gateway`, but the domain
contract still lives here.

Important integration truths:

1. `GET /integration/capabilities` is the source of truth for workflow support and mode support,
2. concentration is the only supported simulation workflow,
3. historical attribution support is intentionally `partial`,
4. signed VaR semantics, attribution reconciliation fields, issuer gating, concentration-only simulation support, and audit lineage metadata must be preserved downstream,
5. downstream consumers should derive affordances from the capability response and endpoint matrix rather than infer support from one successful endpoint call.

The main integration references are:

- `docs/domain-apis/endpoint-matrix.md`
- `docs/domain-apis/integration-capabilities.md`
- `docs/domain-apis/risk-product-surface-alignment.md`
- `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`

## Operations and Runtime Posture

Key operator-facing endpoints:

- `/health`
- `/health/live`
- `/health/ready`
- `/metadata`
- `/ops`
- `/metrics`

Runtime dependencies that matter:

1. `lotus-performance` for returns, benchmark returns, and benchmark exposure context,
2. `lotus-core` for snapshot, simulation, enrichment, and risk-free reference contracts.

Local URL contract and live validation posture are documented in:

- `docs/operations/canonical-local-upstream-urls.md`
- `docs/operations/live-risk-validation-matrix.md`
- `docs/runbooks/service-operations.md`

## Security and Governance

The key governance posture for `lotus-risk` is not generic AI or platform control-plane behavior. It
is analytical truth and contract discipline:

1. risk meaning must not drift downstream,
2. unsupported modes must stay explicitly unsupported,
3. supportability claims must remain evidence-backed,
4. upstream authority boundaries must remain clear,
5. no-alias, vocabulary, and OpenAPI governance are part of the product contract.

Key references:

- `docs/standards/risk-analytics-contract.md`
- `docs/standards/platform-compliance-assessment.md`
- `docs/domain-apis/risk-product-surface-alignment.md`

## Documentation Map

Best starting points:

- service-wide endpoint posture: `docs/domain-apis/endpoint-matrix.md`
- capability publication: `docs/domain-apis/integration-capabilities.md`
- product-surface alignment: `docs/domain-apis/risk-product-surface-alignment.md`
- service operations: `docs/runbooks/service-operations.md`
- development workflow: `docs/operations/development-workflow-and-ci-strategy.md`
- live validation matrix: `docs/operations/live-risk-validation-matrix.md`
- local RFC index: `docs/rfcs/README.md`

Platform governance:

- `../lotus-platform/rfcs/RFC-0067-centralized-api-vocabulary-inventory-and-openapi-documentation-governance.md`
- `../lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
- `../lotus-platform/rfcs/RFC-0082-lotus-core-domain-authority-and-analytics-serving-boundary-hardening.md`

## Wiki

The canonical authored source for the repository wiki lives under `wiki/` in this repository.

If a GitHub wiki is published later, treat `wiki/` as the authored source and any separate
`*.wiki.git` clone only as publication plumbing.
