# Lotus Risk OpenAPI Artifact Evidence

This file records the current generated OpenAPI artifact proof for final PR assembly. The generated
artifact itself is ignored by Git and should be attached to the PR or uploaded as CI evidence rather
than committed.

## Artifact

| Field | Value |
| --- | --- |
| Artifact path | `output/openapi/lotus-risk.openapi.json` |
| Generation command | `make openapi-artifact-gate` |
| Validation command | `make openapi-gate` |
| Generated from branch | `feat/enterprise-risk-refactor-production-hardening` |
| OpenAPI version | `3.1.0` |
| API title | `lotus-risk` |
| API version | `0.1.0` |
| Path count | `16` |
| Operation count | `16` |
| Artifact size bytes | `449637` |
| SHA-256 | `9FA31D518B37B95A4F73079A7393ADDF81A041F8BDA4309CA23D5D42598055F8` |

## Validation

The current local artifact was regenerated and validated with:

```text
make openapi-artifact-gate
make openapi-gate
```

Both commands passed. Final PR evidence should regenerate this file's artifact immediately before PR
creation and attach or reference `output/openapi/lotus-risk.openapi.json` with the current checksum.
