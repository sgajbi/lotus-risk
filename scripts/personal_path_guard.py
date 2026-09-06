"""Reject absolute user-home paths in test sources (#254).

The tokenizer is the right altitude for Python: it already knows which
spans are string literals, so "inside a string" needs no reconstruction.
Non-Python fixtures (JSON, text, snapshots) are scanned as text, because
a home path leaks the same way from either. A web URL is not a path; a
``file://`` URI is judged by its path part; shared profiles (Public,
Shared, Default) are locations, not personal disclosures; and an HTTP
method prefix makes the token a route. Fails closed - an empty scan or
an unreadable source is a failure, never a skip (Gate Liveness Standard
rule 3).
"""

from __future__ import annotations

import ast
import re
import sys
import tokenize
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {"__pycache__", ".pytest_cache"}
#: Account names that name a shared location rather than a person; the
#: replaced guard exempted these and cross-platform fixtures rely on them.
SHARED_PROFILES = {"public", "shared", "default", "all users", "defaultaccount"}
_SEG = r"[^\\/\s\"']+"
#: Every personal-home shape, searched ANYWHERE in the text (a path
#: embedded in a JSON blob or a diagnostic message is the same leak):
#: drive-anchored Windows, UNC server shares, Windows file URIs
#: normalised to /C:/Users/..., POSIX user homes, and root homes. The
#: bare POSIX home form needs a segment AFTER the account name -
#: "/home/dashboard" is as likely a web route as a home - while the
#: drive, UNC and root forms are personal on their face.
PERSONAL_HOME = re.compile(
    rf"(?:[\\/]*[A-Za-z]:[\\/]+(?:Users|home)[\\/]+(?P<drive_account>{_SEG})"
    rf"|[\\/]{{2}}{_SEG}[\\/]+(?:Users|home)[\\/]+(?P<unc_account>{_SEG})"
    rf"|[\\/]+(?:Users|home)[\\/]+(?P<posix_account>{_SEG})[\\/]+{_SEG}"
    rf"|[\\/]+root[\\/]+{_SEG})",
    re.IGNORECASE,
)
#: An exact POSIX home with no child path ("/home/alice"). Alone it is
#: ambiguous - "/home/dashboard" is as likely a route - so it is a finding
#: only where the literal sits in filesystem context, which the AST answers
#: for Python sources.
EXACT_POSIX_HOME = re.compile(rf"^[\\/]+(?:Users|home)[\\/]+(?P<exact_account>{_SEG})[\\/]*$")
#: Web-URL spans are excluded wherever they sit inside the text: a URL
#: containing /home/... is a route. The span stops at characters that
#: cannot continue a URL, so a path after a delimiter is not swallowed.
#: file:// is NOT excluded - its path part is a filesystem path.
_WEB_URL = re.compile(r"\b(?!file:)[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>;,)\]}]*", re.IGNORECASE)
#: An HTTP method immediately before the token makes it a route.
_ROUTE_PREFIX = re.compile(
    r"(?:GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS|TRACE|CONNECT)\s+$", re.IGNORECASE
)
_STRING_TOKENS = {tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}


def _account(match: re.Match[str]) -> str:
    groups = match.groupdict()
    for name in ("drive_account", "unc_account", "posix_account"):
        if groups.get(name):
            return str(groups[name]).casefold()
    return ""


def _findings(text: str, *, context: str = "unknown") -> list[str]:
    """Every personal-home span in one literal, context and exclusions applied.

    ``context`` is what the literal is USED as, which the AST supplies for
    Python sources: a string handed to a route or HTTP-client call is a
    route however home-shaped it looks, and a string handed to a filesystem
    call is a path even when it names a bare home with no child.
    """

    if context == "route":
        return []
    text = _WEB_URL.sub(lambda match: " " * len(match.group(0)), unquote(text))
    hits = [
        match.group(0)
        for match in PERSONAL_HOME.finditer(text)
        if _account(match) not in SHARED_PROFILES
        and not _ROUTE_PREFIX.search(text[: match.start()])
    ]
    if hits or context != "filesystem":
        return hits
    exact = EXACT_POSIX_HOME.match(text)
    if exact and exact.group("exact_account").casefold() not in SHARED_PROFILES:
        return [exact.group(0)]
    return []


