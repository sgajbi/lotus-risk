# Development Workflow and CI Strategy

This repository follows the platform standard for engineering workflow, CI tiering, and merge hygiene.

Canonical standard:
- `lotus-platform/platform-standards/Development-Workflow-and-CI-Strategy-Standard.md`

## Required model
1. Branch from `main` and keep one branch per RFC/slice.
2. Use PR-first delivery (no direct commits to `main`).
3. Keep PR checks fast and meaningful (blocking).
4. Run heavier checks in scheduled/manual/mainline tiers.
5. Merge only with green required checks.
6. Always finish with `local = remote = main`.

## Image release controls

Use `make image-supply-chain-gate` whenever Docker, workflow, deployment, release, or runtime
metadata behavior changes. The gate enforces the current release contract:

1. images are pushed only by the CI image-release workflow,
2. release images are tagged by Git SHA and carry source/build/version/CI OCI labels,
3. release evidence includes SBOM, vulnerability scan, signature, provenance attestation, and a
   digest-bearing release manifest,
4. Kubernetes and Helm deployment manifests must use `image@sha256:<digest>`,
5. Docker `ARG` and `ENV` metadata must not expose secret-like names.
