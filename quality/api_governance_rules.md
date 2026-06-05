# Lotus Risk API Governance Rules

1. Every endpoint must define summary, description, tags, response model, operation ID, examples,
   and standard error responses; the OpenAPI quality gate must fail missing operation IDs and
   missing JSON request examples for mutation endpoints.
2. POST calculation endpoints must document input mode, source ownership, lineage, supportability,
   and failure semantics.
3. Any list endpoint must use consistent pagination, filtering, and sorting contracts before
   publication.
4. Health, liveness, readiness, metrics, operational, internal, and public analytics endpoints must
   remain separated in code and documentation.
5. Deprecation must be explicit in OpenAPI and supported-feature documentation.
6. RFC-0067 vocabulary and no-alias gates remain mandatory.
