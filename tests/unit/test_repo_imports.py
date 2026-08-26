from __future__ import annotations

import re
import sys
from pathlib import Path

from scripts._repo_imports import force_repo_src_first

import pytest

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = ROOT / "tests"
ABSOLUTE_USER_HOME = re.compile(
    r"(?:(?i:[a-z]:[\\/]+(?:users|documents and settings)[\\/]+[^\\/\s\"']+)"
    r"|/ho"
    r"me/[^/\s\"']+(?=/[^/\s\"']+)"
    r"|/Us"
    r"ers/[^/\s\"']+(?=/[^/\s\"']+)"
    r"|/r"
    r"oot(?=/[^/\s\"']+))"
)
IGNORED_GENERATED_TEST_DIRS = {"__pycache__", ".pytest_cache"}
HTTP_ROUTE_PREFIX = re.compile(
    r"(?:^|[\s\"'])(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)\s+$", re.IGNORECASE
)
ROUTE_LITERAL_PREFIX = re.compile(
    r"(?:\b(?:route|endpoint)(?:_path)?\s*=\s*|@\w+(?:\.\w+)*\s*\(\s*)[\"']$",
    re.IGNORECASE,
)
WEB_URL = re.compile(r"(?i:https?://[^\s\"';,)\]}]+|(?<![:/])//[^\s\"';,)\]}]+)")


def _absolute_user_home_references(text: str) -> list[str]:
    references: list[str] = []
    url_spans = [url.span() for url in WEB_URL.finditer(text)]
    for match in ABSOLUTE_USER_HOME.finditer(text):
        preceding_text = text[: match.start()]
        inside_url = any(start <= match.start() < end for start, end in url_spans)
        if (
            inside_url
            or HTTP_ROUTE_PREFIX.search(preceding_text)
            or ROUTE_LITERAL_PREFIX.search(preceding_text)
        ):
            continue
        references.append(match.group(0))
    return references


def test_force_repo_src_first_moves_repo_src_ahead_of_other_lotus_apps(
    tmp_path: Path,
) -> None:
    original_path = list(sys.path)
    repo_src = (ROOT / "src").resolve()
    other_repo_src = (tmp_path / "lotus-sibling" / "src").resolve()
    site_packages = (tmp_path / "python-runtime" / "site-packages").resolve()
    other_repo_src.mkdir(parents=True)
    site_packages.mkdir(parents=True)
    assert repo_src.is_dir(), "The repository src directory moved or is missing."

    try:
        sys.path[:] = [str(other_repo_src), str(repo_src), str(site_packages)]

        force_repo_src_first(ROOT)

        assert Path(sys.path[0]).resolve() == repo_src
        assert Path(sys.path[1]).resolve() == other_repo_src
        assert sys.path.count(str(repo_src)) == 1
    finally:
        sys.path[:] = original_path


def test_absolute_user_home_guard_detects_cross_platform_paths() -> None:
    windows = "/".join(["D:", "Users", "example", "project"])
    escaped_windows = "D:" + "\\\\" + "Users" + "\\\\" + "example" + "\\\\" + "project"
    linux = "/" + "/".join(["home", "example", "project"])
    mac = "/" + "/".join(["Users", "example", "project"])
    root = "/" + "/".join(["root", "project"])
    references = _absolute_user_home_references(
        f"windows={windows} escaped={escaped_windows} linux={linux} mac={mac} root={root}"
    )

    assert references == [
        "/".join(["D:", "Users", "example"]),
        "D:" + "\\\\" + "Users" + "\\\\" + "example",
        "/" + "/".join(["home", "example"]),
        "/" + "/".join(["Users", "example"]),
        "/" + "root",
    ]


def test_absolute_user_home_guard_ignores_web_routes() -> None:
    routes = " ".join(
        [
            "https://example.test/users/123",
            "GET /users/alice",
            "/home/dashboard",
            "GET /home/dashboard/stats",
            "https://example.test/root/project",
            "//example.test/home/dashboard/stats",
            'route = "/home/dashboard/stats"',
            '@router.get("/home/dashboard/stats")',
        ]
    )

    assert _absolute_user_home_references(routes) == []


def test_absolute_user_home_guard_does_not_let_an_adjacent_url_hide_a_path() -> None:
    linux = "/" + "/".join(["home", "alice", "project"])
    payload = f'{{"url":"https://example.test/api","path":"{linux}"}}'

    assert _absolute_user_home_references(payload) == ["/" + "/".join(["home", "alice"])]

    delimited = f"entry=https://example.test/api;{linux}"
    assert _absolute_user_home_references(delimited) == [
        "/" + "/".join(["home", "alice"])
    ]

    path_assignment = f'path = "{linux}"'
    assert _absolute_user_home_references(path_assignment) == [
        "/" + "/".join(["home", "alice"])
    ]


def test_absolute_user_home_guard_detects_file_uris() -> None:
    linux_uri = "file://" + "/" + "/".join(["home", "alice", "project"])
    windows_uri = "file://" + "/" + "/".join(["C:", "Users", "alice", "project"])

    assert _absolute_user_home_references(f"{linux_uri} {windows_uri}") == [
        "/" + "/".join(["home", "alice"]),
        "/".join(["C:", "Users", "alice"]),
    ]


def test_test_sources_do_not_disclose_absolute_user_home_paths() -> None:
    findings: dict[str, list[str]] = {}
    for path in sorted(TESTS_ROOT.rglob("*")):
        if not path.is_file() or any(part in IGNORED_GENERATED_TEST_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        references = _absolute_user_home_references(text)
        if references:
            findings[path.relative_to(ROOT).as_posix()] = references

    assert findings == {}, f"Test sources contain absolute user-home paths: {findings}"
