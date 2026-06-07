# Lotus Risk Security Findings

This register records security findings for the enterprise refactor continuation. Findings require
code and test evidence before closure.

| Finding ID | Class | Status | Evidence | Required action |
| --- | --- | --- | --- | --- |
| SEC-REF-001 | Runtime identity validation evidence | Open, platform-dependent | `quality/refactor_health_report.md`; `docs/security-deployment-policy.md` | Add gateway-backed token-validation and final runtime configuration proof before release promotion. |
| SEC-REF-002 | Sensitive-data logging and metric labels | Reviewing | Existing redaction and bounded-label tests; `make security-audit` baseline passes | Review negative coverage across middleware, downstream failures, and operational diagnostics; add focused tests for any uncovered path. |
| SEC-REF-003 | Dependency and source vulnerability posture | Hardened | `make security-audit`; generated current-state baseline reports zero known dependency vulnerabilities and no high-severity Bandit findings | Keep active in all delivery lanes and document any future exception with owner and expiry. |

