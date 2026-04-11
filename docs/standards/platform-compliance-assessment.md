# lotus-risk Platform Compliance Assessment

## Baseline (Before This Change Set)

- Coverage gate threshold in CI/Makefile: `85%` (below lotus-platform `99%+` policy).
- No explicit in-repo automated test pyramid gate.
- E2E suite depth: 2 smoke tests; low confidence for critical risk workflow contract behavior.
- `openapi_quality_gate.py` depended on pre-installed editable package context.
- README quick-start formatting was malformed.

## Current State (After This Change Set)

- Coverage gate threshold: `99%` in both `Makefile` and CI workflow.
- Test pyramid gate added and wired into CI:
  - Unit: `35` tests (`70%`)
  - Integration: `11` tests (`22%`)
  - E2E: `4` tests (`8%`)
  - Distribution now enforced to platform target bands.
- E2E coverage expanded to include:
  - risk calculate happy path with domain metric assertions
  - risk calculate invalid period contract path (`422`)
- OpenAPI quality gate now resolves `src` path directly for deterministic execution.
- README quick-start blocks corrected.

## Validation Evidence

- `python -m ruff check .`
- `python -m mypy --config-file mypy.ini`
- `python -m pytest -q --cov=src --cov-report=term-missing`
- `python scripts/openapi_quality_gate.py`
- `python scripts/migration_contract_check.py --mode no-schema`
- `python scripts/check_monetary_float_usage.py`
- `python scripts/test_pyramid_gate.py`

All commands passed in local verification for this change set.

## Monetary Float Guard Scope

- The guard now targets money-bearing identifiers only.
- Analytics-only identifiers such as `risk`, `return`, and `weight` are no longer treated as monetary fields by default.
- Monetary-bearing identifiers such as `amount`, `price`, `market_value`, `cash_balance`, `fee_amount`, and `notional` remain blocked unless explicitly allowlisted or annotated for temporary review.
