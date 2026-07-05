# Lotus Risk OpenAPI Artifact Evidence

This file defines the current OpenAPI artifact evidence contract for final PR assembly. Exact
branch, commit, timestamp, checksum, size, path count, and operation count evidence is generated
under `output/openapi/` by `make openapi-artifact-gate`; it is ignored by Git and should be attached
to the PR or uploaded as CI evidence rather than committed.

Do not pin current branch names, commit SHAs, artifact checksums, or test counts in this tracked
file. Those values must come from the generated evidence manifest.

## Generated Files

`make openapi-artifact-gate` writes and validates:

1. `output/openapi/lotus-risk.openapi.json`
2. `output/openapi/lotus-risk.openapi.evidence.json`
3. `output/openapi/lotus-risk.openapi.evidence.md`

The generated evidence includes:

1. Git branch.
2. Git commit SHA.
3. Repository URL.
4. CI pipeline/run ID, or `local` for local runs.
5. UTC generation timestamp.
6. Generation and validation commands.
7. OpenAPI version, API title, API version, Path count, and Operation count.
8. Artifact size bytes.
9. Artifact SHA-256.

## Validation

```text
make openapi-artifact-gate
make openapi-gate
```

`make openapi-artifact-gate` regenerates the artifact and evidence manifests, then validates that
the evidence matches the just-written artifact and current source identity. Final PR evidence should
attach or reference the generated OpenAPI JSON and generated evidence manifest from the final branch
head.
