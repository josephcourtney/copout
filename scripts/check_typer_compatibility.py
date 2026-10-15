#!/usr/bin/env python3
"""Smoke-test Copout's TyperGroup integration in temporary, isolated uv environments.

No dependency or lockfile changes are made to the working tree.
Run from the repository root with: uv run python scripts/check_typer_compatibility.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_VERSIONS = ("0.24.1", "0.26.0", "0.27.2", "0.27.3")
TESTS = (
    "tests/test_cli.py",
    "tests/test_cli_selection_ux.py",
    "tests/test_entrypoint.py",
    "tests/test_selection.py",
)


def run_command(arguments: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--versions", nargs="+", default=list(DEFAULT_VERSIONS),
        help="Exact Typer releases to compare, including pre/post vendored-Click",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if uv is None:
        parser.error("requires uv on PATH")

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="copout-typer-matrix-") as temp:
        for version in args.versions:
            venv = Path(temp) / ("typer-" + version)
            python = venv / "bin" / "python"
            operations = (
                [uv, "venv", "--python", sys.executable, str(venv)],
                [
                    uv, "pip", "install", "--python", str(python),
                    "-e", str(root), "pytest>=9.1", f"typer=={version}",
                ],
                [str(python), "-m", "pytest", "-q", *TESTS],
            )
            for step, command in zip(("venv", "install", "tests"), operations, strict=True):
                result = run_command(command, cwd=root)
                if result.returncode:
                    failures.append(version)
                    print(f"Typer {version}: FAIL ({step})")
                    print(result.stdout[-4000:])
                    print(result.stderr[-4000:], file=sys.stderr)
                    break
            else:
                print(f"Typer {version}: PASS")

    if failures:
        print("Incompatible or unverified Typer releases: " + ", ".join(failures))
        return 1
    print("All selected Typer releases passed CLI compatibility tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
