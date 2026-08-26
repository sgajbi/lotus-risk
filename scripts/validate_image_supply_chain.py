from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
MAKEFILE = ROOT / "Makefile"
WORKFLOW_DIR = ROOT / ".github" / "workflows"
IMAGE_RELEASE_WORKFLOW = WORKFLOW_DIR / "image-release.yml"

REQUIRED_OCI_LABELS = {
    "org.opencontainers.image.revision",
    "org.opencontainers.image.ref.name",
    "org.opencontainers.image.version",
    "org.opencontainers.image.created",
    "org.opencontainers.image.source",
    "org.opencontainers.image.digest",
    "com.lotus.git.branch",
    "com.lotus.ci.pipeline-run-id",
}

REQUIRED_BUILD_ARGS = {
    "LOTUS_GIT_COMMIT_SHA",
    "LOTUS_GIT_BRANCH",
    "LOTUS_SERVICE_VERSION",
    "LOTUS_BUILD_TIMESTAMP",
    "LOTUS_REPO_URL",
    "LOTUS_IMAGE_DIGEST",
    "LOTUS_CI_PIPELINE_RUN_ID",
}

SENSITIVE_BUILD_NAME_PARTS = (
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "CREDENTIAL",
)

FORBIDDEN_RUNTIME_DEV_DEPENDENCIES = (
    "pytest",
    "ruff",
    "mypy",
    "bandit",
    "deptry",
    "radon",
    "vulture",
    "pre_commit",
)

RELEASE_STEP_ORDER = (
    "Build image for validation",
    "Generate SBOM",
    "Vulnerability scan",
    "Authenticate to release registry",
    "Push immutable image after scan",
    "Sign image by digest",
    "Generate provenance attestation",
)

