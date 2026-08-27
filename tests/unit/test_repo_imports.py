from __future__ import annotations

import re
import sys
import tokenize
from pathlib import Path

import pytest

from scripts._repo_imports import force_repo_src_first

pytestmark = pytest.mark.governance

ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = ROOT / "tests"
ABSOLUTE_USER_HOME = re.compile(
    r"(?:(?i:(?:[\\/]{2}[^:\\/\s\"']+[\\/]+|[a-z]:[\\/]+)"
    r"(?:users|documents and settings)[\\/]+(?:\.[\\/]+)*"
    r"(?!\.\.(?:[\\/]+|[\s\"']))[^\\/\s\"']+)"
    r"|/ho"
    r"me/+(?:\./+)*(?!\.\.(?:/+|[\s\"']))[^/\s\"']+(?=/+[^/\s\"']+)"
    r"|/Us"
    r"ers/+(?:\./+)*(?!\.\.(?:/+|[\s\"']))[^/\s\"']+(?=/+[^/\s\"']+)"
    r"|/r"
    r"oot(?=/+(?:\./+)*(?!\.\.(?:/+|[\s\"']))[^/\s\"']+))"
)
EXACT_POSIX_USER_HOME = re.compile(
    r"(?:/ho"
    r"me/+(?:\./+)*(?!\.\.(?:/+|[\s\"']))[^/\s\"']+"
    r"|/Us"
    r"ers/+(?:\./+)*(?!\.\.(?:/+|[\s\"']))[^/\s\"']+"
    r"|/r"
    r"oot)/*(?=$|[\s\"'])"
)
FILESYSTEM_LITERAL_PREFIX = re.compile(
    r"(?:\b(?:Path|PurePath|PurePosixPath)\s*\(\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"'][\\/]*"
    r"|\b(?:open|os\.path\.\w+|os\.(?:chdir|listdir|scandir|stat|remove|unlink|rmdir|mkdir|makedirs))"
    r"\s*\(\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"'][\\/]*"
    r"|file://)$"
)
IGNORED_GENERATED_TEST_DIRS = {"__pycache__", ".pytest_cache"}
HTTP_ROUTE_PREFIX = re.compile(
    r"(?:^|[\s\"'])(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE)\s+$", re.IGNORECASE
)
ROUTE_LITERAL_PREFIX = re.compile(
    r"(?:\b(?:route|endpoint)(?:_path)?\s*=\s*"
    r"|@\w+(?:\.\w+)*\.(?:get|head|post|put|patch|delete|options|trace|route|api_route|websocket)"
    r"\s*\(\s*(?:path\s*=\s*)?"
    r"|\b(?:[a-z_]\w*_client|client|requests?|httpx)(?:\.\w+)*"
    r"\.(?:get|head|post|put|patch|delete|options|websocket_connect)"
    r"\s*\(\s*(?:url\s*=\s*)?)(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:[a-z_]\w*_client|client|requests?|httpx)(?:\.\w+)*"
    r"\.(?:get|head|post|put|patch|delete|options|websocket_connect)"
    r"\s*\((?:[^()]|\([^()]*\))*\burl\s*=\s*"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:[a-z_]\w*_client|client)\.request\s*\(\s*[\"']"
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE)[\"']\s*,\s*(?:url\s*=\s*)?"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:[a-z_]\w*_client|client)\.request\s*\(\s*[\"']"
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE)[\"']\s*,"
    r"(?:[^()]|\([^()]*\))*\burl\s*=\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:[a-z_]\w*_client|client)\.request\s*\(\s*method\s*=\s*[\"']"
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE)[\"']\s*,\s*url\s*=\s*"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:[a-z_]\w*_client|client)\.request\s*\("
    r"(?:[^()]|\([^()]*\))*\bmethod\s*=\s*[\"']"
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE)[\"']"
    r"(?:[^()]|\([^()]*\))*\burl\s*=\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b\w+(?:\.\w+)*\.(?:add_api_route|add_route|add_websocket_route)"
    r"\s*\(\s*(?:path\s*=\s*)?(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b\w+(?:\.\w+)*\.(?:add_api_route|add_route|add_websocket_route)"
    r"\s*\((?:[^()]|\([^()]*\))*\bpath\s*=\s*"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:httpx\.)?Request\s*\(\s*[\"']"
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE)[\"']\s*,\s*(?:url\s*=\s*)?"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:httpx\.)?Request\s*\(\s*method\s*=\s*[\"']"
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE)[\"']\s*,\s*url\s*=\s*"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
    r"|\b(?:\w+\.)*(?:app|[a-z_]\w*_app)\.mount\s*\(\s*(?:path\s*=\s*)?"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$",
    re.IGNORECASE,
)
ROUTE_CONSTRUCTOR_PREFIX = re.compile(
    r"\b(?:Route|WebSocketRoute|Mount)\s*\(\s*(?:path\s*=\s*)?"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
)
ROUTER_PREFIX_ROUTE_PREFIX = re.compile(
    r"\b(?:APIRouter|\w+(?:\.\w+)*\.include_router)\s*\("
    r"(?:[^()]|\([^()]*\))*\bprefix\s*=\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
)
ASGI_SCOPE_ROUTE_PREFIX = re.compile(
    r"\b(?:scope|request_scope)\s*=\s*"
    r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*[\"']path[\"']\s*:\s*"
    r"(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
)
WEB_URL_START = re.compile(
    r"(?i:https?://(?:[a-z0-9]|\[[0-9a-f:.]+\])"
    r"|(?<![:/])//(?:[a-z0-9]|\[[0-9a-f:.]+\]))"
)
INLINE_TEST_CLIENT_ROUTE_SUFFIX = re.compile(
    r"\)\.(?:get|head|post|put|patch|delete|options|websocket_connect)"
    r"\s*\(\s*(?:url\s*=\s*)?(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$"
)


def _balanced_parentheses(text: str) -> bool:
    depth = 0
    quote = ""
    escaped = False
    for character in text:
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not quote


def _has_inline_http_client_route_context(preceding_text: str) -> bool:
    suffix = INLINE_TEST_CLIENT_ROUTE_SUFFIX.search(preceding_text)
    if suffix is None:
        return False
    receiver_candidates = [
        (preceding_text.rfind(constructor, 0, suffix.start()), constructor)
        for constructor in ("TestClient", "httpx.Client", "httpx.AsyncClient")
    ]
    receiver_start, constructor = max(receiver_candidates)
    if receiver_start < 0:
        return False
    receiver = preceding_text[receiver_start + len(constructor) : suffix.start() + 1]
    return receiver.startswith("(") and _balanced_parentheses(receiver)


def _has_inline_http_client_receiver(text: str, call_opening: int, method: str) -> bool:
    method_suffix = re.search(rf"\.{re.escape(method)}\s*$", text[:call_opening])
    if method_suffix is None:
        return False
    receiver_end = method_suffix.start()
    pairs = set(_parenthesis_pairs(text))
    for constructor in ("TestClient", "httpx.Client", "httpx.AsyncClient"):
        constructor_start = text.rfind(constructor, 0, receiver_end)
        constructor_opening = constructor_start + len(constructor)
        if constructor_start >= 0 and (constructor_opening, receiver_end - 1) in pairs:
            return True
    return False


def _active_quote_before(text: str, end: int) -> str:
    quote = ""
    escaped = False
    comment = False
    index = 0
    while index < end:
        character = text[index]
        if comment:
            if character == "\n":
                comment = False
        elif escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif quote:
            if len(quote) == 3 and text.startswith(quote, index):
                quote = ""
                index += 2
            elif len(quote) == 1 and character == quote:
                quote = ""
        elif character in {'"', "'"}:
            quote = character * 3 if text.startswith(character * 3, index) else character
            if len(quote) == 3:
                index += 2
        elif character == "#":
            comment = True
        index += 1
    return quote


def _delimiter_pairs(text: str, opening: str, closing: str) -> list[tuple[int, int]]:
    stack: list[int] = []
    pairs: list[tuple[int, int]] = []
    quote = ""
    escaped = False
    comment = False
    index = 0
    while index < len(text):
        character = text[index]
        if comment:
            if character == "\n":
                comment = False
        elif escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif quote:
            if len(quote) == 3 and text.startswith(quote, index):
                quote = ""
                index += 2
            elif len(quote) == 1 and character == quote:
                quote = ""
        elif character in {'"', "'"}:
            quote = character * 3 if text.startswith(character * 3, index) else character
            if len(quote) == 3:
                index += 2
        elif character == "#":
            comment = True
        elif character == opening:
            stack.append(index)
        elif character == closing and stack:
            pairs.append((stack.pop(), index))
        index += 1
    return pairs


def _parenthesis_pairs(text: str) -> list[tuple[int, int]]:
    return _delimiter_pairs(text, "(", ")")


def _brace_pairs(text: str) -> list[tuple[int, int]]:
    return _delimiter_pairs(text, "{", "}")


def _has_balanced_named_route_call_context(text: str, position: int) -> bool:
    named_value = re.search(
        r"\b(?P<name>url|path|prefix)\s*=\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$",
        text[:position],
    )
    if named_value is None:
        return False

    containing_calls = [pair for pair in _parenthesis_pairs(text) if pair[0] < position < pair[1]]
    if not containing_calls:
        return False
    opening, closing = max(containing_calls, key=lambda pair: pair[0])
    callee = re.search(r"(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*$", text[:opening])
    if callee is None:
        return False

    qualified_name = callee.group("name")
    receiver, _, method = qualified_name.rpartition(".")
    method = method.lower()
    receiver_leaf = receiver.rpartition(".")[2].lower()
    argument_text = text[opening + 1 : closing]
    client_receiver = receiver_leaf == "client" or receiver_leaf.endswith("_client")
    route_methods = {
        "get",
        "head",
        "post",
        "put",
        "patch",
        "delete",
        "options",
        "trace",
        "websocket_connect",
    }

    callee_leaf = qualified_name.rpartition(".")[2].lower()
    if named_value.group("name").lower() == "prefix":
        return callee_leaf == "apirouter" or method == "include_router"

    if named_value.group("name").lower() == "url":
        if method in route_methods and (
            client_receiver
            or receiver_leaf in {"requests", "httpx"}
            or _has_inline_http_client_receiver(text, opening, method)
        ):
            return True
        if method == "request" and (client_receiver or receiver_leaf in {"", "httpx"}):
            http_method = r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE)"
            return bool(
                re.search(rf"^\s*[\"']{http_method}[\"']", argument_text, re.IGNORECASE)
                or re.search(
                    rf"\bmethod\s*=\s*[\"']{http_method}[\"']",
                    argument_text,
                    re.IGNORECASE,
                )
            )
        return False

    if callee_leaf in {"route", "websocketroute"}:
        return True
    if callee_leaf == "mount" and (
        qualified_name == "Mount" or qualified_name.lower() == "starlette.routing.mount"
    ):
        return True
    if method in route_methods | {"api_route", "route", "websocket"}:
        line_prefix = text[text.rfind("\n", 0, callee.start()) + 1 : callee.start()]
        return "@" in line_prefix
    if method == "mount":
        return receiver_leaf == "app" or receiver_leaf.endswith("_app")
    return method in {
        "add_api_route",
        "add_route",
        "add_websocket_route",
    }


def _has_balanced_request_scope_context(text: str, position: int) -> bool:
    if not re.search(
        r"[\"']path[\"']\s*:\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$",
        text[:position],
    ):
        return False
    containing_calls = [pair for pair in _parenthesis_pairs(text) if pair[0] < position < pair[1]]
    if not containing_calls:
        return False
    opening, _ = max(containing_calls, key=lambda pair: pair[0])
    callee = re.search(r"(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*$", text[:opening])
    if callee is None or callee.group("name") not in {
        "Request",
        "fastapi.Request",
        "starlette.requests.Request",
    }:
        return False
    containing_mappings = [pair for pair in _brace_pairs(text) if pair[0] < position < pair[1]]
    if not containing_mappings:
        return False
    mapping_opening, _ = max(containing_mappings, key=lambda pair: pair[0])
    return not text[opening + 1 : mapping_opening].strip()


def _has_balanced_asgi_scope_context(text: str, position: int) -> bool:
    if not re.search(
        r"[\"']path[\"']\s*:\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$",
        text[:position],
    ):
        return False
    containing_mappings = [pair for pair in _brace_pairs(text) if pair[0] < position < pair[1]]
    if not containing_mappings:
        return False
    opening, _ = max(containing_mappings, key=lambda pair: pair[0])
    return bool(
        re.search(
            r"\b(?:scope|request_scope)\s*(?::[^;\n=]+)?=\s*$",
            text[:opening],
        )
    )


def _has_balanced_filesystem_call_context(text: str, position: int) -> bool:
    if not re.search(
        r"\b(?:file|filename|name|path)\s*=\s*(?i:(?:r[fb]?|[fb]r?|u)?)[\"']$",
        text[:position],
    ):
        return False
    containing_calls = [pair for pair in _parenthesis_pairs(text) if pair[0] < position < pair[1]]
    if not containing_calls:
        return False
    opening, _ = max(containing_calls, key=lambda pair: pair[0])
    callee = re.search(r"(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*$", text[:opening])
    if callee is None:
        return False
    qualified_name = callee.group("name")
    filesystem_calls = {
        "open",
        "io.open",
        "os.chdir",
        "os.listdir",
        "os.makedirs",
        "os.mkdir",
        "os.remove",
        "os.rmdir",
        "os.scandir",
        "os.stat",
        "os.unlink",
    }
    return qualified_name in filesystem_calls or qualified_name.startswith("os.path.")


def _web_url_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in WEB_URL_START.finditer(text):
        quote = _active_quote_before(text, match.start())
        end = match.end()
        while end < len(text):
            if quote and text.startswith(quote, end):
                break
            character = text[end]
            if character.isspace() or character == "\\":
                break
            if not quote and character in {'"', "'", ";", ",", ")", "]", "}"}:
                break
            end += 1
        spans.append((match.start(), end))
    return spans


def _absolute_user_home_references(text: str) -> list[str]:
    references: list[str] = []
    url_spans = _web_url_spans(text)
    candidates = [
        *((match, False) for match in ABSOLUTE_USER_HOME.finditer(text)),
        *((match, True) for match in EXACT_POSIX_USER_HOME.finditer(text)),
    ]
    for match, requires_filesystem_context in sorted(candidates, key=lambda item: item[0].start()):
        preceding_text = text[: match.start()]
        filesystem_context = bool(
            FILESYSTEM_LITERAL_PREFIX.search(preceding_text)
            or _has_balanced_filesystem_call_context(text, match.start())
        )
        if requires_filesystem_context and not filesystem_context:
            continue
        inside_url = not filesystem_context and any(
            start <= match.start() < end for start, end in url_spans
        )
        if (
            inside_url
            or HTTP_ROUTE_PREFIX.search(preceding_text)
            or ROUTE_LITERAL_PREFIX.search(preceding_text)
            or ROUTE_CONSTRUCTOR_PREFIX.search(preceding_text)
            or ROUTER_PREFIX_ROUTE_PREFIX.search(preceding_text)
            or ASGI_SCOPE_ROUTE_PREFIX.search(preceding_text)
            or _has_inline_http_client_route_context(preceding_text)
            or _has_balanced_named_route_call_context(text, match.start())
            or _has_balanced_request_scope_context(text, match.start())
            or _has_balanced_asgi_scope_context(text, match.start())
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
    unc_windows = "\\\\" + "\\".join(["server", "Users", "alice", "project"])
    linux = "/" + "/".join(["home", "example", "project"])
    repeated_linux = "/" + "/".join(["home", "example", "", "project"])
    repeated_home_root = "/" + "/".join(["home", "", "example", "project"])
    mac = "/" + "/".join(["Users", "example", "project"])
    root = "/" + "/".join(["root", "project"])
    references = _absolute_user_home_references(
        f"windows={windows} escaped={escaped_windows} unc={unc_windows} linux={linux} "
        f"repeated={repeated_linux} root_repeat={repeated_home_root} mac={mac} root={root}"
    )

    assert references == [
        "/".join(["D:", "Users", "example"]),
        "D:" + "\\\\" + "Users" + "\\\\" + "example",
        "\\\\" + "\\".join(["server", "Users", "alice"]),
        "/" + "/".join(["home", "example"]),
        "/" + "/".join(["home", "example"]),
        "/" + "/".join(["home", "", "example"]),
        "/" + "/".join(["Users", "example"]),
        "/" + "root",
    ]


def test_absolute_user_home_guard_detects_exact_posix_home_in_path_context() -> None:
    exact_home = "/" + "/".join(["home", "alice"])
    doubled_path = "//" + "/".join(["home", "alice", "project"])
    dot_segment_path = "/" + "/".join(["home", "..", "tmp", "data"])
    single_dot_path = "/" + "/".join(["home", ".", "alice", "project"])
    root_parent_path = "/" + "/".join(["root", "..", "tmp", "data"])
    windows_parent_path = "C:" + "\\" + "\\".join(["Users", "..", "Public", "data"])

    assert _absolute_user_home_references(f'Path("{exact_home}")') == [exact_home]
    assert _absolute_user_home_references(f'open("{exact_home}")') == [exact_home]
    assert _absolute_user_home_references(f'open(file="{exact_home}")') == [exact_home]
    assert _absolute_user_home_references(f'os.chdir("{exact_home}")') == [exact_home]
    assert _absolute_user_home_references(f'os.chdir(path="{exact_home}")') == [exact_home]
    assert _absolute_user_home_references(f'os.path.exists("{exact_home}")') == [exact_home]
    assert _absolute_user_home_references(f'Path("{exact_home}/")') == [f"{exact_home}/"]
    assert _absolute_user_home_references(f'Path("{exact_home}//")') == [f"{exact_home}//"]
    assert _absolute_user_home_references(f'Path("{doubled_path}")') == [exact_home]
    assert _absolute_user_home_references(f'open("{doubled_path}")') == [exact_home]
    assert _absolute_user_home_references(f'Path("{dot_segment_path}")') == []
    assert _absolute_user_home_references(f'Path("{single_dot_path}")') == [
        "/" + "/".join(["home", ".", "alice"])
    ]
    assert _absolute_user_home_references(f'Path("{root_parent_path}")') == []
    assert _absolute_user_home_references(f'Path(r"{windows_parent_path}")') == []


def test_absolute_user_home_guard_ignores_web_routes() -> None:
    nested_route = "/" + "/".join(["home", "dashboard", "stats"])
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
            '@app.trace("/home/dashboard/stats")',
            '@app.api_route("/home/dashboard/stats", methods=["GET"])',
            '@app.api_route(path="/home/dashboard/stats", methods=["GET"])',
            f'@app.api_route(methods=["GET"], path="{nested_route}")',
            f'@app.get(response_model=Payload, path="{nested_route}")',
            f'@app.trace(response_model=Payload, path="{nested_route}")',
            'client.get("/home/dashboard/stats")',
            'client.get(url="/home/dashboard/stats")',
            'client.get(headers=HEADERS, url="/home/dashboard/stats")',
            'client.get(headers=build_headers(), url="/home/dashboard/stats")',
            f'client.get(headers=build_headers(Settings()), url="{nested_route}")',
            'client.get(\n headers=HEADERS,\n url="/home/dashboard/stats")',
            'client.get(f"/home/dashboard/{section}")',
            'client.get(r"/home/dashboard/stats")',
            'response_client.get("/home/dashboard/stats")',
            'TestClient(app).get("/home/dashboard/stats")',
            'TestClient(create_app()).get("/home/dashboard/stats")',
            'TestClient(create_app(Settings())).get("/home/dashboard/stats")',
            f'httpx.Client().get("{nested_route}")',
            f'httpx.AsyncClient().get("{nested_route}")',
            f'httpx.Client().get(headers=HEADERS, url="{nested_route}")',
            'client.request("GET", "/home/dashboard/stats")',
            'client.request("GET", headers=HEADERS, url="/home/dashboard/stats")',
            'client.request(method="GET", url="/home/dashboard/stats")',
            'client.request(method="GET", headers=HEADERS, url="/home/dashboard/stats")',
            f'client.request(url="{nested_route}", method="GET")',
            'client.websocket_connect("/home/dashboard/stats")',
            'httpx.Request("GET", "/home/dashboard/stats")',
            f'httpx.Request(headers=HEADERS, method="GET", url="{nested_route}")',
            f'Request({{"type": "http", "path": "{nested_route}"}})',
            f'Request({{"client": ("127.0.0.1", 80), "path": "{nested_route}"}})',
            f'Request({{"state": build_state(Settings()), "path": "{nested_route}"}})',
            'Route("/home/dashboard/stats", endpoint)',
            f'Route(endpoint=handler, path="{nested_route}")',
            f'starlette.routing.Route(endpoint=handler, path="{nested_route}")',
            f'app.mount(path="{nested_route}", app=static_app)',
            f'Mount(app=static_app, path="{nested_route}")',
            'WebSocketRoute(path="/home/dashboard/stats", endpoint=handler)',
            f'WebSocketRoute(endpoint=handler, path="{nested_route}")',
            'scope = {"type": "http", "path": "/home/dashboard/stats"}',
            'scope = {"extensions": {"http.response.debug": {}}, "path": "/home/dashboard/stats"}',
            f'scope = {{"extensions": {{"a": {{"b": {{}}}}}}, "path": "{nested_route}"}}',
            f'scope: Scope = {{"type": "http", "path": "{nested_route}"}}',
            'app.add_api_route("/home/dashboard/stats", handler)',
            'app.add_api_route(path="/home/dashboard/stats", endpoint=handler)',
            'app.add_api_route(endpoint=handler, path="/home/dashboard/stats")',
            'app.add_route("/home/dashboard/stats", handler)',
            'router.add_websocket_route("/home/dashboard/stats", handler)',
            'APIRouter(prefix="/home/dashboard/stats")',
            f'APIRouter(dependencies=[Depends(build_dep(Settings()))], prefix="{nested_route}")',
            'app.include_router(router, prefix="/home/dashboard/stats")',
        ]
    )

    assert _absolute_user_home_references(routes) == []

    triple_quoted_source = '"""Mention a " quote."""\n' + (
        f'client.get(headers=build_headers(Settings()), url="{nested_route}")'
    )
    assert _absolute_user_home_references(triple_quoted_source) == []


def test_absolute_user_home_guard_does_not_let_an_adjacent_url_hide_a_path() -> None:
    linux = "/" + "/".join(["home", "alice", "project"])
    payload = f'{{"url":"https://example.test/api","path":"{linux}"}}'

    assert _absolute_user_home_references(payload) == ["/" + "/".join(["home", "alice"])]

    delimited = f"entry=https://example.test/api;{linux}"
    assert _absolute_user_home_references(delimited) == ["/" + "/".join(["home", "alice"])]

    escaped_newline = f'value = "https://example.test/api\\n{linux}"'
    assert _absolute_user_home_references(escaped_newline) == ["/" + "/".join(["home", "alice"])]

    prefixed_url = f'value = "prefix https://example.test/api\\n{linux}"'
    assert _absolute_user_home_references(prefixed_url) == ["/" + "/".join(["home", "alice"])]

    path_assignment = f'path = "{linux}"'
    assert _absolute_user_home_references(path_assignment) == ["/" + "/".join(["home", "alice"])]

    after_closed_call = f'client.get("/api"); url="{linux}"'
    assert _absolute_user_home_references(after_closed_call) == ["/" + "/".join(["home", "alice"])]

    data_decorator = f'@data_file("{linux}/input.json")'
    assert _absolute_user_home_references(data_decorator) == ["/" + "/".join(["home", "alice"])]

    unrelated_mount = f'volume.mount(source=device, path="{linux}")'
    assert _absolute_user_home_references(unrelated_mount) == ["/" + "/".join(["home", "alice"])]

    unrelated_annotated_mapping = f'scope: Scope; payload = {{"path": "{linux}"}}'
    assert _absolute_user_home_references(unrelated_annotated_mapping) == [
        "/" + "/".join(["home", "alice"])
    ]

    request_body_path = (
        f'httpx.Request("POST", "https://example.test/upload", json={{"path": "{linux}"}})'
    )
    assert _absolute_user_home_references(request_body_path) == ["/" + "/".join(["home", "alice"])]

    comment_apostrophe = "# don" + "'t\n" + f'values = ("https://example.test/api","{linux}")'
    assert _absolute_user_home_references(comment_apostrophe) == ["/" + "/".join(["home", "alice"])]

    triple_quoted_url = 'value = """https://example.test/api""";' + f'path="{linux}"'
    assert _absolute_user_home_references(triple_quoted_url) == ["/" + "/".join(["home", "alice"])]


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
