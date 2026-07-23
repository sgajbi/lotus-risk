# Lotus Risk Documentation Index

This index routes agents, developers, BAs, ops/support, sales/marketing, and business/product users
to implementation-backed `lotus-risk` documentation.

## Start Here

| Audience | Read first | Then use |
| --- | --- | --- |
| Agents | `README.md`, `REPOSITORY-ENGINEERING-CONTEXT.md`, this index | `docs/documentation-gap-ledger.md`, `docs/domain-apis/endpoint-matrix.md`, `docs/rfcs/README.md` |
| Developers | `docs/architecture.md`, `docs/operations/development-workflow-and-ci-strategy.md` | `Makefile`, `tests/`, `scripts/`, `docs/configuration.md` |
| BAs and product | `docs/supported-features.md`, `docs/domain-apis/endpoint-matrix.md` | `docs/domain-apis/integration-capabilities.md`, `wiki/Overview.md`, `wiki/Roadmap.md` |
| Ops and support | `docs/runbooks/service-operations.md`, `wiki/Operations-Runbook.md` | `docs/observability.md`, `docs/security-deployment-policy.md`, `docs/operations/live-risk-validation-matrix.md`, `docs/operations/idea-opportunity-runtime-evidence.md` |
| Sales and marketing | `wiki/Overview.md`, `docs/supported-features.md` | `wiki/Roadmap.md`, `docs/rfcs/RFC-0008-enterprise-bank-readiness-and-live-risk-validation-baseline.md` |
| Business users | `wiki/Overview.md`, `wiki/Supported-Features.md` | `docs/domain-apis/risk-product-surface-alignment.md`, `wiki/Integrations.md` |

## Documentation Layers

1. `README.md` is the fast repo entry point.
2. `wiki/` is the authored source for onboarding, operator, business, and product wiki pages.
3. `docs/` holds detailed architecture, API, methodology, standards, operations, security, RFC, and
   quality evidence.
4. `quality/` holds generated or curated quality reports and PR-readiness evidence.
5. `contracts/` holds repo-native machine-readable domain data product, trust telemetry, and
   observability contracts.

## Implementation Truth Sources

Use code and executable checks when documentation is uncertain:

1. router layout: `src/app/app_factory.py` and `src/app/routers/`,
2. API contracts: `src/app/contracts/`,
3. analytics behavior: `src/app/services/`,
4. upstream integration: `src/app/integrations/`,
5. command surface: `Makefile`,
6. CI lanes: `.github/workflows/`,
7. contract and methodology tests: `tests/unit/` and `tests/integration/`.

## Where To Change What

| Change type | Primary files |
| --- | --- |
| API behavior or request/response shape | `src/app/routers/`, `src/app/contracts/`, `docs/domain-apis/`, OpenAPI gates, integration tests |
| Methodology behavior | `src/app/services/`, `docs/methodologies/`, methodology tests |
| Upstream dependency behavior | `src/app/integrations/`, `docs/domain-apis/RFC-0082-upstream-contract-family-map.md`, integration tests |
| Runtime configuration | `docs/configuration.md`, `.env.example`, `src/app/integrations/downstream_profile_env.py`, configuration tests |
| Observability or supportability | `src/app/observability.py`, `contracts/observability/`, `docs/observability.md`, `docs/runbooks/service-operations.md` |
| Security posture | `src/app/enterprise_readiness.py`, `docs/security-deployment-policy.md`, `docs/security.md`, security tests |
| Business/product support claims | `docs/supported-features.md`, `docs/domain-apis/endpoint-matrix.md`, `wiki/Supported-Features.md`, `docs/operations/idea-opportunity-runtime-evidence.md`, capability tests |
| Wiki truth | `wiki/`, then `../lotus-platform/automation/Sync-RepoWikis.ps1 -CheckOnly -Repository lotus-risk` |

## Validation Entry Points

1. Fast local gate: `make check`.
2. PR-grade local gate: `make ci`.
3. Domain product and mesh contracts: `make mesh-contract-validate`.
4. OpenAPI and vocabulary gates: `make openapi-gate`, `make openapi-artifact-gate`,
   `make api-vocabulary-gate`.
5. Wiki source check: `../lotus-platform/automation/Sync-RepoWikis.ps1 -CheckOnly -Repository lotus-risk`.

