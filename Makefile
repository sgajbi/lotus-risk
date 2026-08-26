.PHONY: architecture-gate complexity-gate source-size-gate dead-code-gate dependency-hygiene-gate github-actions-runtime-gate install install-ci check check-all test test-unit test-integration test-e2e test-all test-coverage test-fast test-all-fast test-all-no-cov test-all-parallel ci ci-local ci-local-docker ci-local-docker-down typecheck typecheck-tests-critical lint monetary-float-guard domain-product-validate domain-data-product-gate trust-telemetry-validate observability-contract-validate mesh-contract-validate idea-opportunity-evidence-gate idea-opportunity-runtime-evidence image-supply-chain-gate no-alias-gate openapi-gate openapi-artifact-gate api-vocabulary-gate format clean run check-deps security-audit migration-smoke migration-apply pre-commit docker-build docker-up docker-down test-pyramid-gate quality-baseline maintainability-report

COVERAGE_FAIL_UNDER ?= 98
SOURCE_FILE_MAX_LINES ?= 450
GIT_COMMIT_SHA ?= $(if $(GITHUB_SHA),$(GITHUB_SHA),$(shell git rev-parse HEAD 2>/dev/null || echo unknown))
GIT_BRANCH ?= $(if $(GITHUB_HEAD_REF),$(GITHUB_HEAD_REF),$(if $(GITHUB_REF_NAME),$(GITHUB_REF_NAME),$(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)))
SERVICE_VERSION ?= 0.1.0
BUILD_TIMESTAMP ?= $(shell python -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'))")
REPO_URL ?= $(if $(GITHUB_REPOSITORY),$(GITHUB_SERVER_URL)/$(GITHUB_REPOSITORY),$(shell git config --get remote.origin.url 2>/dev/null || echo unknown))
IMAGE_DIGEST ?= $(if $(LOTUS_IMAGE_DIGEST),$(LOTUS_IMAGE_DIGEST),unavailable-before-publish)
CI_PIPELINE_RUN_ID ?= $(if $(GITHUB_RUN_ID),$(GITHUB_RUN_ID),local)
CONTAINER_BUILD_TARGET ?= runtime
IDEA_OPPORTUNITY_RISK_BASE_URL ?= http://localhost:8130
IDEA_OPPORTUNITY_GENERATED_AT_UTC ?= $(BUILD_TIMESTAMP)
IDEA_OPPORTUNITY_EVIDENCE_OUTPUT ?= output/idea-opportunity-runtime-evidence/idea-risk-runtime-evidence.json

install:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"
	pre-commit install

install-ci:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"

pre-commit:
	pre-commit run --all-files

check: github-actions-runtime-gate lint no-alias-gate typecheck openapi-gate openapi-artifact-gate api-vocabulary-gate mesh-contract-validate image-supply-chain-gate source-size-gate test

ci: github-actions-runtime-gate lint check-deps architecture-gate no-alias-gate typecheck openapi-gate openapi-artifact-gate api-vocabulary-gate mesh-contract-validate image-supply-chain-gate complexity-gate source-size-gate dependency-hygiene-gate dead-code-gate migration-smoke test-pyramid-gate test-all security-audit docker-build

quality-baseline:
	python scripts/generate_quality_baseline.py

github-actions-runtime-gate:
	python scripts/validate_github_actions_runtime.py

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

# Split-suite local coverage loop without Docker. Use `make ci` for PR-grade parity.
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
	docker compose -f docker-compose.ci-local.yml up --build --force-recreate --remove-orphans --abort-on-container-exit --exit-code-from ci-local ci-local

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

migration-smoke:
	python scripts/migration_contract_check.py --mode no-schema

migration-apply:
	python scripts/migration_contract_check.py --mode no-schema

lint:
	python -m ruff check .
	python -m ruff format --check .
	$(MAKE) monetary-float-guard

architecture-gate:
	python -m importlinter.cli check .importlinter

complexity-gate:
	python scripts/python_complexity_inventory.py --limit 15 --max-cc 24 --max-high-complexity 1 --max-medium-complexity 6

maintainability-report:
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

idea-opportunity-evidence-gate:
	python -m pytest tests/unit/test_idea_opportunity_runtime_evidence.py -q

idea-opportunity-runtime-evidence:
	python scripts/generate_idea_opportunity_runtime_evidence.py \
		--risk-base-url "$(IDEA_OPPORTUNITY_RISK_BASE_URL)" \
		--generated-at-utc "$(IDEA_OPPORTUNITY_GENERATED_AT_UTC)" \
		--output "$(IDEA_OPPORTUNITY_EVIDENCE_OUTPUT)"

image-supply-chain-gate:
	python scripts/validate_image_supply_chain.py

format:
	python -m ruff format .

clean:
	python scripts/clean_generated_artifacts.py

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
	docker build \
		--target "$(CONTAINER_BUILD_TARGET)" \
		--build-arg LOTUS_GIT_COMMIT_SHA="$(GIT_COMMIT_SHA)" \
		--build-arg LOTUS_GIT_BRANCH="$(GIT_BRANCH)" \
		--build-arg LOTUS_SERVICE_VERSION="$(SERVICE_VERSION)" \
		--build-arg LOTUS_BUILD_TIMESTAMP="$(BUILD_TIMESTAMP)" \
		--build-arg LOTUS_REPO_URL="$(REPO_URL)" \
		--build-arg LOTUS_IMAGE_DIGEST="$(IMAGE_DIGEST)" \
		--build-arg LOTUS_CI_PIPELINE_RUN_ID="$(CI_PIPELINE_RUN_ID)" \
		-t lotus-risk:ci .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
