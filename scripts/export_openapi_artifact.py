from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT_PATH = str(PROJECT_ROOT)
if PROJECT_ROOT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_PATH)
SCRIPT_PATH = str(PROJECT_ROOT / "scripts")
if SCRIPT_PATH not in sys.path:
    sys.path.insert(0, SCRIPT_PATH)

from scripts._repo_imports import force_repo_src_first  # noqa: E402
from scripts.openapi_quality_gate import evaluate_schema  # noqa: E402

DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "openapi" / "lotus-risk.openapi.json"
DEFAULT_EVIDENCE_JSON_PATH = (
    PROJECT_ROOT / "output" / "openapi" / "lotus-risk.openapi.evidence.json"
)
DEFAULT_EVIDENCE_MARKDOWN_PATH = (
    PROJECT_ROOT / "output" / "openapi" / "lotus-risk.openapi.evidence.md"
)
SPECTRAL_CONFIG_PATH = PROJECT_ROOT / ".spectral.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}

REQUIRED_SPECTRAL_RULES = {
    "operation-operationId: error",
    "operation-tags: error",
    "operation-summary: error",
    "lotus-standard-error-responses:",
}


def load_generated_schema() -> dict[str, Any]:
    force_repo_src_first(PROJECT_ROOT)
    from app.main import app  # noqa: PLC0415

    schema = app.openapi()
    if not isinstance(schema, dict):
        raise TypeError("Generated OpenAPI schema must be a JSON object.")
    return schema


