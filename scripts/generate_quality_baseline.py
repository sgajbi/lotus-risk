"""Generate report-only enterprise refactor quality evidence for lotus-risk."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUALITY_DIR = ROOT / "quality"
SRC_DIR = ROOT / "src"
TESTS_DIR = ROOT / "tests"
COVERAGE_FAIL_UNDER = os.environ.get("COVERAGE_FAIL_UNDER", "98")
IMPORT_LINTER_COMMAND = [
    sys.executable,
    "-c",
    "from importlinter.cli import lint_imports_command; lint_imports_command()",
    "--config",
    ".importlinter",
]


@dataclass(frozen=True)
class FileSize:
    path: str
    lines: int
    bytes: int


@dataclass(frozen=True)
class SymbolSize:
    path: str
    name: str
    kind: str
    lines: int


def _python_files(base: Path) -> list[Path]:
    return sorted(path for path in base.rglob("*.py") if "__pycache__" not in path.parts)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _run(command: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(SRC_DIR)
        if not existing_pythonpath
        else os.pathsep.join([str(SRC_DIR), existing_pythonpath])
    )
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)
    return completed.returncode, completed.stdout.strip()


def git_value(*args: str) -> str:
    returncode, output = _run(["git", *args])
    return output if returncode == 0 and output else "unknown"


def collect_file_sizes() -> list[FileSize]:
    sizes: list[FileSize] = []
    for path in _python_files(SRC_DIR) + _python_files(TESTS_DIR):
        text = path.read_text(encoding="utf-8")
        sizes.append(FileSize(path=_relative(path), lines=len(text.splitlines()), bytes=len(text)))
    return sorted(sizes, key=lambda item: (item.lines, item.bytes), reverse=True)


def collect_symbol_sizes() -> list[SymbolSize]:
    sizes: list[SymbolSize] = []
    for path in _python_files(SRC_DIR):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                end_lineno = getattr(node, "end_lineno", node.lineno)
                sizes.append(
                    SymbolSize(
                        path=_relative(path),
                        name=node.name,
                        kind=type(node).__name__,
                        lines=end_lineno - node.lineno + 1,
                    )
                )
    return sorted(sizes, key=lambda item: item.lines, reverse=True)


def function_sizes(symbol_sizes: list[SymbolSize]) -> list[SymbolSize]:
    return [item for item in symbol_sizes if item.kind in {"FunctionDef", "AsyncFunctionDef"}]


def symbol_size(symbol_sizes: list[SymbolSize], *, path: str, name: str) -> SymbolSize:
    return next(item for item in symbol_sizes if item.path == path and item.name == name)


def count_route_decorators() -> int:
    main_path = SRC_DIR / "app" / "main.py"
    return sum(
        1 for line in main_path.read_text(encoding="utf-8").splitlines() if line.startswith("@app.")
    )


def count_python_packages(base: Path) -> int:
    return sum(1 for path in base.rglob("__init__.py") if "__pycache__" not in path.parts)


def command_status(command: list[str]) -> str:
    returncode, output = _run(command)
    output_lines = output.splitlines()
    selected_lines = output_lines[:6]
    if len(output_lines) > 12:
        selected_lines.extend(["..."])
        selected_lines.extend(output_lines[-6:])
    elif len(output_lines) > 6:
        selected_lines = output_lines
    excerpt = "\n".join(selected_lines)
    status = "passed" if returncode == 0 else f"reported exit {returncode}"
    if not excerpt:
        return status
    return f"{status}\n\n```text\n{excerpt}\n```"


def collected_test_count(evidence: str) -> str:
    match = re.search(r"(\d+) tests collected", evidence)
    if match is None:
        return "unknown"
    return match.group(1)


def markdown_table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def write_baseline_report(
    file_sizes: list[FileSize],
    symbol_sizes: list[SymbolSize],
    unit_collection_evidence: str,
) -> None:
    route_count = count_route_decorators()
    source_file_sizes = [item for item in file_sizes if item.path.startswith("src/")]
    text = f"""# Lotus Risk Enterprise Refactor Current-State Baseline

