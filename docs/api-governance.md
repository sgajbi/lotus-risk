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

## Current Gates

The repo runs OpenAPI quality, API vocabulary, no-alias, type, lint, security, and test gates
through `Makefile`. `make openapi-gate` evaluates the generated FastAPI OpenAPI schema and fails
missing summaries, descriptions, tags, operation IDs, success/error responses, JSON request
examples for mutation endpoints, schema field descriptions/examples, and duplicate operation IDs.
`.spectral.yaml` remains secondary lint scaffolding until generated Spectral artifact export is
standardized for CI.
