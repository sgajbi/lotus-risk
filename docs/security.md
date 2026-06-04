# Lotus Risk Security

`lotus-risk` handles front-office-facing risk analytics and must avoid leaking sensitive portfolio,
client, request, response, trace, or correlation data through logs, metrics, errors, or diagnostics.

## Current Controls

1. Enterprise audit middleware enforces write-policy headers and redacts sensitive metadata.
2. Correlation middleware controls request correlation and trace propagation.
3. Dependency failures are mapped into bounded error envelopes.
4. Dependency audit is enforced through `make security-audit`.
5. Bandit configuration is added for progressive static security evidence.

## Refactor Requirements

1. Keep authorization and audit policy out of business calculation services.
2. Keep secrets in environment/configuration only.
3. Add abuse-protection and threat-model evidence before promoting enterprise-readiness gates.
4. Prove sensitive-data masking with tests whenever new diagnostics, logs, or metrics are added.
