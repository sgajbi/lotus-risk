from __future__ import annotations

import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
MAKEFILE = ROOT / "Makefile"
WORKFLOW_DIR = ROOT / ".github" / "workflows"
IMAGE_RELEASE_WORKFLOW = WORKFLOW_DIR / "image-release.yml"
UNFIXED_EXCEPTION_EXPIRY_PATTERN = re.compile(
    r'^\s*UNFIXED_VULNERABILITY_EXCEPTION_EXPIRES_ON:\s*"(?P<expiry>[^\"]+)"\s*$',
    flags=re.MULTILINE,
)
TRIVY_ENV_OVERRIDE_PATTERN = re.compile(
    r"(?<![A-Z0-9_])(?P<quote>[\"']?)(?P<name>TRIVY_[A-Z0-9_]+)(?P=quote)(?:\s*:|=)"
)

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
    "Generate complete vulnerability inventory",
    "Upload vulnerability scan results",
    "Block application-library vulnerabilities",
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

FORBIDDEN_TRIVY_OVERRIDE_FIELDS = (
    "docker-host",
    "download-db-only",
    "download-java-db-only",
    "ignorefile",
    "ignore-policy",
    "ignore-status",
    "input",
    "offline-scan",
    "scan-ref",
    "skip-dirs",
    "skip-db-update",
    "skip-files",
    "skip-java-db-update",
    "skip-setup-trivy",
    "trivy-config",
    "trivyignores",
)
FORBIDDEN_DEFAULT_TRIVY_FILES = (
    ".trivyignore",
    ".trivyignore.yaml",
    ".trivyignore.yml",
    "trivy.yaml",
    "trivy.yml",
)
TRIVY_INVENTORY_ALLOWED_FIELDS = {
    "name",
    "uses",
    "with",
    "scan-type",
    "scanners",
    "version",
    "image-ref",
    "format",
    "output",
    "vuln-type",
    "severity",
    "exit-code",
}
TRIVY_LIBRARY_GATE_ALLOWED_FIELDS = TRIVY_INVENTORY_ALLOWED_FIELDS - {"output"}
TRIVY_OS_GATE_ALLOWED_FIELDS = TRIVY_LIBRARY_GATE_ALLOWED_FIELDS | {"ignore-unfixed"}


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
        "COPY contracts/domain-data-products ./contracts/domain-data-products": (
            "runtime data-product declarations"
        ),
        'LOTUS_REPO_ROOT="/app"': "runtime repository-root declaration",
        "apt-get upgrade --yes": "runtime operating-system security update",
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
            f"{workflow_path}: release order must be build, SBOM, vulnerability inventory and "
            "upload, blocking scans, registry authentication, push, signing, then provenance "
            "attestation"
        )
    return issues


def _workflow_step_block(text: str, step_name: str) -> str:
    marker = f"- name: {step_name}"
    start = text.find(marker)
    if start < 0:
        return ""
    next_step = text.find("\n      - name:", start + len(marker))
    return text[start:] if next_step < 0 else text[start:next_step]


def _workflow_field_value(block: str, field: str) -> str | None:
    match = re.search(
        rf"^\s*{re.escape(field)}:\s*(?P<value>.*?)\s*$",
        block,
        flags=re.MULTILINE,
    )
    if match is None:
        return None
    return match.group("value").strip().strip("\"'")


def _trivy_override_fields(block: str) -> list[str]:
    return [
        field
        for field in FORBIDDEN_TRIVY_OVERRIDE_FIELDS
        if _workflow_field_value(block, field) is not None
    ]


def _unexpected_workflow_fields(block: str, allowed_fields: set[str]) -> list[str]:
    field_pattern = re.compile(
        r"^\s*(?:-\s+)?(?P<quote>[\"']?)(?P<field>[A-Za-z0-9_-]+)(?P=quote)\s*:",
        flags=re.MULTILINE,
    )
    declared_fields = {match.group("field") for match in field_pattern.finditer(block)}
    return sorted(declared_fields - allowed_fields)


