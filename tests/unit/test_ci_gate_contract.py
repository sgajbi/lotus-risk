from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
DOCKERFILE = REPO_ROOT / "Dockerfile"
CI_LOCAL_DOCKERFILE = REPO_ROOT / "Dockerfile.ci-local"
CI_LOCAL_COMPOSE = REPO_ROOT / "docker-compose.ci-local.yml"

PR_GRADE_TARGETS = {
    "lint",
    "check-deps",
    "architecture-gate",
    "no-alias-gate",
    "typecheck",
    "openapi-gate",
    "openapi-artifact-gate",
    "api-vocabulary-gate",
    "mesh-contract-validate",
    "image-supply-chain-gate",
    "complexity-gate",
    "source-size-gate",
    "dependency-hygiene-gate",
    "dead-code-gate",
    "migration-smoke",
    "test-pyramid-gate",
    "test-all",
    "security-audit",
    "docker-build",
}


def _make_target_dependencies(target: str) -> set[str]:
    text = MAKEFILE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(f"{target}:"):
            return set(line.split(":", maxsplit=1)[1].split())
    raise AssertionError(f"missing Makefile target: {target}")


def test_make_ci_is_pr_grade_local_gate() -> None:
    assert PR_GRADE_TARGETS <= _make_target_dependencies("ci")


def test_migration_targets_enforce_active_no_schema_contract() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert (
        "migration-smoke:\n\tpython scripts/migration_contract_check.py --mode no-schema"
        in makefile
    )
    assert (
        "migration-apply:\n\tpython scripts/migration_contract_check.py --mode no-schema"
        in makefile
    )
    assert "MIGRATION_SMOKE_TESTS" not in makefile
    assert "Skipping migration smoke tests" not in makefile
    assert "postgres_migrate.py" not in makefile
    assert "--target dpm" not in makefile


def test_ci_local_is_documented_as_partial_split_suite_loop() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "Split-suite local coverage loop without Docker" in makefile
    assert "Use `make ci` for PR-grade parity" in makefile


def test_ci_local_docker_target_points_to_existing_compose_lane() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    compose = CI_LOCAL_COMPOSE.read_text(encoding="utf-8")
    dockerfile = CI_LOCAL_DOCKERFILE.read_text(encoding="utf-8")

    assert "docker-compose.ci-local.yml" in makefile
    assert "--force-recreate --remove-orphans" in makefile
    assert "ci-local:" in compose
    assert "dockerfile: Dockerfile.ci-local" in compose
    assert "command: make ci-local" in compose
    assert 'pip install -e ".[dev]"' in dockerfile
    assert 'CMD ["make", "ci-local"]' in dockerfile


def test_make_clean_delegates_to_cleanup_script() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "clean:" in makefile
    assert "python scripts/clean_generated_artifacts.py" in makefile


def test_docker_build_passes_required_provenance_args() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")

    for build_arg in (
        "LOTUS_GIT_COMMIT_SHA",
        "LOTUS_GIT_BRANCH",
        "LOTUS_SERVICE_VERSION",
        "LOTUS_BUILD_TIMESTAMP",
        "LOTUS_REPO_URL",
        "LOTUS_IMAGE_DIGEST",
        "LOTUS_CI_PIPELINE_RUN_ID",
    ):
        assert f"--build-arg {build_arg}=" in makefile


def test_dockerfile_labels_and_exports_required_image_metadata() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    for label in (
        "org.opencontainers.image.revision",
        "org.opencontainers.image.ref.name",
        "org.opencontainers.image.version",
        "org.opencontainers.image.created",
        "org.opencontainers.image.source",
        "org.opencontainers.image.digest",
        "com.lotus.git.branch",
        "com.lotus.ci.pipeline-run-id",
    ):
        assert label in dockerfile

    for env_name in (
        "LOTUS_GIT_COMMIT_SHA",
        "LOTUS_GIT_BRANCH",
        "LOTUS_SERVICE_VERSION",
        "LOTUS_BUILD_TIMESTAMP",
        "LOTUS_REPO_URL",
        "LOTUS_IMAGE_DIGEST",
        "LOTUS_CI_PIPELINE_RUN_ID",
    ):
        assert f"ENV {env_name}=" in dockerfile or f"    {env_name}=" in dockerfile


def test_governed_workflows_run_mesh_contract_validation() -> None:
    for workflow in (
        "feature-lane.yml",
        "pr-merge-gate.yml",
        "main-releasability.yml",
    ):
        text = (WORKFLOW_DIR / workflow).read_text(encoding="utf-8")
        assert "repository: sgajbi/lotus-platform" in text, workflow
        assert "path: .lotus-platform" in text, workflow
        assert "run: make mesh-contract-validate" in text, workflow
        assert text.index("Dependency Hygiene Gate") < text.index(
            "Checkout Lotus Platform Contracts"
        ), workflow
        assert text.index("Dead Code Gate") < text.index("Checkout Lotus Platform Contracts"), (
            workflow
        )
        assert text.index("Checkout Lotus Platform Contracts") < text.index(
            "Mesh Contract Validation"
        ), workflow


def test_governed_workflows_run_image_supply_chain_gate() -> None:
    for workflow in (
        "feature-lane.yml",
        "pr-merge-gate.yml",
        "main-releasability.yml",
    ):
        text = (WORKFLOW_DIR / workflow).read_text(encoding="utf-8")
        assert "run: make image-supply-chain-gate" in text, workflow