def _literal(token_text: str) -> str:
    try:
        value = ast.literal_eval(token_text)
    except (SyntaxError, ValueError):
        return token_text  # f-strings and joined forms: judge the raw literal
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")  # b"/home/..." is a path too
    return value if isinstance(value, str) else ""


#: Callables whose string arguments are ROUTES, not filesystem paths: HTTP
#: client verbs and the framework route decorators/registrars.
_ROUTE_CALLS = frozenset(
    {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "request",
        "route",
        "api_route",
        "websocket",
        "websocket_route",
        "url_for",
        "add_api_route",
        "add_route",
        "add_websocket_route",
        "include_router",
    }
)
#: Callables whose string arguments ARE filesystem paths, where even a bare
#: home with no child is a personal disclosure.
_FILESYSTEM_CALLS = frozenset(
    {
        "Path",
        "PurePath",
        "open",
        "chdir",
        "listdir",
        "mkdir",
        "makedirs",
        "remove",
        "unlink",
        "rmdir",
        "rmtree",
        "copy",
        "copy2",
        "copytree",
        "move",
        "exists",
        "isdir",
        "isfile",
        "stat",
        "glob",
        "iglob",
        "walk",
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "expanduser",
    }
)


def _call_name(node: ast.AST) -> str:
    func = getattr(node, "func", None)
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _literal_contexts(tree: ast.AST) -> dict[tuple[int, int], str]:
    """Where each string literal sits: route argument, filesystem argument,
    or neither. Python's own parser answers this - no lexer needed."""

    contexts: dict[tuple[int, int], str] = {}
    for node in ast.walk(tree):
        calls = [node] if isinstance(node, ast.Call) else []
        calls += [d for d in getattr(node, "decorator_list", []) if isinstance(d, ast.Call)]
        for call in calls:
            name = _call_name(call)
            if name in _ROUTE_CALLS:
                context = "route"
            elif name in _FILESYSTEM_CALLS:
                context = "filesystem"
            else:
                continue
            arguments = list(call.args) + [kw.value for kw in call.keywords]
            for argument in arguments:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    contexts[(argument.lineno, argument.col_offset)] = context
    return contexts


def _python_literals(source: Path) -> list[tuple[str, str]]:
    """Every string literal in a Python source with the context it is used in."""

    raw = source.read_bytes()
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        tree = None
    contexts = _literal_contexts(tree) if tree is not None else {}
    with source.open("rb") as stream:
        tokens = [
            token for token in tokenize.tokenize(stream.readline) if token.type in _STRING_TOKENS
        ]
    return [
        (_literal(token.string), contexts.get((token.start[0], token.start[1]), "unknown"))
        for token in tokens
    ]


def _fixture_text(source: Path) -> str:
    data = source.read_bytes()
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", data, 0, 1, "undecodable fixture")


def scan(tests_root: Path) -> tuple[dict[str, list[str]], int]:
    findings: dict[str, list[str]] = {}
    scanned = 0
    for path in sorted(tests_root.rglob("*")):
        if not path.is_file() or any(part in IGNORED_DIRS for part in path.parts):
            continue
        scanned += 1
        key = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
        try:
            if path.suffix == ".py":
                pairs = _python_literals(path)
            else:
                pairs = [(_fixture_text(path), "unknown")]
        except (SyntaxError, tokenize.TokenError, UnicodeDecodeError, LookupError, OSError) as err:
            findings[key] = [f"unscannable source: {err}"]
            continue
        hits = [hit for text, context in pairs for hit in _findings(text, context=context)]
        if hits:
            findings[key] = hits
    return findings, scanned


def main() -> int:
    tests_root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tests"
    findings, scanned = scan(tests_root)
    if scanned == 0:
        print(f"Personal-path gate failed: inspected nothing under {tests_root}.")
        return 1
    if findings:
        print("Personal-path gate failed: test sources state absolute user-home paths.")
        for key, hits in sorted(findings.items()):
            print(f"- {key}: {hits}")
        return 1
    print(f"Personal-path gate passed: {scanned} test source(s) scanned, no user-home paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