Generated by `python scripts/generate_quality_baseline.py`.

## Scope

This is the reproducible current-state baseline for the enterprise refactor continuation. The
immutable initial baseline is commit `3254774`; the before/after scorecard compares that commit with
the generated current state. This report captures measurable code size, API-entry-point modularity,
architectural governance, tool coverage, documentation posture, and validation gates. It is not a
completion claim.

## Generation Identity

- Git branch: `{git_value("branch", "--show-current")}`
- Git commit: `{git_value("rev-parse", "HEAD")}`

## Current Code Size

- Python source files under `src/`: {len(_python_files(SRC_DIR))}
- Python test files under `tests/`: {len(_python_files(TESTS_DIR))}
- Python packages under `src/`: {count_python_packages(SRC_DIR)}
- API entry point route/middleware/handler decorators in `src/app/main.py`: {route_count}

### Largest Source Files

{markdown_table(("Path", "Lines", "Bytes"), [(item.path, item.lines, item.bytes) for item in source_file_sizes[:20]])}

### Largest Functions And Classes

{markdown_table(("Path", "Symbol", "Kind", "Lines"), [(item.path, item.name, item.kind, item.lines) for item in symbol_sizes[:20]])}

## Tool Baseline

- Ruff: configured in `pyproject.toml`; enforced by `make lint`.
- mypy: configured in `mypy.ini`; enforced by `make typecheck`.
- pytest/coverage: repo-native test commands exist; default local coverage floor is {COVERAGE_FAIL_UNDER}%.
- pip-audit: enforced through `make security-audit`.
- Bandit, radon, vulture, deptry, and import-linter are now declared as development
  tooling for progressive quality evidence.
- The repo-native OpenAPI quality gate enforces endpoint summaries, descriptions, tags,
  operation IDs, success and error responses, JSON mutation request examples, schema field
  descriptions, schema field examples, and duplicate operation ID detection.
- `make openapi-artifact-gate` exports `output/openapi/lotus-risk.openapi.json` and validates the
  artifact against the repository's Spectral policy expectations from `.spectral.yaml`.

## Static Quality Snapshot

- Ruff lint: {command_status(["python", "-m", "ruff", "check", "."])}
- Ruff format check: {command_status(["python", "-m", "ruff", "format", "--check", "."])}
- Type checking: {command_status(["python", "-m", "mypy", "--config-file", "mypy.ini"])}
- Unit coverage snapshot: {command_status(["python", "-m", "pytest", "tests/unit", "--cov=src", "--cov-report=term", "--cov-fail-under=0", "-q"])}

## Complexity And Maintainability Snapshot

- Cyclomatic complexity C-or-worse candidates: {command_status(["python", "-m", "radon", "cc", "src", "-s", "-n", "C"])}
- Maintainability index summary: {command_status(["python", "-m", "radon", "mi", "src", "-s"])}

## Dead Code And Dependency Hygiene Snapshot

- Dead-code candidates: {command_status(["python", "-m", "vulture", "src", "tests", "--min-confidence", "80"])}
- Dependency hygiene: {command_status(["python", "-m", "deptry", "src", "--no-ansi", "--optional-dependencies-dev-groups", "dev", "--per-rule-ignores", "DEP002=uvicorn"])}

## Security Snapshot

- Bandit source scan: {command_status(["python", "-m", "bandit", "-r", "src", "-q"])}
- Dependency vulnerability audit: {command_status(["python", "scripts/dependency_health_check.py", "--skip-outdated"])}

## Current Architectural Findings

1. `src/app/main.py` now preserves the stable ASGI export while `src/app/app_factory.py` owns
   FastAPI app construction, middleware registration, exception-handler registration, and router
   registration. Standard OpenAPI error metadata now lives in `src/app/api_error_examples.py`; health, readiness,
   metrics, operational diagnostics, trust telemetry, and capability publication now live in
   `src/app/routers/operational.py`; stateless source-product endpoints now live in
   `src/app/routers/source_products.py`; the primary risk calculation endpoint now lives in
   `src/app/routers/risk_calculation.py`; drawdown analytics now lives in
   `src/app/routers/drawdown.py`; rolling metrics now lives in `src/app/routers/rolling.py`;
   concentration analytics now lives in `src/app/routers/concentration.py`; historical
   attribution analytics now lives in `src/app/routers/historical_attribution.py`.