def validate_ci_image_release_workflow(
    workflow_path: Path = IMAGE_RELEASE_WORKFLOW,
    *,
    today: date | None = None,
) -> list[str]:
    if not workflow_path.exists():
        return [f"{workflow_path}: image release workflow is missing"]

    text = _read(workflow_path)
    issues: list[str] = []
    repository_root = (
        ROOT
        if workflow_path.resolve() == IMAGE_RELEASE_WORKFLOW.resolve()
        else workflow_path.parent
    )
    for relative_path in FORBIDDEN_DEFAULT_TRIVY_FILES:
        if (repository_root / relative_path).exists():
            issues.append(
                f"{workflow_path}: repository-default Trivy policy/config file is forbidden: "
                f"{relative_path}"
            )
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

    trivy_env_overrides = sorted(
        {match.group("name") for match in TRIVY_ENV_OVERRIDE_PATTERN.finditer(text)}
    )
    if trivy_env_overrides:
        issues.append(
            f"{workflow_path}: Trivy environment overrides are forbidden: "
            f"{', '.join(trivy_env_overrides)}"
        )

    issues.extend(validate_release_publication_order(text, workflow_path))

    if re.search(r"^\s*push:\s*true\s*$", text, flags=re.MULTILINE):
        issues.append(f"{workflow_path}: build must not publish before the vulnerability scan")
    if "imagetools inspect" in text:
        issues.append(
            f"{workflow_path}: digest must come from this run's push, not a mutable tag lookup"
        )
    inventory = _workflow_step_block(text, "Generate complete vulnerability inventory")
    if (
        _workflow_field_value(inventory, "uses") != "aquasecurity/trivy-action@v0.36.0"
        or _workflow_field_value(inventory, "scan-type") != "image"
        or _workflow_field_value(inventory, "scanners") != "vuln"
        or _workflow_field_value(inventory, "version") != "v0.70.0"
        or _workflow_field_value(inventory, "image-ref")
        != "${{ env.IMAGE_NAME }}:${{ github.sha }}"
        or _workflow_field_value(inventory, "format") != "sarif"
        or _workflow_field_value(inventory, "output") != "output/image-release/trivy-results.sarif"
        or _workflow_field_value(inventory, "vuln-type") != "os,library"
        or _workflow_field_value(inventory, "severity") != "HIGH,CRITICAL"
        or _workflow_field_value(inventory, "exit-code") != "0"
        or _workflow_field_value(inventory, "ignore-unfixed") is not None
    ):
        issues.append(
            f"{workflow_path}: complete HIGH/CRITICAL vulnerability inventory must remain visible"
        )
    if overrides := _trivy_override_fields(inventory):
        issues.append(
            f"{workflow_path}: complete vulnerability inventory must not use scan overrides: "
            f"{', '.join(overrides)}"
        )
    if unexpected_fields := _unexpected_workflow_fields(inventory, TRIVY_INVENTORY_ALLOWED_FIELDS):
        issues.append(
            f"{workflow_path}: complete vulnerability inventory contains unexpected fields: "
            f"{', '.join(unexpected_fields)}"
        )

    inventory_upload = _workflow_step_block(text, "Upload vulnerability scan results")
    if (
        _workflow_field_value(inventory_upload, "uses") != "github/codeql-action/upload-sarif@v4"
        or _workflow_field_value(inventory_upload, "sarif_file")
        != "output/image-release/trivy-results.sarif"
        or _workflow_field_value(inventory_upload, "if") != "always()"
        or _workflow_field_value(inventory_upload, "continue-on-error") is not None
    ):
        issues.append(f"{workflow_path}: complete vulnerability inventory SARIF must be uploaded")

    library_gate = _workflow_step_block(text, "Block application-library vulnerabilities")
    if (
        _workflow_field_value(library_gate, "uses") != "aquasecurity/trivy-action@v0.36.0"
        or _workflow_field_value(library_gate, "scan-type") != "image"
        or _workflow_field_value(library_gate, "scanners") != "vuln"
        or _workflow_field_value(library_gate, "version") != "v0.70.0"
        or _workflow_field_value(library_gate, "image-ref")
        != "${{ env.IMAGE_NAME }}:${{ github.sha }}"
        or _workflow_field_value(library_gate, "vuln-type") != "library"
        or _workflow_field_value(library_gate, "severity") != "HIGH,CRITICAL"
        or _workflow_field_value(library_gate, "exit-code") != "1"
    ):
        issues.append(
            f"{workflow_path}: application-library HIGH/CRITICAL findings must be blocking"
        )
    if overrides := _trivy_override_fields(library_gate):
        issues.append(
            f"{workflow_path}: application-library scan must not use scan overrides: "
            f"{', '.join(overrides)}"
        )
    if unexpected_fields := _unexpected_workflow_fields(
        library_gate, TRIVY_LIBRARY_GATE_ALLOWED_FIELDS
    ):
        issues.append(
            f"{workflow_path}: application-library scan contains unexpected fields: "
            f"{', '.join(unexpected_fields)}"
        )
    if _workflow_field_value(library_gate, "ignore-unfixed") is not None:
        issues.append(f"{workflow_path}: unfixed exception must not apply to application libraries")
    if _workflow_field_value(library_gate, "continue-on-error") is not None:
        issues.append(f"{workflow_path}: application-library scan failure must block publication")
    if _workflow_field_value(library_gate, "if") is not None:
        issues.append(f"{workflow_path}: application-library scan must run unconditionally")

    os_gate = _workflow_step_block(text, "Vulnerability scan")
    if _workflow_field_value(os_gate, "uses") != "aquasecurity/trivy-action@v0.36.0":
        issues.append(f"{workflow_path}: OS vulnerability gate must use the governed Trivy action")
    if _workflow_field_value(os_gate, "scan-type") != "image":
        issues.append(f"{workflow_path}: OS vulnerability gate must use image scan mode")
    if _workflow_field_value(os_gate, "scanners") != "vuln":
        issues.append(f"{workflow_path}: OS vulnerability gate must enable vulnerability scanning")
    if _workflow_field_value(os_gate, "version") != "v0.70.0":
        issues.append(f"{workflow_path}: OS vulnerability gate must use the governed Trivy version")
    if _workflow_field_value(os_gate, "image-ref") != "${{ env.IMAGE_NAME }}:${{ github.sha }}":
        issues.append(f"{workflow_path}: OS vulnerability gate must scan the release image")
    if _workflow_field_value(os_gate, "vuln-type") != "os":
        issues.append(f"{workflow_path}: unfixed exception must be scoped to OS findings")
    if _workflow_field_value(os_gate, "ignore-unfixed") != "true":
        issues.append(
            f"{workflow_path}: OS blocking scan must ignore only vulnerabilities without a fix"
        )
    if _workflow_field_value(os_gate, "exit-code") != "1":
        issues.append(f"{workflow_path}: fixable OS HIGH/CRITICAL findings must be blocking")
    if _workflow_field_value(os_gate, "severity") != "HIGH,CRITICAL":
        issues.append(f"{workflow_path}: OS blocking scan must cover HIGH/CRITICAL findings")
    if _workflow_field_value(os_gate, "continue-on-error") is not None:
        issues.append(f"{workflow_path}: OS vulnerability scan failure must block publication")
    if _workflow_field_value(os_gate, "if") is not None:
        issues.append(f"{workflow_path}: OS vulnerability scan must run unconditionally")
    if overrides := _trivy_override_fields(os_gate):
        issues.append(
            f"{workflow_path}: OS vulnerability scan must not use scan overrides: "
            f"{', '.join(overrides)}"
        )
    if unexpected_fields := _unexpected_workflow_fields(os_gate, TRIVY_OS_GATE_ALLOWED_FIELDS):
        issues.append(
            f"{workflow_path}: OS vulnerability scan contains unexpected fields: "
            f"{', '.join(unexpected_fields)}"
        )

    expiry_match = UNFIXED_EXCEPTION_EXPIRY_PATTERN.search(text)
    if expiry_match is None:
        issues.append(f"{workflow_path}: missing unfixed-vulnerability exception expiry")
    else:
        expiry_text = expiry_match.group("expiry")
        try:
            expiry = date.fromisoformat(expiry_text)
        except ValueError:
            issues.append(
                f"{workflow_path}: invalid unfixed-vulnerability exception expiry {expiry_text!r}"
            )
        else:
            effective_today = today or datetime.now(UTC).date()
            if effective_today > expiry:
                issues.append(
                    f"{workflow_path}: unfixed-vulnerability exception expired on {expiry.isoformat()}"
                )

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
