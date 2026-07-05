from __future__ import annotations

import os

UNKNOWN_BUILD_VALUE = "unknown"

GIT_COMMIT_SHA_ENV = "LOTUS_GIT_COMMIT_SHA"
GIT_BRANCH_ENV = "LOTUS_GIT_BRANCH"
BUILD_TIMESTAMP_ENV = "LOTUS_BUILD_TIMESTAMP"
REPO_URL_ENV = "LOTUS_REPO_URL"
IMAGE_DIGEST_ENV = "LOTUS_IMAGE_DIGEST"
CI_PIPELINE_RUN_ID_ENV = "LOTUS_CI_PIPELINE_RUN_ID"


def _read_build_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    return value or UNKNOWN_BUILD_VALUE


def resolve_build_metadata() -> dict[str, str]:
    return {
        "git_commit_sha": _read_build_value(GIT_COMMIT_SHA_ENV),
        "git_branch": _read_build_value(GIT_BRANCH_ENV),
        "build_timestamp": _read_build_value(BUILD_TIMESTAMP_ENV),
        "repo_url": _read_build_value(REPO_URL_ENV),
        "image_digest": _read_build_value(IMAGE_DIGEST_ENV),
        "ci_pipeline_run_id": _read_build_value(CI_PIPELINE_RUN_ID_ENV),
    }


__all__ = [
    "BUILD_TIMESTAMP_ENV",
    "CI_PIPELINE_RUN_ID_ENV",
    "GIT_BRANCH_ENV",
    "GIT_COMMIT_SHA_ENV",
    "IMAGE_DIGEST_ENV",
    "REPO_URL_ENV",
    "UNKNOWN_BUILD_VALUE",
    "resolve_build_metadata",
]
