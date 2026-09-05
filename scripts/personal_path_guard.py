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


def _findings(text: str) -> list[str]:
    """Every personal-home span in one text, exclusions applied."""

    text = _WEB_URL.sub(lambda match: " " * len(match.group(0)), unquote(text))
    return [
        match.group(0)
        for match in PERSONAL_HOME.finditer(text)
        if _account(match) not in SHARED_PROFILES
        and not _ROUTE_PREFIX.search(text[: match.start()])
    ]


def _literal(token_text: str) -> str:
    try:
        value = ast.literal_eval(token_text)
    except (SyntaxError, ValueError):
        return token_text  # f-strings and joined forms: judge the raw literal
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")  # b"/home/..." is a path too
    return value if isinstance(value, str) else ""


def _python_text(source: Path) -> str:
    with source.open("rb") as stream:
        tokens = tokenize.tokenize(stream.readline)
        literals = [token.string for token in tokens if token.type in _STRING_TOKENS]
    return "\n".join(_literal(literal) for literal in literals)


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
            text = _python_text(path) if path.suffix == ".py" else _fixture_text(path)
        except (SyntaxError, tokenize.TokenError, UnicodeDecodeError, LookupError, OSError) as err:
            findings[key] = [f"unscannable source: {err}"]
            continue
        if hits := _findings(text):
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
