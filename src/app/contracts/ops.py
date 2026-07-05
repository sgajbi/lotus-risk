from __future__ import annotations

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    service: str = Field(
        description="Dependency service identifier.",
        json_schema_extra={"example": "lotus-core"},
    )
    base_url: str = Field(
        description="Canonical base URL configured for the dependency.",
        json_schema_extra={"example": "http://core-control.dev.lotus"},
    )
    status: str = Field(
        description="Dependency runtime state.",
        json_schema_extra={"example": "configured"},
    )
    detail: str | None = Field(
        default=None,
        description="Additional runtime detail for operators.",
        json_schema_extra={"example": "configured_only_no_probe"},
    )
    category: str | None = Field(
        default=None,
        description="Optional structured dependency issue category such as transport, timeout, or data_gap.",
        json_schema_extra={"example": "data_gap"},
    )
    issue_code: str | None = Field(
        default=None,
        description="Optional machine-readable issue code for degraded or unavailable dependency state.",
        json_schema_extra={"example": "RISK_FREE_SERIES_EMPTY"},
    )


class HealthResponse(BaseModel):
    status: str = Field(
        description="Health status indicator.",
        json_schema_extra={"example": "ok"},
    )
    service: str = Field(
        description="Service identifier.",
        json_schema_extra={"example": "lotus-risk"},
    )


class LivenessResponse(BaseModel):
    status: str = Field(
        description="Liveness status indicator.",
        json_schema_extra={"example": "live"},
    )


class ReadinessResponse(BaseModel):
    status: str = Field(
        description="Readiness state.",
        json_schema_extra={"example": "ready"},
    )
    dependencies: list[DependencyStatus] = Field(
        description=(
            "Dependency configuration states and optional runtime override states used to "
            "determine readiness."
        ),
        json_schema_extra={
            "example": [
                {
                    "service": "lotus-performance",
                    "base_url": "http://performance.dev.lotus",
                    "status": "configured",
                    "detail": "configured_only_no_probe",
                }
            ]
        },
    )


class MetadataResponse(BaseModel):
    service: str = Field(
        description="Service identifier.",
        json_schema_extra={"example": "lotus-risk"},
    )
    version: str = Field(
        description="Service version string.",
        json_schema_extra={"example": "0.1.0"},
    )
    rounding_policy_version: str = Field(
        description="Rounding policy revision used by risk outputs.",
        json_schema_extra={"example": "v1"},
    )
    build: "BuildMetadata" = Field(
        description=("Build and image provenance emitted through OCI labels and runtime metadata."),
        json_schema_extra={
            "example": {
                "git_commit_sha": "0123456789abcdef0123456789abcdef01234567",
                "git_branch": "refactor/enterprise-risk-backend",
                "build_timestamp": "2026-07-05T02:44:17Z",
                "repo_url": "https://github.com/sgajbi/lotus-risk",
                "image_digest": (
                    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
                ),
                "ci_pipeline_run_id": "28727286816",
            }
        },
    )


class BuildMetadata(BaseModel):
    git_commit_sha: str = Field(
        description="Git commit SHA used to build the image.",
        json_schema_extra={"example": "0123456789abcdef0123456789abcdef01234567"},
    )
    git_branch: str = Field(
        description="Git branch or ref name used to build the image.",
        json_schema_extra={"example": "refactor/enterprise-risk-backend"},
    )
    build_timestamp: str = Field(
        description="UTC build timestamp associated with the image.",
        json_schema_extra={"example": "2026-07-05T02:44:17Z"},
    )
    repo_url: str = Field(
        description="Repository URL for the source checkout used by the build.",
        json_schema_extra={"example": "https://github.com/sgajbi/lotus-risk"},
    )
    image_digest: str = Field(
        description=(
            "Published image digest supplied by the registry or deployment metadata. Local "
            "unpublished builds may report an explicit unavailable value."
        ),
        json_schema_extra={
            "example": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        },
    )
    ci_pipeline_run_id: str = Field(
        description="CI pipeline or workflow run identifier associated with the image build.",
        json_schema_extra={"example": "28727286816"},
    )


class OpsChecks(BaseModel):
    live: bool = Field(
        description="Liveness check status.",
        json_schema_extra={"example": True},
    )
    ready: bool = Field(
        description="Readiness check status.",
        json_schema_extra={"example": True},
    )
    draining: bool = Field(
        description="Whether the service is currently in draining mode.",
        json_schema_extra={"example": False},
    )


class OpsResponse(BaseModel):
    service: str = Field(
        description="Service identifier.",
        json_schema_extra={"example": "lotus-risk"},
    )
    version: str = Field(
        description="Service version.",
        json_schema_extra={"example": "0.1.0"},
    )
    status: str = Field(
        description="Overall operational status.",
        json_schema_extra={"example": "ok"},
    )
    checks: OpsChecks = Field(
        description="Detailed health checks.",
        json_schema_extra={"example": {"live": True, "ready": True, "draining": False}},
    )
    input_modes: list[str] = Field(
        description="Execution modes exposed by this service.",
        json_schema_extra={"example": ["stateless", "stateful", "simulation"]},
    )
    dependencies: list[DependencyStatus] = Field(
        description=(
            "Dependency configuration diagnostics and optional runtime override states used for "
            "readiness and operations."
        ),
        json_schema_extra={
            "example": [
                {
                    "service": "lotus-core",
                    "base_url": "http://core-control.dev.lotus",
                    "status": "configured",
                    "detail": "configured_only_no_probe",
                }
            ]
        },
    )
