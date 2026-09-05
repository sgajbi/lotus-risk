"""The tokenize-altitude personal-path guard (#254) rejects home paths,
accepts URLs, and fails closed on empty or unscannable input.

Fixture sources are written to ``tmp_path`` with the forbidden values
assembled from parts, so this test file itself carries no matching
string literal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import personal_path_guard as guard

pytestmark = pytest.mark.governance

_SEP = "/"
_WIN_SEP = chr(92)


def _posix_home(*segments: str) -> str:
    return _SEP + _SEP.join(("Users",) + segments)


def _windows_home(*segments: str) -> str:
    """Assembled from parts so this file carries no literal the guard
    forbids - the reason the per-file FLY002 ignore is gone (#254 S4)."""

    return "C:" + _WIN_SEP + _WIN_SEP.join(("Users",) + segments)


def _write(tmp_path: Path, name: str, value: str) -> None:
    (tmp_path / name).write_text(f"PATH = {value!r}\n", encoding="utf-8")


@pytest.mark.parametrize(
    "value",
    [
        _posix_home("alice", "project"),
        _SEP + _SEP.join(["home", "alice", "project"]),
        _windows_home("alice", "project"),
        "file://" + _posix_home("alice", "project"),
        # The shapes the replaced guard caught and a start-anchored
        # matcher would lose: a path EMBEDDED in a larger literal, a root
        # home, a UNC server share, and the standard Windows file URI
        # whose path part normalises to /C:/Users/...
        '{"path":"' + _posix_home("alice", "project") + '"}',
        "snapshot written to " + _SEP + _SEP.join(["home", "alice", "out.json"]),
        _SEP + _SEP.join(["root", "project"]),
        _WIN_SEP * 2 + _WIN_SEP.join(["server", "Users", "alice", "project"]),
        "file:///C:" + _posix_home("alice", "project"),
    ],
)
def test_the_guard_rejects_absolute_user_home_paths(tmp_path: Path, value: str) -> None:
    _write(tmp_path, "test_leak.py", value)

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert list(findings.values()) != []


@pytest.mark.parametrize(
    "value",
    [
        "https://example.test" + _SEP + _SEP.join(["home", "alice", "stats"]),
        _SEP + _SEP.join(["home", "dashboard"]),  # a route, not a home
        _SEP + _SEP.join(["srv", "data", "reports"]),
        # A URL span inside a larger literal is still excluded...
        "see https://example.test" + _SEP + _SEP.join(["home", "a", "b"]) + " for detail",
    ],
)
def test_the_guard_accepts_urls_routes_and_service_paths(tmp_path: Path, value: str) -> None:
    _write(tmp_path, "test_clean.py", value)

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert findings == {}


def test_fstring_literal_text_is_still_judged(tmp_path: Path) -> None:
    leak = _posix_home("alice", "project")
    (tmp_path / "test_fstring.py").write_text(
        "VALUE = f" + repr(leak + "{suffix}") + "\n", encoding="utf-8"
    )

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert list(findings.values()) != []


def test_an_empty_scan_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import sys

    argv = sys.argv
    sys.argv = ["personal_path_guard.py", str(tmp_path)]
    try:
        exit_code = guard.main()
    finally:
        sys.argv = argv

    assert exit_code == 1
    assert "inspected nothing" in capsys.readouterr().out


def test_an_unscannable_python_source_is_itself_a_finding(tmp_path: Path) -> None:
    # A .py the guard cannot read proves nothing about its contents, so it
    # is reported rather than skipped: the scan never passes by looking away.
    (tmp_path / "test_broken.py").write_text('PATH = "unterminated\n', encoding="utf-8")

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert any("unscannable python source" in hit for hits in findings.values() for hit in hits)


def test_the_real_tests_tree_is_scanned_and_clean() -> None:
    findings, scanned = guard.scan(guard.ROOT / "tests")

    assert scanned > 0, "the guard inspected nothing; that is a failure, not a pass"
    assert findings == {}, f"Test sources contain absolute user-home paths: {findings}"


def test_a_url_span_does_not_hide_a_real_path_beside_it(tmp_path: Path) -> None:
    """...but a URL cannot shelter a genuine path sharing the literal -
    the exclusion is per SPAN, not per literal."""

    leak = _SEP + _SEP.join(["home", "alice", "project"])
    _write(
        tmp_path,
        "test_mixed.py",
        "see https://example.test" + _SEP + _SEP.join(["home", "a", "b"]) + " then " + leak,
    )

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert [hit for hits in findings.values() for hit in hits] == [leak]