def write_openapi_artifact(schema: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_git(args: list[str], fallback: str = "unknown") -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    return value or fallback


def _source_identity() -> dict[str, str]:
    repository = os.environ.get("GITHUB_REPOSITORY")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo_url = (
        f"{server_url.rstrip('/')}/{repository}"
        if repository
        else _run_git(["config", "--get", "remote.origin.url"])
    )
    return {
        "git_branch": (
            os.environ.get("GITHUB_HEAD_REF")
            or os.environ.get("GITHUB_REF_NAME")
            or _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        ),
        "git_commit_sha": os.environ.get("GITHUB_SHA") or _run_git(["rev-parse", "HEAD"]),
        "repo_url": repo_url,
        "ci_pipeline_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
    }


def _operation_count(schema: dict[str, Any]) -> int:
    paths = schema.get("paths", {})
    if not isinstance(paths, dict):
        return 0
    return sum(
        1
        for path_item in paths.values()
        if isinstance(path_item, dict)
        for method in path_item
        if method.lower() in HTTP_METHODS
    )


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def build_openapi_evidence(
    schema: dict[str, Any],
    artifact_path: Path,
    *,
    generated_at_utc: str | None = None,
    source_identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    artifact_bytes = artifact_path.read_bytes()
    paths = schema.get("paths", {})
    identity = source_identity or _source_identity()
    return {
        "artifact_path": _display_path(artifact_path),
        "generation_command": "make openapi-artifact-gate",
        "validation_commands": ["make openapi-artifact-gate", "make openapi-gate"],
        "generated_at_utc": generated_at_utc
        or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": identity,
        "openapi": {
            "version": str(schema.get("openapi", "unknown")),
            "title": str(schema.get("info", {}).get("title", "unknown"))
            if isinstance(schema.get("info"), dict)
            else "unknown",
            "api_version": str(schema.get("info", {}).get("version", "unknown"))
            if isinstance(schema.get("info"), dict)
            else "unknown",
            "path_count": len(paths) if isinstance(paths, dict) else 0,
            "operation_count": _operation_count(schema),
        },
        "artifact": {
            "size_bytes": artifact_path.stat().st_size,
            "sha256": hashlib.sha256(artifact_bytes).hexdigest().upper(),
        },
    }


def write_openapi_evidence(
    evidence: dict[str, Any],
    *,
    json_path: Path = DEFAULT_EVIDENCE_JSON_PATH,
    markdown_path: Path = DEFAULT_EVIDENCE_MARKDOWN_PATH,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    source = evidence["source"]
    openapi = evidence["openapi"]
    artifact = evidence["artifact"]
    markdown = f"""# Lotus Risk OpenAPI Artifact Evidence

This generated evidence describes the current OpenAPI artifact produced by
`make openapi-artifact-gate`.

| Field | Value |
| --- | --- |
| Artifact path | `{evidence["artifact_path"]}` |
| Generation command | `{evidence["generation_command"]}` |
| Validation commands | `{", ".join(evidence["validation_commands"])}` |
| Generated at UTC | `{evidence["generated_at_utc"]}` |
| Git branch | `{source["git_branch"]}` |
| Git commit SHA | `{source["git_commit_sha"]}` |
| Repository URL | `{source["repo_url"]}` |
| CI pipeline/run ID | `{source["ci_pipeline_run_id"]}` |
| OpenAPI version | `{openapi["version"]}` |
| API title | `{openapi["title"]}` |
| API version | `{openapi["api_version"]}` |
| Path count | `{openapi["path_count"]}` |
| Operation count | `{openapi["operation_count"]}` |
| Artifact size bytes | `{artifact["size_bytes"]}` |
| SHA-256 | `{artifact["sha256"]}` |
"""
    markdown_path.write_text(markdown, encoding="utf-8")


def load_openapi_artifact(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: OpenAPI artifact root must be a JSON object.")
    return payload


def validate_spectral_policy_config(config_path: Path = SPECTRAL_CONFIG_PATH) -> list[str]:
    if not config_path.exists():
        return [f"{config_path}: Spectral policy config is missing"]

    text = config_path.read_text(encoding="utf-8")
    return [
        f"{config_path}: missing required Spectral policy rule {rule}"
        for rule in sorted(REQUIRED_SPECTRAL_RULES)
        if rule not in text
    ]


def validate_openapi_artifact(path: Path, *, service_name: str = "lotus-risk") -> list[str]:
    if not path.exists():
        return [f"{path}: generated OpenAPI artifact is missing"]

    schema = load_openapi_artifact(path)
    errors = validate_spectral_policy_config()
    errors.extend(evaluate_schema(schema, service_name=service_name))
    return errors


def validate_openapi_evidence(
    evidence: dict[str, Any],
    schema: dict[str, Any],
    artifact_path: Path,
    *,
    source_identity: dict[str, str] | None = None,
) -> list[str]:
    expected = build_openapi_evidence(
        schema,
        artifact_path,
        generated_at_utc=str(evidence.get("generated_at_utc", "")),
        source_identity=source_identity,
    )
    errors: list[str] = []
    for key in (
        "artifact_path",
        "generation_command",
        "validation_commands",
        "source",
        "openapi",
        "artifact",
    ):
        if evidence.get(key) != expected[key]:
            errors.append(f"OpenAPI evidence field {key} is stale or invalid")
    generated_at = evidence.get("generated_at_utc")
    if not isinstance(generated_at, str) or not generated_at.endswith("Z"):
        errors.append("OpenAPI evidence field generated_at_utc must be a UTC timestamp")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export and validate the lotus-risk generated OpenAPI artifact."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path for the generated OpenAPI JSON artifact.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the exported artifact after writing it.",
    )
    parser.add_argument(
        "--evidence-json",
        type=Path,
        default=DEFAULT_EVIDENCE_JSON_PATH,
        help="Path for the generated OpenAPI evidence JSON manifest.",
    )
    parser.add_argument(
        "--evidence-markdown",
        type=Path,
        default=DEFAULT_EVIDENCE_MARKDOWN_PATH,
        help="Path for the generated OpenAPI evidence Markdown manifest.",
    )
    args = parser.parse_args()

    schema = load_generated_schema()
    write_openapi_artifact(schema, args.output)
    evidence = build_openapi_evidence(schema, args.output)
    write_openapi_evidence(
        evidence,
        json_path=args.evidence_json,
        markdown_path=args.evidence_markdown,
    )

    if args.check:
        errors = validate_openapi_artifact(args.output)
        errors.extend(validate_openapi_evidence(evidence, schema, args.output))
        if errors:
            print("\n".join(errors))
            return 1

    print(f"Generated OpenAPI artifact at {args.output}")
    print(f"Generated OpenAPI evidence at {args.evidence_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
