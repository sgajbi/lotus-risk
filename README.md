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
6. `POST /analytics/risk/regime-scenario-pack/evaluate`
7. `POST /analytics/risk/risk-event-cohorts/evaluate`
8. `POST /analytics/risk/mandate-health-context`
9. `GET /integration/capabilities`
10. `GET /ops`

Important posture limits:

1. concentration is the only workflow that currently supports `simulation`,
2. regime scenario-pack evaluation is stateless and consumes caller-supplied exposure weights
   against risk-owned CIO scenario definitions; optional `exposure_components` produce
   source-owned per-security scenario contribution rows that reconcile to the bucket exposures,
   and both bucket allocations and contribution rows are bounded before calculation, but the
   workflow does not forecast markets or accept UI-owned scenario methodology,
3. risk-event affected-cohort evaluation is stateless and consumes caller-supplied candidate
   portfolios and source-supplied exposure weights against risk-owned event definitions; it does
   not create rebalance waves or own campaign approval workflow, and candidate portfolios plus
   exposure buckets are bounded before cohort materialization,
4. mandate risk health context is stateless and returns source-owned tracking-error posture for
   downstream manage consumption; it does not create actions, rebalance waves, orders, execution,
   or client communications,
5. stateful historical attribution supports `ACTIVE_RISK + ISSUER` through lotus-performance benchmark exposure context issuer groups,
6. live validation defaults to canonical portfolio `PB_SG_GLOBAL_BAL_001`,
7. broader enterprise-bank claims require more seeded archetypes and attached evidence.

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
4. `src/app/app_factory.py` and `src/app/routers/`
   application assembly and public API endpoint grouping.
5. `docs/domain-apis/`
   endpoint-by-endpoint contract and product-surface alignment guidance.
6. `docs/methodologies/`
   metric methodology definitions.
7. `docs/operations/` and `docs/runbooks/`
   local runtime, CI, and live validation guidance.
8. `docs/index.md`
   navigable docs map for agents, developers, BAs, ops/support, and business/product readers.

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
- `docs/index.md` audience-oriented documentation map
- `docs/rfcs/` local RFC inventory
- `docs/standards/` repo-local standards
- `wiki/` canonical source pages for the repository wiki

## Quick Start

You need, before anything else:

- **Python 3.12 or newer** — `pyproject.toml` requires `>=3.12` and CI pins 3.12
- **`make`** — every documented command uses it; not a default on Windows
- **Docker** — only for the prod-shaped stack below; the direct local run does not need it
- **A virtual environment, activated before `make install`.** `make install` installs into
  whichever interpreter is on `PATH`; it does not create one. On a PEP 668 distribution
  (Debian/Ubuntu, Fedora, Homebrew Python) installing into the system interpreter is refused
  with `externally-managed-environment`. CI does not see this because `actions/setup-python`
  supplies an isolated interpreter.

  ```shell
  python -m venv .venv
  source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
  ```

Install dependencies and run the fast local gate:

