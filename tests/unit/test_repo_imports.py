from __future__ import annotations

import re
import sys
import tokenize
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
    r"(?:\b(?:route|endpoint)(?:_path)?\s*=\s*"
    r"|@\w+(?:\.\w+)*\.(?:get|head|post|put|patch|delete|options|route|api_route|websocket)"
    r"\s*\(\s*(?:path\s*=\s*)?"
    r"|\b(?:[a-z_]\w*_client|client|requests?|httpx)(?:\.\w+)*"
    r"\.(?:get|head|post|put|patch|delete|options|websocket_connect)"
    r"\s*\(\s*(?:url\s*=\s*)?)(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:[a-z_]\w*_client|client|requests?|httpx)(?:\.\w+)*"
    r"\.(?:get|head|post|put|patch|delete|options|websocket_connect)"
    r"\s*\((?:[^()\r\n]|\([^()\r\n]*\))*\burl\s*=\s*"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b\w+(?:\.\w+)*\.(?:add_api_route|add_route|add_websocket_route)"
    r"\s*\(\s*(?:path\s*=\s*)?(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b\w+(?:\.\w+)*\.(?:add_api_route|add_route|add_websocket_route)"
    r"\s*\((?:[^()\r\n]|\([^()\r\n]*\))*\bpath\s*=\s*"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:httpx\.)?Request\s*\(\s*[\"']"
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)[\"']\s*,\s*(?:url\s*=\s*)?"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:httpx\.)?Request\s*\(\s*method\s*=\s*[\"']"
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)[\"']\s*,\s*url\s*=\s*"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$",
    re.IGNORECASE,
)
REQUEST_SCOPE_ROUTE_PREFIX = re.compile(
    r"\bRequest\s*\([^)]*[\"']path[\"']\s*:\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
)
QUOTED_WEB_URL = re.compile(
    r"(?i:(?<=[\"'])(?:https?://|(?<![:/])//)"
    r"(?:[a-z0-9]|\[[0-9a-f:.]+\])[^\s\"']*)"
)
UNQUOTED_WEB_URL = re.compile(
    r"(?i:https?://(?:[a-z0-9]|\[[0-9a-f:.]+\])[^\s\"';,)\]}]*"
    r"|(?<![:/])//(?:[a-z0-9]|\[[0-9a-f:.]+\])[^\s\"';,)\]}]*)"
)


def _absolute_user_home_references(text: str) -> list[str]:
    references: list[str] = []
    url_spans = [
        url.span()
        for pattern in (QUOTED_WEB_URL, UNQUOTED_WEB_URL)
        for url in pattern.finditer(text)
    ]
    for match in ABSOLUTE_USER_HOME.finditer(text):
        preceding_text = text[: match.start()]
        inside_url = any(start <= match.start() < end for start, end in url_spans)
        request_scope_route = REQUEST_SCOPE_ROUTE_PREFIX.search(preceding_text)
        if (
            inside_url
            or HTTP_ROUTE_PREFIX.search(preceding_text)
            or ROUTE_LITERAL_PREFIX.search(preceding_text)
            or request_scope_route
        ):
            continue
        references.append(match.group(0))
    return references


def _read_scannable_test_text(path: Path) -> str | None:
    if path.suffix == ".py":
        with tokenize.open(path) as source:
            return source.read()
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


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
            "https://[2001:db8::1]:8443/home/dashboard/stats",
            'url = "https://example.test/api;v=1/home/dashboard/stats"',
            "//example.test/home/dashboard/stats",
            'route = "/home/dashboard/stats"',
            '@router.get("/home/dashboard/stats")',
            '@app.api_route("/home/dashboard/stats", methods=["GET"])',
            '@app.api_route(path="/home/dashboard/stats", methods=["GET"])',
            'client.get("/home/dashboard/stats")',
            'client.get(url="/home/dashboard/stats")',
            'client.get(headers=HEADERS, url="/home/dashboard/stats")',
            'client.get(headers=build_headers(), url="/home/dashboard/stats")',
            'client.get(f"/home/dashboard/{section}")',
            'client.get(r"/home/dashboard/stats")',
            'response_client.get("/home/dashboard/stats")',
            'client.websocket_connect("/home/dashboard/stats")',
            'httpx.Request("GET", "/home/dashboard/stats")',
            'Request({"type": "http", "path": "/home/dashboard/stats"})',
            'app.add_api_route("/home/dashboard/stats", handler)',
            'app.add_api_route(path="/home/dashboard/stats", endpoint=handler)',
            'app.add_api_route(endpoint=handler, path="/home/dashboard/stats")',
            'app.add_route("/home/dashboard/stats", handler)',
            'router.add_websocket_route("/home/dashboard/stats", handler)',
        ]
    )

    assert _absolute_user_home_references(routes) == []


def test_absolute_user_home_guard_does_not_let_an_adjacent_url_hide_a_path() -> None:
    linux = "/" + "/".join(["home", "alice", "project"])
    payload = f'{{"url":"https://example.test/api","path":"{linux}"}}'

    assert _absolute_user_home_references(payload) == ["/" + "/".join(["home", "alice"])]

    delimited = f"entry=https://example.test/api;{linux}"
    assert _absolute_user_home_references(delimited) == ["/" + "/".join(["home", "alice"])]

    path_assignment = f'path = "{linux}"'
    assert _absolute_user_home_references(path_assignment) == ["/" + "/".join(["home", "alice"])]

    after_closed_call = f'client.get("/api"); url="{linux}"'
    assert _absolute_user_home_references(after_closed_call) == ["/" + "/".join(["home", "alice"])]

    data_decorator = f'@data_file("{linux}/input.json")'
    assert _absolute_user_home_references(data_decorator) == ["/" + "/".join(["home", "alice"])]


def test_absolute_user_home_guard_detects_file_uris() -> None:
    linux_uri = "file://" + "/" + "/".join(["home", "alice", "project"])
    windows_uri = "file://" + "/" + "/".join(["C:", "Users", "alice", "project"])

    assert _absolute_user_home_references(f"{linux_uri} {windows_uri}") == [
        "/" + "/".join(["home", "alice"]),
        "/".join(["C:", "Users", "alice"]),
    ]

    redundant_slashes = "//" + linux_uri.removeprefix("file://")
    assert _absolute_user_home_references(redundant_slashes) == ["/" + "/".join(["home", "alice"])]


def test_python_test_sources_use_their_declared_encoding(tmp_path: Path) -> None:
    linux = "/" + "/".join(["home", "alice", "project"])
    source = tmp_path / "test_latin1.py"
    source.write_bytes(f"# -*- coding: latin-1 -*-\nPATH = '{linux}/café'\n".encode("latin-1"))

    text = _read_scannable_test_text(source)

    assert text is not None
    assert _absolute_user_home_references(text) == ["/" + "/".join(["home", "alice"])]


def test_test_sources_do_not_disclose_absolute_user_home_paths() -> None:
    findings: dict[str, list[str]] = {}
    for path in sorted(TESTS_ROOT.rglob("*")):
        if not path.is_file() or any(part in IGNORED_GENERATED_TEST_DIRS for part in path.parts):
            continue
        text = _read_scannable_test_text(path)
        if text is None:
            continue
        references = _absolute_user_home_references(text)
        if references:
            findings[path.relative_to(ROOT).as_posix()] = references

    assert findings == {}, f"Test sources contain absolute user-home paths: {findings}"
