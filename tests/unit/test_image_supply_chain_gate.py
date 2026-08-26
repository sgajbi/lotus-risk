from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.validate_image_supply_chain import (
    FORBIDDEN_RUNTIME_DEV_DEPENDENCIES,
    validate_ci_image_release_workflow,
    validate_dockerfile,
    validate_image_supply_chain,
    validate_kubernetes_digest_references,
    validate_release_publication_order,
    validate_runtime_container_contract,
)

import pytest

pytestmark = pytest.mark.governance


def test_image_supply_chain_gate_passes_current_repo() -> None:
    assert validate_image_supply_chain() == []


def test_image_supply_chain_gate_rejects_secret_build_args(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "\n".join(
            [
                "FROM python:3.12-slim",
                "ARG LOTUS_GIT_COMMIT_SHA=unknown",
                "ARG LOTUS_GIT_BRANCH=unknown",
                "ARG LOTUS_SERVICE_VERSION=0.1.0",
                "ARG LOTUS_BUILD_TIMESTAMP=unknown",
                "ARG LOTUS_REPO_URL=unknown",
                "ARG LOTUS_IMAGE_DIGEST=unknown",
                "ARG LOTUS_CI_PIPELINE_RUN_ID=unknown",
                "ARG DEPLOY_TOKEN=unsafe",
                "LABEL org.opencontainers.image.revision=x",
                "LABEL org.opencontainers.image.ref.name=x",
                "LABEL org.opencontainers.image.version=x",
                "LABEL org.opencontainers.image.created=x",
                "LABEL org.opencontainers.image.source=x",
                "LABEL org.opencontainers.image.digest=x",
                "LABEL com.lotus.git.branch=x",
                "LABEL com.lotus.ci.pipeline-run-id=x",
                "ENV LOTUS_GIT_COMMIT_SHA=x LOTUS_GIT_BRANCH=x LOTUS_SERVICE_VERSION=x",
                "ENV LOTUS_BUILD_TIMESTAMP=x LOTUS_REPO_URL=x LOTUS_IMAGE_DIGEST=x",
                "ENV LOTUS_CI_PIPELINE_RUN_ID=x",
            ]
        ),
        encoding="utf-8",
    )

    issues = validate_dockerfile(dockerfile)

    assert any("DEPLOY_TOKEN" in issue for issue in issues)


def test_dockerfile_uses_hardened_runtime_target_without_dev_extra() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert validate_runtime_container_contract() == []
    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "pip install --prefix=/install ." in dockerfile
    assert "apt-get upgrade --yes" in dockerfile
    assert " -e " not in dockerfile
    assert "COPY scripts" not in dockerfile
    assert "COPY contracts/domain-data-products ./contracts/domain-data-products" in dockerfile
    assert 'LOTUS_REPO_ROOT="/app"' in dockerfile
    assert "USER lotus" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert ".[dev]" not in dockerfile
    assert "importlib.util.find_spec" in dockerfile
    for package in FORBIDDEN_RUNTIME_DEV_DEPENDENCIES:
        assert package in dockerfile


def test_runtime_container_contract_rejects_single_stage_root_runtime(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "\n".join(
            [
                "FROM python:3.12-slim",
                "WORKDIR /app",
                "COPY scripts ./scripts",
                'RUN pip install -e "."',
                'CMD ["uvicorn", "src.app.main:app"]',
            ]
        ),
        encoding="utf-8",
    )
    makefile = tmp_path / "Makefile"
    makefile.write_text("docker-build:\n\tdocker build .\n", encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, makefile)

    assert f"{dockerfile}: runtime image must use a multi-stage build" in issues
    assert f"{dockerfile}: runtime package install must not be editable" in issues
    assert f"{dockerfile}: runtime image must not copy repository scripts" in issues
    assert f"{dockerfile}: missing runtime data-product declarations" in issues
    assert f"{dockerfile}: missing runtime repository-root declaration" in issues
    assert f"{dockerfile}: missing non-root runtime user selection" in issues
    assert f"{dockerfile}: missing container healthcheck" in issues
    assert f"{makefile}: missing default runtime build target" in issues
    assert f"{makefile}: missing explicit container build target" in issues