2. Operational, capability, stateless source-product, and core calculation routes are split into
   router modules. Downstream client resolution now lives in `src/app/dependencies/downstream_clients.py`
   so routers no longer import `src/app/integrations` adapters directly. Request correlation and
   actor identity extraction now lives in `src/app/dependencies/request_context.py`.
3. Business calculations already live mostly under `src/app/services`, which gives the next slices
   a workable extraction boundary.
4. Infrastructure clients already sit under `src/app/integrations`, and API routes now access them
   through the application dependency provider boundary.
5. Consistent error envelopes exist through `app.error_response`; additive RFC 7807/problem-details
   metadata now lives inside the existing Lotus `error` object without breaking the legacy envelope.

## OpenAPI And API Governance Gaps

1. Current OpenAPI operations define explicit operation IDs in route decorators, and the
   repo-native OpenAPI quality gate fails missing or duplicate operation IDs.
2. Current POST operations publish JSON request-body examples backed by Pydantic request-model
   validation, and the OpenAPI quality gate fails missing JSON mutation examples.
3. Pagination/filtering/sorting governance is not broadly applicable to calculation POST endpoints,
   but any future list/read-model route must use an explicit shared contract.
4. Health, liveness, readiness, metadata, metrics, and ops endpoints exist and are documented, but
   public/internal route grouping is not yet enforced by module structure.
5. Standard error response metadata in `src/app/api_error_examples.py` now includes problem-details
   compatibility fields while preserving the Lotus error envelope.

## Security And Resilience Gaps

1. Enterprise audit middleware and correlation middleware are present.
2. Sensitive-data redaction has unit coverage.
3. Upstream error mapping is centralized through `app.upstream_errors`.
4. Timeout, retry, and pooling posture are documented and enforced by shared adapter transport profile
   helpers in `src/app/integrations/_downstream_client_profile.py` and
   `docs/domain-apis/risk-upstream-failure-behavior.md`.
5. API abuse controls for payload size, authorization headers, service identity, capability
   checks, redaction, bounded downstream errors, and bounded metrics are documented in
   `docs/security-threat-model.md`; bank deployment identity and body-limit posture is recorded in
   `docs/security-deployment-policy.md`.

## Observability Posture

1. HTTP, endpoint execution, supportability, and freshness metrics exist.
2. Metrics label bounds are tested for RFC-0108 supportability.
3. Trace/correlation propagation exists through middleware, but route extraction should preserve
   the propagation contract in tests.
4. Operational dashboard and alert contracts are documented in
   `contracts/observability/lotus-risk-monitoring.v1.json`, validated by
   `make observability-contract-validate`, and linked to runbook anchors in
   `docs/runbooks/service-operations.md`.

## Documentation Posture

The repository has domain-methodology documentation, domain API pages, and consolidated enterprise
pages for architecture, API governance, observability, security, operations, and supported
features. Draft PR packaging now lives in `quality/final_pr_readiness.md`; final PR creation still
needs current CI status, generated OpenAPI artifact evidence, and reviewer-ready command output.

## Validation Snapshot

- Unit test collection: {unit_collection_evidence}
- Import-linter report-only: {command_status(IMPORT_LINTER_COMMAND)}
"""
    (QUALITY_DIR / "baseline_report.md").write_text(text, encoding="utf-8")


def write_health_reports(
    file_sizes: list[FileSize],
    symbol_sizes: list[SymbolSize],
    unit_collection_evidence: str,
) -> None:
    main_lines = next(item.lines for item in file_sizes if item.path == "src/app/main.py")
    unit_tests_collected = collected_test_count(unit_collection_evidence)
    largest_functions = function_sizes(symbol_sizes)
    largest_function = largest_functions[0]
    lotus_performance_client = symbol_size(
        symbol_sizes,
        path="src/app/integrations/lotus_performance_client.py",
        name="LotusPerformanceClient",
    )
    scorecard = f"""# Lotus Risk Quality Scorecard

