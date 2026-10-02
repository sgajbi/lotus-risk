"""Negative checks for the deployable image's package-manager boundary."""

from pathlib import Path

import pytest

from scripts.validate_image_supply_chain import (
    APPROVED_RUNTIME_BASE,
    RUNTIME_DEPENDENCY_GUARD,
    RUNTIME_ENSUREPIP_REMOVAL,
    RUNTIME_PIP_REMOVAL,
    validate_runtime_container_contract,
)

pytestmark = pytest.mark.governance


def test_runtime_container_contract_rejects_retained_package_manager(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        current.replace(f"{RUNTIME_PIP_REMOVAL}\n", ""),
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must remove pip after installation" in issues


def test_runtime_container_contract_rejects_missing_package_manager_guard(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        current.replace("forbidden=('pip','ensurepip',", "forbidden=("), encoding="utf-8"
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime dependency guard must reject pip and ensurepip" in issues


def test_runtime_container_contract_rejects_retained_ensurepip(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        "\n".join(line for line in current.splitlines() if "shutil.rmtree(path)" not in line),
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must remove bundled ensurepip" in issues


@pytest.mark.parametrize(
    "later_instruction",
    [
        "RUN python -m ensurepip --user",
        "  COPY --from=builder-output-validator /install /usr/local",
        "WORKDIR /opt/hidden",
    ],
)
def test_runtime_container_contract_rejects_package_restore_after_guard(
    tmp_path: Path, later_instruction: str
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(current + f"\n{later_instruction}\n", encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must retain approved terminal instructions" in issues


def test_runtime_container_contract_rejects_commented_removals_and_masked_guard(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    mutated = (
        current.replace(RUNTIME_PIP_REMOVAL, f"# {RUNTIME_PIP_REMOVAL}")
        .replace(RUNTIME_ENSUREPIP_REMOVAL, f"# {RUNTIME_ENSUREPIP_REMOVAL}")
        .replace(
            "else print('runtime dependency guard passed')\"",
            "else print('runtime dependency guard passed')\" || true",
        )
    )
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must remove pip after installation" in issues
    assert f"{dockerfile}: runtime image must remove bundled ensurepip" in issues
    assert f"{dockerfile}: runtime dependency guard must reject pip and ensurepip" in issues


def test_runtime_container_contract_does_not_credit_later_stage_removals(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    mutated = current.replace(
        RUNTIME_PIP_REMOVAL,
        f"FROM python:3.12-slim AS cleanup\n{RUNTIME_PIP_REMOVAL}",
    )
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must remove pip after installation" in issues
    assert f"{dockerfile}: runtime image must remove bundled ensurepip" in issues
    assert f"{dockerfile}: runtime dependency guard must reject pip and ensurepip" in issues


def test_runtime_container_contract_rejects_unvalidated_final_release_stage(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        current + "\nFROM python:3.12-slim AS release\n" + "RUN python -m ensurepip --upgrade\n",
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime stage must be the final Dockerfile stage" in issues


def test_runtime_container_contract_rejects_semantic_noop_removal_and_guard(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    mutated = current.replace("shutil.rmtree(path)", "False and shutil.rmtree(path)").replace(
        "present=[name for name in forbidden if "
        "importlib.machinery.PathFinder.find_spec(name, list(roots)) is not None]",
        "present=[]",
    )
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must remove bundled ensurepip" in issues
    assert f"{dockerfile}: runtime dependency guard must reject pip and ensurepip" in issues


def test_runtime_container_contract_rejects_guard_before_final_user(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    mutated = current.replace("USER lotus\n", "", 1).replace(
        "EXPOSE 8130", "USER lotus\nEXPOSE 8130", 1
    )
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime dependency guard must run as final lotus user" in issues


def test_runtime_container_contract_rejects_shell_override_of_removal_and_guard(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    mutated = (
        current.replace(
            RUNTIME_PIP_REMOVAL,
            f'SHELL ["/bin/true", "-c"]\n{RUNTIME_PIP_REMOVAL}',
        )
        .replace(
            "RUN apt-get update &&",
            'SHELL ["/bin/sh", "-c"]\nRUN apt-get update &&',
        )
        .replace(
            f"USER lotus\n{RUNTIME_DEPENDENCY_GUARD}",
            f'SHELL ["/bin/true", "-c"]\nUSER lotus\n{RUNTIME_DEPENDENCY_GUARD}',
        )
    )
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must not override the Dockerfile shell" in issues


def test_runtime_container_contract_rejects_mutating_healthcheck(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    healthcheck = next(line for line in current.splitlines() if line.startswith("HEALTHCHECK "))
    dockerfile.write_text(
        current.replace(healthcheck, healthcheck + " && cp -r /opt/hidden/pip /app/pip"),
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must retain approved terminal instructions" in issues


def test_runtime_container_contract_rejects_commands_hidden_in_continuations(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    mutated = Path("Dockerfile").read_text(encoding="utf-8")
    for marker in (
        RUNTIME_PIP_REMOVAL,
        RUNTIME_ENSUREPIP_REMOVAL,
        RUNTIME_DEPENDENCY_GUARD,
    ):
        line = next(line for line in mutated.splitlines() if line.startswith(marker))
        mutated = mutated.replace(line, f"RUN true {chr(92)}\n{line}", 1)
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must remove pip after installation" in issues
    assert f"{dockerfile}: runtime image must remove bundled ensurepip" in issues
    assert f"{dockerfile}: runtime dependency guard must reject pip and ensurepip" in issues


def test_runtime_container_contract_rejects_pre_guard_entrypoint(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    mutated = current.replace(
        RUNTIME_PIP_REMOVAL,
        'ENTRYPOINT ["/bin/sh", "-c", "cp -r /opt/pip /app/pip; exec "$@""]\n'
        f"{RUNTIME_PIP_REMOVAL}",
    )
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must not install an entrypoint" in issues


def test_runtime_container_contract_rejects_nondefault_escape_continuations(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    mutated = "# escape=`\n" + Path("Dockerfile").read_text(encoding="utf-8")
    for marker in (
        RUNTIME_PIP_REMOVAL,
        RUNTIME_ENSUREPIP_REMOVAL,
        RUNTIME_DEPENDENCY_GUARD,
    ):
        line = next(line for line in mutated.splitlines() if line.startswith(marker))
        mutated = mutated.replace(line, f"RUN true {chr(96)}\n{line}", 1)
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime image must use default Dockerfile escape" in issues


def test_runtime_container_contract_rejects_custom_syntax_frontend(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        "# syntax=attacker.example/dockerfile:latest\n"
        + Path("Dockerfile").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: image contract must not use a custom syntax frontend" in issues


def test_runtime_container_contract_rejects_commands_hidden_in_heredocs(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    for heredoc_start in (
        "RUN cat <<'#' > /dev/null",
        "RUN cat \\\n<<'#' > /dev/null",
        "RUN cat <\\\n<'#' > /dev/null",
        "RUN cat <\\\n# ignored continuation comment\n<'#' > /dev/null",
    ):
        mutated = Path("Dockerfile").read_text(encoding="utf-8")
        for marker in (
            RUNTIME_PIP_REMOVAL,
            RUNTIME_ENSUREPIP_REMOVAL,
            RUNTIME_DEPENDENCY_GUARD,
        ):
            line = next(line for line in mutated.splitlines() if line.startswith(marker))
            mutated = mutated.replace(line, f"{heredoc_start}\n{line}\n#", 1)
        dockerfile.write_text(mutated, encoding="utf-8")

        issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

        assert f"{dockerfile}: runtime image contract must not use Dockerfile heredocs" in issues


def test_runtime_container_contract_rejects_pre_guard_python_startup_hook(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    startup_hook = (
        "RUN cp -r /usr/local/lib/python3.12/site-packages/pip /opt/pip && "
        "printf 'import importlib.util,sys\\n' "
        "> /usr/local/lib/python3.12/site-packages/sitecustomize.py"
    )
    dockerfile.write_text(
        current.replace(
            RUNTIME_PIP_REMOVAL,
            f"{startup_hook}\n{RUNTIME_PIP_REMOVAL}",
        ),
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime stage must match approved instruction contract" in issues


def test_runtime_container_contract_rejects_inherited_shell_override(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        current.replace(
            f"FROM {APPROVED_RUNTIME_BASE} AS runtime",
            f"FROM {APPROVED_RUNTIME_BASE} AS shell-base\n"
            'SHELL ["/bin/true", "-c"]\n'
            "FROM shell-base AS runtime",
        ),
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: runtime stage must use approved base image directly" in issues


def test_runtime_container_contract_rejects_builder_package_stash(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    builder_install = (
        "RUN python -m pip install --upgrade pip && \\\n"
        "    python -m pip install --prefix=/install ."
    )
    hidden_pip = (
        "RUN mkdir -p /install/lib/python3.12/site-packages/hidden && \\\n"
        "    cp -r /usr/local/lib/python3.12/site-packages/pip "
        "/install/lib/python3.12/site-packages/hidden/pip && \\\n"
        "    printf '/usr/local/lib/python3.12/site-packages/hidden\\n' > "
        "/install/lib/python3.12/site-packages/hidden-pip.pth"
    )
    dockerfile.write_text(
        current.replace(builder_install, f"{builder_install}\n{hidden_pip}"), encoding="utf-8"
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: builder stage must match approved instruction contract" in issues


def test_runtime_container_contract_requires_isolated_builder_output_collision_guard(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        current.replace("find /install -mindepth 1", "find /tmp -mindepth 1"),
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert (
        f"{dockerfile}: builder-output validator must match approved instruction contract" in issues
    )


def test_runtime_container_contract_rejects_builder_pip_executable_collision_bypass(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    dockerfile.write_text(
        current.replace(
            "\\( -name 'python*' -o -name 'pip*' \\)",
            "-name 'python*'",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert (
        f"{dockerfile}: builder-output validator must match approved instruction contract" in issues
    )


def test_runtime_container_contract_rejects_builder_standard_library_collision(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    builder_install = (
        "RUN python -m pip install --upgrade pip && \\\n"
        "    python -m pip install --prefix=/install ."
    )
    collision = "RUN printf 'raise RuntimeError' > /install/lib/python3.12/sysconfig.py"
    dockerfile.write_text(
        current.replace(builder_install, f"{builder_install}\n{collision}"), encoding="utf-8"
    )

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: builder stage must match approved instruction contract" in issues


def test_runtime_container_contract_rejects_builder_controlled_collision_check(
    tmp_path: Path,
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    current = Path("Dockerfile").read_text(encoding="utf-8")
    validator_stage = f"\nFROM {APPROVED_RUNTIME_BASE} AS builder-output-validator\n\n"
    collision_guard = current.split(validator_stage, maxsplit=1)[1].split(
        f"\nFROM {APPROVED_RUNTIME_BASE} AS runtime", maxsplit=1
    )[0]
    mutated = current.replace(validator_stage + collision_guard, "\n" + collision_guard)
    mutated = mutated.replace(
        "COPY --from=builder-output-validator /install /usr/local",
        "COPY --from=builder /install /usr/local",
    )
    dockerfile.write_text(mutated, encoding="utf-8")

    issues = validate_runtime_container_contract(dockerfile, Path("Makefile"))

    assert f"{dockerfile}: builder-output validator must use approved base image directly" in issues
    assert f"{dockerfile}: runtime stage must match approved instruction contract" in issues
