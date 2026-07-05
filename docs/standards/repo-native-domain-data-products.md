# Repo-Native Domain Data Products

This document records the `lotus-risk` repo-native declaration and validation posture introduced for
RFC-0086.

## Declaration Location

The governed in-repo declaration location for `lotus-risk` is:

1. `contracts/domain-data-products/lotus-risk-products.v1.json`
2. `contracts/domain-data-products/lotus-risk-consumers.v1.json`

This location keeps machine-readable producer and consumer truth in the authoritative domain
repository instead of in `lotus-platform`.

## Repo-Native Validation Path

Use:

```powershell
make domain-data-product-gate
```

That target runs `scripts/domain_data_product_contract_check.py`, which:

1. validates the repo-native declarations against the platform-owned RFC-0084 validator logic,
2. loads the platform semantics and trust registries as the governed vocabulary source,
3. cross-checks local consumer dependencies against the currently declared upstream producer files,
4. compares the repo-native files against the transitional platform mirrors to keep additive
   migration truthful,
5. validates each declared `current_routes` success response schema against
   `required_trust_metadata` using governed response paths.

The route-response proof is intentionally schema-based. Product identity must be exposed as
`product_name` and `product_version` and must not be silently inferred from `contract_version`.
Shared lineage fields are normally emitted under `metadata.*`, while route-specific equivalents are
allowed only through the explicit mapping table in `scripts/domain_data_product_contract_check.py`
for fields such as `as_of_date`, `coverage_ratio`, and `coverage_status`.

## Transitional Copy Policy

The platform files:

1. `lotus-platform/platform-contracts/domain-data-products/lotus-risk-products.v1.json`
2. `lotus-platform/platform-contracts/domain-data-products/lotus-risk-consumers.v1.json`

remain explicit transitional mirrors for this rollout wave.

Ownership status is therefore:

1. `lotus-risk` owns the repo-native files in `contracts/domain-data-products/`,
2. `lotus-platform` holds mirror copies only until federation aggregation no longer depends on
   them,
3. the mirror state is temporary and must not be treated as long-term declaration ownership.

## RFC-0087 Preparation Seam

The minimal future telemetry emission seam for `lotus-risk` should be built from existing repo-local
truth rather than new gateway logic:

1. service and dependency runtime state from `src/app/ops_runtime.py`,
2. product execution and dependency call signals from `src/app/observability.py`,
3. product lineage fields already emitted in response metadata through
   `request_fingerprint`, `source_services`, and `upstream_request_fingerprints`.

That is the narrowest additive path into RFC-0087 because it reuses current domain-owned runtime
and lineage evidence instead of inventing a second trust status layer inside the request handlers or
moving product truth into `lotus-gateway`.

The current in-repo preparation seam is `src/app/trust_telemetry.py`, backed by
`src/app/domain_data_products.py`, which assembles a repo-local telemetry seed from those existing
sources and resolves product lifecycle from the repo-native declaration catalog without introducing
platform certification rules or a new publication contract yet.

The current operator-facing inspection path for that seam is `GET /ops/trust-telemetry`. It is a
repo-local raw telemetry snapshot that returns repo-owned seeds for operator review only and must
not be treated as a platform-certified trust artifact until RFC-0087 introduces certified trust
artifacts.

Static/certified trust evidence is tracked separately from the raw operator seam. The
`contracts/trust-telemetry-coverage/lotus-risk-trust-telemetry-coverage.v1.json` contract lists
every active declared product and marks it as either `certified_static_snapshot` with a matching
`contracts/trust-telemetry/*.telemetry.v1.json` artifact or `pending_static_snapshot` with owner,
decision date, and rationale. `scripts/validate_trust_telemetry_contracts.py` fails if an active
product is missing both a static snapshot and a governed coverage treatment.

Each raw seed now carries the declaration-derived `authoritative_domain`, `product_family`, and
`current_routes` fields in addition to runtime and lineage evidence so operator review can connect
the raw trust posture back to the governing repo-native declaration without cross-referencing the
JSON files manually.

The snapshot itself now carries a deterministic declaration fingerprint, and each product seed
includes the declaration-governed `approved_consumers` and `required_trust_metadata` fields. That
lets operator review compare observed runtime posture against the declaration-backed trust contract
without introducing a platform certification plane inside this repo.

The same operator snapshot now also carries the repo-native consumer declaration source,
fingerprint, and declared upstream dependency set. That lets reviewers inspect producer truth,
consumer dependency truth, and raw runtime dependency posture in one place while RFC-0087 is still
at the preparation stage.

Each declared upstream dependency now also carries the current runtime status observed for its
producer service. That keeps the operator snapshot useful for review because declared dependency
posture and live producer-health posture can be compared in one place without implying any platform
certification semantics.

The snapshot now also carries an operator review summary with declared product and dependency counts,
degraded and unavailable dependency counts, and the affected declared dependency product names. That
keeps review fast without changing the underlying raw declaration-backed evidence carried in the
same snapshot.

## Current Open Decisions

1. whether platform aggregation should discover repo-native files directly from this path or through
   a later manifest-driven inventory,
2. when the transitional platform mirrors can be removed safely,
3. whether future trust telemetry should publish one repo-level artifact per product family or one
   per request-capable route family.
