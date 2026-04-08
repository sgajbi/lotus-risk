.PHONY: install lint monetary-float-guard no-alias-gate typecheck openapi-gate api-vocabulary-gate migration-smoke migration-apply test test-unit test-integration test-e2e test-pyramid-gate test-coverage coverage-gate security-audit check ci docker-build clean

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

monetary-float-guard:
	python scripts/check_monetary_float_usage.py

no-alias-gate:
	python scripts/no_alias_contract_guard.py

typecheck:
	mypy --config-file mypy.ini

openapi-gate:
	python scripts/openapi_quality_gate.py

api-vocabulary-gate:
	python scripts/api_vocabulary_inventory.py --validate-only

migration-smoke:
	python scripts/migration_contract_check.py --mode no-schema

migration-apply:
	python scripts/migration_contract_check.py --mode no-schema

test:
	$(MAKE) test-unit

test-unit:
	python -m pytest tests/unit

test-integration:
	python -m pytest tests/integration

test-e2e:
	python -m pytest tests/e2e

test-pyramid-gate:
	python scripts/test_pyramid_gate.py

test-coverage:
	COVERAGE_FILE=.coverage.unit python -m pytest tests/unit --cov=src --cov-report=
	COVERAGE_FILE=.coverage.integration python -m pytest tests/integration --cov=src --cov-report=
	COVERAGE_FILE=.coverage.e2e python -m pytest tests/e2e --cov=src --cov-report=
	python -m coverage combine .coverage.unit .coverage.integration .coverage.e2e
	python -m coverage report --fail-under=98

security-audit:
	python -m pip_audit

check: lint no-alias-gate typecheck openapi-gate api-vocabulary-gate test

ci: lint no-alias-gate typecheck openapi-gate api-vocabulary-gate migration-smoke test-pyramid-gate test-integration test-e2e test-coverage security-audit

docker-build:
	docker build -t backend-service:ci-test .

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache']]; [pathlib.Path(p).unlink(missing_ok=True) for p in ['.coverage', '.coverage.unit', '.coverage.integration', '.coverage.e2e']]"


