# Lotus Risk Security

`lotus-risk` handles front-office-facing risk analytics and must avoid leaking sensitive portfolio,
client, request, response, trace, or correlation data through logs, metrics, errors, or diagnostics.

## Current Controls

1. Enterprise audit middleware enforces write-policy headers and redacts sensitive metadata.
2. Correlation middleware controls request correlation and trace propagation.
3. Dependency failures are mapped into bounded error envelopes.
4. Dependency audit is enforced through `make security-audit` using an isolated project-scoped
   install, not the developer's global Python environment.
5. Bandit configuration is added for progressive static security evidence.
6. Abuse-control and threat-model evidence is recorded in
   [`security-threat-model.md`](security-threat-model.md).
7. Enterprise deployment security posture is recorded in
   [`security-deployment-policy.md`](security-deployment-policy.md).

## Refactor Requirements

1. Keep authorization and audit policy out of business calculation services.
2. Keep secrets in environment/configuration only.
3. Keep abuse-protection and threat-model evidence current before promoting enterprise-readiness
   gates.
4. Prove sensitive-data masking with tests whenever new diagnostics, logs, or metrics are added.
5. Treat `ENTERPRISE_ENFORCE_AUTHZ=true`, `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`, explicit
   capability rules, and ingress/server request body limits as mandatory for bank deployment mode.
