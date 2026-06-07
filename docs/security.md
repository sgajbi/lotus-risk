# Lotus Risk Security

`lotus-risk` handles front-office-facing risk analytics and must avoid leaking sensitive portfolio,
client, request, response, trace, or correlation data through logs, metrics, errors, or diagnostics.

## Current Controls

1. Enterprise audit middleware enforces write-policy headers and redacts sensitive metadata.
2. Correlation middleware treats caller correlation and trace headers as untrusted input:
   correlation IDs are bounded to a safe character set and length, while trace IDs and
   `traceparent` must satisfy the supported W3C format. Unsafe values are replaced instead of
   reflected or logged.
3. Dependency failures are mapped into bounded error envelopes.
   Raw upstream response bodies and transport exception text are not exposed to API callers.
4. Dependency audit is enforced through `make security-audit` using an isolated project-scoped
   install, not the developer's global Python environment.
5. Bandit configuration is added for progressive static security evidence.
6. Abuse-control and threat-model evidence is recorded in
   [`security-threat-model.md`](security-threat-model.md).
7. Enterprise deployment security posture is recorded in
   [`security-deployment-policy.md`](security-deployment-policy.md).
8. Every API response, including early authorization and payload-limit failures, carries
   `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`,
   and the active enterprise policy version.
9. Downstream base URLs fail fast unless they use HTTP(S), include a valid host, and exclude
   embedded credentials, query strings, fragments, whitespace, and control characters. Validation
   errors never echo the rejected value.
10. Authorization-enforced write requests fail closed when no well-formed capability rule matches
    the request path.

## Refactor Requirements

1. Keep authorization and audit policy out of business calculation services.
2. Keep secrets in environment/configuration only.
3. Keep abuse-protection and threat-model evidence current before promoting enterprise-readiness
   gates.
4. Prove sensitive-data masking with tests whenever new diagnostics, logs, or metrics are added.
5. Treat `ENTERPRISE_ENFORCE_AUTHZ=true`, `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`, explicit
   capability rules, and ingress/server request body limits as mandatory for bank deployment mode.
