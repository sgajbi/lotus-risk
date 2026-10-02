from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
MAKEFILE = ROOT / "Makefile"
WORKFLOW_DIR = ROOT / ".github" / "workflows"
IMAGE_RELEASE_WORKFLOW = WORKFLOW_DIR / "image-release.yml"
TRIVY_ENV_OVERRIDE_PATTERN = re.compile(
    r"(?<![A-Z0-9_])(?P<quote>[\"']?)(?P<name>TRIVY_[A-Z0-9_]+)(?P=quote)(?:\s*:|=)"
)
BUILDKIT_SYNTAX_OVERRIDE_PATTERN = re.compile(
    r"(?<![A-Z0-9_])(?P<quote>[\"']?)BUILDKIT_SYNTAX(?P=quote)(?:\s*:|=)",
    flags=re.IGNORECASE,
)
DOCKER_ENDPOINT_OVERRIDE_PATTERN = re.compile(
    r"(?<![A-Z0-9_])(?P<quote>[\"']?)(?P<name>DOCKER_HOST|DOCKER_CONTEXT|BUILDX_BUILDER)"
    r"(?P=quote)(?:\s*:|=)",
    flags=re.IGNORECASE,
)
DOCKER_IMAGE_MUTATION_PATTERN = re.compile(
    r"(?<![A-Z0-9_-])docker\s+(?:(?:image|container)\s+)?"
    r"(?:build|buildx(?:\s+build)?|tag|load|pull|import|commit)\b",
    flags=re.IGNORECASE,
)
APPROVED_RELEASE_BUILD_ARGS = (
    "LOTUS_GIT_COMMIT_SHA=${{ github.sha }}",
    "LOTUS_GIT_BRANCH=${{ github.ref_name }}",
    "LOTUS_SERVICE_VERSION=0.1.0",
    "LOTUS_BUILD_TIMESTAMP=${{ env.LOTUS_BUILD_TIMESTAMP }}",
    "LOTUS_REPO_URL=${{ github.server_url }}/${{ github.repository }}",
    "LOTUS_IMAGE_DIGEST=resolved-after-push-in-release-manifest",
    "LOTUS_CI_PIPELINE_RUN_ID=${{ github.run_id }}",
)
VALIDATED_LOCAL_IMAGE_ID = "${{ steps.validated_image.outputs.image_id }}"
APPROVED_IMAGE_ID_CAPTURE = (
    "set -euo pipefail",
    'image_ref="${IMAGE_NAME}:${GITHUB_SHA}"',
    'image_id="$(docker image inspect --format=\'{{.Id}}\' "$image_ref")"',
    'if [[ ! "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]]; then',
    'echo "::error::Validated build did not produce a local image ID: $image_id"',
    "exit 1",
    "fi",
    'echo "image_id=$image_id" >> "$GITHUB_OUTPUT"',
)
APPROVED_RELEASE_STEP_ENTRIES = (
    "uses: actions/checkout@v6",
    "uses: actions/setup-python@v6",
    "name: Validate image supply-chain contract",
    "name: Resolve build timestamp",
    "uses: docker/setup-buildx-action@v4",
    "name: Build image for validation",
    "name: Capture validated local image identity",
    "name: Prepare image release evidence directory",
    "name: Generate SBOM",
    "name: Generate complete vulnerability inventory",
    "name: Upload vulnerability scan results",
    "name: Block application-library vulnerabilities",
    "name: Vulnerability scan",
    "name: Authenticate to release registry",
    "name: Push immutable image after scan",
    "uses: sigstore/cosign-installer@v3",
    "name: Sign image by digest",
    "name: Generate provenance attestation",
    "name: Write release manifest",
    "name: Upload image release evidence",
)
APPROVED_SUPPLY_CHAIN_VALIDATION_SCRIPT = (
    "python -m pip install --upgrade pip",
    "python -m pip install PyYAML==6.0.3",
    "python -P scripts/validate_image_supply_chain.py",
)
APPROVED_CHECKOUT_STEP = ("- uses: actions/checkout@v6",)
APPROVED_PYTHON_SETUP_STEP = (
    "- uses: actions/setup-python@v6",
    "with:",
    "python-version: ${{ env.PYTHON_VERSION }}",
    'cache: "pip"',
)
APPROVED_BUILDX_SETUP_STEP = ("- uses: docker/setup-buildx-action@v4",)
APPROVED_COSIGN_SETUP_STEP = ("- uses: sigstore/cosign-installer@v3",)
APPROVED_SIGNING_STEP = (
    "- name: Sign image by digest",
    'run: cosign sign --yes "${IMAGE_NAME}@${{ steps.publish.outputs.digest }}"',
)
APPROVED_WORKFLOW_ENVIRONMENT = (
    "env:",
    "IMAGE_NAME: ghcr.io/${{ github.repository }}",
    'PYTHON_VERSION: "3.12"',
)
APPROVED_WORKFLOW_PERMISSIONS = (
    "permissions:",
    "contents: read",
    "packages: write",
    "id-token: write",
    "attestations: write",
    "security-events: write",
)
APPROVED_RELEASE_JOB_HEADER = (
    "jobs:",
    "release-image:",
    "name: Image Release / Build Scan Sign Attest",
    "runs-on: ubuntu-latest",
    "steps:",
)
APPROVED_DECODED_WORKFLOW_FIELDS = ("name", "on", "concurrency", "permissions", "env", "jobs")
APPROVED_DECODED_RELEASE_JOB_FIELDS = ("name", "runs-on", "steps")
APPROVED_WORKFLOW_HEADER = (
    "name: Image Release",
    "on:",
    "push:",
    'branches: [ "main" ]',
    "workflow_dispatch:",
    "concurrency:",
    "group: ${{ github.workflow }}-${{ github.ref }}",
    "cancel-in-progress: false",
    *APPROVED_WORKFLOW_PERMISSIONS,
    *APPROVED_WORKFLOW_ENVIRONMENT,
    "jobs:",
)
APPROVED_PUBLISH_SCRIPT = (
    "set -euo pipefail",
    'image_ref="${IMAGE_NAME}:${GITHUB_SHA}"',
    'validated_image_id="${{ steps.validated_image.outputs.image_id }}"',
    (
        'if [ "$(docker image inspect --format=\'{{.Id}}\' "$image_ref")" '
        '!= "$validated_image_id" ]; then'
    ),
    'echo "::error::The release tag no longer identifies the scanned image."',
    "exit 1",
    "fi",
    'push_output="$(docker push "$image_ref" 2>&1)"',
    "printf '%s\\n' \"$push_output\"",
    'published_digest="$(printf \'%s\\n\' "$push_output" \\',
    "| sed -nE 's/^.*digest: (sha256:[0-9a-f]{64}) size:.*$/\\1/p' \\",
    '| tail -n 1)"',
    'if [[ ! "$published_digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then',
    'echo "::error::Docker push did not return a valid image digest: $published_digest"',
    "exit 1",
    "fi",
    (
        'if [ "$(docker image inspect --format=\'{{.Id}}\' "$image_ref")" '
        '!= "$validated_image_id" ]; then'
    ),
    'echo "::error::The locally scanned image changed during publication."',
    "exit 1",
    "fi",
    'echo "digest=$published_digest" >> "$GITHUB_OUTPUT"',
)
APPROVED_RELEASE_MANIFEST_SCRIPT = (
    "mkdir -p output/image-release",
    "python - <<'PY'",
    "import json",
    "import os",
    "from pathlib import Path",
    "manifest = {",
    '"service": "lotus-risk",',
    '"service_version": "0.1.0",',
    '"image": os.environ["IMAGE_NAME"],',
    '"tag": os.environ["GITHUB_SHA"],',
    '"digest": "${{ steps.publish.outputs.digest }}",',
    '"image_ref": f"{os.environ[\'IMAGE_NAME\']}@${{ steps.publish.outputs.digest }}",',
    '"git_commit_sha": os.environ["GITHUB_SHA"],',
    '"git_branch": os.environ["GITHUB_REF_NAME"],',
    '"build_timestamp": os.environ["LOTUS_BUILD_TIMESTAMP"],',
    "\"repo_url\": f\"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}\",",
    '"ci_pipeline_run_id": os.environ["GITHUB_RUN_ID"],',
    '"sbom": "lotus-risk-sbom.spdx.json",',
    '"vulnerability_scan": "trivy-results.sarif",',
    '"signed": True,',
    '"provenance_attested": True,',
    '"promotion_policy": "promote_same_digest_across_environments",',
    '"kubernetes_image_policy": "deploy_by_digest_only",',
    "}",
    'Path("output/image-release/image-release-manifest.json").write_text(',
    'json.dumps(manifest, indent=2) + "\\n",',
    'encoding="utf-8",',
    ")",
    "PY",
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

RUNTIME_PIP_REMOVAL = (
    'RUN /usr/local/bin/python3.12 -I -S -c "import pathlib, shutil, sysconfig; '
    "roots={pathlib.Path(sysconfig.get_path(name)).resolve() for name in ('purelib','platlib')}; "
    "targets={path for root in roots for pattern in ('pip','pip-*.dist-info') "
    "for path in root.glob(pattern)}; assert targets; "
    '[shutil.rmtree(path) if path.is_dir() else path.unlink() for path in targets]"'
)
RUNTIME_ENSUREPIP_REMOVAL = (
    'RUN /usr/local/bin/python3.12 -I -S -c "import ensurepip, pathlib, shutil, sysconfig; '
    "path=pathlib.Path(ensurepip.__file__).parent.resolve(); "
    "stdlib=pathlib.Path(sysconfig.get_path('stdlib')).resolve(); "
    "assert path == stdlib / 'ensurepip'; shutil.rmtree(path)\""
)
RUNTIME_DEPENDENCY_GUARD = (
    'RUN /usr/local/bin/python3.12 -I -S -c "import importlib.machinery, pathlib, sys, sysconfig; '
    "forbidden=('pip','ensurepip','pytest','ruff','mypy','bandit','deptry','radon',"
    "'vulture','pre_commit','sitecustomize','usercustomize'); install_roots={pathlib.Path("
    "sysconfig.get_path(name)).resolve() "
    "for name in ('purelib','platlib')}; pth_files=sorted(str(path) for root in install_roots "
    "for path in root.glob('*.pth')); sys.exit('Runtime image contains startup path files: '+"
    "', '.join(pth_files)) if pth_files else None; archive_paths=sorted(str(path) for raw_path in "
    "sys.path if raw_path and (path:=pathlib.Path(raw_path)).is_file()); sys.exit('Runtime image "
    "contains import-path archives: '+', '.join(archive_paths)) if archive_paths else None; roots="
    "{*(str(pathlib.Path(raw_path).resolve()) for raw_path in sys.path if raw_path), "
    "*(str(path) for path in install_roots)}; present=[name for name in "
    "forbidden if importlib.machinery.PathFinder.find_spec(name, list(roots)) is not None]; "
    "sys.exit('Runtime image contains forbidden tooling: '+', '.join(present)) "
    "if present else print('runtime dependency guard passed')\""
)
RUNTIME_TERMINAL_INSTRUCTIONS = (
    "EXPOSE 8130",
    (
        "HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 "
        'CMD python -c "import urllib.request; '
        "urllib.request.urlopen('http://127.0.0.1:8130/health/ready', timeout=3).read()\""
    ),
    'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8130"]',
)
APPROVED_RUNTIME_BASE = (
    "python:3.12-alpine3.23@sha256:33a47b0a92c0766bdd77cd82bbaa4c320ce48db01a2bfe1782920ca7a16e3744"
)
RUNTIME_BASE_INSTRUCTION = f"FROM {APPROVED_RUNTIME_BASE} AS runtime"
BUILDER_BASE_INSTRUCTION = f"FROM {APPROVED_RUNTIME_BASE} AS builder"
BUILDER_OUTPUT_VALIDATOR_BASE_INSTRUCTION = (
    f"FROM {APPROVED_RUNTIME_BASE} AS builder-output-validator"
)
BUILDER_OUTPUT_COLLISION_GUARD = (
    'RUN collision="$(find /install -mindepth 1 ! -path /install/bin '
    "! -path '/install/bin/*' ! -path /install/lib ! -path /install/lib/python3.12 "
    "! -path /install/lib/python3.12/site-packages "
    "! -path '/install/lib/python3.12/site-packages/*' -print -quit)\" && "
    'if [ -n "$collision" ]; then echo "Builder output escapes dependency roots: '
    '$collision" >&2; exit 1; fi && collision="$(find /install/bin -maxdepth 1 '
    "\\( -name 'python*' -o -name 'pip*' \\) -print -quit)\" && "
    'if [ -n "$collision" ]; then echo "Builder output replaces protected runtime executable: '
    '$collision" >&2; exit 1; fi'
)
BUILDER_INSTRUCTION_CONTRACT = (
    "ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1",
    "WORKDIR /build",
    "COPY pyproject.toml README.md ./",
    "COPY src ./src",
    "RUN python -m pip install --upgrade pip && python -m pip install --prefix=/install .",
)
BUILDER_OUTPUT_VALIDATOR_INSTRUCTION_CONTRACT = (
    "COPY --from=builder /install /install",
    BUILDER_OUTPUT_COLLISION_GUARD,
)
RUNTIME_INSTRUCTION_CONTRACT = (
    "ARG LOTUS_GIT_COMMIT_SHA=unknown",
    "ARG LOTUS_GIT_BRANCH=unknown",
    "ARG LOTUS_SERVICE_VERSION=0.1.0",
    "ARG LOTUS_BUILD_TIMESTAMP=unknown",
    "ARG LOTUS_REPO_URL=unknown",
    "ARG LOTUS_IMAGE_DIGEST=unavailable-before-publish",
    "ARG LOTUS_CI_PIPELINE_RUN_ID=unknown",
    (
        'LABEL org.opencontainers.image.revision="${LOTUS_GIT_COMMIT_SHA}" '
        'org.opencontainers.image.ref.name="${LOTUS_GIT_BRANCH}" '
        'org.opencontainers.image.version="${LOTUS_SERVICE_VERSION}" '
        'org.opencontainers.image.created="${LOTUS_BUILD_TIMESTAMP}" '
        'org.opencontainers.image.source="${LOTUS_REPO_URL}" '
        'org.opencontainers.image.digest="${LOTUS_IMAGE_DIGEST}" '
        'com.lotus.git.branch="${LOTUS_GIT_BRANCH}" '
        'com.lotus.ci.pipeline-run-id="${LOTUS_CI_PIPELINE_RUN_ID}"'
    ),
    (
        'ENV LOTUS_GIT_COMMIT_SHA="${LOTUS_GIT_COMMIT_SHA}" '
        'LOTUS_GIT_BRANCH="${LOTUS_GIT_BRANCH}" '
        'LOTUS_SERVICE_VERSION="${LOTUS_SERVICE_VERSION}" '
        'LOTUS_BUILD_TIMESTAMP="${LOTUS_BUILD_TIMESTAMP}" '
        'LOTUS_REPO_URL="${LOTUS_REPO_URL}" '
        'LOTUS_IMAGE_DIGEST="${LOTUS_IMAGE_DIGEST}" '
        'LOTUS_CI_PIPELINE_RUN_ID="${LOTUS_CI_PIPELINE_RUN_ID}" '
        'LOTUS_REPO_ROOT="/app" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1'
    ),
    "WORKDIR /app",
    "COPY --from=builder-output-validator /install /usr/local",
    "COPY contracts/domain-data-products ./contracts/domain-data-products",
    RUNTIME_PIP_REMOVAL,
    RUNTIME_ENSUREPIP_REMOVAL,
    ("RUN apk upgrade --no-cache"),
    (
        "RUN addgroup -S -g 10001 lotus && adduser -S -D -H -u 10001 -G lotus "
        "-s /sbin/nologin lotus && chown lotus:lotus /app"
    ),
    "USER lotus",
    RUNTIME_DEPENDENCY_GUARD,
    *RUNTIME_TERMINAL_INSTRUCTIONS,
)

RELEASE_STEP_ORDER = (
    "Build image for validation",
    "Capture validated local image identity",
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
TRIVY_OS_GATE_ALLOWED_FIELDS = TRIVY_LIBRARY_GATE_ALLOWED_FIELDS


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

    if "importlib.machinery.PathFinder.find_spec" not in text:
        issues.append("Dockerfile missing runtime dev-tool dependency guard")
    for package in FORBIDDEN_RUNTIME_DEV_DEPENDENCIES:
        if package not in text:
            issues.append(f"Dockerfile runtime dev-tool guard missing {package}")

    return issues


def _active_dockerfile_instructions(text: str) -> list[tuple[int, str]]:
    """Return active logical instructions after Docker continuation folding."""

    instructions: list[tuple[int, str]] = []
    current = ""
    start_index = -1
    for index, raw_line in enumerate(text.splitlines()):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not current:
            start_index = index
        current = f"{current} {line}".strip()
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        instructions.append((start_index, current))
        current = ""
    if current:
        instructions.append((start_index, current))
    return instructions


def validate_runtime_container_contract(
    dockerfile_path: Path = DOCKERFILE,
    makefile_path: Path = MAKEFILE,
) -> list[str]:
    """Validate the production runtime target and its repository-native build path."""

    dockerfile_text = _read(dockerfile_path)
    makefile_text = _read(makefile_path)
    issues: list[str] = []
    escape_directives = re.findall(r"(?im)^[ \t]*#[ \t]*escape[ \t]*=[ \t]*(\S+)", dockerfile_text)
    if any(escape != "\\" for escape in escape_directives):
        issues.append(f"{dockerfile_path}: runtime image must use default Dockerfile escape")
    if re.search(r"(?im)^[ \t]*#[ \t]*syntax[ \t]*=", dockerfile_text):
        issues.append(f"{dockerfile_path}: image contract must not use a custom syntax frontend")
    required_dockerfile_terms = {
        "AS builder": "builder stage",
        "AS builder-output-validator": "isolated builder-output validation stage",
        "AS runtime": "runtime stage",
        "COPY --from=builder-output-validator /install /usr/local": ("validated dependency copy"),
        "COPY contracts/domain-data-products ./contracts/domain-data-products": (
            "runtime data-product declarations"
        ),
        'LOTUS_REPO_ROOT="/app"': "runtime repository-root declaration",
        "apk upgrade --no-cache": "runtime operating-system security update",
        "addgroup -S -g 10001 lotus": "non-root runtime group",
        "adduser -S -D -H -u 10001": "non-root runtime user",
        "USER lotus": "non-root runtime user selection",
        "HEALTHCHECK": "container healthcheck",
        "http://127.0.0.1:8130/health/ready": "readiness healthcheck endpoint",
        '"app.main:app"': "installed-package application entrypoint",
    }
    for term, description in required_dockerfile_terms.items():
        if term not in dockerfile_text:
            issues.append(f"{dockerfile_path}: missing {description}")

    dockerfile_instructions = _active_dockerfile_instructions(dockerfile_text)
    active_text = "\n".join(
        line for line in dockerfile_text.splitlines() if not line.lstrip().startswith("#")
    )
    continuation_folded_text = re.sub(r"\\[ \t]*\r?\n[ \t]*", "", active_text)
    if any("<<" in line for line in continuation_folded_text.splitlines()):
        issues.append(f"{dockerfile_path}: runtime image contract must not use Dockerfile heredocs")
    if (
        sum(
            bool(re.match(r"^FROM\b", line, flags=re.IGNORECASE))
            for _, line in dockerfile_instructions
        )
        < 2
    ):
        issues.append(f"{dockerfile_path}: runtime image must use a multi-stage build")
    if re.search(r"\bpip\s+install\b[^\n]*\s-e(?:\s|$)", dockerfile_text):
        issues.append(f"{dockerfile_path}: runtime package install must not be editable")
    runtime_stage_declarations = [
        (position, line)
        for position, (_, line) in enumerate(dockerfile_instructions)
        if re.fullmatch(
            r"FROM\s+(?:--\S+\s+)*\S+\s+AS\s+runtime",
            line.split(" #", maxsplit=1)[0],
            flags=re.IGNORECASE,
        )
    ]
    if tuple(line for _, line in runtime_stage_declarations) != (RUNTIME_BASE_INSTRUCTION,):
        issues.append(f"{dockerfile_path}: runtime stage must use approved base image directly")
    builder_stage_declarations = [
        (position, line)
        for position, (_, line) in enumerate(dockerfile_instructions)
        if re.fullmatch(
            r"FROM\s+(?:--\S+\s+)*\S+\s+AS\s+builder",
            line.split(" #", maxsplit=1)[0],
            flags=re.IGNORECASE,
        )
    ]
    if tuple(line for _, line in builder_stage_declarations) != (BUILDER_BASE_INSTRUCTION,):
        issues.append(f"{dockerfile_path}: builder stage must use approved base image directly")
    builder_start = next(
        (
            position
            for position, (_, line) in enumerate(dockerfile_instructions)
            if line == BUILDER_BASE_INSTRUCTION
        ),
        -1,
    )
    builder_instructions: list[tuple[int, str]] = []
    if builder_start >= 0:
        for index, line in dockerfile_instructions[builder_start + 1 :]:
            if re.match(r"^FROM\b", line, flags=re.IGNORECASE):
                break
            builder_instructions.append((index, line))
    if tuple(line for _, line in builder_instructions) != BUILDER_INSTRUCTION_CONTRACT:
        issues.append(f"{dockerfile_path}: builder stage must match approved instruction contract")
    builder_output_validator_stage_declarations = [
        (position, line)
        for position, (_, line) in enumerate(dockerfile_instructions)
        if re.fullmatch(
            r"FROM\s+(?:--\S+\s+)*\S+\s+AS\s+builder-output-validator",
            line.split(" #", maxsplit=1)[0],
            flags=re.IGNORECASE,
        )
    ]
    if tuple(line for _, line in builder_output_validator_stage_declarations) != (
        BUILDER_OUTPUT_VALIDATOR_BASE_INSTRUCTION,
    ):
        issues.append(
            f"{dockerfile_path}: builder-output validator must use approved base image directly"
        )
    builder_output_validator_start = next(
        (
            position
            for position, (_, line) in enumerate(dockerfile_instructions)
            if line == BUILDER_OUTPUT_VALIDATOR_BASE_INSTRUCTION
        ),
        -1,
    )
    builder_output_validator_instructions: list[tuple[int, str]] = []
    if builder_output_validator_start >= 0:
        for index, line in dockerfile_instructions[builder_output_validator_start + 1 :]:
            if re.match(r"^FROM\b", line, flags=re.IGNORECASE):
                break
            builder_output_validator_instructions.append((index, line))
    if (
        tuple(line for _, line in builder_output_validator_instructions)
        != BUILDER_OUTPUT_VALIDATOR_INSTRUCTION_CONTRACT
    ):
        issues.append(
            f"{dockerfile_path}: builder-output validator must match approved instruction contract"
        )
    runtime_start = next(
        (
            position
            for position, (_, line) in enumerate(dockerfile_instructions)
            if line == RUNTIME_BASE_INSTRUCTION
        ),
        -1,
    )
    if runtime_start >= 0 and any(
        re.match(r"^FROM\b", line, flags=re.IGNORECASE)
        for _, line in dockerfile_instructions[runtime_start + 1 :]
    ):
        issues.append(f"{dockerfile_path}: runtime stage must be the final Dockerfile stage")
    runtime_instructions: list[tuple[int, str]] = []
    if runtime_start >= 0:
        for index, line in dockerfile_instructions[runtime_start + 1 :]:
            if re.match(r"^FROM\b", line, flags=re.IGNORECASE):
                break
            runtime_instructions.append((index, line))
    if tuple(line for _, line in runtime_instructions) != RUNTIME_INSTRUCTION_CONTRACT:
        issues.append(f"{dockerfile_path}: runtime stage must match approved instruction contract")
    if any(re.match(r"^SHELL\b", line, flags=re.IGNORECASE) for _, line in runtime_instructions):
        issues.append(f"{dockerfile_path}: runtime image must not override the Dockerfile shell")
    if any(
        re.match(r"^ENTRYPOINT\b", line, flags=re.IGNORECASE) for _, line in runtime_instructions
    ):
        issues.append(f"{dockerfile_path}: runtime image must not install an entrypoint")
    dependency_copy = next(
        (
            index
            for index, line in runtime_instructions
            if line == "COPY --from=builder-output-validator /install /usr/local"
        ),
        -1,
    )
    pip_removal = next(
        (index for index, line in runtime_instructions if line == RUNTIME_PIP_REMOVAL),
        -1,
    )
    if dependency_copy < 0:
        issues.append(f"{dockerfile_path}: runtime image must actively copy installed dependencies")
    if pip_removal < 0 or pip_removal < dependency_copy:
        issues.append(f"{dockerfile_path}: runtime image must remove pip after installation")
    bootstrap_removal = next(
        (index for index, line in runtime_instructions if line == RUNTIME_ENSUREPIP_REMOVAL),
        -1,
    )
    if bootstrap_removal < 0 or bootstrap_removal < pip_removal:
        issues.append(f"{dockerfile_path}: runtime image must remove bundled ensurepip")
    guard_index = next(
        (index for index, line in runtime_instructions if line == RUNTIME_DEPENDENCY_GUARD),
        -1,
    )
    if guard_index < 0:
        issues.append(f"{dockerfile_path}: runtime dependency guard must reject pip and ensurepip")
    elif (
        tuple(line for index, line in runtime_instructions if index > guard_index)
        != RUNTIME_TERMINAL_INSTRUCTIONS
    ):
        issues.append(
            f"{dockerfile_path}: runtime image must retain approved terminal instructions"
        )
    runtime_users = [
        (index, line)
        for index, line in runtime_instructions
        if re.match(r"^USER\b", line, flags=re.IGNORECASE)
    ]
    if guard_index >= 0 and (
        not runtime_users
        or runtime_users[-1][1] != "USER lotus"
        or runtime_users[-1][0] > guard_index
    ):
        issues.append(f"{dockerfile_path}: runtime dependency guard must run as final lotus user")
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


def _workflow_top_level_entry_block(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    next_step = re.search(r"^      - ", text[start + len(marker) :], re.MULTILINE)
    if next_step is None:
        return text[start:]
    return text[start : start + len(marker) + next_step.start()]


def _workflow_step_block(text: str, step_name: str) -> str:
    return _workflow_top_level_entry_block(text, f"- name: {step_name}")


def _workflow_nonempty_lines(block: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in block.splitlines() if line.strip())


def _workflow_field_value(block: str, field: str) -> str | None:
    match = re.search(
        rf"^\s*{re.escape(field)}:\s*(?P<value>.*?)\s*$",
        block,
        flags=re.MULTILINE,
    )
    if match is None:
        return None
    return match.group("value").strip().strip("\"'")


def _workflow_literal_block_lines(block: str, field: str) -> tuple[str, ...] | None:
    lines = block.splitlines()
    field_pattern = re.compile(
        rf"^(?P<indent>\s*){re.escape(field)}:\s*\|\s*$",
    )
    for index, line in enumerate(lines):
        match = field_pattern.match(line)
        if match is None:
            continue
        field_indent = len(match.group("indent"))
        values: list[str] = []
        for value_line in lines[index + 1 :]:
            if not value_line.strip():
                values.append("")
                continue
            value_indent = len(value_line) - len(value_line.lstrip())
            if value_indent <= field_indent:
                break
            values.append(value_line.strip())
        while values and not values[-1]:
            values.pop()
        return tuple(values)
    return None


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


def _duplicate_yaml_mapping_keys(text: str) -> list[str]:
    try:
        document = yaml.compose(text, Loader=yaml.BaseLoader)
    except yaml.YAMLError:
        return []
    duplicates: set[str] = set()

    def visit(node: yaml.Node | None) -> None:
        if isinstance(node, yaml.MappingNode):
            seen: set[str] = set()
            for key_node, value_node in node.value:
                key = key_node.value
                if key in seen:
                    duplicates.add(key)
                seen.add(key)
                visit(value_node)
        elif isinstance(node, yaml.SequenceNode):
            for nested_node in node.value:
                visit(nested_node)

    visit(document)
    return sorted(duplicates)


def _workflow_step_blocks(text: str) -> list[str]:
    starts = [match.start() for match in re.finditer(r"^      - ", text, flags=re.MULTILINE)]
    return [
        text[start : starts[index + 1] if index + 1 < len(starts) else len(text)]
        for index, start in enumerate(starts)
    ]


def _workflow_direct_step_fields(block: str) -> list[str]:
    return [
        match.group("field")
        for match in re.finditer(
            r"^(?:      - |        )(?P<quote>[\"']?)"
            r"(?P<field>[A-Za-z0-9_-]+)(?P=quote)\s*:",
            block,
            flags=re.MULTILINE,
        )
    ]


def _workflow_with_fields(block: str) -> set[str]:
    return {
        match.group("field")
        for match in re.finditer(
            r"^          (?P<quote>[\"']?)(?P<field>[A-Za-z0-9_-]+)(?P=quote)\s*:",
            block,
            flags=re.MULTILINE,
        )
    }


def _hidden_semantic_step_fields(text: str) -> list[tuple[int, list[str]]]:
    try:
        workflow = yaml.load(text, Loader=yaml.BaseLoader)
    except yaml.YAMLError:
        return [(0, ["invalid-yaml"])]
    if not isinstance(workflow, dict):
        return [(0, ["invalid-workflow-mapping"])]
    jobs = workflow.get("jobs")
    release_job = jobs.get("release-image") if isinstance(jobs, dict) else None
    steps = release_job.get("steps") if isinstance(release_job, dict) else None
    raw_step_blocks = _workflow_step_blocks(text)
    if not isinstance(steps, list) or len(steps) != len(raw_step_blocks):
        return [(0, ["invalid-step-structure"])]
    hidden_fields: list[tuple[int, list[str]]] = []
    for index, (step, raw_block) in enumerate(zip(steps, raw_step_blocks, strict=True), start=1):
        if not isinstance(step, dict):
            hidden_fields.append((index, ["invalid-step-mapping"]))
            continue
        raw_direct_fields = _workflow_direct_step_fields(raw_block)
        semantic_direct_fields = {str(field) for field in step}
        hidden = semantic_direct_fields - set(raw_direct_fields)
        with_mapping = step.get("with")
        if isinstance(with_mapping, dict):
            hidden.update(
                f"with.{field}"
                for field in {str(field) for field in with_mapping}
                - _workflow_with_fields(raw_block)
            )
        if "with" in raw_direct_fields:
            with_index = raw_direct_fields.index("with")
            hidden.update(
                f"field-after-with.{field}" for field in raw_direct_fields[with_index + 1 :]
            )
        if hidden:
            hidden_fields.append((index, sorted(hidden)))
    return hidden_fields


def _decoded_workflow_job_ids(text: str) -> tuple[str, ...]:
    try:
        workflow = yaml.load(text, Loader=yaml.BaseLoader)
    except yaml.YAMLError:
        return ()
    if not isinstance(workflow, dict):
        return ()
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return ()
    return tuple(str(job_id) for job_id in jobs)


def _decoded_workflow_control_fields(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        workflow = yaml.load(text, Loader=yaml.BaseLoader)
    except yaml.YAMLError:
        return (), ()
    if not isinstance(workflow, dict):
        return (), ()
    jobs = workflow.get("jobs")
    release_job = jobs.get("release-image") if isinstance(jobs, dict) else None
    job_fields = tuple(str(field) for field in release_job) if isinstance(release_job, dict) else ()
    return tuple(str(field) for field in workflow), job_fields


def validate_ci_image_release_workflow(
    workflow_path: Path = IMAGE_RELEASE_WORKFLOW,
) -> list[str]:
    if not workflow_path.exists():
        return [f"{workflow_path}: image release workflow is missing"]

    text = _read(workflow_path)
    issues: list[str] = []
    if duplicate_keys := _duplicate_yaml_mapping_keys(text):
        issues.append(
            f"{workflow_path}: duplicate decoded YAML mapping keys are forbidden: "
            f"{', '.join(duplicate_keys)}"
        )
    for step_index, hidden_fields in _hidden_semantic_step_fields(text):
        issues.append(
            f"{workflow_path}: release step {step_index} contains decoded YAML fields that are "
            f"not plain declared keys: {', '.join(hidden_fields)}"
        )
    if _decoded_workflow_job_ids(text) != ("release-image",):
        issues.append(f"{workflow_path}: decoded release-image must be the workflow's only job")
    decoded_workflow_fields, decoded_job_fields = _decoded_workflow_control_fields(text)
    if decoded_workflow_fields != APPROVED_DECODED_WORKFLOW_FIELDS:
        issues.append(f"{workflow_path}: decoded workflow fields must match the approved contract")
    if decoded_job_fields != APPROVED_DECODED_RELEASE_JOB_FIELDS:
        issues.append(
            f"{workflow_path}: decoded release job fields must match the approved contract"
        )
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
        "docker/build-push-action@v7": "Docker build/push action",
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
    if BUILDKIT_SYNTAX_OVERRIDE_PATTERN.search(text):
        issues.append(f"{workflow_path}: reserved BUILDKIT_SYNTAX frontend override is forbidden")
    if docker_endpoint_overrides := sorted(
        {match.group("name").upper() for match in DOCKER_ENDPOINT_OVERRIDE_PATTERN.finditer(text)}
    ):
        issues.append(
            f"{workflow_path}: ambient Docker endpoint overrides are forbidden: "
            f"{', '.join(docker_endpoint_overrides)}"
        )
    workflow_permissions_start = text.find("\npermissions:\n")
    workflow_permissions_end = text.find("\nenv:\n", workflow_permissions_start)
    workflow_permissions_block = (
        text[workflow_permissions_start + 1 : workflow_permissions_end]
        if workflow_permissions_start >= 0 and workflow_permissions_end >= 0
        else ""
    )
    if _workflow_nonempty_lines(workflow_permissions_block) != APPROVED_WORKFLOW_PERMISSIONS:
        issues.append(f"{workflow_path}: workflow permissions must match the approved contract")
    workflow_env_start = text.find("\nenv:\n")
    workflow_env_end = text.find("\njobs:\n", workflow_env_start)
    workflow_env_block = (
        text[workflow_env_start + 1 : workflow_env_end]
        if workflow_env_start >= 0 and workflow_env_end >= 0
        else ""
    )
    if _workflow_nonempty_lines(workflow_env_block) != APPROVED_WORKFLOW_ENVIRONMENT:
        issues.append(f"{workflow_path}: workflow environment must match the approved contract")
    jobs_start = text.find("\njobs:\n")
    jobs_block = text[jobs_start + 1 :] if jobs_start >= 0 else ""
    workflow_header = text[: jobs_start + len("\njobs:\n")] if jobs_start >= 0 else ""
    if _workflow_nonempty_lines(workflow_header) != APPROVED_WORKFLOW_HEADER:
        issues.append(f"{workflow_path}: workflow header must match the approved contract")
    steps_marker = "    steps:\n"
    steps_start = text.find(steps_marker, jobs_start)
    release_job_header = (
        text[jobs_start + 1 : steps_start + len(steps_marker)]
        if jobs_start >= 0 and steps_start >= 0
        else ""
    )
    if _workflow_nonempty_lines(release_job_header) != APPROVED_RELEASE_JOB_HEADER:
        issues.append(f"{workflow_path}: release job header must match the approved contract")
    job_ids = tuple(
        match.group("job_id")
        for match in re.finditer(
            r"^  (?P<quote>[\"']?)(?P<job_id>[A-Za-z0-9_-]+)(?P=quote):[ \t]*$",
            jobs_block,
            flags=re.MULTILINE,
        )
    )
    if job_ids != ("release-image",):
        issues.append(f"{workflow_path}: release-image must be the workflow's only job")
    if re.search(
        r"^(?:defaults|[ \t]+(?:defaults|container|services|env)):[ \t]*(?:$|\{)",
        text,
        flags=re.MULTILINE,
    ):
        issues.append(f"{workflow_path}: custom job or step execution context is forbidden")
    if len(re.findall(r"^\s{4}runs-on:\s*ubuntu-latest\s*$", text, flags=re.MULTILINE)) != 1:
        issues.append(f"{workflow_path}: release job must use the approved ubuntu-latest runner")
    build_actions = re.findall(r"docker/build-push-action@[^\s\"']+", text)
    if build_actions != ["docker/build-push-action@v7"]:
        issues.append(
            f"{workflow_path}: release workflow must contain exactly one approved Docker build action"
        )
    if DOCKER_IMAGE_MUTATION_PATTERN.search(text):
        issues.append(
            f"{workflow_path}: release workflow must not mutate the validated local image tag"
        )

    issues.extend(validate_release_publication_order(text, workflow_path))

    if re.search(r"^\s*push:\s*true\s*$", text, flags=re.MULTILINE):
        issues.append(f"{workflow_path}: build must not publish before the vulnerability scan")
    if "imagetools inspect" in text:
        issues.append(
            f"{workflow_path}: digest must come from this run's push, not a mutable tag lookup"
        )
    build = _workflow_step_block(text, "Build image for validation")
    if (
        _workflow_field_value(build, "id") != "build"
        or _workflow_field_value(build, "uses") != "docker/build-push-action@v7"
        or _workflow_field_value(build, "context") != "."
        or _workflow_field_value(build, "file") != "Dockerfile"
        or _workflow_field_value(build, "target") != "runtime"
        or _workflow_field_value(build, "push") != "false"
        or _workflow_field_value(build, "load") != "true"
        or _workflow_field_value(build, "tags") != "${{ env.IMAGE_NAME }}:${{ github.sha }}"
        or _workflow_field_value(build, "provenance") != "false"
        or _workflow_field_value(build, "sbom") != "false"
        or _unexpected_workflow_fields(
            build,
            {
                "name",
                "id",
                "uses",
                "with",
                "context",
                "file",
                "target",
                "push",
                "load",
                "tags",
                "provenance",
                "sbom",
                "build-args",
            },
        )
    ):
        issues.append(
            f"{workflow_path}: release build must use context ., the validated root Dockerfile, "
            "and runtime target"
        )
    if _workflow_literal_block_lines(build, "build-args") != APPROVED_RELEASE_BUILD_ARGS:
        issues.append(f"{workflow_path}: release build arguments must match the approved contract")
    governed_steps_start = steps_start + len(steps_marker) if steps_start >= 0 else -1
    governed_steps_segment = text[governed_steps_start:] if governed_steps_start >= 0 else ""
    governed_step_entries = tuple(
        match.group("entry").strip()
        for match in re.finditer(
            r"^      - (?P<entry>.+)$",
            governed_steps_segment,
            flags=re.MULTILINE,
        )
    )
    if governed_step_entries != APPROVED_RELEASE_STEP_ENTRIES:
        issues.append(f"{workflow_path}: release steps must match the approved contract")
    checkout = _workflow_top_level_entry_block(text, "- uses: actions/checkout@v6")
    python_setup = _workflow_top_level_entry_block(text, "- uses: actions/setup-python@v6")
    buildx_setup = _workflow_top_level_entry_block(text, "- uses: docker/setup-buildx-action@v4")
    if _workflow_nonempty_lines(checkout) != APPROVED_CHECKOUT_STEP:
        issues.append(f"{workflow_path}: checkout step must match the approved contract")
    if _workflow_nonempty_lines(python_setup) != APPROVED_PYTHON_SETUP_STEP:
        issues.append(f"{workflow_path}: Python setup step must match the approved contract")
    if _workflow_nonempty_lines(buildx_setup) != APPROVED_BUILDX_SETUP_STEP:
        issues.append(f"{workflow_path}: Buildx setup step must match the approved local contract")
    supply_chain_validation = _workflow_step_block(text, "Validate image supply-chain contract")
    if _workflow_literal_block_lines(
        supply_chain_validation, "run"
    ) != APPROVED_SUPPLY_CHAIN_VALIDATION_SCRIPT or _unexpected_workflow_fields(
        supply_chain_validation, {"name", "run"}
    ):
        issues.append(
            f"{workflow_path}: supply-chain validation step must match the approved contract"
        )
    build_timestamp = _workflow_step_block(text, "Resolve build timestamp")
    build_timestamp_lines = _workflow_nonempty_lines(build_timestamp)
    if build_timestamp_lines != (
        "- name: Resolve build timestamp",
        'run: echo "LOTUS_BUILD_TIMESTAMP=$(date -u +\'%Y-%m-%dT%H:%M:%SZ\')" >> "$GITHUB_ENV"',
    ):
        issues.append(f"{workflow_path}: build timestamp step must match the approved contract")
    image_capture = _workflow_step_block(text, "Capture validated local image identity")
    if (
        _workflow_field_value(image_capture, "id") != "validated_image"
        or _workflow_field_value(image_capture, "shell") != "bash"
        or _workflow_literal_block_lines(image_capture, "run") != APPROVED_IMAGE_ID_CAPTURE
        or _unexpected_workflow_fields(image_capture, {"name", "id", "shell", "run"})
    ):
        issues.append(f"{workflow_path}: validated local image identity capture must remain locked")
    evidence_directory = _workflow_step_block(text, "Prepare image release evidence directory")
    if _workflow_field_value(
        evidence_directory, "run"
    ) != "mkdir -p output/image-release" or _unexpected_workflow_fields(
        evidence_directory, {"name", "run"}
    ):
        issues.append(f"{workflow_path}: release evidence preparation must remain non-mutating")
    sbom = _workflow_step_block(text, "Generate SBOM")
    if (
        _workflow_field_value(sbom, "uses") != "anchore/sbom-action@v0"
        or _workflow_field_value(sbom, "image") != VALIDATED_LOCAL_IMAGE_ID
        or _workflow_field_value(sbom, "format") != "spdx-json"
        or _workflow_field_value(sbom, "output-file")
        != "output/image-release/lotus-risk-sbom.spdx.json"
        or _unexpected_workflow_fields(
            sbom,
            {"name", "uses", "with", "image", "format", "output-file"},
        )
    ):
        issues.append(f"{workflow_path}: SBOM must use the validated immutable local image ID")
    inventory = _workflow_step_block(text, "Generate complete vulnerability inventory")
    if (
        _workflow_field_value(inventory, "uses") != "aquasecurity/trivy-action@v0.36.0"
        or _workflow_field_value(inventory, "scan-type") != "image"
        or _workflow_field_value(inventory, "scanners") != "vuln"
        or _workflow_field_value(inventory, "version") != "v0.70.0"
        or _workflow_field_value(inventory, "image-ref") != VALIDATED_LOCAL_IMAGE_ID
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
        or _unexpected_workflow_fields(
            inventory_upload,
            {"name", "uses", "if", "with", "sarif_file"},
        )
    ):
        issues.append(f"{workflow_path}: complete vulnerability inventory SARIF must be uploaded")

    library_gate = _workflow_step_block(text, "Block application-library vulnerabilities")
    if (
        _workflow_field_value(library_gate, "uses") != "aquasecurity/trivy-action@v0.36.0"
        or _workflow_field_value(library_gate, "scan-type") != "image"
        or _workflow_field_value(library_gate, "scanners") != "vuln"
        or _workflow_field_value(library_gate, "version") != "v0.70.0"
        or _workflow_field_value(library_gate, "image-ref") != VALIDATED_LOCAL_IMAGE_ID
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
    if _workflow_field_value(os_gate, "image-ref") != VALIDATED_LOCAL_IMAGE_ID:
        issues.append(f"{workflow_path}: OS vulnerability gate must scan the release image")
    if _workflow_field_value(os_gate, "vuln-type") != "os":
        issues.append(f"{workflow_path}: OS vulnerability gate must scan only OS findings")
    if _workflow_field_value(os_gate, "ignore-unfixed") is not None:
        issues.append(f"{workflow_path}: OS vulnerability gate must not ignore unfixed findings")
    if _workflow_field_value(os_gate, "exit-code") != "1":
        issues.append(f"{workflow_path}: OS HIGH/CRITICAL findings must be blocking")
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
    registry_authentication = _workflow_step_block(text, "Authenticate to release registry")
    if (
        _workflow_field_value(registry_authentication, "uses") != "docker/login-action@v4"
        or _workflow_field_value(registry_authentication, "registry") != "ghcr.io"
        or _workflow_field_value(registry_authentication, "username") != "${{ github.actor }}"
        or _workflow_field_value(registry_authentication, "password")
        != "${{ secrets.GITHUB_TOKEN }}"
        or _unexpected_workflow_fields(
            registry_authentication,
            {"name", "uses", "with", "registry", "username", "password"},
        )
    ):
        issues.append(f"{workflow_path}: registry authentication must match the approved contract")

    if 'branches: [ "main" ]' not in text and "branches: [main]" not in text:
        issues.append(f"{workflow_path}: image push must be scoped to main")

    publish = _workflow_step_block(text, "Push immutable image after scan")
    publish_lines = _workflow_literal_block_lines(publish, "run") or ()
    if (
        _workflow_field_value(publish, "id") != "publish"
        or _workflow_field_value(publish, "shell") != "bash"
        or publish_lines != APPROVED_PUBLISH_SCRIPT
        or _unexpected_workflow_fields(publish, {"name", "id", "shell", "run"})
    ):
        issues.append(f"{workflow_path}: publication script must match the approved contract")

    cosign_setup = _workflow_top_level_entry_block(text, "- uses: sigstore/cosign-installer@v3")
    if _workflow_nonempty_lines(cosign_setup) != APPROVED_COSIGN_SETUP_STEP:
        issues.append(f"{workflow_path}: cosign setup must match the approved contract")
    signing = _workflow_step_block(text, "Sign image by digest")
    if _workflow_nonempty_lines(signing) != APPROVED_SIGNING_STEP:
        issues.append(f"{workflow_path}: image signing must match the approved contract")
    provenance = _workflow_step_block(text, "Generate provenance attestation")
    if (
        _workflow_field_value(provenance, "uses") != "actions/attest-build-provenance@v3"
        or _workflow_field_value(provenance, "subject-name") != "${{ env.IMAGE_NAME }}"
        or _workflow_field_value(provenance, "subject-digest")
        != "${{ steps.publish.outputs.digest }}"
        or _workflow_field_value(provenance, "push-to-registry") != "true"
        or _unexpected_workflow_fields(
            provenance,
            {"name", "uses", "with", "subject-name", "subject-digest", "push-to-registry"},
        )
    ):
        issues.append(f"{workflow_path}: provenance must match the approved contract")
    release_manifest = _workflow_step_block(text, "Write release manifest")
    if _workflow_nonempty_lines(release_manifest) != (
        "- name: Write release manifest",
        "run: |",
        *APPROVED_RELEASE_MANIFEST_SCRIPT,
    ):
        issues.append(f"{workflow_path}: release manifest must match the approved contract")
    evidence_upload = _workflow_step_block(text, "Upload image release evidence")
    if (
        _workflow_field_value(evidence_upload, "uses") != "actions/upload-artifact@v6"
        or _workflow_field_value(evidence_upload, "name")
        != "lotus-risk-image-release-${{ github.sha }}"
        or _workflow_field_value(evidence_upload, "path") != "output/image-release/"
        or _workflow_field_value(evidence_upload, "if-no-files-found") != "error"
        or _unexpected_workflow_fields(
            evidence_upload,
            {"name", "uses", "with", "path", "if-no-files-found"},
        )
    ):
        issues.append(f"{workflow_path}: evidence upload must match the approved contract")

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
