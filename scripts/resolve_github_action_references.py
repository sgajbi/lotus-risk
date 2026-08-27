"""Resolve pinned GitHub Action references against the GitHub API.

This network-dependent scheduled check complements, but does not replace, the deterministic
reference-form validation in ``validate_github_actions_runtime.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_github_actions_runtime import ANY_ACTION_USE_PATTERN  # noqa: E402


DEFAULT_WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
EXIT_MISSING = 1
EXIT_INCONCLUSIVE = 2


@dataclass(frozen=True)
class ActionReference:
    slug: str
    ref: str
    path: str
    line_number: int


@dataclass(frozen=True)
class Resolution:
    slug: str
    ref: str
    status: str
    resolved_sha: str | None
    detail: str
    occurrences: tuple[str, ...]


@dataclass(frozen=True)
class ApiResponse:
    status: int
    payload: object | None = None
    detail: str = ""


class ApiClient(Protocol):
    def get(self, path: str) -> ApiResponse: ...


class GitHubApiClient:
    def __init__(self, token: str, *, api_url: str = "https://api.github.com") -> None:
        self._token = token
        self._api_url = api_url.rstrip("/")

    def get(self, path: str) -> ApiResponse:
        request = urllib.request.Request(
            f"{self._api_url}/{path.lstrip('/')}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "lotus-risk-action-reference-resolver",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
                return ApiResponse(status=response.status, payload=json.load(response))
        except urllib.error.HTTPError as error:
            remaining = error.headers.get("x-ratelimit-remaining", "unknown")
            return ApiResponse(
                status=error.code,
                payload=None,
                detail=f"HTTP {error.code}; rate-limit remaining={remaining}",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            return ApiResponse(status=0, payload=None, detail=f"network error: {error}")


def collect_references(workflows_dir: Path) -> list[ActionReference]:
    references: list[ActionReference] = []
    for path in sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")]):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = ANY_ACTION_USE_PATTERN.search(line)
            if match is None:
                continue
            try:
                display_path = str(path.relative_to(REPO_ROOT))
            except ValueError:
                display_path = str(path)
            references.append(
                ActionReference(
                    slug=match.group("slug"),
                    ref=match.group("ref"),
                    path=display_path.replace("\\", "/"),
                    line_number=line_number,
                )
            )
    return references


def _reference_api_path(slug: str, ref: str) -> str:
    escaped_slug = "/".join(urllib.parse.quote(part, safe="") for part in slug.split("/"))
    if len(ref) == 40 and all(character in "0123456789abcdef" for character in ref):
        return f"repos/{escaped_slug}/commits/{ref}"
    return f"repos/{escaped_slug}/git/ref/tags/{urllib.parse.quote(ref, safe='')}"


def _payload_dict(response: ApiResponse) -> dict[str, object]:
    return response.payload if isinstance(response.payload, dict) else {}


def _resolved_sha(
    slug: str, ref: str, response: ApiResponse, client: ApiClient
) -> tuple[str | None, str]:
    """Return the immutable commit SHA behind a commit or lightweight/annotated tag."""
    payload = _payload_dict(response)
    if len(ref) == 40 and all(character in "0123456789abcdef" for character in ref):
        sha = payload.get("sha")
        return (sha if isinstance(sha, str) else ref), response.detail

    target = payload.get("object")
    if not isinstance(target, dict):
        return None, "GitHub returned a tag reference without an object target"
    target_type = target.get("type")
    target_sha = target.get("sha")
    if not isinstance(target_type, str) or not isinstance(target_sha, str):
        return None, "GitHub returned an incomplete tag object target"

    escaped_slug = "/".join(urllib.parse.quote(part, safe="") for part in slug.split("/"))
    for _ in range(10):
        if target_type == "commit":
            return target_sha, response.detail
        if target_type != "tag":
            return None, f"GitHub tag resolved to unsupported object type {target_type!r}"
        peeled = client.get(
            f"repos/{escaped_slug}/git/tags/{urllib.parse.quote(target_sha, safe='')}"
        )
        if peeled.status != 200:
            return None, peeled.detail or f"HTTP {peeled.status} while peeling annotated tag"
        peeled_object = _payload_dict(peeled).get("object")
        if not isinstance(peeled_object, dict):
            return None, "GitHub returned an annotated tag without an object target"
        target_type = peeled_object.get("type")
        target_sha = peeled_object.get("sha")
        if not isinstance(target_type, str) or not isinstance(target_sha, str):
            return None, "GitHub returned an incomplete annotated-tag target"
    return None, "GitHub tag nesting exceeded the resolver safety limit"


def resolve_references(references: list[ActionReference], client: ApiClient) -> list[Resolution]:
    grouped: dict[tuple[str, str], list[ActionReference]] = {}
    for reference in references:
        grouped.setdefault((reference.slug, reference.ref), []).append(reference)

    repository_status: dict[str, ApiResponse] = {}
    resolutions: list[Resolution] = []
    for (slug, ref), occurrences in sorted(grouped.items()):
        locations = tuple(f"{item.path}:{item.line_number}" for item in occurrences)
        if slug not in repository_status:
            repository_status[slug] = client.get(f"repos/{slug}")
        repo_response = repository_status[slug]
        if repo_response.status == 404:
            resolutions.append(
                Resolution(
                    slug,
                    ref,
                    "inconclusive",
                    None,
                    f"repository absent or inaccessible; {repo_response.detail}",
                    locations,
                )
            )
            continue
        if repo_response.status != 200:
            resolutions.append(
                Resolution(slug, ref, "inconclusive", None, repo_response.detail, locations)
            )
            continue

        response = client.get(_reference_api_path(slug, ref))
        if response.status == 200:
            resolved_sha, detail = _resolved_sha(slug, ref, response, client)
            status = "resolved" if resolved_sha is not None else "inconclusive"
        elif response.status == 404:
            status = "missing_ref"
            resolved_sha = None
            detail = response.detail
        else:
            status = "inconclusive"
            resolved_sha = None
            detail = response.detail
        resolutions.append(Resolution(slug, ref, status, resolved_sha, detail, locations))
    return resolutions


def overall_outcome(references: list[ActionReference], resolutions: list[Resolution]) -> str:
    if not references:
        return "missing"
    if any(item.status == "missing_ref" for item in resolutions):
        return "missing"
    if any(item.status == "inconclusive" for item in resolutions):
        return "inconclusive"
    return "resolved"


def _write_report(
    path: Path, references: list[ActionReference], resolutions: list[Resolution]
) -> str:
    outcome = overall_outcome(references, resolutions)
    payload = {
        "schema_version": "1.0.0",
        "outcome": outcome,
        "reference_occurrence_count": len(references),
        "unique_reference_count": len(resolutions),
        "resolutions": [asdict(item) for item in resolutions],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return outcome


def _append_github_metadata(outcome: str, report_path: Path, resolutions: list[Resolution]) -> None:
    if output_path := os.environ.get("GITHUB_OUTPUT"):
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(f"outcome={outcome}\n")
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write("## GitHub Action reference resolution\n\n")
            summary.write(f"Outcome: **{outcome}**  \nReport: `{report_path}`\n\n")
            summary.write("| Action | Status | Locations |\n| --- | --- | --- |\n")
            for item in resolutions:
                summary.write(
                    f"| `{item.slug}@{item.ref}` | {item.status} | "
                    f"{', '.join(item.occurrences)} |\n"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflows-dir", type=Path, default=DEFAULT_WORKFLOWS_DIR)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    references = collect_references(args.workflows_dir.resolve())
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN is required for action-reference resolution.", file=sys.stderr)
        return EXIT_INCONCLUSIVE

    resolutions = resolve_references(references, GitHubApiClient(token))
    outcome = _write_report(args.report, references, resolutions)
    _append_github_metadata(outcome, args.report, resolutions)
    print(
        f"Action-reference resolution {outcome}: {len(references)} occurrences, "
        f"{len(resolutions)} unique references."
    )
    if outcome == "missing":
        return EXIT_MISSING
    if outcome == "inconclusive":
        return EXIT_INCONCLUSIVE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