```shell
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
- `make ci-local` - split-suite local coverage loop without Docker
- `make ci-local-docker` - isolated Docker lane for the split-suite local coverage loop
- `make clean` - remove known generated/local artifacts; regenerate OpenAPI and quality evidence
  afterwards when PR proof needs fresh artifacts
- `make test-unit` - unit suite
- `make test-integration` - integration suite
- `make test-e2e` - e2e suite
- `make domain-data-product-gate` - repo-native domain data product validation
- `make mesh-contract-validate` - domain product, trust telemetry, and observability contract validation
- `make idea-opportunity-evidence-gate` - validate the source-safe Risk runtime evidence contract
  consumed by `lotus-idea` RFC-0002 Slice 16/17
- `make idea-opportunity-runtime-evidence` - generate the Risk producer evidence pack against a
  running `lotus-risk` HTTP API; the proof uses stateful canonical requests for
  `PB_SG_GLOBAL_BAL_001`, `BMK_PB_GLOBAL_BALANCED_60_40`, and `2026-04-10`
- `make migration-smoke` - CI migration smoke proof for the active no-schema contract
- `make migration-apply` - governed no-schema migration contract validation; this service has no
  persistent DPM schema to apply
- `make image-supply-chain-gate` - image metadata, CI-only push, SBOM/signing/provenance, digest deployment, and no-secret ARG/ENV guard
- `make docker-build` - Docker build validation with OCI provenance labels

## Validation and CI

`lotus-risk` follows the Lotus lane model:

1. `Remote Feature Lane`
2. `Pull Request Merge Gate`
3. `Main Releasability Gate`

Repo-native validation mapping:

- fast local gate: `make check`
- PR-grade gate: `make ci`
- isolated split-suite gate: `make ci-local-docker`
- repo-native domain product gate: `make domain-data-product-gate`
- split suites: `make test-unit`, `make test-integration`, `make test-e2e`

The enforced gates currently include:

1. lint,
2. architecture boundary governance,
3. no-alias contract governance,
4. typecheck,
5. OpenAPI quality and generated artifact validation,
6. API vocabulary validation,
7. mesh contract validation across domain products, trust telemetry, and observability contracts,
8. image supply-chain validation for CI-only push, SBOM, vulnerability scan, signing, provenance,
   release manifest, digest deployment, and secret-free Docker metadata,
9. source-size, complexity, dependency-hygiene, and dead-code gates,
10. migration smoke,
11. test-pyramid validation,
12. security audit,
13. coverage-backed testing,
14. Docker build validation.

## Integration Contract

Downstream services should normally consume `lotus-risk` through `lotus-gateway`, but the domain
contract still lives here.

Important integration truths:

1. `GET /integration/capabilities` is the source of truth for workflow support and mode support,
2. concentration is the only supported simulation workflow,
3. historical attribution support is intentionally `partial`,
4. signed VaR semantics, attribution reconciliation fields, issuer active-risk support metadata, concentration-only simulation support, and audit lineage metadata must be preserved downstream,
5. downstream consumers should derive affordances from the capability response and endpoint matrix rather than infer support from one successful endpoint call,
6. `lotus-idea` RFC-0002 Slice 16/17 may consume the source-safe producer proof generated by
   `make idea-opportunity-runtime-evidence`; the artifact is generated from stateful canonical
   requests for `PB_SG_GLOBAL_BAL_001`, `BMK_PB_GLOBAL_BALANCED_60_40`, and `2026-04-10`, carries
   exact RFC-0076 canonical contract provenance, clears only Risk source-proof blockers, and does
   not transfer risk methodology, data-mesh, Gateway/Workbench, client-publication, deployment,
   production, or supported-feature authority.

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
- `/version`
- `/ops`
- `/ops/trust-telemetry`
- `/metrics`

`/metadata` and `/version` expose the same service, policy, build, image, and CI provenance
metadata. Container builds label the image with Git commit SHA, branch/ref, service version, build
timestamp, source repository URL, image digest field, and CI pipeline/run ID. The final registry
digest is supplied by publish/deployment metadata through `LOTUS_IMAGE_DIGEST`; local unpublished
builds use an explicit unavailable value because an image cannot contain its own final digest as a
build-time label without changing that digest. Release images are pushed only by CI, tagged by Git
SHA, scanned, signed, attested, accompanied by SBOM and release-manifest evidence, and promoted
across environments by digest.

Runtime dependencies that matter:

1. `lotus-performance` for returns, benchmark returns, and benchmark exposure context,
2. `lotus-core` for snapshot, simulation, enrichment, and risk-free reference contracts.

Local URL contract and live validation posture are documented in:

- `docs/operations/canonical-local-upstream-urls.md`
- `docs/operations/live-risk-validation-matrix.md`
- `docs/operations/idea-opportunity-runtime-evidence.md`
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

- audience-oriented docs index: `docs/index.md`
- service-wide endpoint posture: `docs/domain-apis/endpoint-matrix.md`
- capability publication: `docs/domain-apis/integration-capabilities.md`
- product-surface alignment: `docs/domain-apis/risk-product-surface-alignment.md`
- supported features and limits: `docs/supported-features.md`
- documentation gap ledger: `docs/documentation-gap-ledger.md`
- service operations: `docs/runbooks/service-operations.md`
- runtime configuration: `docs/configuration.md`
- development workflow: `docs/operations/development-workflow-and-ci-strategy.md`
- live validation matrix: `docs/operations/live-risk-validation-matrix.md`
- Idea opportunity runtime evidence: `docs/operations/idea-opportunity-runtime-evidence.md`
- local RFC index: `docs/rfcs/README.md`

Platform governance:

- `../lotus-platform/rfcs/RFC-0067-centralized-api-vocabulary-inventory-and-openapi-documentation-governance.md`
- `../lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
- `../lotus-platform/rfcs/RFC-0082-lotus-core-domain-authority-and-analytics-serving-boundary-hardening.md`

## Wiki

The canonical authored source for the repository wiki lives under `wiki/` in this repository.

The published GitHub wiki is synchronized from this repo-local source. Treat any separate
`*.wiki.git` clone only as publication plumbing, not as an authored source.