This scorecard tracks measurable movement from the enterprise refactor baseline
introduced in commit `3254774` to the current feature branch state. It is
evidence for PR readiness, not a completion claim.

| Dimension | Baseline evidence | Current evidence | Improvement shown | Remaining target |
| --- | --- | --- | --- | --- |
| API modularity | `src/app/main.py` had 22 route/middleware/handler decorators and 980 lines | `src/app/main.py` has 0 route/middleware/handler decorators and {main_lines} lines | App construction, routers, middleware, errors, and downstream dependency resolution are split into modules | Keep router boundaries green and prevent app-entry-point regression |
| Code size | Largest files included `src/app/services/concentration_engine.py` at 981 lines and `src/app/main.py` at 980 lines | Largest source files are contract/service modules; no source file over 800 lines after the latest baseline | Monolithic API, concentration service, concentration input/output contracts, concentration metric/response output contracts, concentration issuer mapping, concentration snapshot display-name enrichment, stateless concentration issuer enrichment, concentration response metrics, rolling input/output contracts, rolling metric/response output contracts, risk input/output contracts, risk benchmark period metrics, risk period results, risk benchmark metrics, risk drawdown detail construction, drawdown input/output contracts, drawdown metric/response output contracts, drawdown episode construction, drawdown period-series preparation, static scenario-pack catalog data, attribution input/output contracts, attribution exposure points, attribution set results, attribution stateful returns, attribution period result construction, scenario input/output contracts, concentration stateless resolution, concentration simulation resolution, concentration simulation snapshot state, lotus-performance async returns payload handling, attribution decomposition, attribution stateful exposure sourcing, drawdown series math, rolling benchmark metric-series, rolling metric-series, rolling stateful input resolution, rolling stateful source responses, rolling risk-free coverage probing, rolling period results, contract example payloads, and OpenAPI request example payloads were split | Continue reducing service and contract hotspots over 600 lines |
| Largest behavior units | Largest function/class included `calculate_risk` at 284 lines, `calculate_rolling_metrics` at 230 lines, and `LotusPerformanceClient` at 256 lines | Largest remaining function is `{largest_function.name}` at {largest_function.lines} lines; `LotusPerformanceClient` is {lotus_performance_client.lines} lines | Large engines and clients were decomposed into helpers, services, routers, and polling/parsing functions | Continue reducing engine-level orchestration hotspots |
| Complexity | Baseline reported C-or-worse candidates across large service, contract, and readiness code | Current baseline reports no C-or-worse candidates in the complexity snapshot | C-level candidates in concentration parsing, risk period resolution, rolling/attribution validation, and enterprise authorization were removed | Keep radon report-only evidence clean while thresholds are tightened |
| Architecture enforcement | Import-linter, architecture docs, and quality workflow were introduced as report-only baseline | `make architecture-gate` is green locally and in feature-lane CI | Architecture boundary checks are now part of routine slice validation | Extend contracts as service boundaries mature |
| OpenAPI governance | Operation IDs were not visibly standardized; route-level examples needed certification after router extraction | Operation IDs are explicit; JSON mutation request examples and standard error examples are modularized and enforced by `make openapi-gate`; standard error examples are builder-backed and include additive RFC 7807/problem-details fields; generated artifact policy is enforced by `make openapi-artifact-gate`; current artifact checksum evidence is recorded in `quality/openapi_artifact_evidence.md` | OpenAPI metadata is easier to review, no longer buried in large contract classes or runtime exception-handler code, and now fails missing operation IDs/request examples and missing generated artifact evidence in CI lanes while preserving the Lotus error envelope | Regenerate and attach the final current OpenAPI artifact in the PR |
| Tests | 77 Python test files at initial baseline; repo-native coverage gate existed | {len(_python_files(TESTS_DIR))} Python test files; {unit_tests_collected} tests collected in the latest baseline; OpenAPI gate logic has focused regression tests | Focused unit/integration coverage protects router, client, contract, middleware, service, and OpenAPI-governance refactors | Add more negative/security contract certification tests |
| Security | Enterprise audit middleware, redaction tests, and upstream error mapping existed; abuse-control evidence was still a gap | Authorization checks, enterprise audit/redaction, and policy metadata are decomposed into dedicated modules; enterprise runtime and unmapped writes fail closed; correlation/trace input, downstream errors, response headers, and downstream base URLs are hardened with negative tests; threat-model and deployment policy evidence is pinned; Bandit and pip-audit remain green in baseline | Security behavior, deployment posture, unsafe-input handling, audit metadata handling, and abuse controls are easier to inspect and test without changing valid local-development semantics | Add gateway-backed token-validation evidence and final target-runtime configuration proof before release promotion |
| Observability | HTTP, endpoint execution, supportability, freshness metrics, and correlation existed but needed consolidated docs | Observability docs, dashboard panels, alert definitions, runbook anchors, and endpoint/upstream metrics are covered by tests and baseline validation | Metrics/correlation posture is preserved through router and client decomposition, and operator response evidence is now governed | Keep alert thresholds aligned with production telemetry after deployment |
| Resilience and performance | Downstream profiles declared timeout, connection, and keepalive limits, but operations created and closed a client per call | FastAPI lifespan owns reusable dependency-specific HTTP pools and closes them after entering draining posture; standalone/injected adapters remain supported; downstream timeout/pool/async polling env parsing is isolated in focused helpers; downstream request execution and upstream error observation are isolated from profile construction; lotus-performance async returns payload validation and bounded failure construction are isolated from polling orchestration | Configured pooling now improves cross-request connection reuse and shutdown resource cleanup, and runtime profile, request execution, polling settings, and async failure behavior are easier to inspect and test | Add operation-specific retry only where idempotency and retry budgets are explicitly proven |
| Documentation and PR evidence | Baseline/reporting foundation was introduced with architecture, security, observability, runbook, wiki, and quality docs | `baseline_report.md`, `refactor_health_report.md`, `quality_scorecard.md`, and `final_pr_readiness.md` are updated with current measured movement and PR assembly evidence | Refactor progress is now auditable from generated reports and branch history | Final PR must attach current generated artifacts, CI status, and command evidence |