IGNORED_REPOSITORY_SCAN_DIRS = {
    ".git",
    ".lotus-platform",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "lotus-platform",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _declared_docker_args_and_envs(dockerfile_text: str) -> set[str]:
    names: set[str] = set()
    collecting_env = False
    for line in dockerfile_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ARG "):
            names.add(stripped.split(None, 1)[1].split("=", maxsplit=1)[0].strip())
        if stripped.startswith("ENV "):
            collecting_env = stripped.endswith("\\")
            env_part = stripped.split(None, 1)[1]
        elif collecting_env:
            env_part = stripped
            collecting_env = stripped.endswith("\\")
        else:
            continue

        for assignment in env_part.rstrip("\\").split():
            if "=" in assignment:
                names.add(assignment.split("=", maxsplit=1)[0].strip())
    return names


def validate_dockerfile(dockerfile_path: Path = DOCKERFILE) -> list[str]:
    text = _read(dockerfile_path)
    issues: list[str] = []

    for label in sorted(REQUIRED_OCI_LABELS):
        if label not in text:
            issues.append(f"Dockerfile missing required OCI label {label}")

    for build_arg in sorted(REQUIRED_BUILD_ARGS):
        if f"ARG {build_arg}=" not in text:
            issues.append(f"Dockerfile missing required build arg {build_arg}")
        if build_arg not in _declared_docker_args_and_envs(text):
            issues.append(f"Dockerfile does not export runtime metadata {build_arg}")

    for name in _declared_docker_args_and_envs(text):
        if any(part in name.upper() for part in SENSITIVE_BUILD_NAME_PARTS):
            issues.append(f"Dockerfile ARG/ENV must not expose build secret name {name}")

    if '".[dev]"' in text or "'.[dev]'" in text or ".[dev]" in text:
        issues.append("Dockerfile runtime image must not install the project dev extra")

    if "importlib.util.find_spec" not in text:
        issues.append("Dockerfile missing runtime dev-tool dependency guard")
    for package in FORBIDDEN_RUNTIME_DEV_DEPENDENCIES:
        if package not in text:
            issues.append(f"Dockerfile runtime dev-tool guard missing {package}")

    return issues


def validate_runtime_container_contract(
    dockerfile_path: Path = DOCKERFILE,
    makefile_path: Path = MAKEFILE,
) -> list[str]:
    """Validate the production runtime target and its repository-native build path."""

    dockerfile_text = _read(dockerfile_path)
    makefile_text = _read(makefile_path)
    issues: list[str] = []
    required_dockerfile_terms = {
        "AS builder": "builder stage",
        "AS runtime": "runtime stage",
        "COPY --from=builder /install /usr/local": "builder-to-runtime dependency copy",
        "groupadd --system --gid 10001 lotus": "non-root runtime group",
        "useradd --system --uid 10001": "non-root runtime user",
        "USER lotus": "non-root runtime user selection",
        "HEALTHCHECK": "container healthcheck",
        "http://127.0.0.1:8130/health/ready": "readiness healthcheck endpoint",
        '"app.main:app"': "installed-package application entrypoint",
    }
    for term, description in required_dockerfile_terms.items():
        if term not in dockerfile_text:
            issues.append(f"{dockerfile_path}: missing {description}")

    if len(re.findall(r"^FROM\s+", dockerfile_text, flags=re.MULTILINE)) < 2:
        issues.append(f"{dockerfile_path}: runtime image must use a multi-stage build")
    if re.search(r"\bpip\s+install\b[^\n]*\s-e(?:\s|$)", dockerfile_text):
        issues.append(f"{dockerfile_path}: runtime package install must not be editable")
    if re.search(r"^COPY\s+(?:--\S+\s+)*scripts(?:\s|/)", dockerfile_text, flags=re.MULTILINE):
        issues.append(f"{dockerfile_path}: runtime image must not copy repository scripts")

    required_makefile_terms = {
        "CONTAINER_BUILD_TARGET ?= runtime": "default runtime build target",
        '--target "$(CONTAINER_BUILD_TARGET)"': "explicit container build target",
    }
    for term, description in required_makefile_terms.items():
        if term not in makefile_text:
            issues.append(f"{makefile_path}: missing {description}")
    return issues


def _workflow_texts() -> dict[Path, str]:
    return {path: _read(path) for path in WORKFLOW_DIR.glob("*.yml")}


def validate_release_publication_order(text: str, workflow_path: Path) -> list[str]:
    """Require the blocking scan to finish before registry authentication and publication."""

    issues: list[str] = []
    positions: list[int] = []
    for step_name in RELEASE_STEP_ORDER:
        marker = f"- name: {step_name}"
        position = text.find(marker)
        if position < 0:
            issues.append(f"{workflow_path}: missing ordered release step {step_name}")
        positions.append(position)

    if all(position >= 0 for position in positions) and positions != sorted(positions):
        issues.append(
            f"{workflow_path}: release order must be build, SBOM, vulnerability scan, registry "
            "authentication, push, signing, then provenance attestation"
        )
    return issues


def validate_ci_image_release_workflow(
    workflow_path: Path = IMAGE_RELEASE_WORKFLOW,
) -> list[str]:
    if not workflow_path.exists():
        return [f"{workflow_path}: image release workflow is missing"]

    text = _read(workflow_path)
    issues: list[str] = []
    required_terms = {
        "packages: write": "push package permission",
        "id-token: write": "keyless signing/provenance permission",
        "attestations: write": "provenance attestation permission",
        "security-events: write": "vulnerability scan upload permission",
        "docker/build-push-action@v6": "Docker build/push action",
        "push: false": "local-only image build before validation",
        "load: true": "locally loaded image for pre-publication scanning",
        "docker push": "post-scan CI-only image push",
        "push_output=": "digest evidence captured directly from the image push",
        "digest: (sha256:": "immutable digest parsed from the image push response",
        "${{ github.sha }}": "Git SHA image tag",
        "anchore/sbom-action": "SBOM generation",
        "aquasecurity/trivy-action": "vulnerability scan",
        "sigstore/cosign-installer": "cosign installer",
        "cosign sign": "image signing",
        "actions/attest-build-provenance": "provenance attestation",
        "steps.publish.outputs.digest": "post-publication digest capture",
        "image-release-manifest.json": "release manifest",
        "service_version": "release manifest service version",
        "LOTUS_IMAGE_DIGEST": "runtime digest metadata",
    }
    for term, description in required_terms.items():
        if term not in text:
            issues.append(f"{workflow_path}: missing {description}")

    issues.extend(validate_release_publication_order(text, workflow_path))

    if re.search(r"^\s*push:\s*true\s*$", text, flags=re.MULTILINE):
        issues.append(f"{workflow_path}: build must not publish before the vulnerability scan")
    if "imagetools inspect" in text:
        issues.append(
            f"{workflow_path}: digest must come from this run's push, not a mutable tag lookup"
        )
    if 'exit-code: "1"' not in text:
        issues.append(f"{workflow_path}: vulnerability scan must retain blocking exit-code 1")

    if 'branches: [ "main" ]' not in text and "branches: [main]" not in text:
        issues.append(f"{workflow_path}: image push must be scoped to main")

    for path, workflow_text in _workflow_texts().items():
        if path == workflow_path:
            continue
        if re.search(r"^\s*push:\s*true\s*$", workflow_text, flags=re.MULTILINE):
            issues.append(f"{path}: image push is only allowed in image-release.yml")
        if "docker push" in workflow_text:
            issues.append(f"{path}: raw docker push is only allowed in image-release.yml")

    return issues


def validate_kubernetes_digest_references(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for path in root.rglob("*"):
        if any(part in IGNORED_REPOSITORY_SCAN_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in {".yaml", ".yml"}:
            continue
        if not any(
            part.lower() in {"k8s", "kubernetes", "helm", "charts", "deploy"} for part in path.parts
        ):
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip().lstrip("-").strip()
            if stripped.startswith("image:") and "@sha256:" not in stripped:
                issues.append(f"{path}:{line_number}: Kubernetes images must deploy by digest")
    return issues


def validate_image_supply_chain() -> list[str]:
    issues: list[str] = []
    issues.extend(validate_dockerfile())
    issues.extend(validate_runtime_container_contract())
    issues.extend(validate_ci_image_release_workflow())
    issues.extend(validate_kubernetes_digest_references())

    makefile_text = _read(MAKEFILE)
    if "image-supply-chain-gate" not in makefile_text:
        issues.append("Makefile missing image-supply-chain-gate target")
    return issues


def main() -> int:
    issues = validate_image_supply_chain()
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print("Image supply-chain gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
