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
   migration truthful.

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

## Current Open Decisions

1. whether platform aggregation should discover repo-native files directly from this path or through
   a later manifest-driven inventory,
2. when the transitional platform mirrors can be removed safely,
3. whether future trust telemetry should publish one repo-level artifact per product family or one
   per request-capable route family.
