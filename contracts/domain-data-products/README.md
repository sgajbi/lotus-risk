# Repo-Native Domain Data Product Declarations

This directory is the repo-native declaration home for `lotus-risk` under RFC-0086.

Files in this directory are the local source of truth for:

1. producer declarations published by `lotus-risk`,
2. consumer declarations that describe governed upstream dependencies consumed by `lotus-risk`.

Current files:

1. `lotus-risk-products.v1.json`
2. `lotus-risk-consumers.v1.json`

Validation posture:

1. run `make domain-data-product-gate` for the repo-native declaration check,
2. the local gate validates these files against the platform-owned RFC-0084 registries,
3. the local gate also compares the repo-native files against the transitional platform copies in
   `lotus-platform/platform-contracts/domain-data-products/` until the federation migration removes
   those mirrors.

Migration posture:

1. the repo-native files in this directory are the intended owning-repo path,
2. the matching `lotus-platform` declaration files are transitional mirrors for the current rollout
   wave and should be removed once platform aggregation no longer depends on them.