def test_image_supply_chain_gate_rejects_runtime_dev_extra_install(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "\n".join(
            [
                "FROM python:3.12-slim",
                "ARG LOTUS_GIT_COMMIT_SHA=unknown",
                "ARG LOTUS_GIT_BRANCH=unknown",
                "ARG LOTUS_SERVICE_VERSION=0.1.0",
                "ARG LOTUS_BUILD_TIMESTAMP=unknown",
                "ARG LOTUS_REPO_URL=unknown",
                "ARG LOTUS_IMAGE_DIGEST=unknown",
                "ARG LOTUS_CI_PIPELINE_RUN_ID=unknown",
                "LABEL org.opencontainers.image.revision=x",
                "LABEL org.opencontainers.image.ref.name=x",
                "LABEL org.opencontainers.image.version=x",
                "LABEL org.opencontainers.image.created=x",
                "LABEL org.opencontainers.image.source=x",
                "LABEL org.opencontainers.image.digest=x",
                "LABEL com.lotus.git.branch=x",
                "LABEL com.lotus.ci.pipeline-run-id=x",
                "ENV LOTUS_GIT_COMMIT_SHA=x LOTUS_GIT_BRANCH=x LOTUS_SERVICE_VERSION=x",
                "ENV LOTUS_BUILD_TIMESTAMP=x LOTUS_REPO_URL=x LOTUS_IMAGE_DIGEST=x",
                "ENV LOTUS_CI_PIPELINE_RUN_ID=x",
                'RUN pip install --no-cache-dir -e ".[dev]"',
            ]
        ),
        encoding="utf-8",
    )

    issues = validate_dockerfile(dockerfile)

    assert "Dockerfile runtime image must not install the project dev extra" in issues


def test_image_supply_chain_gate_rejects_missing_runtime_dev_tool_guard(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "\n".join(
            [
                "FROM python:3.12-slim",
                "ARG LOTUS_GIT_COMMIT_SHA=unknown",
                "ARG LOTUS_GIT_BRANCH=unknown",
                "ARG LOTUS_SERVICE_VERSION=0.1.0",
                "ARG LOTUS_BUILD_TIMESTAMP=unknown",
                "ARG LOTUS_REPO_URL=unknown",
                "ARG LOTUS_IMAGE_DIGEST=unknown",
                "ARG LOTUS_CI_PIPELINE_RUN_ID=unknown",
                "LABEL org.opencontainers.image.revision=x",
                "LABEL org.opencontainers.image.ref.name=x",
                "LABEL org.opencontainers.image.version=x",
                "LABEL org.opencontainers.image.created=x",
                "LABEL org.opencontainers.image.source=x",
                "LABEL org.opencontainers.image.digest=x",
                "LABEL com.lotus.git.branch=x",
                "LABEL com.lotus.ci.pipeline-run-id=x",
                "ENV LOTUS_GIT_COMMIT_SHA=x LOTUS_GIT_BRANCH=x LOTUS_SERVICE_VERSION=x",
                "ENV LOTUS_BUILD_TIMESTAMP=x LOTUS_REPO_URL=x LOTUS_IMAGE_DIGEST=x",
                "ENV LOTUS_CI_PIPELINE_RUN_ID=x",
                'RUN pip install --no-cache-dir -e "."',
            ]
        ),
        encoding="utf-8",
    )

    issues = validate_dockerfile(dockerfile)

    assert "Dockerfile missing runtime dev-tool dependency guard" in issues


def test_image_supply_chain_gate_rejects_tag_based_kubernetes_images(
    tmp_path: Path,
) -> None:
    manifest_dir = tmp_path / "k8s"
    manifest_dir.mkdir()
    (manifest_dir / "deployment.yaml").write_text(
        "containers:\n  - image: ghcr.io/sgajbi/lotus-risk:latest\n",
        encoding="utf-8",
    )

    issues = validate_kubernetes_digest_references(tmp_path)

    assert issues == [
        f"{manifest_dir / 'deployment.yaml'}:2: Kubernetes images must deploy by digest"
    ]


