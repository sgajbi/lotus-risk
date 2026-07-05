from __future__ import annotations

from pathlib import Path

from scripts.validate_image_supply_chain import (
    validate_ci_image_release_workflow,
    validate_dockerfile,
    validate_image_supply_chain,
    validate_kubernetes_digest_references,
)


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


def test_image_supply_chain_gate_rejects_missing_release_workflow(tmp_path: Path) -> None:
    issues = validate_ci_image_release_workflow(tmp_path / "missing.yml")

    assert issues == [f"{tmp_path / 'missing.yml'}: image release workflow is missing"]
