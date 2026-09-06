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
        # Shared locations are not personal disclosures, and an HTTP
        # method prefix makes the token a route - both exempted by the
        # guard this replaced, both relied on by cross-platform fixtures.
        _windows_home("Public", "test-data"),
        _WIN_SEP * 2 + _WIN_SEP.join(["server", "Users", "Public", "test-data"]),
        _posix_home("Shared", "test-data"),
        "GET " + _SEP + _SEP.join(["home", "alice", "stats"]),
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
    assert any("unscannable source" in hit for hits in findings.values() for hit in hits)


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


def test_a_url_span_stops_at_a_delimiter_before_a_real_path(tmp_path: Path) -> None:
    """The excluded span is the URL itself: a path after a separator the
    URL cannot contain is still found."""

    leak = _SEP + _SEP.join(["home", "alice", "project"])
    _write(tmp_path, "test_delimited.py", "entry=https://example.test/api;" + leak)

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert [hit for hits in findings.values() for hit in hits] == [leak]


def test_a_bytes_literal_path_is_judged_by_its_decoded_value(tmp_path: Path) -> None:
    leak = _SEP + _SEP.join(["home", "alice", "project"])
    (tmp_path / "test_bytes.py").write_text(f"PATH = b{leak!r}\n", encoding="utf-8")

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert [hit for hits in findings.values() for hit in hits] == [leak]


def test_non_python_fixtures_are_scanned_too(tmp_path: Path) -> None:
    """A home path leaks the same way from a JSON or text fixture, and a
    non-UTF-8 fixture is still read rather than skipped."""

    leak = _SEP + _SEP.join(["home", "alice", "project"])
    (tmp_path / "fixture.json").write_text('{"path": "' + leak + '"}', encoding="utf-8")
    (tmp_path / "latin.txt").write_bytes((leak + "/caf\xe9").encode("latin-1"))
    (tmp_path / "test_clean.py").write_text("VALUE = 1\n", encoding="utf-8")

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 3
    assert sorted(Path(key).name for key in findings) == ["fixture.json", "latin.txt"]


def _write_source(tmp_path: Path, name: str, body: str) -> None:
    (tmp_path / name).write_text(body + "\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("test_client_route.py", 'client.get("@ROUTE@")'),
        ("test_client_kwarg_route.py", 'client.request("GET", url="@ROUTE@")'),
        ("test_decorator_route.py", '@router.get("@ROUTE@")\ndef handler(): ...'),
        ("test_app_decorator_route.py", '@app.post("@ROUTE@")\ndef handler(): ...'),
        ("test_add_route.py", 'app.add_api_route("@ROUTE@", handler)'),
    ],
)
def test_framework_route_literals_are_not_filesystem_paths(
    tmp_path: Path, name: str, body: str
) -> None:
    """A home-shaped string handed to a route call or route decorator is a
    ROUTE. The replaced guard exempted these through call context; the
    tokenize guard recovers the same context from Python's own parser rather
    than reconstructing it, and the decorator forms carry no HTTP-method
    prefix inside the literal, so the prefix rule cannot cover them."""

    _write_source(
        tmp_path, name, body.replace("@ROUTE@", _SEP + _SEP.join(["home", "dashboard", "stats"]))
    )

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert findings == {}


def test_an_exact_home_in_filesystem_context_is_rejected(tmp_path: Path) -> None:
    """ "/home/alice" with no child is the most direct disclosure there is.
    Bare, it is ambiguous - "/home/dashboard" is as likely a route - so the
    filesystem call is what settles it, exactly as the replaced guard's
    filesystem context did."""

    home = _SEP + _SEP.join(["home", "alice"])
    _write_source(tmp_path, "test_exact_home.py", f'from pathlib import Path\np = Path("{home}")')

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert [hit for hits in findings.values() for hit in hits] == [home]


@pytest.mark.parametrize(
    "call",
    ['open("@HOME@")', 'os.chdir("@HOME@")', 'shutil.rmtree("@HOME@")'],
)
def test_exact_homes_are_rejected_across_filesystem_calls(tmp_path: Path, call: str) -> None:
    home = _SEP + _SEP.join(["Users", "alice"])
    _write_source(tmp_path, "test_fs_call.py", call.replace("@HOME@", home))

    findings, _ = guard.scan(tmp_path)

    assert [hit for hits in findings.values() for hit in hits] == [home]


def test_a_bare_home_outside_any_call_stays_ambiguous(tmp_path: Path) -> None:
    """Context is what makes an exact home a finding: the same literal with
    no filesystem call around it could be a route, and the guard does not
    guess."""

    _write_source(tmp_path, "test_bare.py", f'VALUE = "{_SEP + _SEP.join(["home", "dashboard"])}"')

    findings, scanned = guard.scan(tmp_path)

    assert scanned == 1
    assert findings == {}


def test_a_shared_profile_stays_exempt_in_filesystem_context(tmp_path: Path) -> None:
    shared = _SEP + _SEP.join(["Users", "Shared"])
    _write_source(tmp_path, "test_shared.py", f'from pathlib import Path\np = Path("{shared}")')

    findings, _ = guard.scan(tmp_path)

    assert findings == {}


DOC_ROOTS = ("docs", "wiki")


def _documentation_sources() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    return sorted(path for directory in DOC_ROOTS for path in (root / directory).rglob("*.md"))


def test_documentation_states_no_personal_checkout_paths() -> None:
    """Docs must be readable by someone whose checkout lives elsewhere.

    A committed RFC map spelled a drive-rooted home directory belonging to one
    developer, which the guard could not see because it scans test sources.
    Canonical repository links work for a reader with no sibling checkout at
    all; a personal checkout path works only for its author.

    Uses the guard's own matcher so there is ONE definition of a personal path:
    a second regex here drifted from it immediately, matching inside web URLs
    the guard excludes and missing case variants and UNC shares it catches.
    """
    sources = _documentation_sources()
    assert sources, "no documentation sources found to scan"

    root = Path(__file__).resolve().parents[2]
    offenders = {
        path.relative_to(root).as_posix(): hits
        for path in sources
        if (hits := guard.findings_in_text(path.read_text(encoding="utf-8")))
    }

    assert not offenders, f"documentation names personal checkout paths: {offenders}"


def test_placeholder_accounts_are_not_disclosures_but_real_names_still_are() -> None:
    """A path shape shown with a placeholder names nobody.

    Documentation has to be able to write the Codex profile location without
    inventing a developer. Pinned in BOTH directions so the exemption cannot
    widen into accepting real accounts.
    """
    drive = "C:" + chr(92) + "Users" + chr(92)

    for placeholder in ("<user>", "${USER}", "%USERNAME%", "{user}"):
        assert guard.findings_in_text(drive + placeholder + chr(92) + "AppData") == [], (
            f"placeholder {placeholder} was reported as a personal path"
        )

    for account in ("jdoe", "Sandeep", "user1"):
        assert guard.findings_in_text(drive + account + chr(92) + "AppData"), (
            f"real account {account} was NOT reported as a personal path"
        )
