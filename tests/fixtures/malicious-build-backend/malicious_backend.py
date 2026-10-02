"""Test-only PEP 517 backend that tampers with builder output and inspection."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

DIST_INFO = "builder_mutation_proof-0.0.0.dist-info"


def build_wheel(
    wheel_directory: str,
    config_settings: object | None = None,
    metadata_directory: str | None = None,
) -> str:
    del config_settings, metadata_directory
    install_bin = Path("/install/bin")
    install_bin.mkdir(parents=True, exist_ok=True)
    (install_bin / "python3.12").write_text("untrusted replacement\n", encoding="utf-8")

    builder_find = Path("/usr/local/bin/find")
    builder_find.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    builder_find.chmod(0o755)

    wheel_name = "builder_mutation_proof-0.0.0-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    with ZipFile(wheel_path, "w", compression=ZIP_DEFLATED) as wheel:
        wheel.writestr(
            f"{DIST_INFO}/METADATA",
            "Metadata-Version: 2.1\nName: builder-mutation-proof\nVersion: 0.0.0\n",
        )
        wheel.writestr(
            f"{DIST_INFO}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: isolation-proof\n"
            "Root-Is-Purelib: true\nTag: py3-none-any\n",
        )
        wheel.writestr(f"{DIST_INFO}/RECORD", "")
    return wheel_name
