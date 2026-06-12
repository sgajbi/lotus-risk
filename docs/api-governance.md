# Lotus Risk API Governance

Risk APIs must remain explicit, version-aware, documented, and domain-correct.

## Endpoint Rules

1. Every endpoint defines summary, description, tags, response model, operation ID, examples, and
   standard error responses.
2. Calculation endpoints document input modes, source ownership, lineage, supportability, and
   downstream failure behavior.
3. Future list endpoints must use shared pagination, filtering, and sorting contracts before
   publication.
4. Health, readiness, liveness, metadata, metrics, operational, and public analytics endpoints must
   remain separated in code and documentation.

## Error Contract

`lotus-risk` preserves the standard Lotus error envelope:

- `error.code`
- `error.message`
- `error.correlation_id`
- optional `error.details`

For RFC 7807/problem-details compatibility, the same `error` object also carries:

- `error.type`
- `error.title`
- `error.status`
- `error.detail`
- `error.instance`

The compatibility fields are additive. They do not replace the Lotus envelope, and clients should
continue to treat `error.code` as the stable machine-readable Lotus error code.

## Current Gates

The repo runs OpenAPI quality, API vocabulary, no-alias, type, lint, security, and test gates
through `Makefile`. `make openapi-gate` evaluates the generated FastAPI OpenAPI schema and fails
missing summaries, descriptions, tags, operation IDs, success/error responses, JSON request
examples for mutation endpoints, schema field descriptions/examples, and duplicate operation IDs.
`make openapi-artifact-gate` exports `output/openapi/lotus-risk.openapi.json` and validates the
artifact against the repository's Spectral policy expectations from `.spectral.yaml`. The generated
artifact is ignored by Git and should be attached as CI/PR evidence rather than committed.
