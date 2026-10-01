"""Checks against the user's real Atuin shell integration."""

import json
import os
import pty
import shutil
import signal
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pytest

_TIMEOUT = 20.0


def _require_live_shell() -> str:
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("requires zsh")
    if shutil.which("atuin") is None:
        pytest.skip("requires atuin")
    return zsh


def _send(fd: int, command: str) -> None:
    os.write(fd, command.encode() + b"\n")


def _wait_for_child(pid: int, *, timeout: float = _TIMEOUT) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        waited_pid, status = os.waitpid(pid, os.WNOHANG)
        if waited_pid == pid:
            return status
        time.sleep(0.05)

    os.kill(pid, signal.SIGTERM)
    os.waitpid(pid, 0)
    pytest.fail(f"interactive zsh did not exit within {timeout:g}s")


def _run_probe_in_atuin_shell(output_path: Path) -> None:
    zsh = _require_live_shell()
    launcher = Path(sysconfig.get_path("scripts")) / "copout"
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(zsh, [zsh, "-il"])

    quoted_launcher = str(launcher).replace("'", "'\\''")
    quoted_output = str(output_path).replace("'", "'\\''")

    try:
        # These are separate interactive input lines, not one compound shell command.
        # The PTY may queue them while zsh starts, but zsh still executes each line as
        # its own command lifecycle. Atuin therefore finalizes the probe before Copout
        # begins the following command.
        _send(fd, "printf 'copout-live-probe\\n'")
        _send(fd, f"'{quoted_launcher}' --print --json --last 10 > '{quoted_output}'")
        _send(fd, "exit")
        status = _wait_for_child(pid)
    finally:
        os.close(fd)

    if status != 0:
        pytest.fail(f"interactive zsh exited with wait status {status}")


def test_live_shell_capture(tmp_path: Path) -> None:
    output_path = tmp_path / "copout-live.json"
    _run_probe_in_atuin_shell(output_path)

    runs = json.loads(output_path.read_text())["runs"]
    probes = [run for run in runs if run["command"].strip() == "printf 'copout-live-probe\\n'"]
    assert probes, "the child Atuin-integrated shell did not record the standalone probe"
    output = probes[-1]["output"]
    assert output["state"] == "captured", (
        output.get("error") or "the real Atuin output cache did not capture the probe"
    )

    # Atuin may retain terminal-cell padding and final blank rows in its capture. Copout removes
    # whitespace only from the end of the complete captured output.
    assert output["text"] == "copout-live-probe"


def test_live_clipboard_delivery_does_not_fork_after_grpc(tmp_path: Path) -> None:
    _require_live_shell()
    launcher = Path(sysconfig.get_path("scripts")) / "copout"
    clipboard_helper = tmp_path / "pbcopy"
    clipboard_helper.write_text(f"#!{sys.executable}\nimport sys\nsys.stdin.read()\n")
    clipboard_helper.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join((str(tmp_path), env.get("PATH", "")))
    result = subprocess.run(
        [str(launcher)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