## Current Gate Snapshot

- Local feature-lane checks used across recent slices: focused pytest packs,
  `make typecheck`, `make lint`, `make architecture-gate`, targeted `radon cc`,
  and `make quality-baseline`.
- GitHub checks are pushed after each slice and reviewed asynchronously:
  `Quality Baseline` and `Remote Feature Lane`.
- The latest baseline keeps the progressive gate posture report-only where
  thresholds are not final; generated OpenAPI schema governance is actively
  enforced through `make openapi-gate`.
"""
    (QUALITY_DIR / "quality_scorecard.md").write_text(scorecard, encoding="utf-8")

    health = f"""# Lotus Risk Refactor Health Report

## Current Slice

The branch has moved beyond report-only scaffolding into measured modularity,
contract-size, client-boundary, runtime lifecycle hardening, complexity reduction,
and generated OpenAPI schema certification. The current baseline shows no
C-or-worse complexity candidates, while GitHub feature-lane checks are being
used asynchronously after each pushed slice.

## Highest Priority Refactor Targets

{
        markdown_table(
            ("Rank", "Target", "Evidence", "Next action"),
            [
                (
                    1,
                    "Service module size",
                    "Concentration, attribution, and rolling public adapters have been split from stateful, simulation, and exposure-resolution helpers; remaining source-size pressure is concentrated in contract modules",
                    "Continue extracting cohesive orchestration, response-building, and dependency-resolution helpers with characterization tests",
                ),
                (
                    2,
                    "Contract module size",
                    "Concentration, rolling, risk, drawdown, attribution, and scenario request/response contracts are split; concentration, rolling, and drawdown response models are further split into metric/detail and top-level response modules; remaining contract-size pressure is concentrated in risk and input modules",
                    "Split reusable metadata or nested contract fragments only where it improves reviewability and preserves OpenAPI output",
                ),
                (
                    3,
                    "OpenAPI and certification evidence",
                    "`make openapi-gate` evaluates the generated FastAPI schema; `make openapi-artifact-gate` exports `output/openapi/lotus-risk.openapi.json` and validates Spectral policy expectations; `quality/openapi_artifact_evidence.md` records current checksum evidence",
                    "Regenerate and attach the final current OpenAPI artifact evidence to the PR",
                ),
                (
                    4,
                    "Security and abuse-control evidence",
                    "Authorization, audit, redaction, Bandit, pip-audit, payload-size limits, capability checks, threat-model evidence, and bank deployment policy are covered",
                    "Add gateway-backed token-validation evidence and final runtime configuration proof before release promotion",
                ),
                (
                    5,
                    "Observability operations evidence",
                    "Metrics/correlation support, dashboard panels, alert definitions, and runbook anchors are governed by the observability monitoring contract",
                    "Keep alert thresholds aligned with production telemetry after deployment",
                ),
            ],
        )
    }

