"""Reject absolute user-home paths in test sources (#254).

The tokenizer is the right altitude: Python already knows which spans are
string literals, so "inside a string / URL / call" needs no
reconstruction. A web URL is not a path; a ``file://`` URI is judged by
its path part. Fails closed - an empty scan or an unreadable ``.py``
source is a failure, never a skip (Gate Liveness Standard rule 3).
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
_SEG = r"[^\\/\s\"']+"
#: Every personal-home shape, searched ANYWHERE in a literal (a path
#: embedded in a JSON blob or a diagnostic message is the same leak):
#: drive-anchored Windows, UNC server shares, Windows file URIs
#: normalised to /C:/Users/..., POSIX user homes, and root homes. The
#: bare POSIX home form needs a segment AFTER the account name -
#: "/home/dashboard" is as likely a web route as a home - while the
#: drive, UNC and root forms are personal on their face.
PERSONAL_HOME = re.compile(
    rf"(?:[\\/]*[A-Za-z]:[\\/]+(?:Users|home)[\\/]+{_SEG}"
    rf"|[\\/]{{2}}{_SEG}[\\/]+(?:Users|home)[\\/]+{_SEG}"
    rf"|[\\/]+(?:Users|home)[\\/]+{_SEG}[\\/]+{_SEG}"
    rf"|[\\/]+root[\\/]+{_SEG})",
    re.IGNORECASE,
)
#: Web-URL spans are excluded wherever they sit inside a literal: a URL
#: containing /home/... is a route. file:// is NOT excluded - its path
#: part is a filesystem path.
_WEB_URL = re.compile(r"\b(?!file:)[A-Za-z][A-Za-z0-9+.-]*://[^\s\"']*", re.IGNORECASE)
_STRING_TOKENS = {tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}


def _findings(value: str) -> list[str]:
    """Every personal-home span in one literal, web URLs excluded."""

    value = _WEB_URL.sub(lambda match: " " * len(match.group(0)), unquote(value))
    return [match.group(0) for match in PERSONAL_HOME.finditer(value)]


def _string_values(source: Path) -> list[str]:
    with source.open("rb") as stream:
        tokens = tokenize.tokenize(stream.readline)
        return [token.string for token in tokens if token.type in _STRING_TOKENS]


def _literal(text: str) -> str:
    try:
        value = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return text  # f-strings and joined forms: judge the raw literal text
    return value if isinstance(value, str) else ""


def scan(tests_root: Path) -> tuple[dict[str, list[str]], int]:
    findings: dict[str, list[str]] = {}
    scanned = 0
    for path in sorted(tests_root.rglob("*.py")):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        scanned += 1
        key = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
        try:
            values = _string_values(path)
        except (SyntaxError, tokenize.TokenError, UnicodeDecodeError, LookupError) as error:
            findings[key] = [f"unscannable python source: {error}"]
            continue
        hits = [hit for value in values for hit in _findings(_literal(value))]
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
