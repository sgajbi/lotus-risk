# Lotus Risk Codebase Review Playbook

## Purpose

This playbook governs the enterprise refactor continuation. Reviews are pattern-based, evidence-led,
and completed in small behavior-preserving slices.

## Status Model

| Status | Meaning |
| --- | --- |
| Planned | Scope identified but not yet inspected |
| Reviewing | Evidence collection is active |
| Refactor Needed | Material issue confirmed and not yet resolved |
| Hardened | Material issue improved with focused evidence; broader follow-up remains |
| Signed Off | Scope has code, tests, relevant gates, and no known material follow-up |

## Review Units

1. quality measurement and CI truthfulness,
2. architecture dependency boundaries,
3. router and application orchestration thinness,
4. analytics calculation correctness and complexity,
5. downstream client resilience and error mapping,
6. API/OpenAPI governance,
7. security and sensitive-data controls,
8. observability and operational diagnostics,
9. dead code, duplication, and dependency hygiene,
10. implementation-backed documentation and PR evidence.

## Evidence Standard

A review unit may be signed off only when the ledger records:

1. concrete findings and their consequence,
2. code or documentation changes where needed,
3. focused tests or characterization evidence,
4. applicable lint, type, architecture, security, OpenAPI, or runtime gates,
5. explicit follow-up for anything not completed.

Full-suite or end-to-end success is supporting proof, not a substitute for focused lower-level tests.