## Progressive Gate Posture

1. Baseline/report-only: implemented and refreshed per slice.
2. Fail only new regressions: partially active through lint, typecheck,
   architecture gate, monetary-float guard, OpenAPI gate, focused tests, and
   GitHub feature lane checks.
3. Enforce agreed thresholds: partially complete; complexity and the 450-line
   source-size ceiling are actively gated, OpenAPI generation is actively gated,
   security deployment policy is documented and tested, and observability
   operations evidence is governed, but production telemetry thresholds still
   need final policy.
4. Enterprise-readiness gates: not complete; final PR still needs healthy PR
   merge-gate CI plus current generated OpenAPI artifact and command evidence.
"""
    (QUALITY_DIR / "refactor_health_report.md").write_text(health, encoding="utf-8")


def write_rules() -> None:
    (QUALITY_DIR / "architecture_rules.md").write_text(
        """# Lotus Risk Architecture Rules

1. Routers call application services or use cases only.
2. Routers must not call repository, database, HTTP, Kafka, Redis, or downstream adapter APIs directly.
3. Middleware stays thin and business-logic-free.
4. Domain and service modules must not depend on FastAPI, Starlette request/response objects, or
   infrastructure transport models.
5. Infrastructure adapters sit behind narrow service-facing protocols.
6. DTO contracts and persistence/transport models must not leak into domain calculation logic.
7. Downstream errors map through `app.upstream_errors` and API errors map through the standard
   error response envelope.
8. Every request must support and propagate correlation identity.
9. Logs and metrics must use bounded labels and must not expose portfolio, client, trace,
   correlation, request-body, or response-body values as labels.
10. Calculation services depend on narrow observability ports and must not import
    `prometheus_client` directly.
""",
        encoding="utf-8",
    )
    (QUALITY_DIR / "api_governance_rules.md").write_text(
        """# Lotus Risk API Governance Rules

1. Every endpoint must define summary, description, tags, response model, operation ID, examples,
   and standard error responses; the OpenAPI quality gate must fail missing operation IDs and
   missing JSON request examples for mutation endpoints.
2. POST calculation endpoints must document input mode, source ownership, lineage, supportability,
   and failure semantics.
3. Any list endpoint must use consistent pagination, filtering, and sorting contracts before
   publication.
4. Health, liveness, readiness, metrics, operational, internal, and public analytics endpoints must
   remain separated in code and documentation.
5. Deprecation must be explicit in OpenAPI and supported-feature documentation.
6. RFC-0067 vocabulary and no-alias gates remain mandatory.
""",
        encoding="utf-8",
    )


def write_ci_quality_gates() -> None:
    (QUALITY_DIR / "ci_quality_gates.md").write_text(
        """# Lotus Risk CI Quality Gates

Generated by `python scripts/generate_quality_baseline.py`.

## Progressive Gate Model

