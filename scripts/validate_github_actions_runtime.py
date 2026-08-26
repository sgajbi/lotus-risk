"""Validate GitHub Actions runtime posture for governed workflow dependencies."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

ACTION_MINIMUM_MAJOR_BY_SLUG = {
    "actions/upload-artifact": 6,
    "actions/download-artifact": 7,
}

ACTION_RUNTIME_RATIONALE_BY_SLUG = {
    "actions/upload-artifact": "v6 is the first upload-artifact major using the Node 24 runtime.",
    "actions/download-artifact": "v7 is the first download-artifact major using the Node 24 runtime.",
}

ACTION_USE_PATTERN = re.compile(
    r"""
    \buses\s*:\s*
    (?P<quote>["']?)
    (?P<slug>actions/(?:upload|download)-artifact)
    @
    (?P<ref>[A-Za-z0-9_.-]+)
    (?P=quote)
    """,
    re.VERBOSE,
)


# Every `uses: owner/repo@ref` in a workflow. Unlike ACTION_USE_PATTERN above, which governs the
# Node runtime major of two specific artifact actions, this one exists to answer a cruder question:
# does the reference resolve at all.
ANY_ACTION_USE_PATTERN = re.compile(
    r"""
    \buses\s*:\s*
    (?P<quote>["']?)
    (?P<slug>[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*)
    @
    (?P<ref>[A-Za-z0-9_./-]+)
    (?P=quote)
    """,
    re.VERBOSE,
)

# A resolvable reference is a `v`-prefixed tag or a full commit SHA. Every action publisher this
# repository consumes tags with a `v`; `aquasecurity/trivy-action@0.32.0` did not exist and never
# had, and the release lane failed at `Set up job` before a single step ran - for seven weeks,
# invisibly, because the workflow had never been triggered. See issue #227.
RESOLVABLE_REF_PATTERN = re.compile(r"^(?:v\d+(?:[._-].*)?|[0-9a-f]{40})$")


@dataclass(frozen=True)
class WorkflowActionViolation:
    path: Path
    line_number: int
    slug: str
    ref: str
    minimum_major: int
    rationale: str

    def format(self, *, root: Path) -> str:
        try:
            display_path = self.path.relative_to(root)
        except ValueError:
            display_path = self.path
        if self.minimum_major == 0:
            return f"{display_path}:{self.line_number}: {self.slug}@{self.ref} {self.rationale}"
        return (
            f"{display_path}:{self.line_number}: {self.slug}@{self.ref} is below "
            f"the governed minimum major v{self.minimum_major}. {self.rationale}"
        )


def _extract_major(ref: str) -> int | None:
    match = re.fullmatch(r"v(?P<major>\d+)(?:\..*)?", ref)
    if match is None:
        return None
    return int(match.group("major"))


def _validate_reference_forms(path: Path) -> list[WorkflowActionViolation]:
    """Fail on an action reference that cannot resolve.

    This is deliberately an offline, syntactic check rather than a registry lookup: a gate that
    needs the network fails for reasons unrelated to the repository, and would not run at all in
    the pre-push validation where this belongs.
    """

    violations: list[WorkflowActionViolation] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = ANY_ACTION_USE_PATTERN.search(line)
        if match is None:
            continue
        ref = match.group("ref")
        if RESOLVABLE_REF_PATTERN.fullmatch(ref):
            continue
        violations.append(
            WorkflowActionViolation(
                path=path,
                line_number=line_number,
                slug=match.group("slug"),
                ref=ref,
                minimum_major=0,
                rationale=(
                    "An action reference must be a `v`-prefixed tag or a 40-character commit "
                    "SHA. A bare version like `0.32.0` does not resolve at all and the job fails "
                    "at `Set up job` before any step runs; a branch like `main` resolves but is "
                    "unpinned, so the action can change under the workflow with no commit."
                ),
            )
        )
    return violations


def validate_workflow_file(path: Path) -> list[WorkflowActionViolation]:
    violations = _validate_reference_forms(path)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = ACTION_USE_PATTERN.search(line)
        if match is None:
            continue
        slug = match.group("slug")
        ref = match.group("ref")
        minimum_major = ACTION_MINIMUM_MAJOR_BY_SLUG[slug]
        major = _extract_major(ref)
        if major is None or major < minimum_major:
            violations.append(
                WorkflowActionViolation(
                    path=path,
                    line_number=line_number,
                    slug=slug,
                    ref=ref,
                    minimum_major=minimum_major,
                    rationale=ACTION_RUNTIME_RATIONALE_BY_SLUG[slug],
                )
            )
    return violations


def validate_workflows(workflows_dir: Path) -> list[WorkflowActionViolation]:
    if not workflows_dir.exists():
        return [
            WorkflowActionViolation(
                path=workflows_dir,
                line_number=0,
                slug=".github/workflows",
                ref="missing",
                minimum_major=1,
                rationale="Expected a workflow directory to validate GitHub Actions runtime posture.",
            )
        ]

    violations: list[WorkflowActionViolation] = []
    for path in sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")]):
        violations.extend(validate_workflow_file(path))
    return violations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when governed GitHub artifact actions use stale Node runtime majors."
    )
    parser.add_argument(
        "--workflows-dir",
        type=Path,
        default=DEFAULT_WORKFLOWS_DIR,
        help="Directory containing GitHub Actions workflow YAML files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workflows_dir = args.workflows_dir.resolve()
    violations = validate_workflows(workflows_dir)
    if violations:
        print("GitHub Actions runtime gate failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation.format(root=REPO_ROOT)}", file=sys.stderr)
        return 1

    print("GitHub Actions runtime gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
