"""Quality evidence must come from the selected toolchain, not PATH fallback."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import generate_quality_baseline as baseline

pytestmark = pytest.mark.governance


def test_python_child_preserves_selected_interpreter_arguments_and_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("LOTUS_QUALITY_PROBE", "retained")
    command = [
        "python",
        "-c",
        (
            "import json,os,sys; print(json.dumps([sys.executable,sys.argv[1],"
            "os.environ['LOTUS_QUALITY_PROBE'],os.environ['PYTHONPATH']]))"
        ),
        "argument with spaces",
    ]
    original = command.copy()

    code, output = baseline._run(command)

    assert code == 0, output
    executable, argument, environment, pythonpath = json.loads(output)
    assert Path(executable).resolve() == Path(sys.executable).resolve()
    assert argument == "argument with spaces"
    assert environment == "retained"
    assert pythonpath.split(os.pathsep)[0] == str(baseline.SRC_DIR)
    assert command == original


def test_real_python_failure_is_retained_in_diagnostic_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    command = ["python", "-c", "import sys; print('owned failure'); sys.exit(7)"]

    assert baseline._run(command) == (7, "owned failure")
    assert baseline.command_status(command) == "reported exit 7\n\n```text\nowned failure\n```"


@pytest.mark.parametrize("executable", ["git", "python3", "python-tool", sys.executable])
def test_non_symbolic_python_commands_keep_their_exact_argv(
    executable: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded.append(command.copy())
        return subprocess.CompletedProcess(command, 9, "failure preserved\n")

    monkeypatch.setattr(subprocess, "run", run)
    command = [executable, "argument with spaces", "--flag=value"]
    assert baseline._run(command) == (9, "failure preserved")
    assert recorded == [command]


def test_missing_non_python_program_remains_an_explicit_failure() -> None:
    code, output = baseline._run(["lotus-quality-nonexistent-program-379"])
    assert code == 127
    assert output


def test_collection_and_every_diagnostic_use_selected_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded.append(command.copy())
        output = "2 tests collected" if "--collect-only" in command else "probe output"
        return subprocess.CompletedProcess(command, 0, output)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    count, output = baseline.collect_unit_test_count()
    baseline.write_diagnostics(output)

    assert count == "2"
    assert recorded[0] == [sys.executable, "-m", "pytest", "tests/unit", "--collect-only", "-q"]
    python_commands = [command for command in recorded if command[0] != "git"]
    assert len(python_commands) == 12  # collection plus all 11 diagnostic tools
    assert all(command[0] == sys.executable for command in python_commands)
    transcript = (tmp_path / "output/quality/baseline-command-transcript.md").read_text()
    assert f"- Python interpreter: `{sys.executable}`" in transcript
    assert f"- Python version: `{sys.version.split()[0]}`" in transcript
    assert "Diagnostic runner evidence only; PR/main gates own acceptance." in transcript


@pytest.mark.parametrize("code,output", [(5, "2 tests collected"), (0, "no count")])
def test_collection_does_not_promote_failed_or_unattributable_output(
    code: int, output: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(baseline, "_run", lambda _command: (code, output))
    with pytest.raises(RuntimeError, match=f"unit test collection failed \\(exit {code}\\)"):
        baseline.collect_unit_test_count()


@pytest.mark.parametrize(
    "output,expected",
    [
        (
            (
                "tests/unit/test_probe.py::test_refusal[5-2 tests collected]\n"
                "1639 tests collected in 0.87s"
            ),
            "1639",
        ),
        ("tests/unit/test_probe.py::test_refusal[5-2 tests collected]", "unknown"),
        ("1 test collected in 0.01s", "1"),
        ("2 tests collected\n3 tests collected in 0.1s", "3"),
    ],
)
def test_only_collection_summary_lines_can_measure_test_count(output: str, expected: str) -> None:
    assert baseline.collected_test_count(output) == expected