def test_image_supply_chain_gate_skips_nested_platform_checkouts(tmp_path: Path) -> None:
    manifest_dir = tmp_path / ".lotus-platform" / "charts"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "deployment.yaml").write_text(
        "containers:\n  - image: ghcr.io/sgajbi/lotus-platform:latest\n",
        encoding="utf-8",
    )

    assert validate_kubernetes_digest_references(tmp_path) == []


def test_image_supply_chain_gate_rejects_missing_release_workflow(tmp_path: Path) -> None:
    issues = validate_ci_image_release_workflow(tmp_path / "missing.yml")

    assert issues == [f"{tmp_path / 'missing.yml'}: image release workflow is missing"]


def test_image_release_scans_before_registry_authentication_and_publication() -> None:
    workflow_path = Path(".github/workflows/image-release.yml")
    workflow = workflow_path.read_text(encoding="utf-8")

    assert validate_release_publication_order(workflow, workflow_path) == []
    assert "push: false" in workflow
    assert "load: true" in workflow
    assert "Generate complete vulnerability inventory" in workflow
    assert 'exit-code: "0"' in workflow
    assert "ignore-unfixed: true" in workflow
    assert 'exit-code: "1"' in workflow
    assert workflow.index("- name: Block application-library vulnerabilities") < workflow.index(
        "- name: Vulnerability scan"
    )
    assert workflow.index("- name: Vulnerability scan") < workflow.index(
        "- name: Push immutable image after scan"
    )


def test_image_release_order_guard_rejects_publication_before_scan(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    workflow = "\n".join(
        f"- name: {step}"
        for step in (
            "Build image for validation",
            "Generate SBOM",
            "Block application-library vulnerabilities",
            "Authenticate to release registry",
            "Push immutable image after scan",
            "Vulnerability scan",
            "Sign image by digest",
            "Generate provenance attestation",
        )
    )

    issues = validate_release_publication_order(workflow, workflow_path)

    assert issues == [
        f"{workflow_path}: release order must be build, SBOM, vulnerability scan, registry "
        "authentication, push, signing, then provenance attestation"
    ]


def test_image_release_contract_rejects_build_time_publication(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(current.replace("push: false", "push: true"), encoding="utf-8")

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: build must not publish before the vulnerability scan" in issues


def test_image_release_contract_rejects_unactionable_blocking_scan(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace("          ignore-unfixed: true\n", ""),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert (
        f"{workflow_path}: blocking scan must ignore only vulnerabilities without a fix" in issues
    )


def test_image_release_contract_rejects_library_unfixed_exception(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "          vuln-type: library\n",
            "          vuln-type: library\n          ignore-unfixed: true\n",
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: unfixed exception must not apply to application libraries" in issues


def test_image_release_contract_rejects_unscoped_os_exception(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace("          vuln-type: os\n", ""),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: unfixed exception must be scoped to OS findings" in issues


def test_image_release_contract_rejects_expired_unfixed_exception(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    workflow_path.write_text(
        Path(".github/workflows/image-release.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path, today=date(2026, 10, 1))

    assert f"{workflow_path}: unfixed-vulnerability exception expired on 2026-09-30" in issues


def test_image_release_contract_rejects_malformed_unfixed_exception(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace('EXPIRES_ON: "2026-09-30"', 'EXPIRES_ON: "renew-later"'),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path, today=date(2026, 8, 27))

    assert (
        f"{workflow_path}: invalid unfixed-vulnerability exception expiry 'renew-later'" in issues
    )


def test_image_release_contract_rejects_digest_lookup_by_mutable_tag(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            'push_output="$(docker push "$image_ref" 2>&1)"',
            'push_output="$(docker push "$image_ref" 2>&1)"\n'
            '          docker buildx imagetools inspect "$image_ref"',
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert (
        f"{workflow_path}: digest must come from this run's push, not a mutable tag lookup"
        in issues
    )
