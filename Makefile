.PHONY: install install-ci verify-dependencies lint monetary-float-guard no-alias-gate typecheck openapi-gate api-vocabulary-gate migration-smoke migration-apply test test-unit test-integration test-e2e test-pyramid-gate test-coverage coverage-gate security-audit check ci docker-build clean

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

install-ci:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

verify-dependencies:
	python scripts/dependency_health_check.py --skip-audit --skip-outdated

lint:
	python -m ruff check .
	python -m ruff format --check .

monetary-float-guard:
	python scripts/check_monetary_float_usage.py

no-alias-gate:
	python scripts/no_alias_contract_guard.py

typecheck:
	python -m mypy --config-file mypy.ini

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
	python scripts/dependency_health_check.py --skip-outdated

check: lint no-alias-gate typecheck openapi-gate api-vocabulary-gate test

ci: lint no-alias-gate typecheck openapi-gate api-vocabulary-gate migration-smoke test-pyramid-gate security-audit test-unit test-integration test-e2e test-coverage docker-build

docker-build:
	docker build -t backend-service:ci-test .

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache']]; [pathlib.Path(p).unlink(missing_ok=True) for p in ['.coverage', '.coverage.unit', '.coverage.integration', '.coverage.e2e']]"