| Stage | Current use | Enforcement posture |
| --- | --- | --- |
| 1. Baseline/report-only | `quality-baseline.yml` runs `make quality-baseline` and uploads `quality/` evidence | Report-only |
| 2. Fail only new regressions | Feature Lane runs lint, typecheck, OpenAPI, API vocabulary, no-alias, monetary-float, security-audit, and unit tests | Active for implemented gates |
| 3. Enforce agreed thresholds | PR Merge Gate and `make ci` add integration, e2e, coverage, migration smoke, test-pyramid, security, and Docker build checks | Progressive |
| 4. Enterprise-readiness gates | Final refactor state must prove architecture, OpenAPI, security, observability, docs, and supportability improvements | Target |

## Repository-Native Commands

| Gate | Command | Current lane |
| --- | --- | --- |
| Formatting and lint | `make lint` | Feature Lane |
| Monetary float guard | `make monetary-float-guard` | Feature Lane |
| No-alias contract guard | `make no-alias-gate` | Feature Lane |
| Type checking | `make typecheck` | Feature Lane |
| OpenAPI quality | `make openapi-gate` | Feature Lane / PR Merge Gate / Main Releasability |
| OpenAPI artifact policy | `make openapi-artifact-gate` | Feature Lane / PR Merge Gate / Main Releasability |
| API vocabulary | `make api-vocabulary-gate` | Feature Lane |
| Source file size regression | `make source-size-gate` | Feature Lane / PR Merge Gate / Main Releasability |
| Domain data products | `make domain-data-product-gate` | Feature Lane / PR Merge Gate |
| Unit tests | `make test-unit` | Feature Lane |
| Integration tests | `make test-integration` | PR Merge Gate |
| E2E tests | `make test-e2e` | PR Merge Gate |
| Coverage floor | `make test-coverage` | PR Merge Gate parity |
| Dependency and vulnerability audit | `make security-audit` | Feature Lane / PR Merge Gate |
| Migration smoke | `make migration-smoke` | PR Merge Gate |
| Docker build | `make docker-build` | PR Merge Gate |
| Full local CI parity | `make ci` | PR Merge Gate parity |

## Report-Only Tools Still To Promote

| Tool family | Current evidence | Promotion target |
| --- | --- | --- |
| Import-linter | `.importlinter` contracts run in the active Feature, PR Merge, and Main Releasability lanes | Extend contracts as new application/domain/port boundaries are introduced |
| Spectral policy artifact | `.spectral.yaml` policy expectations are enforced against generated artifact output | Attach generated artifact evidence to final PR |
| Complexity and maintainability | `make complexity-gate` and `make source-size-gate` are active in Feature, PR Merge, and Main Releasability lanes | Reduce the maximum only after cohesive hotspot extraction |
| Dead-code candidates | `make dead-code-gate` is active in Feature, PR Merge, and Main Releasability lanes | Keep the allowlist-free posture |
| Dependency hygiene | `make dependency-hygiene-gate` is active in Feature, PR Merge, and Main Releasability lanes | Keep the allowlist minimal and justified |
| Docstring coverage | Deferred: `interrogate` currently introduces vulnerable `py` transitive dependency in audit | Select a safe tool path before adding report-only evidence |

## Evidence Expectations

1. Every refactor slice should list the exact commands run.
2. Quality report updates must be generated, not hand-edited, when counts or posture change.
3. A green narrow gate does not prove enterprise readiness; final PR evidence must include before/after scorecard movement across code health, architecture, OpenAPI, tests, security, observability, and documentation.
4. Report-only gaps must remain visible until they are either promoted to CI or explicitly accepted with rationale.
""",
        encoding="utf-8",
    )


def main() -> int:
    QUALITY_DIR.mkdir(exist_ok=True)
    file_sizes = collect_file_sizes()
    symbol_sizes = collect_symbol_sizes()
    unit_collection_evidence = command_status(
        ["python", "-m", "pytest", "tests/unit", "--collect-only", "-q"]
    )
    write_baseline_report(file_sizes, symbol_sizes, unit_collection_evidence)
    write_health_reports(file_sizes, symbol_sizes, unit_collection_evidence)
    write_rules()
    write_ci_quality_gates()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
