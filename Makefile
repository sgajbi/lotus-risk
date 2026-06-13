.PHONY: architecture-gate complexity-gate source-size-gate dead-code-gate dependency-hygiene-gate install install-ci check check-all test test-unit test-integration test-e2e test-all test-coverage test-fast test-all-fast test-all-no-cov test-all-parallel ci ci-local ci-local-docker ci-local-docker-down typecheck typecheck-tests-critical lint monetary-float-guard domain-product-validate domain-data-product-gate trust-telemetry-validate observability-contract-validate mesh-contract-validate no-alias-gate openapi-gate openapi-artifact-gate api-vocabulary-gate format clean run check-deps security-audit migration-smoke migration-apply pre-commit docker-build docker-up docker-down test-pyramid-gate quality-baseline

COVERAGE_FAIL_UNDER ?= 98
SOURCE_FILE_MAX_LINES ?= 450

install:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"
	pre-commit install

install-ci:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"

pre-commit:
	pre-commit run --all-files

check: lint no-alias-gate typecheck openapi-gate openapi-artifact-gate api-vocabulary-gate mesh-contract-validate source-size-gate test

ci: lint no-alias-gate typecheck openapi-gate openapi-artifact-gate api-vocabulary-gate migration-smoke source-size-gate test-all security-audit

quality-baseline:
	python scripts/generate_quality_baseline.py

test-pyramid-gate:
	python scripts/test_pyramid_gate.py

test:
	$(MAKE) test-unit

test-unit:
	python -m pytest tests/unit

test-integration:
	python -m pytest tests/integration

test-e2e:
	python -m pytest tests/e2e

test-all:
	python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=$(COVERAGE_FAIL_UNDER)

test-coverage: test-all

# Fast local loop: unit tests only (no coverage)
test-fast:
	python -m pytest tests/unit -q

# Full suite with coverage gate, but without term-missing output overhead
test-all-fast:
	python -m pytest --cov=src --cov-report= --cov-fail-under=$(COVERAGE_FAIL_UNDER)

# Full suite without coverage for quickest full functional signal
test-all-no-cov:
	python -m pytest

# Full suite, optional parallel workers when pytest-xdist is installed
test-all-parallel:
	python -c "import importlib.util, subprocess, sys; args=[sys.executable,'-m','pytest','--cov=src','--cov-report=','--cov-fail-under=$(COVERAGE_FAIL_UNDER)']; args += (['-n','auto','--dist','loadscope'] if importlib.util.find_spec('xdist') else []); raise SystemExit(subprocess.call(args))"

# Local execution flow aligned with the Pull Request Merge Gate workflow
ci-local: lint check-deps
	COVERAGE_FILE=.coverage.unit python -m pytest tests/unit --cov=src --cov-report=
	COVERAGE_FILE=.coverage.integration python -m pytest tests/integration --cov=src --cov-report=
	COVERAGE_FILE=.coverage.e2e python -m pytest tests/e2e --cov=src --cov-report=
	python -m coverage combine .coverage.unit .coverage.integration .coverage.e2e
	python -m coverage report --fail-under=$(COVERAGE_FAIL_UNDER)
	$(MAKE) no-alias-gate
	$(MAKE) openapi-gate
	$(MAKE) api-vocabulary-gate
	$(MAKE) typecheck

ci-local-docker:
	docker compose -f docker-compose.ci-local.yml up --build --abort-on-container-exit --exit-code-from ci-local ci-local

ci-local-docker-down:
	docker compose -f docker-compose.ci-local.yml down -v --remove-orphans

check-all: lint typecheck test-all

typecheck:
	python -m mypy --config-file mypy.ini

typecheck-tests-critical:
	python -m mypy tests/unit/core/test_capabilities.py tests/unit/dpm/engine/test_engine_workflow_gates.py

openapi-gate:
	python scripts/openapi_quality_gate.py

openapi-artifact-gate:
	python scripts/export_openapi_artifact.py --check

no-alias-gate:
	python scripts/no_alias_contract_guard.py

api-vocabulary-gate:
	python scripts/api_vocabulary_inventory.py --validate-only

MIGRATION_SMOKE_TESTS := $(wildcard tests/unit/shared/dependencies/test_postgres_migrations.py tests/unit/shared/dependencies/test_production_cutover_contract.py)

migration-smoke:
	@if [ -n "$(MIGRATION_SMOKE_TESTS)" ]; then \
		python -m pytest $(MIGRATION_SMOKE_TESTS) -q; \
	else \
		echo "Skipping migration smoke tests: legacy migration smoke test files are not present."; \
	fi

migration-apply:
	python scripts/postgres_migrate.py --target dpm

lint:
	python -m ruff check .
	python -m ruff format --check .
	$(MAKE) monetary-float-guard

architecture-gate:
	python -m importlinter.cli check .importlinter

complexity-gate:
	python -m radon cc src -s -n C
	python -m radon mi src -s

source-size-gate:
	python scripts/source_size_gate.py --max-lines=$(SOURCE_FILE_MAX_LINES)

dependency-hygiene-gate:
	python -m deptry .

dead-code-gate:
	python -m vulture src tests --min-confidence 80

monetary-float-guard:
	python scripts/check_monetary_float_usage.py

domain-product-validate:
	python scripts/domain_data_product_contract_check.py

domain-data-product-gate: domain-product-validate

trust-telemetry-validate:
	python scripts/validate_trust_telemetry_contracts.py

observability-contract-validate:
	python scripts/validate_observability_contracts.py

mesh-contract-validate: domain-product-validate trust-telemetry-validate observability-contract-validate

format:
	python -m ruff format .

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['__pycache__', '.pytest_cache', 'htmlcov', '.ruff_cache', '.mypy_cache']]; pathlib.Path('.coverage').unlink(missing_ok=True)"

run:
	uvicorn src.app.main:app --reload --port 8130

run-canonical:
	uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8130

check-deps:
	python -m pip check

security-audit:
	# PYSEC-2024-277 / CVE-2024-34997 is a disputed joblib trusted-cache
	# deserialization advisory with no fixed release in the current audit feed.
	python -m bandit -q -r src -c pyproject.toml --severity-level high
	python scripts/dependency_health_check.py --skip-outdated

docker-build:
	docker build -t lotus-risk:ci .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
