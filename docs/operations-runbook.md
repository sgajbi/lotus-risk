# Lotus Risk Operations Runbook

This file is a pointer. Everything it used to restate is authored in one of the places below, and
keeping a second copy here let the two drift.

| what you came for | where it is authored |
|---|---|
| standard commands, incident first checks, alert runbooks, escalation paths | [`docs/runbooks/service-operations.md`](runbooks/service-operations.md) |
| operational entry points, `/health/ready` and `/ops` interpretation, CI-local container isolation, canonical local upstreams, common misconfiguration | [Operations Runbook](https://github.com/sgajbi/lotus-risk/wiki/Operations-Runbook) |
| enterprise deployment security posture, authorization, key and rotation configuration, ingress body limits, trusted ingress | [`docs/security-deployment-policy.md`](security-deployment-policy.md) |
| every runtime setting, downstream connection pools, safe-URL policy | [`docs/configuration.md`](configuration.md) |
| upstream failure behaviour and dependency-specific pool variables | [`docs/domain-apis/risk-upstream-failure-behavior.md`](domain-apis/risk-upstream-failure-behavior.md) |
| quality-baseline posture and why report-only gates are not readiness proof | [Validation and CI](https://github.com/sgajbi/lotus-risk/wiki/Validation-and-CI) |
