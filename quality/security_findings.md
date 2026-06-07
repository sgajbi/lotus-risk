# Lotus Risk Security Findings

This register records security findings for the enterprise refactor continuation. Findings require
code and test evidence before closure.

| Finding ID | Class | Status | Evidence | Required action |
| --- | --- | --- | --- | --- |
| SEC-REF-001 | Runtime identity validation evidence | Open, platform-dependent | `quality/refactor_health_report.md`; `docs/security-deployment-policy.md` | Add gateway-backed token-validation and final runtime configuration proof before release promotion. |
| SEC-REF-002 | Untrusted request-correlation and trace headers | Hardened | Correlation middleware previously reflected and logged unbounded caller-supplied correlation IDs and preserved malformed or mismatched `traceparent` values. | Bounded correlation IDs to a safe character set and length; validate W3C trace IDs/traceparent; replace malformed, zero, or mismatched values; retain focused negative tests. |
| SEC-REF-003 | Sensitive-data logging and metric labels | Reviewing | Existing redaction and bounded-label tests; `make security-audit` baseline passes | Review negative coverage across downstream failures and operational diagnostics; add focused tests for any uncovered path. |
| SEC-REF-004 | Dependency and source vulnerability posture | Hardened | `make security-audit`; generated current-state baseline reports zero known dependency vulnerabilities and no high-severity Bandit findings | Keep active in all delivery lanes and document any future exception with owner and expiry. |
