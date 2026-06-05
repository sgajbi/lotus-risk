from __future__ import annotations

import argparse
import json
from pathlib import Path
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
SPECTRAL_CONFIG_PATH = PROJECT_ROOT / ".spectral.yaml"

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
    args = parser.parse_args()

    schema = load_generated_schema()
    write_openapi_artifact(schema, args.output)

    if args.check:
        errors = validate_openapi_artifact(args.output)
        if errors:
            print("\n".join(errors))
            return 1

    print(f"Generated OpenAPI artifact at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
